# Begin live validation

Docker was still absent when checked on 2026-10-27. The development Mac reports arm64; use the official [Docker Desktop download page](https://www.docker.com/products/docker-desktop/) and select Mac / Apple Silicon. Install and start the application yourself, then confirm that `docker version` shows both Client and Server. Doctor never installs or starts a runtime automatically.

Two additional development fixtures are prepared by:

```sh
python scripts/prepare_live_validation.py --output /new/path/live-review
```

This creates ordinary authored Git repositories, verified snapshots and **blocked draft plans**. It does not run fixture code, access Docker, fetch images or create approvals. The fixtures are separate from the frozen held-out evaluation:

- `state-success`: a literal environment assignment and directory change must apply to a finite Python launch. Expected final marker: `DOCTOR_STATE_SUCCESS`.
- `failure-stops`: the first Python command deliberately exits 7. The later command must remain not reached; expected overall failure is not a harness defect.

After the runtime is available, select and prepare a trusted CPython 3.12 Linux image separately. Record its actual digest and architecture; no invented digest or mutable tag will be accepted for execution. Rebuild each plan with that digest using `reprodoctor plan SNAPSHOT --image DIGEST_REFERENCE --platform linux/arm64 --output NEW_PLAN.json`. Image selection does not verify its presence or controls.

Read each fixture source, every command and the full plan/settings, then use the existing interactive `reprodoctor approve` command to approve its exact digest. Supply the actual local Unix socket for Docker Desktop if it differs from `/var/run/docker.sock`. Neither the preparation script nor tests manufacture a real execution approval.

First live acceptance will compare genuine preflight observations, directory/environment state, recorded exit code, not-reached steps and confirmed cleanup. Both reports must retain `live_validation: pending` until the broader Part 6 checklist is complete. These two basic checks alone do not prove resource enforcement, network isolation, interrupt cleanup, recovery or arbitrary-code safety.
