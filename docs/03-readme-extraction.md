# Milestone 3: README instruction extraction

Status: implemented. Local verification uses macOS, Python 3.14.5, markdown-it-py 4.2.0 and mdurl 0.1.2. Other supported Python/platform combinations still need CI verification.

## Implemented contract

`reprodoctor extract SNAPSHOT [--output NEW_JSON_FILE]` consumes the prior milestone's snapshot. It revalidates inventory, SHA-256 hashes, Git blob IDs and executable modes, and rejects unexpected files/directories or symlinks. The serialized inventory digest establishes consistency with the supplied manifest; it is neither authentication nor execution approval.

The extractor uses CommonMark token/source maps for root README.md, with sh/bash/shell fences and untagged fences as candidates. It never runs a shell, imports repository code, installs project dependencies, follows README links, renders HTML, or applies suggested transformations to source files. HTML block boundaries are parsed so hidden HTML comments do not turn into commands. Markdown inside HTML is subject to CommonMark parsing rules, not browser visibility.

Each candidate records:

- Stable sequential ID and order, parent block ID, source path, one-based inclusive start/end lines.
- Exact source text including original newline style and Markdown container indentation.
- Proposed candidate text, with visible review flags for prompt or Markdown-indentation removal.
- Heuristic command phase and heading phase, selected phase, heading context and classification.
- Ambiguity reasons and `requires_review: true` for every candidate.

The document includes source-block inventories, review/coverage items, the README hash, repository commit and content digest, limitations, and `execution_permitted: false`. This is an intermediate extraction artifact, not a completed reproducibility report or an execution plan.

Simple nonblank, noncomment lines retain separate order within a block. Root-shell-looking comments remain ambiguous candidates. Multiline continuations, heredocs, control flow, unbalanced quotes, nested blocks and compound shell syntax cause the whole block to be retained for review. The parser does not select alternative branches, infer working-directory/environment state, resolve variables, or interpret shell semantics. `$ ` prompt removal affects proposed text only; raw evidence retains the prompt.

Other fenced languages and indented blocks receive explicit omission entries. Recognizable imperative prose is marked for manual review; inline commands are not promoted to executable candidates. A missing root README is an explicit missing-coverage state. Invalid UTF-8, NUL bytes, changed snapshots, or bounds failures stop extraction with a nonzero CLI status.

## Completion checks

- A hand-authored golden README and expected JSON verify installation, configuration, tests and launch; exact text, line ranges and order are asserted independently of generated expectations.
- Tests verify deterministic output, LF/CRLF/CR source mapping, no final newline, Unicode separators, nested lists/quotes, unclosed fences, multiline constructs, alternative headings and prompt handling.
- Unsupported syntax, unknown output/transcript lines, placeholders, configuration activation, heading conflicts, excluded code formats and hidden HTML receive explicit handling.
- Integration tests use actual temporary Git snapshots; a `touch` README command leaves its marker absent. CLI stdout and file output agree, existing files are not overwritten, and output within a snapshot is rejected.
- Tampered README and other files, changed permissions, added files, symlinks, and malformed/adversarial manifest fields stop extraction.
- Limits are 1 MiB README input, 2,000 command candidates and 8 MiB serialized evidence. Repeated large heading context is bounded before output serialization can amplify the input without limit. JSON escapes terminal control characters.
- The eight development and four held-out scenario definitions were committed in local baseline `745ed5a` before extraction tuning. Their reservation bytes remain unchanged. Extraction regression fixtures are separate development cases; no held-out evaluation results or accuracy claims exist yet.

## Limits and next boundary

Command and phase recognition use a small set of deterministic patterns. Review flags can be conservative, including for quoted shell punctuation, extras syntax, or mixed installation/test headings. They are not defect findings. Prose-only instructions, non-root documentation, other Markdown dialects, PowerShell, interactive sessions and broader Python packaging workflows remain outside the supported subset.

File-size and evidence limits bound accepted inputs and output; they are not OS-enforced CPU/memory isolation for the Markdown parser. Concurrent hostile filesystem mutation remains outside the current local threat model. Every extracted command is still untrusted, regardless of its classification or flags.

Part 4 static checks are now tracked in [milestone 4](04-static-checks.md). Command approval, containers, runtime failure diagnosis and reports containing execution evidence remain later milestones.
