# Milestone 4: static checks

Status: implemented and verified locally on macOS / Python 3.14.5. The full suite has 109 passing tests; lint and formatting checks pass. Runtime coverage for other Python/platform combinations remains a CI/release task.

## Interface and evidence

`reprodoctor check SNAPSHOT --python-version 3.12.0 --format json|markdown [--output NEW_FILE]` first revalidates the complete snapshot using the existing integrity checks. It reads bounded text and parses TOML, dependency strings and Python ASTs. No target code, extracted command, installer, resolver, project import, build backend or network request runs.

Each finding records a stable rule family and sequential finding ID, status/severity, observed fact, evidence, suggested action and check limitation. Evidence includes a snapshot-relative path, whole-file SHA-256 and physical line range when it can be located precisely. Manifest-wide syntax/type observations use whole-file evidence rather than guessed line numbers. Absence observations cite the command/include location plus the absent snapshot-relative target. Inventory/coverage observations may have no individual file location.

The report records commit, snapshot digest, static target, Doctor version, checker Python and installed parser/specifier dependency versions. It explicitly states `execution_status: not_run` and `execution_permitted: false`. JSON is the underlying record; Markdown renders those same facts, actions, evidence and limitations, escaping HTML, Markdown control characters and terminal controls in untrusted strings. Neither format approves a command or proposes running it automatically.

CLI exit 0 means an inspection completed, not that the project is reproducible. Exit 2 indicates invalid input, unsupported target syntax, exceeded limits or an output failure. Findings do not turn the CLI exit code into an execution verdict.

## Rule coverage and limits

| Rule family | Supported observations | What remains unknown |
| --- | --- | --- |
| dependencies | Inventory root pyproject.toml, setup.py/setup.cfg/Pipfile/poetry.lock/uv.lock and requirements*.txt / requirements/*.txt; parse `[project].dependencies`, dynamic metadata types, PEP 508 strings and supported requirement lines | Optional/build-system dependency validation, dependency completeness, import-to-distribution mapping, package availability, lockfile semantics, recursive dependency resolution and installer options |
| python | Parse project.requires-python, one numeric minor/patch .python-version, and standalone unfenced/non-HTML README `Python: X.Y[.Z]` or `Python ==X.Y[.Z]`; compare exact static target | General prose, version-manager aliases, multiple pins, non-CPython runtimes, platform compatibility and actual execution |
| references | Check literal pip `-r`/`-c` inputs, requirements include paths, direct Python script inputs, copy sources and simple relative `cd`; allow lexical `..` within the snapshot | Arbitrary prose links, shell expansion, ambiguous command state, pipelines, options outside the subset and external prerequisites |
| environment | Match literal README export/braced variable names and simple os.environ/os.getenv source AST patterns against root .env.example key names | Requiredness, optional defaults, aliases, shadowed os names, dynamic access, actual environment values, framework settings and external config |
| consistency | Compare explicit Python constraints for disjoint ranges; flag directly conflicting static/dynamic dependency declarations as metadata findings | Broad README/config agreement, test tool availability, dependency-version conflicts and application correctness |

Requirements includes are checked for literal file presence without recursively resolving arbitrary installer inputs. A present file does not prove every instruction inside it was analyzed. Unknown options/paths remain unknown. No unavailable-distribution claim is made from static data.

Reference paths are normalized against an explicitly tracked relative directory and looked up in an in-memory snapshot inventory. No referenced path is opened on the host. Escaping paths become review items, and expansions/absolute paths remain unknown. Ambiguous preceding commands invalidate the directory assumption rather than creating confident missing-file claims. Missing files are observed as absent from the snapshot and explicitly may be generated. A simple documented copy can downgrade a later target absence to a generation review hint, without pretending the copy ran.

Minor Python declarations represent a whole series (`3.12` becomes `==3.12.*`); they are never silently treated as patch 3.12.0. Disjoint constraints use packaging's interval comparison, requiring packaging >=26.3. The exact default target 3.12.0 is merely an inspection parameter. Overlapping constraints produce a narrow pass, and excluded targets produce unsupported findings; neither establishes an execution result. Arbitrary-equality or oversized constraints are left unknown.

Environment findings report names and locations, not example/default values or raw source lines. A missing .env.example key is always a review hint, including for direct indexing; Doctor does not infer that a setting is required. This is not a secret scanner or a guarantee that all other report metadata is safe to publish.

## Bounds

Snapshot/README input bounds remain unchanged. Static output is capped at 2,000 findings and 8 MiB, and Python declaration comparisons at 1,000 pairs; exceeding a report limit fails without writing a partial analysis document. Environment source scans stop after 100 Python files, 2 MiB aggregate source bytes, 128 KiB per source file and 50,000 AST nodes per file. Skips and parser failures produce unknown coverage observations. Input bounds are not OS-enforced CPU/memory isolation of trusted parsers.

## Acceptance evidence

- Every rule family has positive, negative and unknown/review scenarios. Tests distinguish absent manifests from absent dependencies and validate dynamic, malformed and legacy metadata without running it.
- Version tests cover allowed/excluded exact targets, contradictory README/configuration, compatible minor-series pins, unknown aliases/prose, hidden HTML/code examples and invalid declarations.
- Reference tests cover relative directories, absent inputs, requirements includes, copy-generation hints, unknown state, expansions and paths outside the snapshot. A host sentinel's contents never enter findings.
- Environment tests cover matched/unmatched keys, optional defaults, aliases, dynamic expressions, syntax failures and byte-budget skips. Fixture values are absent from serialized findings.
- Integration tests verify deterministic repeated inspection, JSON/Markdown equivalence, output refusal, snapshot tampering, target validation and no fixture code execution. Rendering tests cover HTML/link/control-character injection.
- An authored static fixture and generated sample reports demonstrate both mismatches and passes. The generator pins a deterministic fixture commit and deletes its temporary repository/snapshot. It never executes fixture code.
- Reserved held-out scenario definitions and their hash remain unchanged. This milestone's tests and sample are development cases; no accuracy claim or held-out evaluation result is reported.

References for supported metadata semantics: [PyPA pyproject specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/), [packaging specifier API](https://packaging.pypa.io/en/stable/specifiers/).

## Next milestone

Part 5 will present extracted commands, required network/artifacts, environment and container settings in a reviewable execution plan, bind approval to source/plan digests and support a no-execution dry-run. No approval workflow or container runner has been implemented in Part 4.
