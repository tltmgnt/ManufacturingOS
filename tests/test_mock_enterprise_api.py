"""Exercise a real loopback transport and reject writes/malformed responses."""
from contextlib import contextmanager
import hashlib
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from examples.mock_enterprise_api import EXPORT_PATH, SOURCE_REVISION, fetch_export, mock_server, run_api_rehearsal

RAW = (Path(__file__).resolve().parents[1] / "examples/synthetic-batch-export.csv").read_bytes()


@contextmanager
def response_server(status=200, **changes):
    headers = {"Content-Type": "text/csv", "Content-Length": str(len(RAW)),
               "X-Source-Revision": SOURCE_REVISION, "ETag": '"' + hashlib.sha256(RAW).hexdigest() + '"'}
    headers.update(changes)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_response(status)
            for name, value in headers.items():
                if value is not None:
                    self.send_header(name, value)
            self.end_headers()
            self.wfile.write(RAW)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


class MockEnterpriseAPITests(unittest.TestCase):
    def test_real_get_preserves_bytes_and_records_only_read_request(self):
        with mock_server(RAW) as (port, audit):
            received, provenance = fetch_export(port)
        self.assertEqual(received, RAW)
        self.assertEqual(provenance["sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertFalse(provenance["source_authenticated"])
        self.assertEqual(audit, [{"method": "GET", "path": EXPORT_PATH, "status": 200}])

    def test_write_methods_are_rejected_and_export_is_unchanged(self):
        with mock_server(RAW) as (port, audit):
            for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                connection = HTTPConnection("127.0.0.1", port, timeout=2)
                try:
                    connection.request(method, EXPORT_PATH)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 405)
                    self.assertEqual(response.getheader("Allow"), "GET")
                    response.read()
                finally:
                    connection.close()
            self.assertEqual(fetch_export(port)[0], RAW)
        self.assertEqual(len(audit), 7)
        self.assertTrue(all(row["status"] == 405 for row in audit[:6]))

    def test_unknown_route_is_not_a_source_selector(self):
        with mock_server(RAW) as (port, audit):
            connection = HTTPConnection("127.0.0.1", port, timeout=2)
            try:
                connection.request("GET", EXPORT_PATH + "?source=other")
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
            finally:
                connection.close()

    def test_redirect_and_error_statuses_fail_without_retry(self):
        for status in (301, 302, 401, 403, 429, 500, 503):
            with self.subTest(status=status), response_server(status=status) as port:
                with self.assertRaisesRegex(ValueError, f"HTTP {status}"):
                    fetch_export(port)

    def test_invalid_metadata_and_resource_limits_fail(self):
        cases = [{"Content-Type": "application/json"}, {"Content-Length": None},
                 {"Content-Length": "65537"}, {"Content-Length": "-1"},
                 {"X-Source-Revision": "other"}, {"ETag": '"wrong"'},
                 {"Transfer-Encoding": "chunked"}]
        for values in cases:
            with self.subTest(values=values), response_server(**values) as port:
                with self.assertRaises(ValueError):
                    fetch_export(port)

    def test_synthetic_guard_applies_to_received_response(self):
        with mock_server(RAW.replace(b"synthetic,demo-batch", b"real,demo-batch")) as (port, audit):
            with self.assertRaisesRegex(ValueError, "synthetic"):
                fetch_export(port)

    def test_end_to_end_retains_transport_and_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "api"
            result = run_api_rehearsal(output)
            self.assertEqual(result["intake"]["bundle_status"], "VERIFIED_CONTENT")
            self.assertEqual((output / "source-export.csv").read_bytes(), RAW)
            audit = json.loads((output / "mock-request-audit.json").read_text())
            self.assertEqual([row["method"] for row in audit["requests"]], ["GET"])
            saved = (output / "api-rehearsal-summary.json").read_bytes()
            with patch("examples.mock_enterprise_api.mock_server") as server:
                with self.assertRaises(FileExistsError):
                    run_api_rehearsal(output)
                server.assert_not_called()
            self.assertEqual((output / "api-rehearsal-summary.json").read_bytes(), saved)

    def test_invalid_ports_are_rejected_before_transport(self):
        for port in (0, -1, 65536, True, "80"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                fetch_export(port)
