# Part 9 — evaluation completed for the reference scope

The original reservation contains eight development and four separate held-out authored scenarios. Fixture definitions were frozen before tuning. The public split is not blinded and is too small to represent GitHub repositories generally. No first-of-kind or general accuracy claim is made.

## Recorded studies

- [First static evaluation](../evaluation/results-static.json): 10 development and 7 held-out rule/status assertions. One held-out label incorrectly mapped a version inconsistency to `python/finding` rather than `consistency/finding`. The original mismatch is retained; rules/results were not rewritten to hide it.
- [Development repetition](../evaluation/results-live-development.json): 10/10 executions of one approved fixture completed with the expected marker and confirmed removal. This measures that fixture on one runtime, not broad reliability.
- [Control probes](../evaluation/results-live-controls.json) and [lifecycle/artifact acceptance](../evaluation/results-live-lifecycle.json): genuine network/resource/log/deadline/interruption/recovery/path/artifact observations with explicit limits.
- [Reserved runtime evaluation](../evaluation/results-runtime-v1.md): seven executions, five planning abstentions, all seven executed containers removed. All 12 frozen outcome/check expectations matched, including abstentions. These are not 12 successful setups.

The four development diagnosis categories each had one positive and four negative executed-case presence assertions: TP=1, FP=0, TN=4, FN=0. Held-out category assertions had zero positives and two negatives; precision/recall are undefined, not perfect. Both clean examples had zero definitive static findings. Missing-file/offline-artifact signatures remained suggestions; unsuccessful tests/timeouts were observed statuses. The held-out resource-abuse failure retained an unknown cause and partial interruption-coverage abstention.

Runtime p50 was 1.314749 seconds and nearest-rank p95 120.588570 seconds across seven executions. The maximum is the intentional timeout, not representative application setup duration. Raw counts, source/plan bindings, unknowns, omitted execution and original record hashes are published.

## Reproduction and audit

See [the frozen protocol and commands](../evaluation/README.md). Runtime rules, package sources, corpus JSON, harness and dependency versions were frozen before the first runtime execution in `runtime-freeze-v1.json`. No rules, original fixtures or runtime labels changed after viewing results. Fresh interactive approvals are required for a rerun; the harness never manufactures them and refuses to overwrite prior results. Original records retain their conservative experimental/pending fields; they are not retroactively certified.

The explicit abstentions preserve the MVP boundary: unsupported copy/multiline/placeholder instructions, incompatible selected Python with no executable step, and state-only documentation. No workflow was silently repaired. Future tuning needs a new version and fresh held-out cases. Other execution configurations, broader dependency/build workflows and real-world setup/causal accuracy remain unverified.
