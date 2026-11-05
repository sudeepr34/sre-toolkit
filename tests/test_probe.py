import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sre_toolkit.probe import ProbeResult, probe_url, to_markdown


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ok":
            self._send(200, b"ok")
        elif self.path == "/fail":
            self._send(500, b"error")
        else:
            self._send(404, b"not found")

    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_ok_result_has_no_failures():
    result = ProbeResult(url="http://x", status_code=200, latency_ms=10)
    assert result.status == "ok"
    assert result.failures() == []


def test_wrong_status_is_failure():
    result = ProbeResult(url="http://x", status_code=500, latency_ms=10)
    assert result.status == "fail"
    assert result.failures() == ["status 500, expected 200"]


def test_slow_is_failure():
    result = ProbeResult(url="http://x", status_code=200, latency_ms=1500)
    assert result.status == "fail"
    assert "latency 1500ms over max 1000ms" in result.failures()[0]


def test_unreachable_is_failure():
    result = ProbeResult(url="http://x", status_code=0, latency_ms=5, error="boom")
    assert result.status == "fail"
    assert result.failures() == ["unreachable (boom)"]


def test_probe_ok_endpoint(server):
    result = probe_url(f"{server}/ok")
    assert result.status_code == 200
    assert result.status == "ok"


def test_probe_failing_endpoint(server):
    result = probe_url(f"{server}/fail")
    assert result.status_code == 500
    assert result.status == "fail"


def test_probe_missing_endpoint(server):
    result = probe_url(f"{server}/nope", expected_status=200)
    assert result.status_code == 404
    assert "status 404, expected 200" in result.failures()


def test_probe_unreachable():
    result = probe_url("http://127.0.0.1:1/", timeout=1)
    assert result.status_code == 0
    assert result.status == "fail"


def test_markdown_lists_failures():
    results = [
        ProbeResult(url="http://a", status_code=200, latency_ms=10),
        ProbeResult(url="http://b", status_code=500, latency_ms=10),
    ]
    md = to_markdown(results)
    assert "# Endpoint probes" in md
    assert "Probed 2 endpoints: 1 fail, 1 ok" in md
    assert "| http://b | 500 | 10ms | status 500, expected 200 |" in md
    assert "## Failures" in md


def test_markdown_all_healthy():
    md = to_markdown([ProbeResult(url="http://a", status_code=200, latency_ms=10)])
    assert "All endpoints healthy." in md
