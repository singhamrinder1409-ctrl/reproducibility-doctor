"""IN-CONTAINER reviewed whole-budget fixture only; never run on the host."""

import time

print("DOCTOR_PAUSE_STARTED", flush=True)
time.sleep(110)
print("DOCTOR_PAUSE_FINISHED", flush=True)
