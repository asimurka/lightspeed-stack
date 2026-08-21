#!/usr/bin/env python3
"""Rename Llama Stack prose to OGX/ogx in docs, docstrings, and comments only.

Casing policy:
- ``OGX`` (uppercase): product name in flowing prose (e.g. "connect to OGX").
- ``ogx`` (lowercase): slug-like references (containers, run.yaml, config files,
  make-target help text, schema field names, remote/separate service roles).
Functional identifiers (``llama_stack``, make target names, package pins,
``ogx stack run``, etc.) are preserved unchanged.
"""

from __future__ import annotations

import ast
import re
import sys
import tokenize
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

SKIP_FILES = {
    "tests/benchmarks/data/python_10000_lines.py",
    "tests/benchmarks/data/json_10000_lines.json",
    "docs/devel_doc/openapi.json",
    "docs/user_doc/config.json",
    "docs/user_doc/config.html",
    "uv.lock",
    "scripts/rename_llama_stack_docs.py",
}

SKIP_FILE_GLOBS = (
    "docs/models/*.json",
    ".konflux/*.lock.yaml",
    "artifacts.lock.yaml",
)

DOC_SUFFIXES = {".md", ".txt", ".rst", ".html", ".puml", ".htm"}
COMMENT_SUFFIXES = {
    ".yaml",
    ".yml",
    ".sh",
    ".toml",
    ".feature",
    ".env",
    ".containerfile",
    ".properties",
    ".ini",
    ".cfg",
    ".service",
    ".svg",
}
COMMENT_FILENAMES = {
    "Makefile",
    "Containerfile",
    "Dockerfile",
    "docker-compose.yaml",
    "docker-compose-library.yaml",
    "lightspeed-stack.yaml",
    "run.yaml",
    "pyproject.toml",
    "pyproject.llamastack.toml",
}
DOC_ROOT_FILES = {
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
}

PRESERVE_PATTERNS = [
    r"https?://[^\s\)\]`\"']+",
    r"\bllama_stack(?:\.[A-Za-z0-9_]+)?\b",
    r"\bLLAMA_STACK(?:_[A-Z0-9_]+)?\b",
    r"\bllama_stack_configuration(?:\.py)?\b",
    r"\bllama-stack-entrypoint(?:\.sh)?\b",
    r"\bllama-stack-config\b",
    r"\bllama-stack-runner\b",
    r"\b(?:build|stop|remove|start|wait-for|clean|run)-llama-stack(?:-[a-z]+)?\b",
    r"\bllama-stack==[\d.]+\b",
    r"\bllama-stack\.readthedocs\.io\b",
    r"\bgithub\.com/llamastack/llama-stack\b",
    r"\bhttp://llama-stack(?::\d+)?\b",
    r"\bpydantic_ai_lightspeed\.llamastack(?:\.[A-Za-z0-9_]+)?\b",
    r"\btests/unit/pydantic_ai_lightspeed/llamastack(?:/[A-Za-z0-9_\.]+)?\b",
    r"\bsrc/pydantic_ai_lightspeed/llamastack(?:/[A-Za-z0-9_\.]+)?\b",
    r"\bllamastack/\b",
    r"\bx-llamastack-provider-data\b",
    r"\bllamastack-faiss\b",
    r"\bllama stack run\b(?!\.yaml)",
    r"\bogx stack run\b",
    r"\bllama stack documentation\b",
    r"\bllamastack supported providers\b",
    r"\bUnifiedLlamaStackConfig\b",
    r"\bLlamaStackConfiguration\b",
    r"\bSAMPLE_LLAMA_STACK_CONFIG\b",
    r"\bto_llama_stack_conversation_id\b",
    r"\bcheck_llama_stack_version\b",
    r"\bbuild_llama_stack_snapshot\b",
    r"\btest_llama_stack\b",
    r"\bllama_stack_utils\b",
    r"\bllama_prow_utils\b",
    r"\bllama_config_utils\b",
    r"\bllama-stack-config-merge\b",
    r"\bcore2llama-stack\b",
    r"\bpyproject\.llamastack\b",
    r"provider name is ['\"]llama-stack['\"]",
    r"['\"]llama-stack['\"]",
    r"`llama_stack(?:\.[A-Za-z0-9_.]+)*`",
    r"\bpath-to-llama-stack-run\.yaml-file\b",
    r"\bllama-stack-run\.yaml\b",
    r"\bllama-stack-service\b",
    r"\blightspeed-llama-stack\b",
    r"\bE2E_LLAMA_HOSTNAME\b",
    r"\bLLAMA_STACK_CONFIG\b",
    r"\bLLAMA_STACK_CONTAINER_NAME\b",
    r"\bLLAMA_STACK_IMAGE\b",
    r"\$\(params\.llama-stack-image\)",
    r"\$\(params\.llamastackimage\)",
]


