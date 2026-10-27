# Reproducibility Doctor

An open-source developer-tool project for checking whether documented Python setup instructions can be reproduced, with evidence for each finding.

**Current status: milestone 5, execution-plan review and dry-run.** The CLI inspects committed source, produces static reports, and prepares digest-bound command plans for explicit review. It does not execute extracted commands, diagnose runtime failures, or run containers.

## Install locally

Requires Python 3.12+ and Git on Linux or macOS. Windows is not supported yet. No API key, Docker installation, or hosted service is needed for the implemented inspection, planning or dry-run workflow.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt -e .
reprodoctor --help
```

## Pin and inspect a repository

Choose a new output directory outside the input repository. Its parent must exist.

```sh
reprodoctor intake /path/to/project --output /path/to/snapshot
reprodoctor intake /path/to/project --ref FULL_COMMIT_ID --committed-only --output /path/to/pinned-snapshot
reprodoctor intake https://github.com/OWNER/REPOSITORY --ref main --output /path/to/github-snapshot
```

The first command requires working-tree files and index entries to match the selected commit. Untracked files, ignored files, and extra directories also require `--committed-only`; this deliberately avoids reading ignore rules or running Git filters. That flag explicitly selects committed contents and ignores local edits. It never changes the input repository.

GitHub intake requires a public HTTPS repository URL, disables authentication prompts and redirects, and does not inherit tokens, SSH agents, proxies, credential helpers, or the user's Git configuration. Private repositories are unsupported. GitHub intake downloads Git objects; it does not run setup commands. A missing repository, private repository, unavailable network, or invalid ref produces a generic infrastructure error rather than a setup verdict.

Output:

```text
snapshot/
  snapshot.json       # versioned manifest, full commit ID, digests and limits
  files/              # regular tracked files; no .git directory
