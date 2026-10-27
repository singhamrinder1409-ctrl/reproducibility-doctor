# Milestone 5: execution-plan review and dry-run

Status: implemented on the current local macOS / Python 3.14.5 development environment. The preceding static milestone was saved as local commit `60c3037`. No executor, container creation, runtime preflight or image fetching is implemented here.

## Contract

1. `plan SNAPSHOT --output NEW_PLAN` verifies the snapshot, re-extracts instructions, inventories explicitly selected wheel artifacts, compiles supported literal steps and produces a canonical plan. Omitted image or unresolved instructions produce a blocked draft, not a silent default.
2. `--decisions FILE` supplies per-instruction accept/exclude/replace inputs with mandatory reasons. Every original instruction remains visible, including excluded/replaced ones. Rebuild a new plan after edits; do not hand-edit derived fields.
3. `approve PLAN --snapshot SNAPSHOT --output NEW_APPROVAL` reconstructs and validates the plan, displays it fully with terminal-control escaping, refuses blockers, requires an interactive stdin/stdout terminal and the entire plan digest, then revalidates source/artifacts and creates the approval record. EOF, Ctrl-C and digest mismatches create no approval.
4. `run PLAN --snapshot SNAPSHOT --dry-run [--approval FILE]` verifies the plan and optional matching approval without invoking subprocesses, sockets, Docker, installers or project commands. It writes no files or approval record. The result includes the entire validated plan, logical plan state, approval match and explicit `execution_status: not_run` / `runtime_preflight: not_performed` / `executor_available: false`.
5. `run` without `--dry-run` refuses, even with a valid approval. Actual execution belongs to milestone 6.

If wheel artifacts are included, supply `--wheelhouse DIR` again on approval/dry-run. The plan stores file names, sizes and SHA-256 hashes rather than embedded host source paths. The tool never follows a host artifact path supplied by untrusted plan JSON. New output files must be outside snapshot/wheelhouse inputs and have owner-only permissions.

## Canonical plan and approval binding

The plan has a versioned envelope and `plan_digest = SHA256(canonical(payload))`. The payload records:

- Commit and complete source inventory digest; extraction digest; tool, parser and planner-code fingerprint.
- Every ordered instruction with exact README text, source line range, phase and ambiguity flags.
- Review decisions/reasons; reviewed command; exact effective argv, state before/after, transformations and network assessment, or an explicit blocker/exclusion.
- Digest-pinned image reference, Linux platform, expected CPython 3.12 series, complete fixed policy, artifact inventory/digest and logical state.

Validation checks the digest, rebuilds the entire payload from the current snapshot, selected wheelhouse and decision inputs, and compares canonical documents. Extra fields and altered derived argv/settings fail validation even when a caller recomputes the outer digest. A valid change of image/platform or review decision yields a different plan digest and invalidates an older approval. Changed source, artifacts, parser versions or planner code also require rebuilding/review.

The approval record binds that plan digest and the repository commit/content digest, tool version, method and timezone-aware UTC timestamp. It is an editable local audit record, not cryptographic authentication, identity verification, a signed attestation or a defense against a compromised host. Whitespace/key-order changes to JSON do not change canonical meaning. Duplicate keys, nonfinite numbers, wrong envelope types and excessive JSON size/nesting are rejected rather than interpreted ambiguously.

Approval does not change the immutable plan's `needs_approval` state: the separate matching record is the evidence of approval. No approval is inferred from a decisions file or a dry-run. The future executor must revalidate the exact record, source, artifact bytes actually copied and all runtime controls before any project step.

## Supported command/state subset

- Direct `python` / `python3` / `python3.12` script paths or module launches, and pytest through the container Python. Original executable normalization is visible.
- Restricted pip install targets and separate `-r`/`--requirement`, `-c`/`--constraint`, `-e`/`--editable` operands. Direct URLs and other installer flags remain blocked. A reviewed nonempty wheelhouse is required even when an install might otherwise use only local source; this is a conservative MVP restriction, not evidence the project needs network.
- One literal environment assignment and simple repository-relative `cd`, recorded as state changes rather than host shell commands. Runtime environment names and loader/Python/pip overrides are reserved. No host environment value is implicitly copied.
- Shell quotes are parsed into literal argv and unquoted comments are removed with an explicit transformation note. Pipelines, redirects, substitutions, control characters, multiline shell, activation scripts, sudo, venv creation, OS installers, background jobs and arbitrary executables remain blocked.

