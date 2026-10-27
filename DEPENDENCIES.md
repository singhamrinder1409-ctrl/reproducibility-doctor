# Dependencies and licenses

Runtime packages are installed separately from the package registry; their source is not vendored here. Local installed distribution license files were inspected for the pinned development environment:

| Package | Role | License |
| --- | --- | --- |
| markdown-it-py 4.2.0 | Source-aware CommonMark parsing | MIT (including upstream markdown-it attribution) |
| mdurl 0.1.2 | Markdown URL parsing, transitive | MIT |
| packaging 26.3 | Python/dependency specifiers | Apache-2.0 OR BSD-2-Clause |

Their own distributions contain their respective license notices. This project's MIT license covers Doctor's authored code and fixtures, not those packages. Keep upstream notices when redistributing dependency distributions. Development dependencies are listed in `requirements-dev.txt`; pytest and Ruff are developer tools, not runtime imports.

Python, Git and optional Docker are separately installed infrastructure with their own licenses and installation requirements. No Docker runtime or base image is bundled. Inspect and trust the selected digest-pinned image separately. No hosted or paid API is required by Doctor. First-time installation and CI dependency downloads still need network access; offline target execution requires pre-provisioned artifacts.
