"""IN-CONTAINER reviewed log fixture only; never run on the host."""

import os

chunk = b"\x1b[2J\xff" + b"x" * 65530 + b"\n"
assert len(chunk) == 65536
for _ in range(48):
    for stream in (1, 2):
        remaining = memoryview(chunk)
        while remaining:
            remaining = remaining[os.write(stream, remaining) :]
