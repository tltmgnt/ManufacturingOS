"""Local read-only mock ERP/MES export rehearsal; no real enterprise connection."""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading

from .synthetic_export_intake import parse_export, run_intake_bytes
from .temporary_use_case import encode

EXPORT_PATH = "/v1/batches/demo-batch-001/export"
SOURCE_REVISION = "synthetic-export-1"
MAX_EXPORT_BYTES = 65536


def validate_token(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise ValueError("Mock token must contain 32–128 URL-safe characters")


def handler_for(raw: bytes, audit: list, read_token: str, denied_token: str | None = None, fault: str | None = None):
    """Immutable fixture responses; write methods never touch a source."""
    if fault not in (None, "throttled", "unavailable", "stale_revision", "hash_mismatch"):
        raise ValueError("Unknown synthetic server fault")
    validate_token(read_token)
    if denied_token is not None:
        validate_token(denied_token)
        if hmac.compare_digest(read_token, denied_token):
            raise ValueError("Read and denied-scope tokens must be distinct")
    class Handler(BaseHTTPRequestHandler):
        server_version = "SyntheticERP/1"
        sys_version = ""

        def log_message(self, *args):
            pass

        def respond(self, status, body, content_type="application/json"):
            audit.append({"method": self.command, "path": self.path, "status": status})
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if status == 401:
                self.send_header("WWW-Authenticate", "Bearer")
            if status == 429:
                self.send_header("Retry-After", "1")
            if status == 405:
                self.send_header("Allow", "GET")
            if status == 200 and self.path == EXPORT_PATH:
                self.send_header("X-Source-Revision", "stale-fixture" if fault == "stale_revision" else SOURCE_REVISION)
                self.send_header("ETag", '"' + ("0" * 64 if fault == "hash_mismatch" else hashlib.sha256(raw).hexdigest()) + '"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def authorize_read(self):
            headers = self.headers.get_all("Authorization", [])
            if len(headers) != 1 or headers[0][:7].lower() != "bearer ":
                self.respond(401, b'{"error":"mock read credential required"}\n')
                return False
            supplied = headers[0][len("Bearer "):]
            if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", supplied):
                self.respond(401, b'{"error":"invalid mock credential"}\n')
                return False
            if hmac.compare_digest(supplied, read_token):
                return True
            if denied_token is not None and hmac.compare_digest(supplied, denied_token):
                self.respond(403, b'{"error":"mock credential lacks exports:read scope"}\n')
            else:
                self.respond(401, b'{"error":"invalid mock credential"}\n')
            return False

        def do_GET(self):
            if not self.authorize_read():
                return
            if self.path == EXPORT_PATH:
                if fault in ("throttled", "unavailable"):
                    self.respond(429 if fault == "throttled" else 503, b'{"error":"synthetic service fault"}\n')
                else:
                    self.respond(200, raw, "text/csv; charset=utf-8")
            else:
                self.respond(404, b'{"error":"unknown mock endpoint"}\n')

        def deny_write(self):
            self.respond(405, b'{"error":"read-only mock: GET only"}\n')

        do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = deny_write
    return Handler


@contextmanager
def mock_server(raw: bytes, *, read_token: str, denied_token: str | None = None, fault: str | None = None):
    audit = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(raw, audit, read_token, denied_token, fault))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], audit
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def fetch_export(port: int, token: str) -> tuple[bytes, dict]:
    # Host/path are fixed; only an ephemeral mock token is accepted, never a real credential.
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Mock API port must be an integer from 1 to 65535")
    validate_token(token)
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request("GET", EXPORT_PATH, headers={"Accept": "text/csv", "Authorization": "Bearer " + token})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Mock export failed with HTTP {response.status}; no redirect or retry performed")
        if response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "text/csv":
            raise ValueError("Mock response must declare text/csv")
        if response.getheader("Transfer-Encoding") is not None:
            raise ValueError("Mock response must use a fixed Content-Length, not transfer encoding")
        length = response.getheader("Content-Length", "")
        if not re.fullmatch(r"[0-9]{1,6}", length) or int(length) > MAX_EXPORT_BYTES:
            raise ValueError("Mock response has missing/invalid/excessive Content-Length")
        if response.getheader("X-Source-Revision") != SOURCE_REVISION:
            raise ValueError("Mock source revision differs from the pinned fixture revision")
        raw = response.read(MAX_EXPORT_BYTES + 1)
        if len(raw) != int(length) or len(raw) > MAX_EXPORT_BYTES:
            raise ValueError("Mock response byte count differs from the declared length")
        content_hash = hashlib.sha256(raw).hexdigest()
        if response.getheader("ETag") != '"' + content_hash + '"':
            raise ValueError("Mock response ETag does not match received bytes")
        parse_export(raw)
        return raw, {"scope": "LOCAL_MOCK_ERP_MES_API", "host": "127.0.0.1", "method": "GET",
                     "path": EXPORT_PATH, "status": 200, "source_revision": SOURCE_REVISION,
                     "received_bytes": len(raw), "sha256": content_hash,
                     "source_authenticated": False, "live_integration_complete": False,
                     "access_control": "EPHEMERAL_MOCK_BEARER", "required_scope": "exports:read",
                     "production_authorized": False,
                     "limitations": ["Loopback HTTP and an ephemeral mock token only; no TLS, real identity or enterprise authorization review.",
                                     "Pinned revision and ETag check supplied-source consistency, not origin authenticity."]}
    finally:
        connection.close()


class MockAPIRejected(ValueError):
    """A rejected source response with a credential-free request audit."""
    def __init__(self, message, audit):
        super().__init__(message)
        self.audit = [dict(row) for row in audit]


def run_api_rehearsal(output: Path, *, failure: str | None = None) -> dict:
    # Reject previous runs before starting a server or making a request.
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output path already exists")
    if failure not in (None, "invalid_credential", "insufficient_scope", "throttled", "unavailable", "stale_revision", "hash_mismatch"):
        raise ValueError("Unknown synthetic API failure")
    raw_fixture = (Path(__file__).resolve().parent / "synthetic-batch-export.csv").read_bytes()
    read_token = secrets.token_urlsafe(32)
    denied_token = ("y" if read_token[0] == "x" else "x") + read_token[1:]
    supplied_token = denied_token if failure in ("invalid_credential", "insufficient_scope") else read_token
    server_fault = failure if failure in ("throttled", "unavailable", "stale_revision", "hash_mismatch") else None
    with mock_server(raw_fixture, read_token=read_token,
                     denied_token=denied_token if failure == "insufficient_scope" else None,
                     fault=server_fault) as (port, audit):
        try:
            received, transport = fetch_export(port, supplied_token)
        except ValueError as exc:
            raise MockAPIRejected(str(exc), audit) from exc
    result = run_intake_bytes(received, output)
    if result["raw_sha256"] != transport["sha256"]:
        raise RuntimeError("Transport and retained intake bytes differ")
    (output / "transport-provenance.json").write_bytes(encode(transport))
    (output / "mock-request-audit.json").write_bytes(encode({"scope": "LOCAL_MOCK_REQUESTS", "requests": audit}))
    summary = {"scope": "MOCK_API_REHEARSAL", "status": "PASS", "intake": result,
               "transport": transport, "request_count": len(audit), "live_integration_complete": False,
               "empirical_calibration_complete": False, "production_authorized": False}
    (output / "api-rehearsal-summary.json").write_bytes(encode(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New rehearsal directory")
    args = parser.parse_args()
    try:
        result = run_api_rehearsal(args.output)
    except Exception as exc:
        parser.exit(2, f"Mock API rehearsal error: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
