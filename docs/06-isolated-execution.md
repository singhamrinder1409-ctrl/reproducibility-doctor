# Part 6: isolated execution prototype

Status: **implemented as an experimental prototype; acceptance incomplete**. At initial implementation Docker, Podman and Colima were absent. Docker Desktop is now installed; the first live attempt and corrective preflight inspection are recorded below. The user explicitly chose to leave live validation pending. No runtime was installed, no image pulled and no target repository code executed. The user subsequently authorized offline Parts 7–10 before returning to live validation; diagnosis, reports and public preview publication are now implemented. See [live validation preparation](11-live-validation-start.md).

Initial prototype verification: 198 tests passed and the live smoke test was skipped by default. Lint/format checks pass. Simulated daemon tests validate control flow and rejection logic; they do **not** demonstrate kernel/container containment. Host process tests execute only fixed Doctor infrastructure test code to exercise pipe draining and timers, never extracted target instructions.

## Entry and approval gates

`run` requires `--experimental-execution`, a matching `--approval`, an explicit `--snapshot` and a new `--output`. Dry-run is a mutually exclusive mode, performs no runtime call and accepts no output file. There is no `--yes`, implicit approval, image download, runtime installation, Docker build, remote daemon or fallback to running target code on the host.

The runner reconstructs the complete plan and verifies approval before touching the runtime. Its code is now part of the planner fingerprint: old Part 5 plans/approvals must be rebuilt and reviewed. Selecting experimental mode is an acknowledgment of incomplete live testing, not a substitute for approving commands.

Only local Unix Docker sockets are supported. The CLI runs with an empty private configuration/home and a minimal host environment, using explicit infrastructure argument arrays. No inherited Docker context, registry credentials, SSH agent, proxy or Docker environment variable is used. Docker's local API socket stays on the host and is never exposed to target code.

## Execution sequence

1. Verify plan, source, approval and wheel bindings. Create an owner-only journal before a container operation can begin.
2. Check the existing Docker server is Linux/cgroup v2 with builtin seccomp. Inspect the local image; match its repository digest, immutable image ID and platform. Reject declared volumes and malformed environment keys. No pull occurs.
3. Stage a host-created tar containing only verified regular source/wheel bytes. Recheck the bytes actually staged, not just earlier filesystem metadata. No project archive is extracted on the host.
4. Create a uniquely named/labeled disposable container using immutable image ID, no pull, overridden entrypoint, disabled healthchecks/restarts, no persistent runtime log driver and the fixed approved policy. Clear image environment values; project steps receive only their explicit reviewed environment.
5. Inspect the resulting container configuration. Reject unexpected binds, mounts, devices, extra capabilities, ports, namespace modes, environment values, restart/logging policies or weakened limits.
6. Before target files are transferred, run only Doctor's trusted bootstrap with Python `-I -S`. Observe exact CPython version/implementation, IDs, capabilities, no-new-privileges, seccomp, cgroup values, read-only mounts, tmpfs sizes/types and network interface flags, addresses and routes. Non-loopback devices must be down/not running and unaddressed, IPv4 routes are refused, and IPv6 routes/addresses must belong to loopback. Unknown/missing controls fail closed. These checks use normal conditionals and remain active under Python optimization.
7. Transfer data into bounded container tmpfs with a fixed bootstrap that accepts only regular files rooted under /workspace or /wheels. Re-read copied files and compare the aggregate path/size/mode/hash record with the host-staged record before any project step. Disposable source uses user-writable 0644/0755 modes matching Git's executable bit; host snapshots remain read-only. Umask is explicitly 0022.
8. Run reviewed process argv using a fixed in-container bootstrap, JSON stdin and execve-style environment passing; no host or target shell is used. Directory state is checked inside the container and rejects resolution outside /workspace. Literal environment state changes are recorded and applied to subsequent jobs. Stop after the first failed/timed-out step and list steps not reached. Explicit exclusions stay excluded.
9. Capture observations, inspect final container state, force-remove only the owned container and confirm absence. Write the report and journal atomically as private host artifacts. Temporary staging/config files are removed.

The trusted base image and Docker/kernel remain security dependencies. This is not a malware sandbox. A container never makes arbitrary code completely safe, even when checks pass.

## Resource and log handling

The approved profile retains 1 CPU, 1 GiB RAM with zero extra swap, 128 PIDs, 120 seconds per step, a 600-second run budget, read-only image root, 256 MiB /workspace, 64 MiB /tmp, 128 MiB /wheels and 16 MiB /dev/shm. The prototype adds hard nofile=256 and core=0 limits, disabled image healthchecks and a disabled runtime log driver, all included in the plan digest. Source/wheel bytes are initial inputs; approved code may modify its writable container state during the run.

