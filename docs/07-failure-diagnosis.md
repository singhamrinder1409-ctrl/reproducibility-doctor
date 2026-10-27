# Part 7 — conservative failure diagnosis

The user explicitly authorized completing the remaining offline work before returning to Part 6 live validation on 2026-10-27. That changes milestone order, not the pending runtime acceptance gate.

`reprodoctor diagnose EXECUTION.json --format json|markdown [--output NEW_FILE]` reads a bounded local execution report and runs no project or Docker command. It checks the record structure, rejects duplicate JSON keys, nonfinite numbers, duplicate step IDs and oversized logs. Reports are editable evidence, not authenticated attestations.

Observed step status, exit code/source, README provenance and JSON pointers are distinct from suggested causes. Fixed signatures cover missing files, missing imports, unavailable offline dependency artifacts, Python/resolver conflicts and possible configuration failures. The test phase yields an unsuccessful-tests observation. Timeout, cancellation, infrastructure and incomplete cleanup have their own observations. Unknown logs stay unknown. Docker-ambiguous 125/126/127 codes, successful steps, infrastructure failures and interruption do not yield project-cause suggestions.

Every log hint includes the retained text hash, match span, bounded excerpt, step ID, stream pointer and truncation flag. Even a traceback can be forged by repository code: hints never establish required configuration, remote package availability or exact root cause. Fixes are not applied. No signal is inferred from an exit code.

Completion checks: development tests cover all categories, unknowns, forged logs on successful commands, ambiguous transport codes, interruption, cleanup, malformed records and nonmutation. These verify diagnosis of records, not real execution or causal accuracy on arbitrary projects. Part 6 remains open.
