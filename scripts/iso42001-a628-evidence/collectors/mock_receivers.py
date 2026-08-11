#!/usr/bin/env python3
"""Local mock receivers for A.6.2.8 audit evidence collection.

Serves:
  * Splunk HEC on :8090  (/services/collector)
  * OTLP HTTP on :4318   (/v1/traces, /v1/metrics, /v1/logs)
  * Sentry-compatible envelope intake on :9090 (/api/<project>/envelope/)

Events are appended as JSON lines under the output directory for later
screenshot packaging.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()


class EvidenceStore:
    """Append-only JSONL store for mock receiver payloads."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize store directories under ``output_dir``."""
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.paths = {
            "splunk": self.output_dir / "splunk-events.jsonl",
            "otel": self.output_dir / "otel-spans.jsonl",
            "sentry": self.output_dir / "sentry-events.jsonl",
        }
        for path in self.paths.values():
            path.touch(exist_ok=True)

    def append(self, kind: str, record: dict[str, Any]) -> None:
        """Append one JSON record for the given pipeline kind."""
        payload = {"received_at": _now(), **record}
        with self.paths[kind].open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
        print(f"[{_now()}] {kind}: stored event", flush=True)


STORE: EvidenceStore | None = None


class MultiplexHandler(BaseHTTPRequestHandler):
    """HTTP handler that routes Splunk HEC, OTLP, and Sentry intake."""

    server_version = "LCORE-A628-MockReceivers/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        """Log request lines with timestamps."""
        print(f"[{_now()}] {self.address_string()} - {format % args}", flush=True)

    def _read_body(self) -> bytes:
        """Read the raw request body."""
        length = int(self.headers.get("Content-Length", "0") or "0")
        return self.rfile.read(length) if length else b""

    def _json_response(self, code: int, body: dict[str, Any]) -> None:
        """Write a JSON response."""
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        """Health / readiness for the multiplex receivers."""
        path = urlparse(self.path).path
        if path in ("/", "/health", "/healthz"):
            self._json_response(
                200,
                {
                    "status": "ok",
                    "service": "lcore-a628-mock-receivers",
                    "timestamp": _now(),
                },
            )
            return
        self._json_response(404, {"error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        """Accept Splunk HEC, OTLP, or Sentry envelope POSTs."""
        assert STORE is not None
        path = urlparse(self.path).path
        body = self._read_body()
        auth = self.headers.get("Authorization", "")

        if path.startswith("/services/collector"):
            text = body.decode("utf-8", errors="replace").strip()
            events: list[Any] = []
            if text:
                # HEC may send one JSON object or NDJSON
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        events.append({"raw": line})
            STORE.append(
                "splunk",
                {
                    "path": path,
                    "authorization_present": bool(auth),
                    "events": events,
                },
            )
            self._json_response(200, {"text": "Success", "code": 0})
            return

        if path.startswith("/v1/traces") or path.startswith("/v1/metrics") or path.startswith(
            "/v1/logs"
        ):
            content_type = self.headers.get("Content-Type", "")
            record: dict[str, Any] = {
                "path": path,
                "content_type": content_type,
                "bytes": len(body),
            }
            if "json" in content_type:
                try:
                    record["payload"] = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    record["payload_raw"] = body[:2000].decode("utf-8", errors="replace")
            else:
                # protobuf or other binary — keep a short hex prefix for evidence
                record["payload_hex_prefix"] = body[:64].hex()
                record["note"] = "OTLP protobuf accepted (body not decoded)"
            STORE.append("otel", record)
            self.send_response(200)
            self.end_headers()
            return

        if "/envelope/" in path or path.startswith("/api/"):
            # Sentry envelope: header JSON line + optional items
            text = body.decode("utf-8", errors="replace")
            lines = [line for line in text.splitlines() if line.strip()]
            parsed: list[Any] = []
            for line in lines[:20]:
                try:
                    parsed.append(json.loads(line))
                except json.JSONDecodeError:
                    parsed.append({"raw": line[:500]})
            STORE.append(
                "sentry",
                {
                    "path": path,
                    "bytes": len(body),
                    "envelope_items": parsed,
                },
            )
            self.send_response(200)
            self.end_headers()
            return

        self._json_response(404, {"error": "not found", "path": path})


def _serve(host: str, port: int) -> None:
    """Run one ThreadingHTTPServer forever."""
    httpd = ThreadingHTTPServer((host, port), MultiplexHandler)
    print(f"[{_now()}] listening on http://{host}:{port}", flush=True)
    httpd.serve_forever()


def main() -> int:
    """Start one or more mock receiver ports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output" / "raw",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--ports",
        default="8090,4318,9090",
        help="Comma-separated ports: Splunk HEC, OTLP HTTP, Sentry",
    )
    args = parser.parse_args()

    global STORE  # noqa: PLW0603
    STORE = EvidenceStore(args.output_dir)

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    if len(ports) == 1:
        _serve(args.host, ports[0])
        return 0

    # Multiplex: same handler on each port (path-based routing)
    import threading

    threads = [
        threading.Thread(target=_serve, args=(args.host, port), daemon=True)
        for port in ports
    ]
    for thread in threads:
        thread.start()
    print(
        f"[{_now()}] mock receivers up on ports {ports} → {args.output_dir}",
        flush=True,
    )
    for thread in threads:
        thread.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
