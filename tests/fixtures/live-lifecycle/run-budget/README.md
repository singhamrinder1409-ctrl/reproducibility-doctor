# Run the whole-run budget fixture

Six explicit sequential commands each sleep for 110 seconds. Every individual sleep is below the 120-second step limit. Together they exceed the 600-second run budget, so the last command must time out and cleanup must succeed. This test intentionally takes about ten minutes while mostly idle. No networking is needed; no host access is needed.

```sh
python pause.py
python pause.py
python pause.py
python pause.py
python pause.py
python pause.py
```
