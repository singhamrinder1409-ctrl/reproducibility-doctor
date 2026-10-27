"""Conservative static observations. No imports, builds, resolution or execution."""

from __future__ import annotations

import ast
import hashlib
import platform
import re
import shlex
import tomllib
from collections import Counter
from importlib.metadata import version
from pathlib import Path, PurePosixPath

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from . import __version__
from .extraction import encode_candidates, extract_readme
from .intake import IntakeError
from .snapshot import load_snapshot

RULES = {
    "dependencies": "Manifest checks do not prove dependency completeness or availability.",
    "python": "Only explicit declarations are compared; the static target has not run.",
    "references": "Only literal inputs are checked; missing files may be generated or external.",
    "environment": "Name matching does not establish requiredness or resolve dynamic access.",
    "consistency": "Explicit declaration overlap does not prove runtime compatibility.",
}
ENV_NAME = r"[A-Za-z_][A-Za-z0-9_]*"


class Checks:
    def __init__(self, contents: dict[str, bytes], python_version: str):
        if len(python_version) > 32 or not re.fullmatch(r"3\.[0-9]+\.[0-9]+", python_version):
            raise IntakeError("Static Python target must be an exact version such as 3.12.0")
        self.contents = contents
        self.target = python_version
        self.findings: list[dict] = []
        self.declarations: list[tuple[str, SpecifierSet, dict]] = []
        self.texts: dict[str, str | None] = {}
        self.hashes: dict[str, str] = {}
        self.requirements = sorted(
            p
            for p in contents
            if re.fullmatch(r"requirements[^/]*\.txt|requirements/[^/]+\.txt", p)
        )
        self.extraction = extract_readme(contents.get("README.md", b""))

    def text(self, path: str) -> str | None:
        if path not in self.texts:
            try:
                self.texts[path] = self.contents[path].decode("utf-8-sig")
            except UnicodeError:
                self.texts[path] = None
        return self.texts[path]

    def evidence(self, path: str, line: int | None = None, end: int | None = None) -> dict:
        if path in self.contents and path not in self.hashes:
            self.hashes[path] = hashlib.sha256(self.contents[path]).hexdigest()
        return {
            "path": path,
            "start_line": line,
            "end_line": end or line,
            "sha256": self.hashes.get(path),
        }

    def add(self, rule: str, status: str, fact: str, evidence: list[dict], action: str) -> None:
        if len(self.findings) >= 2000:
            raise IntakeError("Static finding limit exceeded; no partial report")
        self.findings.append(
            {
                "id": f"static-{len(self.findings) + 1:04d}",
                "rule_id": rule,
                "status": status,
                "severity": "warning" if status in {"finding", "review"} else "info",
                "observed_fact": fact,
                "evidence": evidence,
                "suggested_action": action,
                "limitation": RULES[rule],
            }
        )

    def manifest_checks(self) -> None:
        recognized = self.requirements + [
            p
            for p in (
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "Pipfile",
                "poetry.lock",
                "uv.lock",
            )
            if p in self.contents
        ]
        self.add(
            "dependencies",
            "pass" if recognized else "review",
            "Recognized manifest files are present."
            if recognized
            else "No recognized dependency manifest was found in supported locations.",
            [self.evidence(p) for p in recognized],
            "Review the dependency workflow; manifest presence is not an installation result.",
        )
        if "pyproject.toml" in self.contents:
            text = self.text("pyproject.toml")
            try:
                if text is None:
                    raise ValueError()
                config = tomllib.loads(text)
                project = config.get("project", {})
                if not isinstance(project, dict):
                    raise ValueError()
            except (ValueError, RecursionError):
                self.add(
                    "dependencies",
                    "finding",
                    "pyproject.toml is not readable UTF-8/TOML or [project] is not a table.",
                    [self.evidence("pyproject.toml")],
                    "Repair the manifest before relying on its metadata.",
                )
            else:
                dynamic = project.get("dynamic", [])
                if not isinstance(dynamic, list) or not all(isinstance(v, str) for v in dynamic):
                    self.add(
                        "dependencies",
                        "finding",
                        "project.dynamic is not an array of strings.",
                        [self.evidence("pyproject.toml")],
                        "Check the project metadata types.",
                    )
                    dynamic = ["dependencies", "requires-python"]
                dependencies = project.get("dependencies")
                if "dependencies" in dynamic and dependencies is not None:
                    self.add(
                        "dependencies",
                        "finding",
                        "Dependencies are declared both static and dynamic.",
                        [self.evidence("pyproject.toml")],
                        "Declare each metadata field either statically or dynamically.",
                    )
                if "dependencies" in dynamic or dependencies is None:
                    self.add(
                        "dependencies",
                        "unknown",
                        "Project dependencies are dynamic or not explicitly declared.",
                        [self.evidence("pyproject.toml")],
                        "Review metadata manually without running the build backend.",
                    )
                elif not isinstance(dependencies, list) or not all(
                    isinstance(d, str) for d in dependencies
                ):
                    self.add(
                        "dependencies",
                        "finding",
                        "project.dependencies is not an array of strings.",
                        [self.evidence("pyproject.toml")],
                        "Use PEP 508 dependency strings.",
                    )
                else:
                    try:
                        for dependency in dependencies:
                            Requirement(dependency)
                    except InvalidRequirement:
                        self.add(
                            "dependencies",
                            "finding",
                            "At least one project dependency is not a valid PEP 508 declaration.",
                            [self.evidence("pyproject.toml")],
                            "Review dependency syntax; no index was queried.",
                        )
                    else:
                        self.add(
                            "dependencies",
                            "pass",
                            "Explicit project dependency strings parse successfully.",
                            [self.evidence("pyproject.toml")],
                            "Verify completeness and installation in an approved environment.",
                        )
                requires = project.get("requires-python")
                if "requires-python" in dynamic:
                    self.add(
                        "python",
                        "unknown",
                        "Python metadata is declared dynamic; no static constraint is assumed.",
                        [self.evidence("pyproject.toml")],
                        "Review Python metadata manually.",
                    )
                elif requires is not None:
                    self.declare_python(requires, self.evidence("pyproject.toml"))
        for path in recognized:
            if path not in self.requirements and path != "pyproject.toml":
                self.add(
                    "dependencies",
                    "unknown",
                    "Manifest is inventoried but its dependency semantics are not supported.",
                    [self.evidence(path)],
                    "Review this packaging workflow manually.",
                )
        for path in self.requirements:
            text = self.text(path)
            if text is None:
                self.add(
                    "dependencies",
                    "unknown",
                    "Requirements file is not UTF-8.",
                    [self.evidence(path)],
                    "Review encoding manually.",
                )
                continue
            unknown = False
            for line, value in enumerate(_lines(text), 1):
                value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
                if not value or value.startswith("#"):
                    continue
                if value.startswith(("-r", "-c", "--requirement", "--constraint")):
                    try:
                        words = shlex.split(value)
                    except ValueError:
                        unknown = True
                        continue
                    reference = self.requirement_paths(words)
                    if reference:
                        for name in reference:
                            self.reference(
                                name, str(PurePosixPath(path).parent), self.evidence(path, line)
                            )
                    else:
                        unknown = True
                else:
                    try:
                        Requirement(value)
                    except InvalidRequirement:
                        unknown = True
            self.add(
                "dependencies",
                "unknown" if unknown else "pass",
                "Requirements contain unsupported options, paths or syntax."
                if unknown
                else "Supported requirement lines parse; include paths were checked.",
                [self.evidence(path)],
                "Review installer options and artifacts; no package availability is inferred.",
            )

    def declare_python(self, value: object, evidence: dict) -> None:
        if isinstance(value, str) and (len(value) > 256 or "===" in value):
            self.add(
                "python",
                "unknown",
                "Python declaration exceeds the supported constraint subset.",
                [evidence],
                "Review unusually large or arbitrary-equality constraints manually.",
            )
            return
        try:
            if not isinstance(value, str) or not value.strip():
                raise InvalidSpecifier()
            spec = SpecifierSet(value)
        except InvalidSpecifier:
            self.add(
                "python",
                "finding",
                "Python requirement is not a nonempty version specifier.",
                [evidence],
                "Correct the Python declaration.",
            )
            return
        self.declarations.append((value, spec, evidence))

    def python_checks(self) -> None:
        if ".python-version" in self.contents:
            text = self.text(".python-version")
            values = text.strip().splitlines() if text is not None else []
            if len(values) == 1 and re.fullmatch(r"3\.[0-9]+(?:\.[0-9]+)?", values[0]):
                version = values[0]
                self.declare_python(
                    "==" + version + (".*" if version.count(".") == 1 else ""),
                    self.evidence(".python-version", 1),
                )
            else:
                self.add(
                    "python",
                    "unknown",
                    ".python-version is not one supported numeric CPython declaration.",
                    [self.evidence(".python-version")],
                    "Review version-manager aliases and multiple versions manually.",
                )
        readme = self.text("README.md") if "README.md" in self.contents else None
        if readme:
            for line, value in enumerate(_lines(readme), 1):
                # Do not treat code blocks or hidden HTML as prose declarations.
                excluded = self.extraction["blocks"] + [
                    r
                    for r in self.extraction["review_items"]
                    if r["reason"] == "html_block_not_extracted"
                ]
                if any(b["start_line"] <= line <= b["end_line"] for b in excluded):
                    continue
                match = re.fullmatch(
                    r"\s*Python\s*(?::|==)\s*(3\.[0-9]+(?:\.[0-9]+)?)\s*", value, re.I
                )
                if match:
                    version = match[1]
                    self.declare_python(
                        "==" + version + (".*" if version.count(".") == 1 else ""),
                        self.evidence("README.md", line),
                    )
        if not self.declarations:
            self.add(
                "python",
                "unknown",
                "No supported explicit Python version declarations were parsed.",
                [],
                "Declare Python support; unrecognized prose may still contain guidance.",
            )
        for value, spec, evidence in self.declarations:
            compatible = spec.contains(Version(self.target), prereleases=False)
            self.add(
                "python",
                "pass" if compatible else "unsupported",
                f"Static target Python {self.target} "
                f"{'satisfies' if compatible else 'is excluded by'} declaration {value}.",
                [evidence],
                "Choose an allowed exact runtime; exclusion does not mean the project is broken.",
            )
        comparisons = 0
        for index, (left, lspec, lev) in enumerate(self.declarations):
            for right, rspec, rev in self.declarations[index + 1 :]:
                comparisons += 1
                if comparisons > 1000:
                    raise IntakeError("Python declaration comparison limit exceeded")
                disjoint = lspec.is_disjoint(rspec)
                self.add(
                    "consistency",
                    "finding" if disjoint else "pass",
                    f"Explicit Python declarations {left} and {right} "
                    f"{'have no overlap' if disjoint else 'overlap'}.",
                    [lev, rev],
                    "Reconcile disjoint declarations; overlap does not prove compatibility.",
                )
        if not comparisons:
            self.add(
                "consistency",
                "unknown",
                "Fewer than two supported Python declarations are available to compare.",
                [],
                "Review documentation and configuration together.",
            )

    @staticmethod
    def requirement_paths(words: list[str]) -> list[str]:
        results = []
        for index, word in enumerate(words):
            if word in {"-r", "-c", "--requirement", "--constraint"}:
                if index + 1 < len(words):
                    results.append(words[index + 1])
            elif word.startswith(("--requirement=", "--constraint=")):
                results.append(word.split("=", 1)[1])
            elif word.startswith(("-r", "-c")) and len(word) > 2:
                results.append(word[2:])
        return results

    def reference(
        self,
        name: str,
        cwd: str | None,
        evidence: dict,
        *,
        directory: bool = False,
        generated: set[str] | None = None,
    ) -> str | None:
        if (
            cwd is None
            or not name
            or re.search(r"[$*?{}\[\]~<>\\]|://", name)
            or name.startswith(("/", "-"))
        ):
            self.add(
                "references",
                "unknown",
                "Reference needs an unknown directory, expansion or external location.",
                [evidence],
                "Resolve the intended location during review; no host path was accessed.",
            )
            return None
        parts: list[str] = []
        for part in (PurePosixPath(cwd) / name).parts:
            if part == "..":
                if not parts:
                    self.add(
                        "references",
                        "review",
                        "Reference escapes the repository snapshot.",
                        [evidence],
                        "Review the external prerequisite; no file outside the snapshot was read.",
                    )
                    return None
                parts.pop()
            elif part != ".":
                parts.append(part)
        path = "/".join(parts) or "."
        present = (
            (path == "." or any(p.startswith(path + "/") for p in self.contents))
            if directory
            else path in self.contents
        )
        generated_hint = path in (generated or set())
        self.add(
            "references",
            "pass" if present else "review" if generated_hint else "finding",
            f"Literal {'directory' if directory else 'input file'} {path!r} is "
            + (
                "present in the snapshot."
                if present
                else "a target of an earlier documented copy, not present in the snapshot."
                if generated_hint
                else "absent from the snapshot."
            ),
            [evidence, self.evidence(path)],
            "Check spelling, working directory and generation before calling this a defect.",
        )
        return path

    def reference_checks(self) -> None:
        cwd: str | None = "."
        generated: set[str] = set()
        handled = 0
        harmless_flags = {
            "shell_prompt_removed_in_candidate",
            "markdown_indentation_removed_in_candidate",
            "phase_context_conflict",
        }
        for instruction in self.extraction["instructions"]:
            evidence = self.evidence(
                "README.md", instruction["start_line"], instruction["end_line"]
            )
            if set(instruction["ambiguity_reasons"]) - harmless_flags:
                cwd = None
                continue
            words = shlex.split(instruction["candidate_text"], comments=True)
            if not words:
                continue
            if words[0] == "cd":
                if len(words) == 2:
                    cwd = self.reference(words[1], cwd, evidence, directory=True)
                    handled += 1
                else:
                    cwd = None
            elif words[:2] == ["git", "clone"] or words[0] in {"source", "."}:
                cwd = None
            elif (
                words[0] in {"pip", "pip3"}
                and words[1:2] == ["install"]
                or (
                    words[0] in {"python", "python3", "python3.12"}
                    and words[1:4] == ["-m", "pip", "install"]
                )
            ):
                for name in self.requirement_paths(
                    words[2:] if words[0] in {"pip", "pip3"} else words[4:]
                ):
                    self.reference(name, cwd, evidence, generated=generated)
                    handled += 1
            elif (
                words[0] in {"python", "python3", "python3.12"}
                and len(words) >= 2
                and words[1].endswith(".py")
            ):
                self.reference(words[1], cwd, evidence, generated=generated)
                handled += 1
            elif words[0] == "cp" and len(words) == 3 and not words[1].startswith("-"):
                source = self.reference(words[1], cwd, evidence)
                if (
                    source in self.contents
                    and cwd is not None
                    and not words[2].startswith(("/", "-"))
                    and ".." not in PurePosixPath(words[2]).parts
                ):
                    generated.add(str(PurePosixPath(cwd) / words[2]))
                handled += 1
        self.add(
            "references",
            "unknown",
            f"Inspected {handled} supported inputs; ambiguous commands and prose paths "
            "were not resolved.",
            [],
            "Review extraction flags, shell state and generated files manually.",
        )

    def environment_checks(self) -> None:
        examples = {}
        if ".env.example" in self.contents:
            text = self.text(".env.example")
            if text is not None:
                for line, value in enumerate(_lines(text), 1):
                    match = re.match(rf"\s*(?:export\s+)?({ENV_NAME})\s*=", value)
                    if match:
                        examples[match[1]] = self.evidence(".env.example", line)
        references: list[tuple[str, dict]] = []
        if "README.md" in self.contents and (readme := self.text("README.md")) is not None:
            for line, value in enumerate(_lines(readme), 1):
                names = set(re.findall(rf"\bexport\s+({ENV_NAME})\s*=|\$\{{({ENV_NAME})\}}", value))
                for pair in sorted(names):
                    references.append((pair[0] or pair[1], self.evidence("README.md", line)))
        scanned = 0
        for file_count, path in enumerate(sorted(p for p in self.contents if p.endswith(".py"))):
            if file_count >= 100:
                self.add(
                    "environment",
                    "unknown",
                    "Source scan stopped at the 100-file budget.",
                    [],
                    "Review remaining Python files manually.",
                )
                break
            data = self.contents[path]
            scanned += len(data)
            if len(data) > 128 * 1024 or scanned > 2 * 1024 * 1024:
                self.add(
                    "environment",
                    "unknown",
                    "Source scan byte budget excluded this file.",
                    [self.evidence(path)],
                    "Review remaining source manually.",
                )
                continue
            try:
                tree = ast.parse(data)
            except (SyntaxError, ValueError, RecursionError):
                self.add(
                    "environment",
                    "unknown",
                    "Source could not be parsed without execution.",
                    [self.evidence(path)],
                    "Review this file and its Python syntax version manually.",
                )
                continue
            for count, node in enumerate(ast.walk(tree)):
                if count >= 50_000:
                    self.add(
                        "environment",
                        "unknown",
                        "Source AST scan reached its node budget.",
                        [self.evidence(path)],
                        "Review remaining source manually.",
                    )
                    break
                key = None
                if isinstance(node, ast.Subscript) and _os_attribute(node.value, "environ"):
                    key = node.slice
                elif (
                    isinstance(node, ast.Call)
                    and node.args
                    and isinstance(node.func, ast.Attribute)
                ):
                    if _os_attribute(node.func, "getenv") or (
                        node.func.attr == "get" and _os_attribute(node.func.value, "environ")
                    ):
                        key = node.args[0]
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and re.fullmatch(ENV_NAME, key.value)
                ):
                    references.append((key.value, self.evidence(path, node.lineno)))
        seen = set()
        for name, evidence in references:
            identity = (name, evidence["path"], evidence["start_line"])
            if identity in seen:
                continue
            seen.add(identity)
            self.add(
                "environment",
                "pass" if name in examples else "review",
                f"Environment name {name} {'has' if name in examples else 'has no'} "
                "matching key in root .env.example.",
                [evidence] + ([examples[name]] if name in examples else []),
                "Confirm requiredness and document a safe example. Values are omitted.",
            )
        self.add(
            "environment",
            "unknown",
            "Variable requiredness and dynamically constructed names are not established.",
            [],
            "Review aliases, defaults and external configuration before diagnosing a defect.",
        )


def _os_attribute(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def check_snapshot(root: Path, *, python_version: str = "3.12.0") -> dict:
    manifest, contents = load_snapshot(root)
    checks = Checks(contents, python_version)
    checks.manifest_checks()
    checks.python_checks()
    checks.reference_checks()
    checks.environment_checks()
    report = {
        "schema_version": 1,
        "tool_version": __version__,
        "kind": "static_report",
        "checker_environment": {
            "python": platform.python_version(),
            "dependencies": {
                name: version(name) for name in ("packaging", "markdown-it-py", "mdurl")
            },
        },
        "repository": {"commit": manifest["commit"], "content_digest": manifest["content_digest"]},
        "target_python": python_version,
        "execution_permitted": False,
        "execution_status": "not_run",
        "summary": dict(sorted(Counter(f["status"] for f in checks.findings).items())),
        "findings": checks.findings,
        "extraction_coverage": {
            "candidates": len(checks.extraction["instructions"]),
            "review_items": len(checks.extraction["review_items"]),
            "readme_present": "README.md" in contents,
        },
        "limitations": list(RULES.values())
        + ["Static passes are not setup runs; no index or build backend was queried."],
    }
    encode_candidates(report)
    return report
