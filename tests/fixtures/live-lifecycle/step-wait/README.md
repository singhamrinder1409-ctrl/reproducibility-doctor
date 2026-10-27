# Run the wait fixture

The first command writes a start marker and sleeps for one hour. Doctor must stop it at the approved 120-second step limit. The same plan will be reused for explicit Ctrl-C, SIGTERM and host-process SIGKILL recovery tests. SIGKILL cannot run finally cleanup: the harness must use the exact owned journal to recover the container and verify a separately owned sentinel container remains untouched. The next source command must never start after timeout/cancellation. No host application processes will be signaled; the harness signals only its own Doctor child process. No network access, host mounts, paid service; automatic approval is not used is used.

```sh
python wait.py
python never.py
```