def _preserve_placeholders(text: str) -> tuple[str, list[str]]:
    """Replace functional references with placeholders before prose substitution."""
    preserved: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        preserved.append(match.group(0))
        return f"__PRESERVE_{len(preserved) - 1}__"

    pattern = "|".join(f"(?:{item})" for item in PRESERVE_PATTERNS)
    return re.sub(pattern, _replace, text, flags=re.IGNORECASE), preserved


def _restore_placeholders(text: str, preserved: list[str]) -> str:
    """Restore placeholders created by `_preserve_placeholders`."""
    for index, original in enumerate(preserved):
        text = text.replace(f"__PRESERVE_{index}__", original)
    return text


def rename_prose(text: str) -> str:
    """Apply OGX prose substitutions while preserving functional references."""
    protected, preserved = _preserve_placeholders(text)

    replacements = [
        (r"\bllama-stack\b", "ogx"),
        (r"\bllamastack\b", "ogx"),
        (r"\bLlama-Stack\b", "OGX"),
        (r"\bLlama Stack\b", "OGX"),
        (r"\bllama stack\b", "OGX"),
        (r"\bLlamaStack\b", "OGX"),
        (r"\bLLAMA_STACK\b", "OGX"),
    ]
    for pattern, replacement in replacements:
        protected = re.sub(pattern, replacement, protected, flags=re.IGNORECASE)

    restored = _restore_placeholders(protected, preserved)
    return normalize_ogx_casing(restored)


