# Reproducibility Doctor: scope and architecture

Status: Part 1 complete as a design baseline. See the project README for implementation progress; design decisions below describe the intended first release.

## Purpose and feasibility

Reproducibility Doctor checks the experience of a new contributor following a project's README. It records the instructions, checks what can be checked without running code, asks a person to review an execution plan, and records what happens when approved steps run in a disposable container. Its output answers: “What did we try, in which environment, what happened, and what evidence supports that conclusion?”

The primary user is a Python project maintainer or prospective contributor investigating setup problems. A secondary user is a student demonstrating practical work in parsing, developer experience, testing, and security boundaries.

This is realistic for a student portfolio as a deliberately limited CLI. Budget roughly 6–8 part-time weeks, with extra time for container and cross-platform issues; this is an estimate, not a deadline. General shell interpretation, universal Python packaging support, and safe execution of arbitrary hostile repositories would exceed this scope. The project makes no priority or “first of its kind” claim. Its value is a careful, demonstrable workflow with evidence and honest limits.

## Minimal first release

- Input: a local Git repository at a clean commit, or an HTTPS public github.com owner/repository URL with a selected ref resolved to a full commit ID.
- Projects: single-root, pure-Python libraries and command-line applications using pip with requirements.txt or a statically readable pyproject.toml. Other packaging styles may receive static findings but execution is unsupported.
- Documentation: root README.md; ordered fenced sh/bash/shell blocks and adjacent headings. Untagged blocks are candidates requiring review. Prose-only instructions, multiple alternative paths, placeholders, and ambiguous commands remain manual review items.
- Environment: one recorded CPython 3.12 Linux image pinned by digest. A project requiring a different Python version is reported as unsupported for execution, not broken. The tool itself uses Python 3.12+.
- Workflow: inspect → extract → static checks → reviewable plan → explicit approval → execution → JSON and Markdown reports.
- Execution: sequential reviewed pip installation, environment assignments, relative directory changes, tests, and finite launch commands. No interactive shells, sudo, Docker-in-Docker, OS package installation, services, notebooks, GPUs, or multi-repository setup.
- Network: execution is offline. Dependencies must be supplied as a reviewed wheelhouse, with artifact hashes recorded. A bundled minimal demo needs no external dependencies. Automated restricted dependency fetching is deferred until a real enforcement mechanism exists.
- Interface: CLI only. Local processing, no paid APIs, no hosted service, no telemetry.

Offline constraints mean some projects cannot be evaluated. Report “blocked: dependency artifacts unavailable” rather than treating this as a README defect. Installing the repository itself can execute build backend code and belongs inside the approved execution boundary.

## Threat model and controls

Treat repository names, Git metadata, README text, manifests, dependency artifacts, project code, and captured output as attacker-controlled. Protect host files, credentials, network services, machine resources, and the integrity of approval and reports. Trust the installed Doctor program, its dependencies, the container runtime, and the chosen base image within their documented limits.

| Risk | Required design control | Remaining limit |
| --- | --- | --- |
| Code execution during inspection | Parse text and TOML only; never import modules, run setup.py, invoke project scripts, or ask pip for metadata | Parsers and Git still have vulnerabilities; bound input sizes |
| Intake escape or unexpected fetching | Read Git objects into a fresh snapshot; do not initialize submodules, run hooks, use local filters, or copy .git; reject symlinks and special files in v0.1 | These restrictions exclude legitimate repositories |
| Changed source after review | Hash snapshot contents and canonical plan; bind approval to both and revalidate immediately before execution | Local host compromise is outside this model |
| Credential theft or filesystem damage | Copy only the sanitized tracked snapshot; never mount source, home, credentials, SSH agent, or Docker socket; start with an explicit minimal environment | A committed secret may still exist in source; scanning is imperfect |
| Network access and exfiltration | Use network=none, no ports, no host networking; reject overrides | Runtime or kernel compromise can bypass assumptions |
| Resource exhaustion | CPU, memory, PID, wall-clock, log, and disk budgets; fail closed when required controls cannot be enforced | Disk limits vary by runtime; tmpfs and explicit preflight checks are needed |
| Malicious logs or reports | Strip terminal controls, escape rendered content, cap output, avoid HTML rendering and raw CI command annotations | Automatic secret redaction cannot identify every secret |
| Container escape | Non-root UID, dropped capabilities, no-new-privileges, default seccomp, read-only root filesystem, bounded writable tmpfs | Containers share security boundaries with the runtime/kernel; arbitrary code is never completely safe |

The initial executor is for controlled fixtures and repositories the user has reviewed. Do not advertise it as a malware sandbox. Recommend a disposable VM for repositories of unknown provenance. Rootless Docker is preferred where supported; Linux is the reference execution platform. macOS may use a Linux VM runtime but must pass the same capability checks. Static inspection remains usable without Docker.

