#!/usr/bin/env python3
"""Render per-pipeline HTML pages for A.6.2.8 screenshot capture."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


PIPELINES = [
    (
        "01-app-access-logs",
        "Application / access logs",
        "01-app-access-logs.txt",
        "Timestamped LCORE application and HTTP access log lines for the labeled inference request.",
    ),
    (
        "02-prometheus-metrics",
        "Prometheus /metrics",
        "02-prometheus-metrics.txt",
        "Prometheus text exposition after the inference request (counters, latency, token metrics).",
    ),
    (
        "03-splunk-events",
        "Splunk HEC telemetry",
        "03-splunk-events.jsonl",
        "HEC events received for the inference (sourcetype, model, request_id, timestamps).",
    ),
    (
        "04-sentry-events",
        "Sentry error tracking",
        "04-sentry-events.jsonl",
        "Sentry envelope items received by the local intake (or disabled-pipeline note).",
    ),
    (
        "05-otel-spans",
        "OpenTelemetry traces",
        "05-otel-spans.jsonl",
        "OTLP payloads exported for the inference request.",
    ),
    (
        "06-transcript",
        "Conversation transcripts",
        "06-transcript.json",
        "On-disk transcript JSON with query/response metadata and identifiers.",
    ),
]


PAGE_CSS = """
body { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
       background: #0f1419; color: #e7ecf1; margin: 0; padding: 24px; }
header { border-bottom: 1px solid #2a3440; margin-bottom: 16px; padding-bottom: 12px; }
h1 { font-size: 18px; margin: 0 0 6px; color: #f0f3f6; }
.meta { color: #9aa7b5; font-size: 12px; line-height: 1.5; }
.badge { display: inline-block; background: #1f6feb; color: white; padding: 2px 8px;
         border-radius: 4px; font-size: 11px; margin-right: 8px; }
pre { white-space: pre-wrap; word-break: break-word; background: #161b22; border: 1px solid #30363d;
      border-radius: 8px; padding: 16px; font-size: 12px; line-height: 1.45; max-height: 720px;
      overflow: auto; }
"""


def _strip_leading_comment_headers(text: str) -> str:
    """Remove leading ``#`` comment / blank header lines from an artifact body."""
    cleaned: list[str] = []
    skipping_header = True
    for line in text.splitlines():
        if skipping_header and (not line.strip() or line.lstrip().startswith("#")):
            continue
        skipping_header = False
        cleaned.append(line)
    return "\n".join(cleaned) if cleaned else text


def _load(path: Path) -> str:
    """Load file contents or a placeholder note."""
    if not path.exists():
        return f"(missing artifact: {path.name})\nPipeline may be disabled or not yet flushed."
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return f"(empty artifact: {path.name})\nNo events captured for this pipeline."
    # Prefer pretty JSON when possible
    if path.suffix in {".json", ".jsonl"}:
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.dumps(json.loads(line), indent=2))
            except json.JSONDecodeError:
                lines.append(line)
        if lines:
            return "\n\n".join(lines)
    # Keep metrics readable but not enormous
    if path.name.endswith("metrics.txt"):
        keep = []
        for line in text.splitlines():
            if line.startswith("#") or any(
                key in line
                for key in (
                    "ls_rest_api",
                    "ls_llm",
                    "ls_provider",
                    "http_request",
                    "process_",
                    "python_info",
                )
            ):
                keep.append(line)
        if keep:
            return "\n".join(keep[:200])
    return _strip_leading_comment_headers(text)[:20000]


def render_page(
    out_path: Path,
    title: str,
    description: str,
    body: str,
    timestamp: str,
    label: str,
) -> None:
    """Write one HTML evidence page."""
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)} — LCORE A.6.2.8</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
  <header>
    <h1><span class="badge">ISO/IEC 42001 A.6.2.8</span>{html.escape(title)}</h1>
    <div class="meta">
      Lightspeed Core Stack — in-system event log evidence<br/>
      Captured (UTC): {html.escape(timestamp)}<br/>
      Test request label: {html.escape(label)}<br/>
      {html.escape(description)}
    </div>
  </header>
  <pre>{html.escape(body)}</pre>
</body>
</html>
"""
    out_path.write_text(content, encoding="utf-8")


def main() -> None:
    """Render HTML pages for each pipeline artifact."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--html-dir", type=Path, required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    args.html_dir.mkdir(parents=True, exist_ok=True)
    for slug, title, filename, description in PIPELINES:
        body = _load(args.raw_dir / filename)
        # Fallbacks for receiver dumps that use different names
        if body.startswith("(missing") or body.startswith("(empty"):
            alt = {
                "03-splunk-events.jsonl": "splunk-events.jsonl",
                "04-sentry-events.jsonl": "sentry-events.jsonl",
                "05-otel-spans.jsonl": "otel-spans.jsonl",
            }.get(filename)
            if alt:
                body = _load(args.raw_dir / alt)
        render_page(
            args.html_dir / f"{slug}.html",
            title,
            description,
            body,
            args.timestamp,
            args.label,
        )
    print(f"Rendered HTML under {args.html_dir}")


if __name__ == "__main__":
    main()
