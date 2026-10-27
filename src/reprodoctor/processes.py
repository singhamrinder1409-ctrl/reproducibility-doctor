"""Bounded host infrastructure processes. No shell; never runs target Python here."""

from __future__ import annotations

import hashlib
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import BinaryIO


@dataclass
class Capture:
    limit: int
    prefix: bytearray = field(default_factory=bytearray)
    total: int = 0
    hasher: object = field(default_factory=hashlib.sha256)

    def feed(self, data: bytes) -> None:
        self.total += len(data)
        self.hasher.update(data)
        self.prefix.extend(data[: max(0, self.limit - len(self.prefix))])

    def record(self) -> dict:
        text = self.prefix.decode("utf-8", errors="replace")
        text = "".join(
            c if c in "\n\t" or (ord(c) >= 32 and not 127 <= ord(c) <= 159) else f"\\u{ord(c):04x}"
            for c in text
        )
        return {
            "text": text,
            "total_bytes": self.total,
            "captured_bytes": len(self.prefix),
            "truncated": self.total > len(self.prefix),
            "sha256_observed_stream": self.hasher.hexdigest(),
        }


def bounded_process(
    argv: list[str],
    *,
    environment: dict,
    cwd: str,
    seconds: float,
    cap: int,
    stdin: BinaryIO | None = None,
) -> dict:
    """Drain bounded prefixes, discard overflow and kill host process group on timeout.

    Killing a Docker CLI does NOT kill its container. The caller must remove it.
    No unbounded temporary log files or subprocess.communicate buffers are used.
    """
    started = time.monotonic()
    stdout, stderr = Capture(cap), Capture(cap)
    timed_out = False
    process = subprocess.Popen(
        argv,
        env=environment,
        cwd=cwd,
        start_new_session=True,
        stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        with selectors.DefaultSelector() as selector:
            for stream, capture in ((process.stdout, stdout), (process.stderr, stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, capture)
            if stdin:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, None)
            pending = b""
            while selector.get_map() or process.poll() is None:
                if time.monotonic() - started >= seconds:
                    timed_out = True
                    break
                for key, _ in selector.select(
                    timeout=min(0.05, max(0, seconds - (time.monotonic() - started)))
                ):
                    stream = key.fileobj
                    if key.data is None:
                        if not pending:
                            pending = stdin.read(65536)
                        if not pending:
                            selector.unregister(stream)
                            stream.close()
                            continue
                        try:
                            written = os.write(stream.fileno(), pending)
                            pending = pending[written:]
                        except BrokenPipeError:
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 65536)
                        if chunk:
                            key.data.feed(chunk)
                        else:
                            selector.unregister(stream)
                            stream.close()
            if timed_out and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        # Handles Ctrl-C and broken I/O. Container cleanup is the caller's finally block.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            timed_out = True
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
    return {
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "seconds": round(time.monotonic() - started, 6),
        "host_process_reaped": process.poll() is not None,
        "stdout": stdout.record(),
        "stderr": stderr.record(),
    }
