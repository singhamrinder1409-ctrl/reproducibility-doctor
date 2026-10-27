# Part 8 — reports and CLI

`reprodoctor report EXECUTION.json [--static STATIC.json] --format markdown|json [--output NEW_FILE]` combines the original execution record, diagnosis and optional static inspection. Static and execution records must bind the same commit and snapshot digest. This command never approves or runs commands.

JSON schema version 1 preserves exact recorded source, argv/state, initial settings, observed preflight, artifacts, engine, bounded logs, exit-code provenance, exclusions, unreached steps, timings and cleanup. The input execution record has a canonical JSON SHA-256 for comparison; that hash does not authenticate its author. Markdown renders these fields as escaped text with diagnosis and reproduction prerequisites. Original JSON remains the complete machine-readable evidence.

All untrusted text uses the existing Markdown escaping routine: no raw repository HTML, clickable repository-supplied Markdown or terminal control sequences. Inputs have a 64 MiB execution-record budget, 200 steps and bounded per-stream text; output is capped at 128 MiB. Duplicate/nonfinite JSON is refused. Output must be new, created owner-only. No overwriting inputs. STDOUT is an explicit user choice.

Reports contain exact commands, configuration literals and project logs. They are **not automatically redacted**. Review and redact a separate sharing copy before publication; do not publish approval receipts, actual private source or credentials. Authored public examples contain no real credentials. Redaction would change recorded evidence hashes and is a future separate export feature, not a claimed guarantee.

Tests check source-binding rejection, schema rejection, hostile HTML/Markdown/control escaping, CLI output permissions, refusal to overwrite, original-record preservation and facts versus suggestions. A local GUI is deferred because the CLI covers the review workflow without extra infrastructure. Real run validation and execution evaluation remain pending.
