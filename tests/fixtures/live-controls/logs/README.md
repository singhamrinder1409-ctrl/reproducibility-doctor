# Run the bounded-log probe

Each invocation emits three MiB to stdout and three MiB to stderr, including terminal controls and invalid UTF-8. Three explicit sequential invocations exercise the per-stream and whole-run retained-byte budgets. No files are written by this fixture. Doctor must drain/discard overflow, escape controls, report truncation, preserve timings and remove the container. Its runtime log driver must remain disabled.

```sh
python flood.py
python flood.py
python flood.py
```
