"""IN-CONTAINER reviewed resource fixture only; never run on the host."""

import errno
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

CGROUP = Path("/sys/fs/cgroup")


def counters(name):
    return dict(
        (key, int(value))
        for key, value in (line.split() for line in (CGROUP / name).read_text().splitlines())
    )


observations = {}
# Four CPU workers run for four wall-clock seconds, within the one-CPU cgroup quota.
before = counters("cpu.stat")
started = time.monotonic()
workers = []
try:
    code = "import time\nend=time.monotonic()+4\nwhile time.monotonic()<end: pass\n"
    for _ in range(4):
        workers.append(subprocess.Popen([sys.executable, "-I", "-S", "-c", code]))
    for worker in workers:
        assert worker.wait(timeout=15) == 0
finally:
    for worker in workers:
        if worker.poll() is None:
            worker.kill()
        worker.wait(timeout=5)
elapsed = time.monotonic() - started
usage = (counters("cpu.stat")["usage_usec"] - before["usage_usec"]) / 1_000_000
assert 0 < usage <= elapsed * 1.5 + 0.1
observations["cpu"] = {
    "elapsed": elapsed,
    "cpu_seconds": usage,
    "quota": (CGROUP / "cpu.max").read_text().strip(),
}
# Trigger an OOM in a child, then require matching cgroup OOM-kill evidence.
before = counters("memory.events")
code = "blocks=[]\nfor _ in range(96): blocks.append(bytearray(16*1024*1024))\n"
child = subprocess.run([sys.executable, "-I", "-S", "-c", code], timeout=30)
after = counters("memory.events")
assert child.returncode < 0 and after["oom_kill"] > before["oom_kill"]
assert (CGROUP / "memory.swap.max").read_text().strip() == "0"
observations["memory"] = {
    "child_return_code": child.returncode,
    "oom_kill_delta": after["oom_kill"] - before["oom_kill"],
    "swap_max": "0",
}
# A finite upper bound avoids an unbounded fork loop even if enforcement fails.
before = counters("pids.events")
children = []
blocked = False
try:
    for _ in range(160):
        try:
            children.append(subprocess.Popen(["/bin/sleep", "15"]))
        except OSError as error:
            assert error.errno == errno.EAGAIN
            blocked = True
            break
    assert blocked and counters("pids.events")["max"] > before["max"]
    observations["pids"] = {"children_started": len(children), "creation_denied": True}
finally:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        child.wait(timeout=5)
# Exhaust only this process's file descriptors, then close all handles.
handles = []
blocked = False
try:
    for _ in range(400):
        try:
            handles.append(os.open("/dev/null", os.O_RDONLY))
        except OSError as error:
            assert error.errno == errno.EMFILE
            blocked = True
            break
    assert blocked and len(handles) < 256
    observations["nofile"] = {
        "opened": len(handles),
        "limit": resource.getrlimit(resource.RLIMIT_NOFILE),
    }
finally:
    for handle in handles:
        os.close(handle)
assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
child = subprocess.run(
    [sys.executable, "-I", "-S", "-c", "import os; os.abort()"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    timeout=10,
)
assert child.returncode < 0
assert not list(Path("/workspace").glob("core*")) and not list(Path("/tmp").glob("core*"))
observations["core"] = {"limit": [0, 0], "aborting_child_code": child.returncode}
# Fill each tmpfs separately with bounded writes, observing ENOSPC and removing its file.
storage = []
for directory, mib in (("/workspace", 256), ("/tmp", 64), ("/wheels", 128), ("/dev/shm", 16)):
    path = Path(directory) / "doctor-reviewed-storage-probe"
    written = 0
    blocked = False
    try:
        with path.open("xb", buffering=0) as stream:
            for _ in range(mib + 4):
                try:
                    written += stream.write(b"x" * (1024 * 1024))
                except OSError as error:
                    assert error.errno == errno.ENOSPC
                    blocked = True
                    break
        assert blocked and mib * 1024**2 * 0.8 <= written <= mib * 1024**2
        storage.append({"directory": directory, "bytes_written": written, "enospc": True})
    finally:
        path.unlink(missing_ok=True)
observations["storage"] = storage
print(json.dumps({"marker": "DOCTOR_RESOURCE_CHECKS", "observations": observations}), flush=True)