Proposed default limits: 1 CPU, 1 GiB memory with no extra swap, 128 PIDs, 120 seconds per step, 600 seconds per run, 1 MiB captured output per stream per step, a 256 MiB writable workspace and 64 MiB /tmp. Milestone 5 adds a separately bounded 128 MiB /wheels artifact tmpfs and 16 MiB shared memory. Bound snapshot size to 50 MiB and individual parsed files to 1 MiB. Store truncation markers and counts. Validate these defaults against fixtures before release; if a runtime cannot enforce the disk budget, execution is unavailable on that runtime.

## Architecture and invariants

Data flow:

    input → immutable snapshot → instructions + static findings → canonical plan
                                                              ↓ human review
    Markdown / JSON report ← diagnosis ← step results ← approved plan executor

Suggested modules: intake, extraction, checks, planning, approval, execution, diagnosis, reporting, and cli. Keep inspection modules independent of the executor. Invoke infrastructure tools with argument arrays and sanitized environments. Repository text never becomes a host shell command.

Core records:

- RepositorySnapshot: origin, full commit ID, content digest, file inventory, omissions, size limits.
- Instruction: ID, exact text, README path, start/end lines, order, phase, candidate classification, ambiguity reasons.
- Finding: stable rule ID, status, severity, evidence location, observed fact, interpretation, suggested action, check limitation.
- ExecutionPlan: schema/tool versions, snapshot digest, original and reviewed command text, any transformations, ordered steps, working directories, explicit environment names/values or placeholders, image digest, artifact hashes, network policy and budgets.
- Approval: exact plan digest and snapshot digest, explicit local confirmation, timestamp. An approval file is an audit record, not proof of human identity. Changed contents or settings require fresh review; unattended blanket approval is outside v0.1.
- StepResult: step ID, effective command, exit status or signal, elapsed time, bounded stdout/stderr, truncation, timeout/OOM/cancellation evidence, environment references.
- Report: schema version, context, findings, execution results, coverage and omissions, reproduction steps, suggested actions.

Plan states: draft → needs-review → approved → running → completed / failed / timed-out / cancelled / infrastructure-error. Static findings and execution outcomes are separate. Unsupported, skipped, and unknown never become passes. A zero exit code means only that the selected command exited successfully in the recorded environment. It does not establish application correctness or universal reproducibility.

Readme commands retain their order. Persistent shell effects require explicit modeling: reviewed environment assignments and relative directory changes update plan state. Unsupported pipelines, substitutions, background jobs, source/activation scripts, or multiline constructs block automatic plan completion. Never silently split compound commands or omit a command. A finite launch can succeed by exiting zero; a long-running server reaching a timeout is inconclusive unless a separately reviewed health check defines success.

Implemented CLI flow through milestone 5:

    reprodoctor intake INPUT --ref REF --output SNAPSHOT
    reprodoctor extract SNAPSHOT --output INSTRUCTIONS_JSON
    reprodoctor check SNAPSHOT --output STATIC_REPORT_JSON
    reprodoctor plan SNAPSHOT --output PLAN_JSON
    reprodoctor approve PLAN_JSON --snapshot SNAPSHOT --output APPROVAL_JSON
    reprodoctor run PLAN_JSON --snapshot SNAPSHOT --dry-run

The approve command displays the full effective plan and requires interactive confirmation of its digest. Experimental execution now requires matching approval, explicit opt-in and successful runtime preflight; live acceptance remains pending. Normal run without opt-in refuses. Dry-run performs no project execution, dependency installation, image pull, or container creation. Image preparation is an explicit prerequisite. A plan that requires edits returns to review. JSON is the canonical static report; Markdown is generated from that same record.

## Static checks and their limits

| Check | Evidence and possible finding | Limit |
| --- | --- | --- |
| Dependency manifests | Missing referenced requirements file; manifest presence and format | Presence does not establish completeness or installability |
| Python declarations | Compare requires-python, .python-version, and explicit README versions | Text extraction can miss declarations; do not guess compatibility |
| Referenced files | Resolve literal repository-relative paths inside the snapshot | Generated files, substitutions, and external files may be intentional |
| Configuration examples | Compare literal README variable names, .env.example keys, and recognizable source access patterns | Dynamic access and optional values prevent proving requiredness |
| Documentation/configuration agreement | Explicit conflicting versions or test command vs available configuration | Emit strong findings only for direct contradictions; otherwise mark review |

No static rule claims a dependency is unavailable on a remote index. No source inspection imports project modules. Unknown variables are review hints, not confirmed missing configuration.

## Stack decision

Use Python 3.12+, argparse for a small dependency-free CLI, dataclasses plus explicit schema validation for records, tomllib for TOML, markdown-it-py for Markdown structure/source maps, and packaging for Python version specifiers. Use pytest for tests and Ruff for linting. Use Git CLI with controlled configuration for intake and Docker CLI for runtime control, avoiding an additional Docker SDK dependency. Pin development dependencies and record actual tool versions.

Keep JSON and Markdown generation in Python; no database, web framework, LLM, agent framework, or queue is necessary. Markdown parsing provides structure, not semantic understanding of shell. Select a maintained permissive license before publication and check dependency licenses.

Docker requires explicit resource limits, and network=none supplies the intended offline network mode. Dependency installation is executable behavior: pip build backends can run project code. These facts motivate the execution boundary rather than treating pip install as a harmless inspection operation.

