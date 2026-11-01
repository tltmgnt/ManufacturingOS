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
from zipfile import ZipFile
from unittest.mock import patch

from examples.mock_enterprise_api import EXPORT_PATH, SOURCE_REVISION, fetch_export, mock_server, run_api_rehearsal

TOKEN = "r" * 43
DENIED_TOKEN = "d" * 43

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
        with mock_server(RAW, read_token=TOKEN) as (port, audit):
            received, provenance = fetch_export(port, TOKEN)
        self.assertEqual(received, RAW)
        self.assertEqual(provenance["sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertFalse(provenance["source_authenticated"])
        self.assertEqual(audit, [{"method": "GET", "path": EXPORT_PATH, "status": 200}])

    def test_write_methods_are_rejected_and_export_is_unchanged(self):
        with mock_server(RAW, read_token=TOKEN) as (port, audit):
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
            self.assertEqual(fetch_export(port, TOKEN)[0], RAW)
        self.assertEqual(len(audit), 7)
        self.assertTrue(all(row["status"] == 405 for row in audit[:6]))

    def test_unknown_route_is_not_a_source_selector(self):
        with mock_server(RAW, read_token=TOKEN) as (port, audit):
            connection = HTTPConnection("127.0.0.1", port, timeout=2)
            try:
                connection.request("GET", EXPORT_PATH + "?source=other", headers={"Authorization": "Bearer " + TOKEN})
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
            finally:
                connection.close()

    def test_redirect_and_error_statuses_fail_without_retry(self):
        for status in (301, 302, 401, 403, 429, 500, 503):
            with self.subTest(status=status), response_server(status=status) as port:
                with self.assertRaisesRegex(ValueError, f"HTTP {status}"):
                    fetch_export(port, TOKEN)

    def test_invalid_metadata_and_resource_limits_fail(self):
        cases = [{"Content-Type": "application/json"}, {"Content-Length": None},
                 {"Content-Length": "65537"}, {"Content-Length": "-1"},
                 {"X-Source-Revision": "other"}, {"ETag": '"wrong"'},
                 {"Transfer-Encoding": "chunked"}]
        for values in cases:
            with self.subTest(values=values), response_server(**values) as port:
                with self.assertRaises(ValueError):
                    fetch_export(port, TOKEN)

    def test_synthetic_guard_applies_to_received_response(self):
        with mock_server(RAW.replace(b"synthetic,demo-batch", b"real,demo-batch"), read_token=TOKEN) as (port, audit):
            with self.assertRaisesRegex(ValueError, "synthetic"):
                fetch_export(port, TOKEN)

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
                fetch_export(port, TOKEN)


    def test_missing_invalid_and_insufficient_scope_credentials_are_denied(self):
        with mock_server(RAW, read_token=TOKEN, denied_token=DENIED_TOKEN) as (port, audit):
            for value, status in [(None, 401), ("Bearer " + "x" * 43, 401),
                                  ("Bearer " + DENIED_TOKEN, 403), ("bearer " + TOKEN, 200)]:
                connection = HTTPConnection("127.0.0.1", port, timeout=2)
                try:
                    headers = {} if value is None else {"Authorization": value}
                    connection.request("GET", EXPORT_PATH, headers=headers)
                    response = connection.getresponse()
                    self.assertEqual(response.status, status)
                    if status == 401:
                        self.assertEqual(response.getheader("WWW-Authenticate"), "Bearer")
                    response.read()
                finally:
                    connection.close()
        self.assertEqual([row["status"] for row in audit], [401, 401, 403, 200])
        self.assertNotIn(TOKEN, json.dumps(audit))
        self.assertNotIn(DENIED_TOKEN, json.dumps(audit))

    def test_duplicate_authorization_headers_are_rejected(self):
        with mock_server(RAW, read_token=TOKEN) as (port, audit):
            connection = HTTPConnection("127.0.0.1", port, timeout=2)
            try:
                connection.putrequest("GET", EXPORT_PATH)
                connection.putheader("Authorization", "Bearer " + TOKEN)
                connection.putheader("Authorization", "Bearer " + TOKEN)
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 401)
                response.read()
            finally:
                connection.close()

    def test_previous_run_token_is_not_valid_for_another_server(self):
        with mock_server(RAW, read_token="n" * 43) as (port, audit):
            with self.assertRaisesRegex(ValueError, "HTTP 401"):
                fetch_export(port, TOKEN)

    def test_invalid_client_token_is_rejected_before_transport(self):
        with patch("examples.mock_enterprise_api.HTTPConnection") as connection:
            for token in (None, "short", "x" * 129, "x" * 40 + "\r\nX:evil"):
                with self.subTest(token=token), self.assertRaises(ValueError):
                    fetch_export(12345, token)
            connection.assert_not_called()

    def test_ephemeral_token_is_absent_from_all_retained_files_and_bundles(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "api"
            with patch("examples.mock_enterprise_api.secrets.token_urlsafe", return_value=TOKEN):
                result = run_api_rehearsal(output)
            self.assertEqual(result["transport"]["required_scope"], "exports:read")
            for path in output.rglob("*"):
                if path.is_file():
                    self.assertNotIn(TOKEN.encode(), path.read_bytes(), str(path))
                    if path.suffix == ".zip":
                        with ZipFile(path) as archive:
                            for name in archive.namelist():
                                self.assertNotIn(TOKEN.encode(), archive.read(name), name)


    def test_invalid_timeouts_are_rejected_before_transport(self):
        with patch("examples.mock_enterprise_api.HTTPConnection") as connection:
            for timeout in (0, -1, 3.1, float("nan"), float("inf"), True, "1"):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    fetch_export(12345, TOKEN, timeout=timeout)
            connection.assert_not_called()

    def test_partial_response_is_not_parsed_as_a_source_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "truncated"
            with patch("examples.mock_enterprise_api.parse_export") as parser:
                with self.assertRaisesRegex(ValueError, "byte count"):
                    run_api_rehearsal(output, failure="truncated")
                parser.assert_not_called()
            self.assertFalse(output.exists())