```

`snapshot.json` records source, selected ref, resolved commit, every file's mode/size/Git object ID/SHA-256, total bytes, a deterministic inventory digest, Git/tool versions, omissions and limits. Files have read-only permissions to discourage accidental changes. This is a content-addressed snapshot, not tamper-proof storage: later execution must revalidate contents against the approved digest. Treat exported files as untrusted; do not import or run them.

Intake copies tracked contents, which may include committed secrets. It does not scan or guarantee redaction of those contents. Keep snapshots local and out of Git; public examples will use authored fixtures only.

## Extract README instruction candidates

```sh
reprodoctor extract /path/to/snapshot --output /path/to/instructions.json
```

Omit `--output` to print JSON. Output files must be new and outside the snapshot. Extraction first revalidates the complete inventory, file hashes and executable modes; changed or unexpected files stop extraction. This detects changes relative to the manifest, not a forged manifest's provenance.

The extractor reads root `README.md` as UTF-8 and selects fenced `sh`, `bash`, `shell`, and untagged blocks. It preserves document order, exact source text and one-based inclusive line ranges. Each candidate includes its proposed command text, installation/configuration/test/launch phase hint, heading context, and ambiguity reasons. Unknown commands remain review candidates. Other code blocks and recognizable prose instructions appear as review/coverage items rather than being silently interpreted as commands.

```json
{
  "order": 1,
  "path": "README.md",
  "start_line": 6,
  "end_line": 6,
  "raw_text": "python -m pip install -r requirements.txt\n",
  "candidate_text": "python -m pip install -r requirements.txt",
  "phase": "installation",
  "ambiguity_reasons": [],
  "requires_review": true
}
```

This example is an excerpt from the authored [extraction fixture](tests/fixtures/extraction/basic.md). An empty ambiguity list does **not** approve a command. Every candidate requires review and the document explicitly records `execution_permitted: false`. Prompts, alternatives, placeholders, nested Markdown, multiline constructs, shell expansion and unsupported syntax receive review flags. Complex shell blocks are kept together; the extractor does not resolve shell state or choose an installation branch.

Missing root README is reported as missing coverage, not a setup failure. Parsing is limited to 1 MiB, 2,000 candidates and 8 MiB of JSON evidence; exceeding a limit fails without producing a partial candidate document. Phase and ambiguity rules are deliberately conservative and can miss instructions or flag benign quoted text.

## Run static checks

```sh
reprodoctor check /path/to/snapshot --output /path/to/static-report.json
reprodoctor check /path/to/snapshot --python-version 3.12.0 --format markdown --output /path/to/static-report.md
```

`--python-version` is an exact **static target**, defaulting to 3.12.0. It is independent of the Python interpreter running Doctor and does not select or launch a container. Both formats come from the same findings, recording the commit/digest, checker versions, evidence locations and hashes, observed facts, suggested actions, and the limits of each check. Output must be a new file outside the snapshot; omit `--output` for stdout.

Supported checks:

- Dependency manifest inventory, root PEP 621 dependency string parsing and supported requirements-file syntax. Missing manifests prompt review; they do not prove missing dependencies. No package index or build backend is queried.
- `project.requires-python`, one numeric `.python-version`, and standalone README declarations such as `Python: 3.12`. Exact versions and minor-series ranges are compared. Disjoint declarations are inconsistencies; a target excluded by a declaration is unsupported, not proof of a broken project.
- Literal requirements/constraints include paths, direct Python script inputs, copy sources and relative directory changes. Paths are resolved inside the snapshot inventory. Shell expansion, uncertain command state and external paths remain unknown/review items. Generated targets receive only a documented-copy hint.
- Environment names in README `export NAME=...` / `${NAME}` and simple source patterns `os.environ["NAME"]`, `os.getenv("NAME")`, `os.environ.get("NAME")`, compared with root `.env.example`. Missing keys prompt review; requiredness is never inferred. Example/default values are omitted from findings.

Statuses are `pass` (the narrow static observation holds), `finding` (an observed absence, malformed declaration or direct inconsistency), `review`, `unknown`, and `unsupported`. Every report says execution was **not run**. CLI exit 0 means inspection completed, even with findings; exit 2 means input/inspection/output failed. A static pass does not establish a successful setup.

See the authored [Markdown sample](examples/static-report.md), [JSON sample](examples/static-report.json), and [regeneration instructions](examples/README.md). Static reports are bounded to 2,000 findings and 8 MiB. Source scanning for environment names has additional documented budgets and coverage limits. The report is not a secret scanner; review it before sharing.

## Review an execution plan without running it

Create a blocked draft and inspect the full plan in a dry-run:

```sh
reprodoctor plan /path/to/snapshot --output /path/to/draft-plan.json
reprodoctor run /path/to/draft-plan.json --snapshot /path/to/snapshot --dry-run
```

The draft has no default image. To make a plan eligible for approval, supply an explicitly selected image reference pinned to a SHA-256 digest with `--image`, and resolve every ambiguity. Image presence, Python version and runtime controls are **not verified** at this milestone; no image is pulled. The planned runtime is CPython 3.12 on Linux, with `--platform linux/amd64` or `linux/arm64`.

Every plan displays original instructions and locations, reviewed commands, exact proposed argv, transformations, command order, directory/environment state, offline artifact hashes, network assessments, container settings, limits and blockers. Supported steps are direct Python script/module launches, pytest, a restricted pip-install subset, simple relative `cd` and literal environment assignments. Unsupported shell commands stay blocked. Missing input files can still be tested later; the planner does not silently create or repair them.

For an ambiguous instruction, create a decisions JSON file outside the snapshot. Keys are extracted instruction IDs. These are examples of the three supported actions; choose decisions for your actual instructions:

```json
{
  "instruction-0001": {"action": "accept", "reason": "Reviewed the visible prompt removal."},
  "instruction-0002": {"action": "exclude", "reason": "This alternative is outside the selected workflow."},
  "instruction-0003": {"action": "replace", "command": "python app.py", "reason": "Use an explicitly reviewed finite launch."}
}
```

Rebuild into a new plan file using `--decisions /path/to/decisions.json`, your actual digest-pinned `--image`, and optionally `--wheelhouse /path/to/wheels`. Original text and order remain in the plan even for excluded/replaced instructions. An accept decision acknowledges ambiguity; it cannot enable unsupported pipelines, expansions or other commands outside the subset. Decisions are review inputs, not execution approval.

All pip-install steps require an explicitly selected nonempty offline wheelhouse in this MVP. It accepts only regular `.whl` files, hashes their names/bytes, downloads nothing, and does not claim the wheels are valid or sufficient. Pip argv transformations are visible: no index/cache/input, no automatic build isolation, find links only in `/wheels`, and install into `/workspace/.doctor-packages`. Build dependencies must already be in the selected image or earlier explicit steps. There is no automatic missing-dependency installation.

For an unblocked plan, review and approve in an interactive terminal:

```sh
reprodoctor approve /path/to/plan.json --snapshot /path/to/snapshot --output /path/to/approval.json
reprodoctor run /path/to/plan.json --snapshot /path/to/snapshot --approval /path/to/approval.json --dry-run
```

Supply the same `--wheelhouse` to both commands if the plan contains wheels. The approval command prints the entire escaped plan and requires typing its **full digest**; there is no `--yes` or piped approval. It revalidates source and artifacts after confirmation. A mismatch, interruption, blocker or changed input writes no approval record. Plan/approval output files must be new and outside snapshot/wheelhouse inputs; they are created with owner-only permissions.

Approval binds the commit, source digest, instructions, review decisions, argv/state, artifact hashes, image/platform, fixed settings and planner implementation. A changed input requires rebuilding and fresh review. Validation reconstructs the plan, so simply rehashing edited derived fields cannot weaken policy. Artifact paths are supplied explicitly again rather than followed from an untrusted plan file.

The fixed proposed policy denies networking and ports; permits no host mounts or inherited host environment; requires non-root, dropped capabilities, no-new-privileges, default seccomp, a read-only root, bounded tmpfs storage, CPU/memory/PID/time/log limits, and cleanup. These are **requirements for the future executor**, not controls exercised by dry-run. Dry-run performs no container/runtime call, image pull, installation, project execution or approval write. `run` without `--dry-run` currently refuses execution.

Keep plans local: they retain exact README commands and literal configuration values. Approval records are editable local audit data, not identity proof or protection against host compromise. Containers do not make arbitrary code completely safe. See [milestone 5 details](docs/05-execution-plan-review.md) for the complete contract and limits.

## Limits and exclusions

- Ordinary local SHA-1 Git repositories only; linked worktrees, bare repositories, shared/alternate object stores, and SHA-256 repositories are unsupported.
- Reject symlinks, submodules, special files, unsafe paths, and case/Unicode-normalization collisions. No hooks, checkout filters, submodule initialization, project imports or package installation occur during intake.
- Default snapshot limits: 50 MiB total, 1 MiB per file, 5,000 files. All tracked regular files count, not just Python and documentation files.
- Git operations have time and output budgets. Remote fetch has a 120-second deadline and a monitored 100 MiB Git-store budget. Monitoring can overshoot between checks; this is not a hard OS disk quota or a sandbox for Git. Network transfer and malicious pack decompression remain limitations.
- Git tree output is capped at 4 MiB. Local Git object-store traversal rejects more than 100,000 entries. The local object database is not copied.
- Git is trusted infrastructure and must be kept updated. No claim is made that processing arbitrary hostile Git data is completely safe. Concurrent malicious modification of local metadata is outside the current threat model.

## Development and milestone checks

```sh
python -m pytest -q
ruff check .
ruff format --check .
```

Tests generate authored Git repositories in temporary directories. They check intake isolation, extraction provenance, static evidence, plan/approval binding, policy tampering, command/state review, offline artifact changes, cancellation, and dry-run side effects. Dry-run tests prohibit subprocess and socket calls and compare file contents/permissions before and after. Normal tests do not access the network, create containers or execute fixture project code or README commands. Interactive approval tests simulate terminal input for authored fixtures; they do not approve real project execution.

See [scope and architecture](docs/01-scope-and-architecture.md), [milestone 2 evidence](docs/02-repository-intake.md), [milestone 3 evidence](docs/03-readme-extraction.md), [milestone 4 evidence](docs/04-static-checks.md), [milestone 5 evidence](docs/05-execution-plan-review.md), and the [reserved evaluation scenarios](evaluation/README.md). Next milestone: isolated execution, after runtime controls and cleanup are implemented and verified. No setup execution is implemented yet.
