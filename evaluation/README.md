# Evaluation reservation

`scenarios.json` reserves eight development scenarios and four separate held-out scenarios before README extraction or static checks exist. `reservation.sha256` records the exact initial specification bytes. This reservation is an audit aid; it is not a claim that held-out evaluation has happened or that labels are hidden from the author.

Develop and tune against `development` only. Do not add held-out cases to regression tests or tune rules against their results before the first frozen evaluation. Materialize held-out repositories and expected labels once, freeze them before opening results, and record the tool revision and all amendments. If a held-out result drives a fix, report it and create fresh held-out cases for a later unbiased evaluation.

The intake unit tests are development/security regressions, not the held-out setup evaluation. No third-party repository contents are included. No accuracy figures should be reported yet.
