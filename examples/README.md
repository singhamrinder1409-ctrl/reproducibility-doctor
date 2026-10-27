# Static-only sample reports

`static-fixture/` is authored for this project and intentionally contains mismatches. The Markdown and JSON reports are generated from the same validated snapshot; they do not claim a setup run occurred.

Regenerate from the project root after installing the development dependencies:

```sh
python scripts/generate_static_sample.py
```

This script creates a temporary Git repository using a fixed fixture identity, date and commit message. It copies the authored fixture, pins the commit, runs static inspection, writes the two sample reports and deletes the temporary repository/snapshot. It never runs fixture commands, installs fixture dependencies or imports fixture modules. Git and Doctor's own trusted implementation run locally. No third-party repository contents or host environment variables are used as fixture inputs.

Expected observations: requirements.txt is absent; the explicit README Python declaration conflicts with pyproject.toml; app.py exists; SERVICE_TOKEN has no matching example key, which is only a review hint because source defaults and requiredness are not diagnosed. The static target 3.12.0 satisfies the project constraint but is excluded by the README declaration.

The fixture is a development demonstration, separate from reserved held-out scenarios. It is not a complete installable application or an executed failure diagnosis. Reports record the local checker runtime/dependency versions, so those metadata values can differ when regenerated elsewhere.

## Captured CLI walkthrough

Open `demo/index.html` locally for a readable walkthrough, `demo/transcript.txt` for captured output, or replay `demo/demo.cast` with an asciinema-compatible player. The recording is generated from real Doctor CLI output, paced for presentation, with temporary paths normalized to `$DEMO`. It is static-only: the missing-file fixture's README commands never run. No execution sample is fabricated while Docker validation remains pending.

Regenerate into a new directory:

```sh
python scripts/demo.py --output /new/path/doctor-demo
```

The script uses only the authored development fixture, creates temporary Git metadata, runs intake/extract/check/blocked-plan/dry-run, checks each CLI status, records output and removes temporary files. It never approves a plan, starts Docker or executes fixture code. The generated plan is a blocked draft with no selected image; it is not an executable plan or approval receipt.

## Genuine live preflight failure

`live-preflight-failed.json` and `.md` record the first approved live attempt. Docker/kernel settings were observed, but the original strict network enumeration stopped the runner before source transfer or target code execution. Cleanup succeeded. The original evidence is retained after fixing the network probe; it does not demonstrate successful setup or complete containment acceptance. No approval receipt or private source is published.

## Genuine approved target runs

- `live-success.json` / `.md`: environment and directory state succeeded; expected marker observed; container removed.
- `live-failure-stops.json` / `.md`: deliberate exit 7 recorded; the later command remained not reached; container removed.
- `live-success-fixture/` and `live-failure-stops-fixture/`: exact authored snapshot source used for these records. These source copies are excluded from Ruff reformatting to preserve their recorded bytes. They are never imported/run by default tests.

The reports are genuine, retain their original `experimental` and `live_validation: pending` fields, and contain only the authored fixture's harmless literals and logs. Approval receipts and private host paths are excluded. They demonstrate those narrow outcomes on one runtime, not universal reproducibility or complete containment.

## Approved network and resource probes

`live-network.json` / `.md` and `live-resources.json` / `.md` are genuine approved development runs with successful cleanup. Their source is in `tests/fixtures/live-controls`; the network sentinel configuration is generated explicitly by the preparation helper and contains only an authored temporary path. No host credentials or approval receipts are included. The [control evaluation](../evaluation/results-live-controls.json) preserves flood-stream metadata and hashes without publishing multi-MiB log prefixes; complete original logs remain private local artifacts.
