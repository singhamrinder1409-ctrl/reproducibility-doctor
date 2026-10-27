# Run the resource-control probe

Review probe.py before approval. It deliberately exercises limits inside the disposable container: four short CPU workers; a child that tries to allocate up to 1.5 GiB to trigger the container's 1 GiB memory limit; up to 160 lightweight sleep children to reach the 128 PID limit; file descriptor exhaustion; a core-disabled aborting child; and bounded temporary filler files in each writable tmpfs. Children and filler files are cleaned up by the probe, and Doctor must remove the entire container afterward. No host folders are mounted. These are stress tests with residual shared-kernel risk; a container does not make arbitrary code completely safe.

```sh
python probe.py
```