Acknowledging an extraction ambiguity cannot bypass the command subset. An unresolved step invalidates subsequent state assumptions; approval waits until the reviewer accepts a supported interpretation, replaces it or explicitly excludes it. A plan with no executable process cannot be approved. File absence is not silently repaired: documented missing inputs may still be tested as failures later.

Pip transforms are explicit in the reviewed argv: use the container Python, isolated pip mode, no index, no cache, no input, `/wheels` find-links, no build isolation and a writable `/workspace/.doctor-packages` target on the approved PYTHONPATH. This changes the documented environment and must be visible in later execution reports. Disabling build isolation means build prerequisites must already be present through the image or earlier explicit steps. No hidden bootstrap installation is inserted.

Network requirements of arbitrary code cannot be proven statically. Install steps explicitly note possible dependency/build downloads, but the only approved policy is offline. Other programs have unknown network needs and still receive no network access. URLs buried in requirements or code do not grant access. Wheel hashes identify selected bytes; files are not unpacked or claimed valid, compatible or sufficient.

## Required future runtime settings

| Setting | Fixed plan requirement |
| --- | --- |
| Image/platform | Explicit digest pin; linux/amd64 or linux/arm64; CPython 3.12 series |
| Network | none; no published ports |
| Host access | No host mounts, Docker socket, credential mounts or inherited host environment; verified source/wheels copied only |
| Privileges | UID/GID 65532, no privileged mode, all capabilities dropped, no-new-privileges, default seccomp required |
| Filesystem | Read-only image root; tmpfs /workspace 256 MiB, /tmp 64 MiB, /wheels 128 MiB; shared memory 16 MiB |
| Resources | 1 CPU, 1 GiB RAM, zero extra swap, 128 PIDs |
| Time/logs | 120 seconds per step, 600 seconds per run, 1 MiB per stream per step |
| Startup | Override image entrypoint, clear image environment, verify interpreter/platform and reject images declaring volumes |
| Cleanup | Remove disposable container/data on normal/error exits and reconcile interrupted runs |

These are declarative requirements, not demonstrated containment. Image strings are checked for digest-pin syntax only; a correctly formatted placeholder/nonexistent image can produce an approvable plan but must fail actual runtime preflight. This milestone does not inspect, pull or run the image. A selected image is a trusted input requiring review. Containers share runtime/kernel security boundaries and never make arbitrary code completely safe.

## Bounds and acceptance evidence

- Maximum 200 instruction records and 8 MiB JSON documents; reviewed command 16 KiB and decision reason 1,024 characters. Unsupported/oversized inputs fail without execution.
- Wheelhouse inventory stops at 100 entries, accepts regular `.whl` files only, rejects symlinks/directories/other files, and limits files to 32 MiB each / 128 MiB total. Hashing is bounded and detects changes during reads.
- Tests cover deterministic plans, exact provenance/order, explicit exclusions/replacements, state propagation, invalid image refs, missing artifacts, changed artifact bytes and source data, changed planner identity, approval mismatch, policy/argv tampering with and without rehashing, malformed review JSON and unsupported commands.
- Approval tests simulate terminals for authored fixtures and verify full-digest confirmation, noninteractive refusal, cancellation, new-file-only writes, private permissions, and source revalidation after review. They create no authorization for real repositories and execute no fixture command.
- Dry-run tests prohibit subprocess and socket calls and compare input file bytes/modes and directory inventory before/after. Valid/blocked plans and optional approval checks retain `not_run` status.
- The installed CLI is exercised separately with a temporary authored fixture and an intentionally missing image. No image pull, Docker command or real approval is performed.
- Reserved held-out setup scenarios remain unchanged; these are development/security regressions rather than held-out evaluation results.

Implementation references: [Docker run controls](https://docs.docker.com/reference/cli/docker/container/run/), [pip install options](https://pip.pypa.io/en/stable/cli/pip_install/), [pip build isolation responsibility](https://pip.pypa.io/en/stable/reference/build-system/).

## Next boundary

Milestone 6 must implement and verify runtime preflight, copied-byte integrity, resource/network/filesystem enforcement, process/log/time handling, actual environment capture and cleanup before offering execution. A runtime that cannot enforce a required control must fail closed. Runtime checks, container security tests and failure diagnosis have not been performed by this milestone.
