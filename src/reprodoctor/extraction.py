"""Deterministic command candidates, never a shell interpreter or execution plan."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path

from markdown_it import MarkdownIt

from . import __version__
from .intake import IntakeError, Limits
from .snapshot import load_snapshot

SHELL_LANGUAGES = {"sh", "bash", "shell"}
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024
PHASE_WORDS = {
    "installation": r"\b(install(?:ation)?|setup|getting started|dependencies)\b",
    "configuration": r"\b(configur(?:ation|e)|environment|settings)\b",
    "test": r"\b(tests?|testing)\b",
    "launch": r"\b(run|running|launch|usage|start)\b",
}


def _lines(text: str) -> list[str]:
    # Match Markdown's CR/LF line boundaries, not Python's broader Unicode splitlines.
    return [line for line in re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text) if line]


def _phase(text: str) -> str:
    matches = [key for key, pattern in PHASE_WORDS.items() if re.search(pattern, text, re.I)]
    return matches[0] if len(matches) == 1 else "unknown"


def _command_phase(text: str) -> str:
    try:
        words = shlex.split(text, comments=True)
    except ValueError:
        return "unknown"
    if not words:
        return "unknown"
    executable = words[0]
    python = executable in {"python", "python3", "python3.12"}
    if (
        (executable in {"pip", "pip3"} and "install" in words[1:2])
        or (python and words[1:4] == ["-m", "pip", "install"])
        or (python and words[1:3] == ["-m", "venv"])
        or words[:2] == ["git", "clone"]
    ):
        return "installation"
    if executable in {"pytest", "tox", "unittest"} or (
        python and words[1:3] in [["-m", "pytest"], ["-m", "unittest"]]
    ):
        return "test"
    if executable in {"export", "cd", "source", ".", "cp"} or re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*=.*", executable, re.S
    ):
        return "configuration"
    return "launch" if python else "unknown"


def _reasons(text: str) -> list[str]:
    reasons = []
    if re.search(r"<[^>\n]+>|\{\{.+?\}\}|\b(?:YOUR_[A-Z_]+|TODO|CHANGEME)\b", text):
        reasons.append("placeholder")
    if re.search(r"\$\(|`|[;&|<>]|\\\s*$|[\r\n]", text):
        reasons.append("unsupported_shell_syntax")
    if "$" in text or re.search(r"[*?\[\]{}~]", text):
        reasons.append("shell_expansion_needs_review")
    if re.match(r"\s*(sudo|curl|wget|docker|ssh|source)\b|\s*\.\s", text):
        reasons.append("unsupported_command")
    try:
        shlex.split(text, comments=True)
    except ValueError:
        reasons.append("unbalanced_shell_quotes")
    return reasons


def encode_candidates(report: dict, *, maximum_bytes: int = MAXIMUM_JSON_BYTES) -> str:
    chunks = []
    size = 0
    for chunk in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(report):
        size += len(chunk)  # ensure_ascii makes character count equal the UTF-8 byte count.
        if size + 1 > maximum_bytes:
            raise IntakeError("Extraction JSON exceeds the output byte limit; no partial result")
        chunks.append(chunk)
    return "".join(chunks) + "\n"


def extract_readme(data: bytes, *, maximum_candidates: int = 2000) -> dict:
    if len(data) > Limits().file_bytes:
        raise IntakeError("README exceeds the parsing byte limit")
    if maximum_candidates < 1:
        raise ValueError("Candidate limit must be positive")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise IntakeError("README must be UTF-8") from exc
    if "\0" in text:
        raise IntakeError("README contains NUL bytes")
    # Keep raw physical lines: Markdown normalizes CRLF and container indentation.
    lines = _lines(text)
    parser_text = text.removeprefix("\ufeff")
    # Parse HTML boundaries so hidden comment/script contents do not become commands.
    # Never render HTML or interpret any markup as instructions to this program.
    tokens = MarkdownIt("commonmark", {"html": True}).parse(parser_text)
    headings: list[dict] = []
    context = ""
    instructions = []
    blocks = []
    review_items = []
    instruction_bytes = 0
    for index, token in enumerate(tokens):
        if token.type == "html_block":
            review_items.append(
                {
                    "reason": "html_block_not_extracted",
                    "path": "README.md",
                    "start_line": token.map[0] + 1,
                    "end_line": token.map[1],
                }
            )
            context = ""
        if token.type == "heading_open":
            level = int(token.tag[1:])
            title = tokens[index + 1].content
            headings = [h for h in headings if h["level"] < level]
            headings.append({"level": level, "text": title, "line": token.map[0] + 1})
            context = ""
        if token.type == "paragraph_open":
            context = tokens[index + 1].content
            if re.search(r"\b(run|install|execute|configure|launch|test)\b", context, re.I):
                review_items.append(
                    {
                        "reason": "prose_instruction_not_extracted",
                        "path": "README.md",
                        "start_line": token.map[0] + 1,
                        "end_line": token.map[1],
                        "raw_text": "".join(lines[token.map[0] : token.map[1]]),
                    }
                )
        if token.type not in {"fence", "code_block"}:
            continue
        start, end = token.map
        info = token.info.strip()
        language = info.split()[0].lower() if info else ""
        included = token.type == "fence" and language in SHELL_LANGUAGES | {""}
        blocks.append(
            {
                "id": f"block-{len(blocks) + 1:04d}",
                "path": "README.md",
                "start_line": start + 1,
                "end_line": end,
                "language": language,
                "included": included,
                "raw_text": "".join(lines[start:end]),
                "omission_reason": None if included else "unsupported_language_or_indented_block",
            }
        )
        if not included:
            review_items.append(
                {
                    "reason": "code_block_not_extracted",
                    "block_id": blocks[-1]["id"],
                    "path": "README.md",
                    "start_line": start + 1,
                    "end_line": end,
                }
            )
            context = ""
            continue
        closed = bool(
            end > start + 1
            and re.fullmatch(
                rf"[ \t>]*{re.escape(token.markup[0])}{{{len(token.markup)},}}[ \t]*",
                lines[end - 1].rstrip("\r\n"),
            )
        )
        body_end = end - 1 if closed else end
        body = lines[start + 1 : body_end]
        normalized_lines = _lines(token.content)
        common_reasons = []
        if not language:
            common_reasons.append("untagged_block")
        if info != language:
            common_reasons.append("nonstandard_fence_info")
        if not closed:
            common_reasons.append("unclosed_fence")
        if re.search(
            r"\b(or|alternatively|either|option|instead)\b",
            context + " " + " ".join(h["text"] for h in headings),
            re.I,
        ):
            common_reasons.append("alternative_instructions")
        if token.level:
            common_reasons.append("nested_markdown")
        # Retain whole multiline constructs; never guess their boundaries or split them.
        multiline = bool(
            re.search(
                r"\\[ \t]*\r?\n|<<|(?m:^\s*(?:if|for|while|case|function|do|then)\b)",
                token.content,
            )
        )
        multiline = multiline or any(
            set(_reasons(line.rstrip("\r\n")))
            & {
                "unsupported_shell_syntax",
                "unbalanced_shell_quotes",
            }
            or re.match(r"\s*(?:[(){}]|(?:else|elif|fi|done|esac)\b)", line)
            for line in normalized_lines
        )
        grouped = multiline or bool(token.level) or len(body) != len(normalized_lines)
        if grouped:
            common_reasons.append("compound_block_needs_review")
            chunks = [(start + 2, body_end, "".join(body), token.content.rstrip("\n"))]
        else:
            chunks = [
                (start + 2 + n, start + 2 + n, raw, normalized.rstrip("\r\n"))
                for n, (raw, normalized) in enumerate(zip(body, normalized_lines, strict=True))
            ]
        for first, last, raw, command in chunks:
            root_prompt = bool(
                re.match(r"\s*#\s+(?:pip3?|python3?|pytest|sudo|git|export|cd)\b", command)
            )
            if not command.strip() or (
                not grouped and command.lstrip().startswith("#") and not root_prompt
            ):
                continue
            reasons = common_reasons.copy()
            if not grouped and raw.rstrip("\r\n") != command:
                reasons.append("markdown_indentation_removed_in_candidate")
            if root_prompt:
                reasons.append("comment_or_root_shell_prompt")
            prompt = re.match(r"^(\s*)\$ (.*)$", command)
            if prompt:
                command = prompt[2]
                reasons.append("shell_prompt_removed_in_candidate")
            elif re.match(r"\s*(?:>>>|\.\.\.|# |\w+@[^ ]+[#$] )", command):
                reasons.append("ambiguous_prompt_or_transcript")
            reasons.extend(_reasons(command))
            command_phase = _command_phase(command)
            heading_phase = next(
                (p for h in reversed(headings) if (p := _phase(h["text"])) != "unknown"),
                "unknown",
            )
            if command_phase == "unknown":
                reasons.append("unrecognized_command")
            if command_phase != "unknown" and heading_phase not in {command_phase, "unknown"}:
                reasons.append("phase_context_conflict")
            instructions.append(
                {
                    "id": f"instruction-{len(instructions) + 1:04d}",
                    "order": len(instructions) + 1,
                    "block_id": blocks[-1]["id"],
                    "path": "README.md",
                    "start_line": first,
                    "end_line": last,
                    "raw_text": raw,
                    "candidate_text": command,
                    "phase": command_phase if command_phase != "unknown" else heading_phase,
                    "command_phase": command_phase,
                    "heading_phase": heading_phase,
                    "heading_context": list(headings),
                    "classification": "command_candidate"
                    if command_phase != "unknown"
                    else "ambiguous_candidate",
                    "ambiguity_reasons": list(dict.fromkeys(reasons)),
                    "requires_review": True,
                }
            )
            # Bound repeated heading context before serialization can amplify input.
            instruction_bytes += len(json.dumps(instructions[-1], ensure_ascii=True))
            if instruction_bytes > MAXIMUM_JSON_BYTES:
                raise IntakeError("Extraction exceeds its evidence byte limit; no partial result")
            if len(instructions) > maximum_candidates:
                raise IntakeError("README exceeds the command-candidate limit; no partial result")
        context = ""
    result = {
        "schema_version": 1,
        "tool_version": __version__,
        "kind": "instruction_candidates",
        "readme": {
            "path": "README.md",
            "sha256": hashlib.sha256(data).hexdigest(),
            "status": "present",
        },
        "instructions": instructions,
        "blocks": blocks,
        "review_items": review_items,
        "execution_permitted": False,
        "limitations": [
            "Only root README.md sh/bash/shell and untagged fenced blocks are candidates.",
            "Command and phase detection are heuristics, not shell parsing or safety judgments.",
            "All candidates require human review, including those with no ambiguity flags.",
            "Prose, inline code, HTML, other languages and indented blocks are not commands.",
            "Alternatives, placeholders, transcripts and shell state are not resolved.",
        ],
    }
    encode_candidates(result)
    return result


def extract_snapshot(root: Path) -> dict:
    manifest, contents = load_snapshot(root)
    if "README.md" in contents:
        result = extract_readme(contents["README.md"])
    else:
        result = extract_readme(b"")
        result["readme"] = {"path": "README.md", "sha256": None, "status": "missing"}
        result["review_items"].append({"reason": "root_readme_missing", "path": "README.md"})
    result["repository"] = {
        "commit": manifest["commit"],
        "content_digest": manifest["content_digest"],
    }
    return result
