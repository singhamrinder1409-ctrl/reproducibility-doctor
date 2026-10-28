# Reserved runtime evaluation v1

Local run date: 2026-10-27 (America/Vancouver). Original machine records use UTC.

**12 cases: 7 executed, 5 explicit planning abstentions; 7/7 executed containers removed.** All frozen per-case checks matched, including abstention expectations. This is not a 100% general accuracy claim.

| Case | Split | Expected / observed | Cleanup | Seconds |
| --- | --- | --- | --- | --- |
| dev-01 | development | completed / completed | removed | 2.291353 |
| dev-02 | development | failed / failed | removed | 1.469633 |
| dev-03 | development | abstain / abstain | not run | — |
| dev-04 | development | abstain / abstain | not run | — |
| dev-05 | development | failed / failed | removed | 0.764366 |
| dev-06 | development | abstain / abstain | not run | — |
| dev-07 | development | timed_out / timed_out | removed | 120.58857 |
| dev-08 | development | failed / failed | removed | 1.314749 |
| hold-01 | held_out | completed / completed | removed | 0.757788 |
| hold-02 | held_out | abstain / abstain | not run | — |
| hold-03 | held_out | abstain / abstain | not run | — |
| hold-04 | held_out | failed / failed | removed | 1.107365 |

Runtime p50: 1.314749 seconds. Nearest-rank p95: 120.588570 seconds across seven executions; the maximum is the intentional two-minute timeout. These timings are not representative application benchmarks.

## Diagnosis assertions

Each of four development categories (missing file, unavailable offline artifact, unsuccessful tests, timeout) had one positive and four negative executed-case presence assertions: TP=1, FP=0, TN=4, FN=0 per category. Each held-out category had zero positives and two negatives: TP=0, FP=0, TN=2, FN=0. Held-out precision/recall are undefined (null), not evidence of perfect detection.

The two clean successful examples had zero definitive static findings. The held-out control-output/resource-abuse case failed with controls escaped and no invented causal suggestion. Its exact cause and controlled interruption component remain unestablished by that single command; separate development resource/signal tests do not become held-out evidence.

## Abstentions


- dev-03: Selected Python is excluded; no executable instruction is documented.
- dev-04: Only environment state is documented; there is no executable process or established configuration requiredness.
- dev-06: Alternative/placeholder installation instructions require manual selection; none is silently chosen.
- hold-02: Documented cp is outside the executor subset; no replacement is silently inserted.
- hold-03: Contradictory Python declarations and multiline installation require review; the prior static label mapping error is retained separately.

## Limits and audit

The original corpus is public and not blinded. No detection rules, original fixtures or frozen runtime labels were changed after viewing these runtime results. The earlier static evaluation label mapping error remains in its original record. Log signatures are suggestions, not verified causes; unavailable offline artifacts do not establish remote-package availability.

Source/protocol/dependency bindings are in `runtime-freeze-v1.json`. Full structured outcomes are in `results-runtime-v1.json`; original execution hashes are in `runtime-record-hashes-v1.json`. Genuine readable examples are under `examples/runtime-*.md`. Approval receipts, private paths and full multi-MiB flood text are not published.
