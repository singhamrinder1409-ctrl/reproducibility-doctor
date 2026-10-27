"""IN-CONTAINER reviewed fixture only; never import or execute on the host."""

import errno
import json
import os
import socket
from pathlib import Path

config = json.loads(Path("sentinel.json").read_text())
assert not Path(config["host_only_path"]).exists(), "Host-only sentinel is visible"
assert "DOCTOR_HOST_SENTINEL" not in os.environ, "Host-only environment was inherited"
for path in ("/Users", "/var/run/docker.sock", "/run/host-services"):
    assert not Path(path).exists(), f"Unexpected host-access path: {path}"
mounts = Path("/proc/self/mountinfo").read_text().splitlines()
assert not any(line.split(" - ", 1)[1].split()[0] in {"virtiofs", "9p"} for line in mounts)
observations = []
for family, destination in (
    (socket.AF_INET, ("192.0.2.1", 9)),
    (socket.AF_INET6, ("2001:db8::1", 9, 0, 0)),
):
    with socket.socket(family, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        try:
            connection.connect(destination)
        except OSError as error:
            assert error.errno in {
                errno.ENETUNREACH,
                errno.EHOSTUNREACH,
                errno.ENETDOWN,
                errno.EACCES,
                errno.EPERM,
            }, f"Inconclusive network result: {error!r}"
            observations.append({"family": family, "errno": error.errno})
        else:
            raise AssertionError("Unexpected network connection succeeded")
print(
    json.dumps(
        {
            "marker": "DOCTOR_NETWORK_HOST_CHECKS",
            "attempts": observations,
            "host_sentinel_absent": True,
            "host_environment_absent": True,
        }
    ),
    flush=True,
)
