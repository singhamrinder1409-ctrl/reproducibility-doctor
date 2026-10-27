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
