# Part 9 — evaluation

See [evaluation protocol, results and label amendment note](../evaluation/README.md). The original eight-development/four-held-out reservation is preserved. All twelve repositories and labels are now authored JSON fixtures, frozen before the first static run; the implementation has not been tuned against observed held-out results.

Completed: reproducible static-only harness, recorded source hashes, split-specific per-rule/status assertion counts, undefined metrics represented as null, false positives/negatives, unknown and unsupported counts, runtime distribution and transparent label mismatch disclosure. Harness metrics have a development unit test; held-out scenarios have not become regression tests.

Pending: container execution success/failure outcomes, source/credential and network sentinel tests, actual resource enforcement, interruption/cleanup reliability, ten repeated approved runs and their durations. Fixture code and README commands remain unexecuted. This milestone is partially complete, not an end-to-end evaluation claim.

## Runtime phase ready for explicit review

Part 6 reference acceptance is now complete for the recorded Docker Desktop ARM64 setup. The unchanged reserved corpus has been materialized for the first runtime evaluation: seven new executable plans await real interactive approval; five unsupported/ambiguous/state-only workflows remain explicit abstentions. No reserved runtime command has run. The protocol/source/dependency freeze is committed before results; see [runtime protocol and commands](../evaluation/README.md). Neither development controls/repetition nor their approvals are substituted for these corpus inputs.