Docker configuration is checked and the bootstrap observes actual memory.max, memory.swap.max, pids.max, cpu.max, rlimits and mount state. Cgroup read-only status is checked so target code cannot relax its limits. Runtime mounts still include Docker's standard virtual /proc and /dev facilities; non-root/capability/seccomp protections and the shared kernel are material limits. The code cannot establish safety against a compromised daemon/kernel or malicious base image.

Host-side timers bound Docker infrastructure and step invocations; killing the CLI alone does not stop container execution, so timeout/error paths remove the entire container. Cleanup uses separate bounded calls (up to roughly 45 seconds beyond the main run budget). Uninterruptible host I/O and daemon failure can prevent complete cleanup; the journal remains available.

Both output streams are drained concurrently. Each retains at most 1 MiB raw bytes per step, with an aggregate 4 MiB raw capture budget across the run. Overflow is drained/discarded rather than buffered on disk or held unbounded in memory. Once the aggregate budget is spent, later logs retain byte counts/hashes/truncation markers with empty prefixes. Counts/hashes describe bytes observed by the host; timeout/crash can cut a stream short. Invalid UTF-8 is replaced for display and terminal controls become literal escapes. No daemon-side project log file is enabled.

Execution JSON is capped at 64 MiB, including escaped bounded logs and provenance. It records approved settings, exact initial per-step environments/argv, engine code fingerprint, image/server/kernel observations, source/artifact bindings, Docker exec CLI exit status, timings, byte counts/truncation/hashes and cleanup status. A reported zero status is not proof of application correctness. Codes 125/126/127 may be Docker launch errors or program-selected statuses; 128+N is not treated as proof of a particular signal. Final Docker OOMKilled state is recorded as an observation, not a complete account of every exec-process OOM event. No diagnosis rules are added here.

## Cleanup and recovery

The journal is `<report>.run.json`, containing unique run ID, exact container name, plan digest, state and cleanup outcome. `cleanup JOURNAL --docker-socket /local/socket` checks both ownership labels and removes only that container; it never prunes images, volumes belonging to others or unrelated containers. A failed cleanup remains visible, makes CLI success impossible, and can be retried when the daemon is available.

Ctrl-C and SIGTERM attempt cleanup and preserve a cancelled report. A second interruption, SIGKILL, host crash, process failure during audit writes or an unavailable daemon can leave a partial journal or container. No program can promise finally-block cleanup after SIGKILL. Project-created background descendants may remain inside the same constrained container until removal. After host failure, the host wall-clock watchdog is unavailable; do not rely on the container's keepalive as an adversary-proof independent timer. These are reasons the live recovery gates remain required.

The hardening pass now records attempted steps before launching transport, so cancellation and unexpected transport errors cannot mislabel them as never reached or leave the overall result completed. Interrupted host capture preserves its bounded observed output after process cleanup; its exit status is labeled as the interrupted host Docker CLI, not a proven target-program status. Attempts receive finish timestamps and observed timings even when transport fails. Collection of final diagnostic state is best effort: malformed data or an interruption there cannot suppress the container-removal attempt. A final CLI cancellation message directs users to the report/journal rather than falsely asserting nothing ran.

## Tests completed without Docker

- Simulated success, nonzero exit, timeout, cancellation, partial-create/start failure, failed inspect/kernel controls, transfer mismatch, cleanup failure and explicit recovery.
- Rejection of host networking/mounts/devices, weaker resource/security settings, writable root/cgroup mounts, unexpected interfaces, image-declared volumes and unsupported server controls.
- Explicit opt-in and matching approval before backend access, inherited host credentials/config exclusion and local-socket-only selection.
- Byte-verified source/wheel transfer contracts, source provenance, state forwarding, not-reached steps, private artifacts and aggregate log budgets.
- Real bounded pipe-I/O tests of fixed trusted host helpers, including simultaneous stdout/stderr, stdin and timeout. Bootstrap snippets are syntax-parsed on the host; they are never executed there.
- Security-verifier rejection still active under `python -O`.
- Cancellation retains partial bounded output and attempted-step evidence; unexpected transport errors and run-budget expiry cannot produce completed reports. Malformed/interrupted final-state diagnostics still lead to container removal.

The live smoke gate requires an explicit `--live-container` pytest option and manually prepared `--live-plan`, `--live-snapshot`, `--live-approval` inputs (plus wheelhouse/socket when needed). It never fabricates a real execution approval. Default test runs skip it.

## Remaining gates before Part 6 can be called complete

