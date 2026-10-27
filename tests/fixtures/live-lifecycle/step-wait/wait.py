"""IN-CONTAINER reviewed wait fixture only; never run on the host."""

import time
from pathlib import Path

Path("wait-started").write_text("authored start marker\n")
print("DOCTOR_WAIT_STARTED", flush=True)
time.sleep(3600)
raise AssertionError("The step watchdog did not stop this fixture")
