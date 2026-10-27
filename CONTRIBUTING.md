# Contributing

Use Python 3.12+ and Git on Linux or macOS. From a clean checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt -e .
ruff check .
ruff format --check .
python -m pytest -q
python scripts/demo.py --output /new/path/doctor-demo
```

Default tests never run target fixture commands; simulated Docker tests are not containment evidence. Never introduce auto-approval, host execution fallback, automatic image pulls, bridge networking or sensitive mounts. Actual live testing requires manually reviewed plans and explicit interactive approvals. Keep live validation visibly pending until its checklist is complete.

Add focused development regressions for meaningful changes. Do not tune on the published held-out scenarios: the first evaluation is frozen with a documented label mapping error. Changing rules invalidates its freeze; record a new evaluation version and fresh held-out scenarios rather than overwriting the first result. Execution/planner code changes also invalidate existing plans and approvals.

Keep records bounded and escape untrusted output. Include evidence locations, observed facts, limitations and separate suggested fixes. Do not paste credentials, private repository contents or actual approval receipts into issues or sample reports. Only authored fixtures belong in this repository.
