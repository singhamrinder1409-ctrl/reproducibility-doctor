# Reproducibility Doctor — static inspection

Execution: **not run**. This report contains static observations, not a setup verdict.

Commit: 593c52a77464eef9b1db4893b8614e5f7530488a
Snapshot digest: f86b1e8f4e7d4e011339015240f993bc55179b88e82b0a651c705dc2c7950eac
Static target Python: 3.12.0
Checker environment: {&#x27;python&#x27;: &#x27;3.14.5&#x27;, &#x27;dependencies&#x27;: {&#x27;packaging&#x27;: &#x27;26.3&#x27;, &#x27;markdown-it-py&#x27;: &#x27;4.2.0&#x27;, &#x27;mdurl&#x27;: &#x27;0.1.2&#x27;}}

Status counts: finding=2, pass=4, review=1, unknown=2, unsupported=1

## static-0001: dependencies — pass

Observed: Recognized manifest files are present.

Suggested next action: Review the dependency workflow; manifest presence is not an installation result.

Limit: Manifest checks do not prove dependency completeness or availability.

Evidence: pyproject.toml; SHA-256: 5cb9f53d803bc814371a7f73165a5c68c3e262c663d71b78d9a38bc0d7758204

## static-0002: dependencies — pass

Observed: Explicit project dependency strings parse successfully.

Suggested next action: Verify completeness and installation in an approved environment.

Limit: Manifest checks do not prove dependency completeness or availability.

Evidence: pyproject.toml; SHA-256: 5cb9f53d803bc814371a7f73165a5c68c3e262c663d71b78d9a38bc0d7758204

## static-0003: python — pass

Observed: Static target Python 3.12.0 satisfies declaration &gt;=3.12.

Suggested next action: Choose an allowed exact runtime; exclusion does not mean the project is broken.

Limit: Only explicit declarations are compared; the static target has not run.

Evidence: pyproject.toml; SHA-256: 5cb9f53d803bc814371a7f73165a5c68c3e262c663d71b78d9a38bc0d7758204

## static-0004: python — unsupported

Observed: Static target Python 3.12.0 is excluded by declaration ==3.11.&#42;.

Suggested next action: Choose an allowed exact runtime; exclusion does not mean the project is broken.

Limit: Only explicit declarations are compared; the static target has not run.

Evidence: README.md:3; SHA-256: d81636374153ec8f78a30381ab36b373c66d91156dc08df5bc0e84726cae5e98

## static-0005: consistency — finding

Observed: Explicit Python declarations &gt;=3.12 and ==3.11.&#42; have no overlap.

Suggested next action: Reconcile disjoint declarations; overlap does not prove compatibility.

Limit: Explicit declaration overlap does not prove runtime compatibility.

Evidence: pyproject.toml; SHA-256: 5cb9f53d803bc814371a7f73165a5c68c3e262c663d71b78d9a38bc0d7758204

Evidence: README.md:3; SHA-256: d81636374153ec8f78a30381ab36b373c66d91156dc08df5bc0e84726cae5e98

## static-0006: references — finding

Observed: Literal input file &#x27;requirements.txt&#x27; is absent from the snapshot.

Suggested next action: Check spelling, working directory and generation before calling this a defect.

Limit: Only literal inputs are checked; missing files may be generated or external.

Evidence: README.md:8; SHA-256: d81636374153ec8f78a30381ab36b373c66d91156dc08df5bc0e84726cae5e98

Evidence: requirements.txt; SHA-256: absent

## static-0007: references — pass

Observed: Literal input file &#x27;app.py&#x27; is present in the snapshot.

Suggested next action: Check spelling, working directory and generation before calling this a defect.

Limit: Only literal inputs are checked; missing files may be generated or external.

Evidence: README.md:14; SHA-256: d81636374153ec8f78a30381ab36b373c66d91156dc08df5bc0e84726cae5e98

Evidence: app.py; SHA-256: 1479972bee8529081b50ff04f7a2a75c113b5e76be8aabf960d7c3918442ddb2

## static-0008: references — unknown

Observed: Inspected 2 supported inputs; ambiguous commands and prose paths were not resolved.

Suggested next action: Review extraction flags, shell state and generated files manually.

Limit: Only literal inputs are checked; missing files may be generated or external.

Evidence: snapshot inventory / limited check coverage.

## static-0009: environment — review

Observed: Environment name SERVICE&#95;TOKEN has no matching key in root .env.example.

Suggested next action: Confirm requiredness and document a safe example. Values are omitted.

Limit: Name matching does not establish requiredness or resolve dynamic access.

Evidence: app.py:5; SHA-256: 1479972bee8529081b50ff04f7a2a75c113b5e76be8aabf960d7c3918442ddb2

## static-0010: environment — unknown

Observed: Variable requiredness and dynamically constructed names are not established.

Suggested next action: Review aliases, defaults and external configuration before diagnosing a defect.

Limit: Name matching does not establish requiredness or resolve dynamic access.

Evidence: snapshot inventory / limited check coverage.

## Reproduce this inspection

1. Obtain the same committed source and verify the recorded snapshot digest.
2. Use the recorded Doctor version and dependency versions.
3. Run reprodoctor check SNAPSHOT --python-version 3.12.0 --format markdown.
4. Review findings alongside the source. No project commands have run.

Doctor version: 0.1.0.dev0

## Coverage and limitations

- Manifest checks do not prove dependency completeness or availability.
- Only explicit declarations are compared; the static target has not run.
- Only literal inputs are checked; missing files may be generated or external.
- Name matching does not establish requiredness or resolve dynamic access.
- Explicit declaration overlap does not prove runtime compatibility.
- Static passes are not setup runs; no index or build backend was queried.