def normalize_ogx_casing(text: str) -> str:
    """Use lowercase ``ogx`` for slug-like references; keep ``OGX`` for product prose."""
    keepers: list[str] = []

    def _keep(match: re.Match[str]) -> str:
        keepers.append(match.group(0))
        return f"__OGXKEEP_{len(keepers) - 1}__"

    for pattern in (
        r'backend_name="OGX"',
        r"backend_name='OGX'",
        r'backend_name: "OGX"',
        r'ServiceUnavailableResponse\(backend_name="OGX"',
    ):
        text = re.sub(pattern, _keep, text)

    lowercase_replacements = [
        (r"\bBuild OGX\b", "Build ogx"),
        (r"\bStopping OGX\b", "Stopping ogx"),
        (r"\bStarting OGX\b", "Starting ogx"),
        (r"\bRemoving OGX\b", "Removing ogx"),
        (r"\bRemove OGX\b", "Remove ogx"),
        (r"\bExpose OGX\b", "Expose ogx"),
        (r"\bWait for OGX\b", "Wait for ogx"),
        (r"\bRestart the OGX\b", "Restart the ogx"),
        (r"\bremote OGX provider\b", "remote ogx provider"),
        (r"\bremote OGX\b", "remote ogx"),
        (r"\bseparate OGX to\b", "separate ogx to"),
        (r"\ba separate OGX\b", "a separate ogx"),
        (r"\bseparate OGX\b", "separate ogx"),
        (r"\bembedded OGX\b", "embedded ogx"),
        (r"\brebuilding OGX\b", "rebuilding ogx"),
        (r"\bQuay pull secret for OGX images\b", "Quay pull secret for ogx images"),
        (r"\bOGX run\.yaml\b", "ogx run.yaml"),
        (r"\bOGX run configs\b", "ogx run configs"),
        (r"\bOGX run-from-source\b", "ogx run-from-source"),
        (r"\bOGX config merge\b", "ogx config merge"),
        (r"\bOGX configuration enrichment\b", "ogx configuration enrichment"),
        (r"\bOGX configuration snapshot\b", "ogx configuration snapshot"),
        (r"\bOGX configuration dict\b", "ogx configuration dict"),
        (r"\bOGX configuration path\b", "ogx configuration path"),
        (r"\bOGX configuration file\b", "ogx configuration file"),
        (r"\bOGX configuration\b", "ogx configuration"),
        (r"\bOGX config\b", "ogx config"),
        (r"\bEffective OGX config\b", "Effective ogx config"),
        (r"\benriched OGX config\b", "enriched ogx config"),
        (r"\bsynthesized OGX config\b", "synthesized ogx config"),
        (r"\bparsed OGX configuration\b", "parsed ogx configuration"),
        (r"\bmasked OGX configuration\b", "masked ogx configuration"),
        (r"\bReading OGX configuration\b", "Reading ogx configuration"),
        (r"\bWriting OGX configuration\b", "Writing ogx configuration"),
        (r"\bWrote synthesized OGX configuration\b", "Wrote synthesized ogx configuration"),
        (r"\bEnriching OGX config\b", "Enriching ogx config"),
        (r"\bFailed to read ogx config\b", "Failed to read ogx config"),
        (r"\bWrote enriched ogx config\b", "Wrote enriched ogx config"),
        (r"\boriginal OGX config\b", "original ogx config"),
        (r"\bOGX container startup\b", "ogx container startup"),
        (r"\bOGX container lifecycle\b", "ogx container lifecycle"),
        (r"\bOGX container HEALTHCHECK\b", "ogx container HEALTHCHECK"),
        (r"\bOGX container image\b", "ogx container image"),
        (r"\bOGX container\b", "ogx container"),
        (r"\bOGX containers\b", "ogx containers"),
        (r"\bOGX image builds\b", "ogx image builds"),
        (r"\bOGX image\b", "ogx image"),
        (r"\bOGX images\b", "ogx images"),
        (r"\bOGX distribution\b", "ogx distribution"),
        (r"\bOGX distro\b", "ogx distro"),
        (r"\bOGX entrypoint\b", "ogx entrypoint"),
        (r"\bOGX lifecycle\b", "ogx lifecycle"),
        (r"\bOGX migration\b", "ogx migration"),
        (r"\bOGX pod\b", "ogx pod"),
        (r"\bOGX server\b", "ogx server"),
        (r"\bOGX service mode\b", "ogx service mode"),
        (r"\bOGX schema\b", "ogx schema"),
        (r"\bOGX shields\b", "ogx shields"),
        (r"\bOGX-specific\b", "ogx-specific"),
        (r"\bOGX provider_type\b", "ogx provider_type"),
        (r"\bOGX provider_id\b", "ogx provider_id"),
        (r"\bOGX vector_io\b", "ogx vector_io"),
        (r"\bOGX provider blocks\b", "ogx provider blocks"),
        (r"\bOGX provider entries\b", "ogx provider entries"),
        (r"\binto OGX provider entries\b", "into ogx provider entries"),
        (r"\bOGX list API\b", "OGX list API"),
        (r"\bOGX list\b", "OGX list"),
        (r"\bOGX on (\d+)\b", r"ogx on \1"),
        (r"\brun OGX manually\b", "run ogx manually"),
        (r"\bOGX manually\b", "ogx manually"),
        (r"\bOGX requires authentication\b", "ogx requires authentication"),
        (r"\bOGX ~/.llama\b", "ogx ~/.llama"),
        (r"\binto the OGX pod\b", "into the ogx pod"),
        (r"\binto OGX pod\b", "into ogx pod"),
        (r"\bOGX pod\b", "ogx pod"),
        (r"\bOGX diagnostics\b", "ogx diagnostics"),
        (r"\bOGX connection\b", "ogx connection"),
        (r"\bOGX disrupt\b", "ogx disrupt"),
        (r"\bNo separate OGX service\b", "No separate ogx service"),
        (r"\bUnified OGX configuration\b", "Unified ogx configuration"),
        (r"\bOGX URL\b", "ogx URL"),
        (r"\bTitle: OGX configuration\b", "Title: ogx configuration"),
        (r"\bOGX configuration\]\(#OGX-configuration\b", "ogx configuration](#ogx-configuration"),
        (r"\]\(#OGX-configuration\b", "](#ogx-configuration"),
        (r"#### OGX configuration\b", "#### ogx configuration"),
        (r"\*\*OGX configuration\*\*", "**ogx configuration**"),
        (r"\bTools configured in the OGX run\.yaml\b", "Tools configured in the ogx run.yaml"),
        (r"\bwhere LCORE synthesizes the OGX run\.yaml\b", "where LCORE synthesizes the ogx run.yaml"),
        (r"\bpath where the synthesized OGX run\.yaml\b", "path where the synthesized ogx run.yaml"),
        (r"\bpath to the legacy OGX run\.yaml\b", "path to the legacy ogx run.yaml"),
        (r"\bCannot synthesize OGX config\b", "Cannot synthesize ogx config"),
        (r"\baugment the OGX configuration\b", "augment the ogx configuration"),
        (r"\bProvider ID must match the provider_id in your OGX config\b", "Provider ID must match the provider_id in your ogx config"),
        (r"\bFeature design: OGX config merge\b", "Feature design: ogx config merge"),
        (r"\bAt OGX container startup\b", "At ogx container startup"),
        (r"\bValidation pre-flight against the OGX schema\b", "Validation pre-flight against the ogx schema"),
        (r"\bEscape hatch — raw OGX schema\b", "Escape hatch — raw ogx schema"),
        (r"\bRaw OGX schema\b", "Raw ogx schema"),
        (r"\bused for vector_stores\.default_\* in the synthesized OGX config\b", "used for vector_stores.default_* in the synthesized ogx config"),
        (r"\bDefault OGX baseline\b", "Default ogx baseline"),
        (r"\bStart OGX with\b", "Start ogx with"),
        (r"\bFramework OGX\b", "Framework ogx"),
        (r"\bStart OGX \(run-ci\.yaml\)\b", "Start ogx (run-ci.yaml)"),
    ]
    for pattern, replacement in lowercase_replacements:
        text = re.sub(pattern, replacement, text)

    grammar_replacements = [
        (r"\bto a ogx\b", "to an ogx"),
        (r"\bto a OGX\b", "to an OGX"),
        (r"\bTo a ogx\b", "To an ogx"),
        (r"\bTo a OGX\b", "To an OGX"),
        (r"\ba ogx\b", "an ogx"),
        (r"\bA ogx\b", "An ogx"),
        (r"\ba OGX\b", "an OGX"),
        (r"\bA OGX\b", "An OGX"),
        (r"\ban OGX message\b", "an OGX message"),
    ]
    for pattern, replacement in grammar_replacements:
        text = re.sub(pattern, replacement, text)

    for index, original in enumerate(keepers):
        text = text.replace(f"__OGXKEEP_{index}__", original)
    return text


