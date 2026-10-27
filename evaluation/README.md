# Evaluation reservation

`scenarios.json` reserves eight development scenarios and four separate held-out scenarios before README extraction or static checks exist. `reservation.sha256` records the exact initial specification bytes. This reservation is an audit aid; it is not a claim that held-out evaluation has happened or that labels are hidden from the author.

Develop and tune against `development` only. Do not add held-out cases to regression tests or tune rules against their results before the first frozen evaluation. Materialize held-out repositories and expected labels once, freeze them before opening results, and record the tool revision and all amendments. If a held-out result drives a fix, report it and create fresh held-out cases for a later unbiased evaluation.

The intake unit tests are development/security regressions, not the held-out setup evaluation. No third-party repository contents are included. No accuracy figures should be reported yet.

The reservation was recorded in local baseline commit `745ed5a` before Part 3 extraction tuning. Extraction golden fixtures live under `tests/fixtures/extraction` and are development regressions, separate from the held-out setup scenarios.

## First frozen static evaluation (2026-10-27)

The user requested finishing offline work before live Docker validation. Twelve authored repositories are materialized temporarily from `fixtures/*.json`; no fixture Python or README command runs. Rules, fixtures, labels and harness were frozen in `f7638b3` before opening results. `frozen.sha256` binds implementation/fixture/harness bytes; reruns refuse drift. The original reservation remains unchanged.

Run from an installed development checkout:

```sh
python scripts/evaluate.py --output /new/path/results.json
```

`results-static.json` contains all 12 source bindings, per-assertion outcomes, split-specific confusion counts/precision/recall/false-positive denominators, unknown/unsupported finding counts, environment and p50/p95 wall time including temporary Git intake. Execution attempted count is **0**; execution reliability and cleanup rate are **unmeasured**, not zero or successful.

The development split has 10 labeled rule/status assertions. The held-out split has 7. One held-out assertion mismatches: `hold-03` expects `python/finding`, while disjoint declarations are reported under `consistency/finding` by the preexisting checker. This is a frozen **label mapping error**, not evidence that the checker missed the contradiction. The original label and result are retained; no rules were changed after viewing results. Consequently the recorded `python/finding` held-out recall is 0/1 and should not be presented as semantic defect-detection accuracy. A future evaluation needs amended labels documented separately and fresh held-out cases if tuning occurs.

The small public split was reserved before tuning but is not blinded. Metrics measure only explicit assertions; they do not measure all possible defects, full extraction recall, diagnosis causality, successful setup or real-world GitHub accuracy. No broad “accuracy” percentage is claimed. Full Part 9 acceptance remains pending live execution, resource/cleanup tests and ten repeated supported offline runs.

The later Docker Desktop CLI discovery change modifies a frozen implementation file, so the first evaluation's drift guard now intentionally rejects reruns on the current checkout. To reproduce that historical evaluation unchanged, use a separate checkout at `f7638b3` and write results to a new path. The recorded first results and labels have not been overwritten or tuned. Runtime integration work is not a replacement held-out evaluation.
