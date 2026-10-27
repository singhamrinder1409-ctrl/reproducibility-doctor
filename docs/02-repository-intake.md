# Milestone 2: repository intake

Status: implemented and verified locally on macOS with Python 3.14.5 and Apple Git 2.50.1. Linux and Python 3.12 runtime verification remain for the CI/release milestone. The implementation uses Python 3.12-compatible syntax and APIs.

## Completed boundary

`reprodoctor intake` accepts an ordinary local SHA-1 Git repository or public HTTPS GitHub repository URL. It resolves a full commit ID, inventories the committed tree, validates modes/paths/limits, reads blobs, and atomically publishes `snapshot.json` plus `files/`. Input repositories are never modified. Output must be a new directory outside the local source.

All Git commands use argument arrays, a minimal environment and a fresh bare metadata directory with an empty template. Local objects are read through `GIT_OBJECT_DIRECTORY`; the source repository's config, hooks, refs replacement mechanisms, attributes and checkout filters are not loaded. Local refs are resolved from bounded metadata reads. The committed index is compared only for the default clean-input policy. No project imports, build backends, setup commands, hooks, submodule initialization or checkout occur.

For local input, the default policy rejects modified, staged, missing, untracked and ignored files, as well as extra directories. `--committed-only` explicitly selects the requested commit and ignores working-tree/index differences. It never silently includes uncommitted work. Refs with ambiguous local branch/tag matches require a full commit ID.

Public GitHub intake uses a fresh shallow fetch with no tags or recursive submodules. Only the HTTPS GitHub repository URL form is accepted; embedded credentials, query strings, non-HTTPS protocols and tree/file URLs are rejected. Authentication prompts, credential helpers, redirects, inherited tokens and SSH agents are disabled. Network failures produce infrastructure errors, not README defect findings.

## Acceptance evidence

- Development tests create authored temporary repositories; they never execute the contained Python program.
- Two exports of one commit have identical manifests and digests. A selected earlier commit retains the same digest after a later commit changes the source.
- Tests cover dirty input policies, staged-only differences, packed refs and annotated tags, malicious config/filter/hook declarations and inherited Git environment variables.
- Unsafe-path tests, committed symlinks, gitlinks/submodules, case collisions, shared objects, per-file/total/file-count budgets, output refusal and cleanup are exercised.
- Infrastructure subprocess tests exercise output truncation prevention and process-group timeout termination. Test transport stubs exercise the GitHub fetch contract and failure cleanup without a network dependency.
- A separate live public-GitHub smoke check fetched `pypa/sampleproject` at commit `621e4974ca25ce531773def586ba3ed8e736b3fc`: 12 files, 13,390 bytes. It ran no project code. The complete temporary snapshot was deleted; no third-party source is shipped.
- The package installs in a local virtual environment, and the installed CLI exposes help. Development versions are recorded in `requirements-dev.txt`.
- Eight development and four held-out setup scenario definitions are reserved in `evaluation/scenarios.json`, with a byte-level reservation hash. No README extraction or static-check rules have been tuned. These are reserved definitions, not completed evaluation results.

## Explicit limits

Snapshot contents are read-only by convention, not immutable against an owner who changes permissions. Later milestones must verify hashes before accepting an execution plan. There is no execution or setup verdict yet.

The Git download watchdog polls disk usage and output sizes, so it can overshoot between checks. It does not isolate Git itself or guarantee a hard disk/CPU/memory quota. Git pack parsing and local object reads rely on an up-to-date trusted Git installation. Concurrent hostile mutation of local metadata is outside the current threat model. Tracked secrets can be copied; host credential files and untracked files are not automatically added, and no secret scanner is claimed.

Linked worktrees, bare input, SHA-256 object stores, alternate/shared stores, sparse or split-index layouts, symlinks, submodules, special files and path collisions are unsupported. Large legitimate repositories may hit conservative limits. Local inspection assumes exact file bytes and executable bits; line-ending conversion can require `--committed-only`.

The reserved fixture definitions must be recorded in version control before tuning starts. Publication, CI, full fixture materialization, reports and a recorded demo remain later milestones. The next implementation milestone is Part 3, ordered README instruction extraction with source locations and explicit ambiguity.