- [x] Run the approved zero-dependency success fixture on Linux/cgroup-v2 Docker Desktop ARM64; verify preflight and exact environment evidence. This validates this specific VM runtime, not all Linux/macOS hosts.
- [x] Verify actual failed-step status and that later steps never start.
- [ ] Observe network denial and absence of host files/credentials/mounts using approved sentinel fixtures.
- [ ] Exercise actual CPU, memory/swap, PID, core/nofile and writable-storage limits; include logs of the observed outcomes.
- [ ] Flood stdout/stderr beyond both per-step and aggregate caps; verify no daemon log growth and correct truncation/timing.
- [ ] Exercise step and whole-run timeouts, Ctrl-C and SIGTERM; confirm all processes/containers are removed.
- [ ] Exercise host interruption, retained journal and targeted recovery; verify unrelated containers/images remain intact.
- [ ] Test source/wheel mutations around staging and copied-byte verification; exercise malicious target filenames/symlinks inside the disposable environment.
- [ ] Record repeatability/runtime results and either verify macOS VM support or explicitly limit the release to the validated Linux configuration.

One passing live smoke does not satisfy this checklist. Reserved held-out setup-evaluation scenarios remain unchanged, and no detection-accuracy or containment claim follows from mocked tests. The user approved proceeding with offline milestones while these gates remain pending. Their completion does not close the live gates.

References: [Docker resource controls](https://docs.docker.com/engine/containers/resource_constraints/), [Docker exec environment behavior](https://docs.docker.com/reference/cli/docker/container/exec/), [Docker tmpfs behavior](https://docs.docker.com/engine/storage/tmpfs/).

## First approved live attempt — 2026-10-27

The user interactively approved both original ARM64 fixture plans. The success fixture attempt created a constrained container, passed Docker configuration inspection, then stopped before source transfer because the original sysfs enumeration expected exactly `lo`. Cleanup was confirmed removed. [Original report](../examples/live-preflight-failed.json) and [readable evidence](../examples/live-preflight-failed.md) are genuine preflight observations, not a project failure. The second target plan was not run because the same shared preflight blocked progress.

An infrastructure-only follow-up (no target transfer/import/execution) established that socket interface enumeration includes dormant tunnel devices; `/sys/class/net` additionally contains the non-interface `bonding_masters` entry. The corrected fixed probe uses socket enumeration plus ioctl interface flags/IPv4 addresses and proc IPv4/IPv6 route/address observations. Every non-loopback device must be DOWN/not RUNNING and lack an IPv4 address; IPv4 routes and any non-loopback IPv6 addresses/routes are rejected. It still requires no networking in Docker, zero capabilities, non-root and the other original controls. Missing/malformed observations fail closed. No external-interface activation or egress exception is allowed. Regression tests cover up/running devices, addresses, routes and malformed/missing mappings.

The revised kernel preflight passed in a separately constrained infrastructure-only inspection container, with removal confirmed. The two target plans were rebuilt and dry-run validated; they require fresh full-digest approval because the runner fingerprint changed. No target setup command has run yet. Resource-abuse, egress, timeouts, recovery and repeatability gates remain unchecked.

## Approved target results and next probes — 2026-10-27

The user interactively approved the corrected plans. The state-success fixture completed: the environment assignment persisted, the relative directory change passed, and the final Python command emitted `DOCTOR_STATE_SUCCESS` with exit 0. The deliberate failure fixture emitted `DOCTOR_EXPECTED_FAILURE` with exit 7; `instruction-0002` was not reached. Both containers were removed and absence confirmed. Genuine JSON/Markdown records are linked in [examples](../examples/README.md).

The explicit pytest live smoke passed with the actual user-approved plan/receipt. A ten-run series of the same approved success fixture completed with the expected marker and removal in all ten cases; [runtime measurements](../evaluation/results-live-development.json) record the exact denominator, engine/image and timings. This provides basic state/exit/cleanup repeatability evidence on Docker Desktop 4.97.0 / Engine 29.9.2 / CPython 3.12.16 / Linux ARM64. It does not complete broader enforcement or platform acceptance.

Three NEW development plans are prepared by `scripts/prepare_live_controls.py`, requiring a new output directory, explicit image digest and platform. It copies authored fixtures without importing them, creates a harmless private host-only sentinel outside container inputs, pins snapshots, and generates unapproved plans plus an approval-only helper. It never starts Docker or creates approval receipts. Unit tests allow only trusted Git infrastructure calls during preparation and syntax-parse fixture Python rather than executing it.

The new probes cover network/host sentinels, bounded CPU/memory/PID/descriptor/core/tmpfs stress, and per-stream/whole-run log overflow. None has run yet. For the future network run, the harness must verify the original host-only file still exists with its recorded hash and set the synthetic `DOCTOR_HOST_SENTINEL` in Doctor's host environment; neither belongs in the target environment or staged file inventory. Remove only that exact authored sentinel after the probe, never broad host files. CPU/memory probes have finite source-side bounds in addition to the approved cgroup limits. Containers still share a kernel and do not make arbitrary code completely safe.

Timeouts (including the full 600-second run budget), Ctrl-C, SIGTERM, host-kill recovery, unrelated-resource preservation, live staging/mutation cases and held-out execution remain subsequent gates. Full live validation remains pending.