References: [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/), [Docker network drivers](https://docs.docker.com/engine/network/drivers/), [Docker security](https://docs.docker.com/engine/security/), [pip build-system interface](https://pip.pypa.io/en/stable/reference/build-system/).

## Ordered milestones and completion gates

Complete each gate before starting the next. The ten parts form one release; the first useful intermediate deliverable is a static-only report after milestone 4.

| Milestone | Deliverable | Concrete completion check |
| --- | --- | --- |
| 1. Scope and architecture | This design, threat model, boundaries, records and stack | User, supported inputs, unsupported states, approval boundary, network policy, risks and all release gates are explicit. Complete as a design; runtime controls remain unverified. |
| 2. Repository intake | Immutable local/GitHub snapshots | Same commit yields the same content digest; dirty local input requires an explicit committed snapshot; GitHub ref resolves to a full SHA; traversal, symlink, submodule, size and credential-handling cases tested; no project hooks or code run. Reserve held-out fixture scenarios here before tuning. |
| 3. Extraction | Ordered instruction candidates with provenance | Golden fixtures verify exact text, line ranges, order, phases, prompts and ambiguity; unsupported shell is retained for review; no command runs. |
| 4. Static checks | Evidence-backed findings and static-only report | Each rule has a positive, negative and unknown case; relative paths cannot escape snapshot; no “missing dependency” claim from manifest absence alone; repeated inspection produces equivalent findings. |
| 5. Execution-plan review | Plan schema, dry-run and digest-bound confirmation | All commands, edits, artifacts, environment and limits visible; source/command/settings tampering invalidates approval; dry-run has no execution side effects; unresolved ambiguity blocks run. |
| 6. Isolated execution | Offline disposable runner | Controlled tests prove enforced resource/network/filesystem settings, sequential state, exit capture, truncation, timeout, interrupt cleanup and startup recovery; no sensitive mounts; cleanup failure is visible; missing controls fail closed. |
| 7. Diagnosis | Conservative failure categories | Labeled cases cover missing files, unavailable offline artifacts, version conflict, missing config, test failure and unknown; facts cite step/log evidence; suggested fixes are separate and never applied automatically. |
| 8. Reports and CLI | Versioned JSON and readable Markdown | Schema validation, equivalent report content, escaped hostile output, coverage/omissions, exact environment and reproduction prerequisites verified; redacted reports never embed approval secrets. |
| 9. Evaluation | Reproducible evaluation script and results | Freeze rules before opening held-out labels; report per-rule precision/recall, false positives, abstentions, sample counts, reliable completed runs and p50/p95 duration; no aggregate accuracy without denominator. |
| 10. GitHub release | Standalone public source, CI, docs and demo | Clean-clone install and demo succeed; tests and lint pass; architecture, limitations, generated sample reports and short recording/screenshots included; license chosen; secrets and vendored third-party repos absent; GitHub URL and checks verified after publication. |

Release acceptance: at least 12 authored scenarios (8 development, 4 held out) with documented expected evidence, including successful setup, missing files, configuration hints, incompatible declared Python versions, failed tests, ambiguous commands and hostile/resource cases. Categories may overlap. Commit held-out scenario definitions before tuning and do not use their labels to tune. Require every held-out scenario to produce its expected outcome or an explicit justified abstention, no incorrect definitive defect claims on clean success fixtures, and 10/10 repeated supported offline fixture runs to terminate and clean up within budget. Report small sample limitations; these are engineering gates, not evidence of broad real-world accuracy.

## Hardest risks and future extensions

1. README semantics and shell state: the narrow subset and explicit abstention prevent false confidence. Measure extraction omissions separately from check accuracy.
2. Runtime containment and cleanup: enforce controls on the actual runtime, stream logs rather than buffering unlimited output, kill the whole container, and reconcile leftover containers by run label after interruptions. Never infer safety from a container starting successfully.
3. Dependencies versus restricted networking: offline artifacts are a real usability limit. Future fetching needs a separate restricted downloader, explicit destinations and redirects policy, artifact hashes and no project build execution on the host. Bridge networking or a claimed hostname allowlist alone is insufficient.
4. Causal diagnosis: a failure signature may have several causes. Preserve raw bounded evidence, label hypotheses, and allow unknown.
5. Reproducibility versus mutable inputs: record image digest, wheel hashes, runtime versions and platform. A commit hash alone does not freeze dependency indexes or hardware.

Needed now: narrow deterministic parsing, immutable evidence, manual review, offline execution, controlled fixtures, honest reports and a clean release.

Future: Poetry/uv/Conda, more Python versions and OSes, online dependency broker, lockfile interpretation, services and health probes, broader shell support, CI integrations, GUI, other languages, optional local AI explanations. AI must never bypass approval or turn repository text into trusted instructions.

## Part 1 completion record

At Part 1 completion, the requested scope, architecture, threat model, first-release boundary, justified stack, risks, and milestone gates were documented. No GitHub repository was created or project code executed. Repository intake and fixture reservation are now tracked in [milestone 2](02-repository-intake.md).