def _split_markdown_code(text: str) -> list[tuple[str, bool]]:
    """Split markdown into prose and fenced-code segments."""
    segments: list[tuple[str, bool]] = []
    fence_pattern = re.compile(r"(```[\s\S]*?```|`[^`\n]+`)")
    last = 0
    for match in fence_pattern.finditer(text):
        if match.start() > last:
            segments.append((text[last : match.start()], False))
        segments.append((match.group(0), True))
        last = match.end()
    if last < len(text):
        segments.append((text[last:], False))
    if not segments:
        segments.append((text, False))
    return segments


def rename_markdown(text: str) -> str:
    """Rename prose in markdown, preserving functional identifiers via placeholders."""
    return rename_prose(text)


def _encode_string_constant(value: str, original_segment: str) -> str:
    """Rebuild a string literal, preserving multiline concatenation layout."""
    stripped = original_segment.lstrip()
    if stripped.startswith(('"""', "'''")) or stripped.startswith(('r"""', "r'''")):
        raw_prefix = "r" if stripped.startswith("r") else ""
        if stripped.startswith('r"""') or stripped.startswith('"""'):
            quote = '"""'
        else:
            quote = "'''"
        prefix = original_segment[: len(original_segment) - len(stripped)]
        return f"{prefix}{raw_prefix}{quote}{value}{quote}"

    if "\n" in original_segment:
        lines = original_segment.splitlines()
        quote_lines = [
            index
            for index, line in enumerate(lines)
            if line.strip().startswith(('"', "'"))
        ]
        if len(quote_lines) > 1:
            words = value.split()
            chunk_count = len(quote_lines)
            chunk_size = max(1, (len(words) + chunk_count - 1) // chunk_count)
            chunks = [
                " ".join(words[index : index + chunk_size])
                for index in range(0, len(words), chunk_size)
            ]
            while len(chunks) < chunk_count:
                chunks.append("")
            chunks = chunks[:chunk_count]

            chunk_index = 0
            rebuilt_lines: list[str] = []
            for line in lines:
                stripped = line.strip()
                if not stripped.startswith(('"', "'")):
                    rebuilt_lines.append(line)
                    continue
                quote = stripped[0]
                trailing_space = " " if chunk_index < chunk_count - 1 else ""
                indent = line[: len(line) - len(line.lstrip())]
                rebuilt_lines.append(
                    f"{indent}{quote}{chunks[chunk_index]}{trailing_space}{quote}"
                )
                chunk_index += 1
            return "\n".join(rebuilt_lines)

    if original_segment.startswith(("'''", '"""')):
        quote = original_segment[:3]
        return f"{quote}{value}{quote}"

    quote = '"' if original_segment.startswith('"') else "'"
    if "\n" in value:
        return f'"""{value}"""'
    return f"{quote}{value}{quote}"


def _encode_docstring(value: str, original_segment: str) -> str:
    """Rebuild a docstring literal preserving the original quote style."""
    return _encode_string_constant(value, original_segment)


def _iter_docstring_nodes(
    tree: ast.Module,
) -> list[tuple[ast.AST, ast.Constant]]:
    """Collect AST nodes whose first statement is a docstring."""
    nodes: list[tuple[ast.AST, ast.Constant]] = []

    def maybe_add(node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first = body[0]
        if not isinstance(first, ast.Expr):
            return
        if not isinstance(first.value, ast.Constant):
            return
        if not isinstance(first.value.value, str):
            return
        nodes.append((first, first.value))

    maybe_add(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            maybe_add(node)
    return nodes


def _node_source_span(source: str, node: ast.AST) -> tuple[int, int]:
    """Return start/end character offsets for an AST node in *source*."""
    lines = source.splitlines(keepends=True)
    start = sum(len(lines[index]) for index in range(node.lineno - 1)) + node.col_offset
    end = sum(len(lines[index]) for index in range(node.end_lineno - 1)) + node.end_col_offset
    return start, end


def _rename_python_docstrings(source: str) -> str:
    """Rename prose inside module/class/function docstrings only."""
    tree = ast.parse(source)
    replacements: list[tuple[int, int, str]] = []

    for expr_node, constant in _iter_docstring_nodes(tree):
        segment = ast.get_source_segment(source, expr_node)
        if not segment:
            continue
        updated_value = rename_prose(constant.value)
        if updated_value == constant.value:
            continue
        start, end = _node_source_span(source, expr_node)
        replacements.append(
            (start, end, _encode_docstring(updated_value, segment))
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg not in {"description", "title", "summary"}:
                continue
            if not isinstance(keyword.value, ast.Constant):
                continue
            if not isinstance(keyword.value.value, str):
                continue
            segment = ast.get_source_segment(source, keyword.value)
            if not segment:
                continue
            updated_value = rename_prose(keyword.value.value)
            if updated_value == keyword.value.value:
                continue
            start, end = _node_source_span(source, keyword.value)
            replacements.append(
                (start, end, _encode_docstring(updated_value, segment))
            )

    replacements.sort(key=lambda item: item[0], reverse=True)
    updated = source
    for start, end, new_segment in replacements:
        updated = updated[:start] + new_segment + updated[end:]
    return updated


def _rename_python_comments(source: str) -> str:
    """Rename prose inside Python comments only."""
    tokens = list(tokenize.tokenize(BytesIO(source.encode("utf-8")).readline))
    updated_tokens: list[tokenize.TokenInfo] = []

    for token in tokens:
        if token.type == tokenize.COMMENT:
            prefix, _, body = token.string.partition("#")
            updated = f"{prefix}#{rename_prose(body)}"
            token = tokenize.TokenInfo(
                token.type, updated, token.start, token.end, token.line
            )
        updated_tokens.append(token)

    result = tokenize.untokenize(updated_tokens)
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return result


def _rename_python_source(source: str) -> str:
    """Rename prose in Python docstrings and comments."""
    updated = _rename_python_docstrings(source)
    return _rename_python_comments(updated)


def _rename_hash_comment_line(line: str) -> str:
    """Rename prose in the `#` comment portion of a single line."""
    if line.startswith("#!"):
        return line

    in_single = False
    in_double = False
    escape = False
    for index, char in enumerate(line):
        if escape:
            escape = False
            continue
        if char == "\\" and in_double:
            escape = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            prefix = line[:index]
            comment = line[index + 1 :]
            return f"{prefix}#{rename_prose(comment)}"
    return line


def _rename_puml_comment_line(line: str) -> str:
    """Rename prose in PlantUML single-quote comment lines."""
    stripped = line.lstrip()
    if not stripped.startswith("'"):
        return line
    indent = line[: len(line) - len(stripped)]
    return f"{indent}{rename_prose(stripped)}"


def _rename_html_comments(text: str) -> str:
    """Rename prose inside HTML/XML comment blocks."""

    def _replace(match: re.Match[str]) -> str:
        body = match.group(1)
        return f"<!--{rename_prose(body)}-->"

    return re.sub(r"<!--([\s\S]*?)-->", _replace, text)


def _rename_hash_comment_file(text: str) -> str:
    """Rename `#` comments line-by-line."""
    lines = text.splitlines(keepends=True)
    updated: list[str] = []
    for line in lines:
        newline = ""
        if line.endswith("\r\n"):
            newline = "\r\n"
            core = line[:-2]
        elif line.endswith("\n"):
            newline = "\n"
            core = line[:-1]
        else:
            core = line
        updated.append(_rename_hash_comment_line(core) + newline)
    return "".join(updated)


def _rename_puml_file(text: str) -> str:
    """Rename `#`-style and `'` comment lines in PlantUML sources."""
    lines = text.splitlines(keepends=True)
    updated: list[str] = []
    for line in lines:
        newline = ""
        if line.endswith("\r\n"):
            newline = "\r\n"
            core = line[:-2]
        elif line.endswith("\n"):
            newline = "\n"
            core = line[:-1]
        else:
            core = line
        if core.lstrip().startswith("'"):
            core = _rename_puml_comment_line(core)
        else:
            core = _rename_hash_comment_line(core)
        updated.append(core + newline)
    return "".join(updated)


def _is_skipped(path: Path) -> bool:
    """Return True when a path should be excluded from processing."""
    rel = path.relative_to(ROOT).as_posix()
    if rel in SKIP_FILES:
        return True
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    for pattern in SKIP_FILE_GLOBS:
        if path.match(pattern):
            return True
    return False


def _should_process(path: Path) -> bool:
    """Return True when a path should be processed by this script."""
    if _is_skipped(path):
        return False
    if path.name in DOC_ROOT_FILES or path.name in COMMENT_FILENAMES:
        return True
    if path.suffix in DOC_SUFFIXES | COMMENT_SUFFIXES:
        return True
    if path.suffix == ".py":
        return True
    if path.name.endswith(".containerfile"):
        return True
    return False


def _process_file(path: Path, source: str) -> str | None:
    """Return updated file contents, or None when the file should be skipped."""
    updated: str | None
    if path.suffix == ".py":
        try:
            updated = _rename_python_source(source)
        except (SyntaxError, tokenize.TokenError) as exc:
            print(f"SKIP {path}: {exc}", file=sys.stderr)
            return None
    elif path.suffix in {".md", ".txt", ".rst", ".html", ".htm"}:
        updated = rename_markdown(source)
        if path.suffix in {".html", ".htm"}:
            updated = _rename_html_comments(updated)
    elif path.suffix == ".puml":
        updated = _rename_puml_file(source)
    elif path.suffix in COMMENT_SUFFIXES or path.name in COMMENT_FILENAMES:
        if path.suffix == ".svg":
            updated = _rename_html_comments(source)
        else:
            updated = _rename_hash_comment_file(source)
    else:
        return None

    return normalize_ogx_casing(updated)


def iter_target_files() -> list[Path]:
    """Collect files eligible for non-functional rename."""
    targets: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if _should_process(path):
            targets.append(path)
    return sorted(targets)


def main() -> int:
    """Run prose rename across eligible files."""
    changed: list[str] = []
    for path in iter_target_files():
        original = path.read_text(encoding="utf-8")
        updated = _process_file(path, original)
        if updated is None or updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        changed.append(path.relative_to(ROOT).as_posix())

    print(f"Updated {len(changed)} files")
    for item in changed:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
