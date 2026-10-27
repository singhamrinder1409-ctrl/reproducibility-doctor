# Part 10 — development preview and release checklist

## Prepared locally

- Standalone source tree; bounded CLI workflow and automated development tests.
- MIT license, package metadata/readme, contributor and security documents.
- Versioned static sample reports with authored source; no third-party repository contents.
- Captured static CLI transcript, asciinema-compatible recording and local HTML walkthrough.
- Frozen 12-fixture static evaluation, transparent counts and label-error disclosure.
- CI definition: Linux/macOS and Python 3.12–3.14, lint/format/tests, static demo and wheel installation smoke. It uses read-only GitHub permissions, no checkout credentials, no live execution or publishing secrets. Actions are pinned to upstream commit SHAs: [checkout v6.0.2](https://github.com/actions/checkout/releases/tag/v6.0.2), [setup-python v6.0.0](https://github.com/actions/setup-python/releases/tag/v6.0.0).

## Before claiming a stable execution release

- Complete every unchecked Part 6 live gate and record the actual supported Docker hosts.
- Measure execution/cleanup reliability and repeated-run timings for Part 9.
- Generate a genuine reviewed execution report and recording; never substitute simulated evidence.
- Confirm a fresh source install, wheel install and static demo work on supported hosts.
- Scan tracked artifacts for credentials, personal paths, private source and approval receipts. Literal fixture names/values must be safe authored examples.
- Publish to an explicitly owned public GitHub repository and verify the remote commit and CI run. No green badge or stable release claim before those runs finish.
- Confirm private vulnerability reporting settings if offering that channel.

The source can be published as an **experimental development preview** with live gates visibly pending. No stable tag or PyPI publication is prepared automatically. Publishing source does not complete the live-runtime gate.

## Local verification record — 2026-10-27

A wheel was built with isolated build dependencies, installed with runtime dependencies into a fresh virtual environment, and its CLI entry point displayed all commands. Local Ruff lint/format and the authored test suite were run. See the final verification record below for the final count. This verifies Doctor packaging, not target-project installation. The static demo was regenerated into a separate new directory and every captured CLI command returned zero. No target code or live container ran.

The first static evaluation has 10 development and 7 held-out labeled assertions; the one held-out label mapping error remains disclosed. No post-result rule tuning occurred. Runtime dependency license notices were inspected; see [dependency notes](../DEPENDENCIES.md).

The GitHub connection could read the owner profile and repository list, but has no repository-creation tool. No `reproducibility-doctor` remote existed. The browser creation page required sign-in. Publication/remote CI are pending user sign-in or an empty destination repository, rather than being claimed complete locally.

Final local checks: **214 tests passed, 1 live Docker test skipped**; Ruff lint and all 47 Python files' formatting passed. A clean local Git clone installed into a fresh virtual environment and ran the static-only CLI demo successfully. These results are from macOS with Python 3.14.5; the CI matrix is prepared but has not run remotely. Runtime/container acceptance remains pending.

## Publication record — 2026-10-27

The public [GitHub repository](https://github.com/singhamrinder1409-ctrl/reproducibility-doctor) was created in the owner’s signed-in browser. All local source commits were pushed to `main`; the initial remote head matched `253d60acdbe1fc3694efc8d882ba7845d163c4a3`. The README now links the real repository and [CI runs](https://github.com/singhamrinder1409-ctrl/reproducibility-doctor/actions). This is an experimental source preview, with no stable release tag and no claimed live Docker acceptance. The earlier sign-in blocker is resolved.
