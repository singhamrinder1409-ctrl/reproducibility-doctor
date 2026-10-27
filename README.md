# Reproducibility Doctor

An open-source developer-tool project for checking whether documented Python setup instructions can be reproduced, with evidence for each finding.

**Current status: milestone 2, repository intake only.** The CLI pins a commit and exports a bounded snapshot without checking out files or executing project code. It does not yet extract README commands, diagnose setup problems, or run containers.

## Install locally

Requires Python 3.12+ and Git on Linux or macOS. Windows is not supported yet. No API key, Docker installation, or hosted service is needed for intake.

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

Tests generate authored Git repositories in temporary directories. They check commit pinning, deterministic export, dirty/index states, hooks/filters/config isolation, invalid paths, symlinks/submodules, bounds, errors, and the GitHub transport contract. Normal tests do not access the network or execute fixture project code.

See [scope and architecture](docs/01-scope-and-architecture.md), [milestone 2 evidence](docs/02-repository-intake.md), and the [reserved evaluation scenarios](evaluation/README.md). Next milestone: README instruction extraction. No setup execution is implemented.
