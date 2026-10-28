# Part 10 — experimental preview release

Release version: **0.1.0.dev0**, offered as a development pre-release rather than a stable or hardened execution service. [Source](https://github.com/singhamrinder1409-ctrl/reproducibility-doctor), [CI](https://github.com/singhamrinder1409-ctrl/reproducibility-doctor/actions), [downloads](https://github.com/singhamrinder1409-ctrl/reproducibility-doctor/releases).

## Completed project deliverables

- Scope, supported Python subset, threat model, ordered milestone records and honest exclusions.
- Commit-pinned intake, provenance-preserving extraction, deterministic static checks and limits.
- Explicit plan review, exact-digest interactive approval, dry-run and resumable fixture approval UX.
- Disposable offline Docker runner, bounded logs, environment evidence, deadlines and targeted recovery.
- Conservative diagnosis and escaped Markdown/structured JSON reports, with facts separate from suggestions.
- Reference acceptance on Docker Desktop 4.97.0 / Engine 29.9.2 / Linux ARM64 / CPython 3.12.16, including controlled resource/network/log/interruption/path/artifact cases. Containers do not make arbitrary code completely safe.
- Frozen 12-case authored corpus: seven executions, five explicit abstentions, seven confirmed removals. Prior static label error and undefined held-out metrics remain disclosed. Separate ten-run development repetition succeeded.
- Genuine sample reports, static CLI walkthrough and read-only replay of actual diagnosis output. Replays are paced captured output, not fabricated target execution or a new screen recording.
- MIT license, installation/contributor/security/dependency docs and a public standalone GitHub repository.
- Linux/macOS CI matrix for Python 3.12–3.14: lint, format, default tests, read-only demos, wheel build and fresh installed-wheel smoke. CI has read-only permissions, no checkout credentials, no target execution or publishing secrets.

## Release verification

Before publishing the pre-release, run local lint/format/tests, verify the frozen runtime protocol still matches, build a fresh wheel, check a clean source clone and isolated wheel installation, regenerate/read the demos, and scan the exact tracked archive for private paths, credentials, approval receipts and vendored third-party content. Source archives exclude `.git`, virtual environments, snapshots and private review artifacts. SHA-256 checksums provide artifact integrity comparison, not authenticated identity.

Publish only after the final commit's six CI jobs pass. The GitHub release body records its exact commit/check link and provides the source archive, wheel and checksums. Do not claim PyPI publication, stable execution support or a verified private vulnerability-reporting channel. There are no paid APIs or hosted backend requirements; initial dependency/image provisioning still needs downloads.

## Boundaries retained

Only the recorded Docker Desktop ARM64 reference execution configuration was tested. Linux/macOS inspection is exercised in CI; other Docker hosts/images and Windows execution are unverified. Arbitrary shell workflows, online dependency fetching, Poetry/uv/Conda, native builds, long-running services and AI explanations remain future work. A local GUI is unnecessary for this release.

Reports/plans/logs are not automatically redacted. Published examples contain only authored harmless values; actual private source, host credentials and approval receipts remain excluded. SIGKILL/host loss or daemon failure can prevent automatic cleanup; exact-journal recovery was observed with the daemon available, not guaranteed universally.

The raw runner's conservative `live_validation: pending`/experimental markers are preserved rather than treated as automated platform certification. Current reference evidence and reserved-corpus outcomes are the explicit auditable records in Parts 6 and 9.
