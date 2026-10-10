"""The tus upload against real local listeners: no redirect is followed, and every request
after creation goes to the configured Galaxy whatever host its Location names."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import Mock, patch

import pytest
from tusclient.client import TusClient

from galaxy_mcp.tus_upload import (
    UPLOAD_ROUTE,
    GalaxyTusUploader,
    TusRefusedError,
    redirect_target,
    upload_path_in,
    upload_via_tus,
)

from .test_helpers import galaxy_state, upload_file_fn

KEY = "secret-key"
PAYLOAD = b"ACGT\n" * 10


class FakeServer:
    """A tus server that records every request and answers from per-method overrides."""

    def __init__(self, host: str = "127.0.0.1") -> None:
        self.hits: list[tuple[str, str, dict[str, str]]] = []
        self.responses: dict[str, tuple[int, dict[str, str]]] = {}
        self.received = b""
        self.location: str | None = None
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def _answer(self, method: str) -> None:
                server.hits.append((method, self.path, dict(self.headers)))
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                if method in server.responses:
                    status, headers = server.responses[method]
                elif method == "POST":
                    status = 201
                    headers = {"Location": server.location or f"{UPLOAD_ROUTE}/abc123"}
                elif method == "PATCH":
                    server.received += body
                    status, headers = 204, {"Upload-Offset": str(len(server.received))}
                else:
                    status, headers = 200, {"Upload-Offset": str(len(server.received))}
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Tus-Resumable", "1.0.0")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self) -> None:
                self._answer("POST")

            def do_PATCH(self) -> None:
                self._answer("PATCH")

            def do_HEAD(self) -> None:
                self._answer("HEAD")

            def do_GET(self) -> None:
                self._answer("GET")

        self.httpd = ThreadingHTTPServer((host, 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, args=(0.01,), daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def methods(self) -> list[str]:
        return [method for method, _, _ in self.hits]


@pytest.fixture
def galaxy() -> Iterator[FakeServer]:
    server = FakeServer()
    yield server
    server.close()


@pytest.fixture
def target() -> Iterator[FakeServer]:
    """Where a redirect or a foreign Location points. It must never be dialled."""
    server = FakeServer()
    yield server
    server.close()


@pytest.fixture
def upload(tmp_path: Any) -> str:
    path = tmp_path / "reads.fasta"
    path.write_bytes(PAYLOAD)
    return str(path)


def base(server: FakeServer, host: str = "localhost") -> str:
    return f"http://{host}:{server.port}"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_on_creation_is_refused_once(galaxy, target, upload, status):
    galaxy.responses["POST"] = (status, {"Location": f"{base(target)}/elsewhere"})

    with pytest.raises(TusRefusedError) as caught:
        upload_via_tus(base(galaxy), KEY, upload)

    assert str(caught.value) == (
        f"Galaxy answered {status} and redirects are not followed; "
        f"Galaxy redirected to {base(target)}/elsewhere -- check GALAXY_URL"
    )
    assert galaxy.methods() == ["POST"]
    assert target.hits == []


def test_redirect_on_patch_is_final_even_with_retries(galaxy, target, upload):
    galaxy.responses["PATCH"] = (307, {"Location": f"{base(target)}{UPLOAD_ROUTE}/abc123"})
    client = TusClient(f"{base(galaxy)}{UPLOAD_ROUTE}", headers={"x-api-key": KEY})
    uploader = GalaxyTusUploader(
        file_path=upload, client=client, retries=3, retry_delay=0, galaxy_url=base(galaxy)
    )

    with pytest.raises(TusRefusedError, match="Galaxy answered 307 and redirects are not followed"):
        uploader.upload()

    assert galaxy.methods() == ["POST", "PATCH"]
    assert target.hits == []


def test_304_is_not_a_redirect(galaxy, upload):
    galaxy.responses["PATCH"] = (304, {})
    with pytest.raises(Exception) as caught:
        upload_via_tus(base(galaxy), KEY, upload)
    assert not isinstance(caught.value, TusRefusedError)


def test_off_host_location_is_rerooted(galaxy, target, upload):
    galaxy.location = f"{base(target)}{UPLOAD_ROUTE}/abc123"

    session_id = upload_via_tus(base(galaxy), KEY, upload)

    assert session_id == "abc123"
    assert galaxy.methods() == ["POST", "PATCH"]
    assert galaxy.hits[1][1] == f"{UPLOAD_ROUTE}/abc123"
    assert galaxy.hits[1][2]["x-api-key"] == KEY
    assert galaxy.received == PAYLOAD
    assert target.hits == []


def test_other_scheme_is_rerooted(galaxy, upload):
    galaxy.location = f"https://galaxy.example.org{UPLOAD_ROUTE}/abc123"
    assert upload_via_tus(base(galaxy), KEY, upload) == "abc123"
    assert galaxy.methods() == ["POST", "PATCH"]


def test_query_kept_and_fragment_dropped(galaxy, upload):
    galaxy.location = f"http://proxy.internal{UPLOAD_ROUTE}/abc123?part=1#frag"

    assert upload_via_tus(base(galaxy), KEY, upload) == "abc123"
    assert galaxy.hits[1][1] == f"{UPLOAD_ROUTE}/abc123?part=1"


def test_galaxy_under_a_path_prefix(galaxy, upload):
    galaxy.location = f"http://elsewhere/galaxy{UPLOAD_ROUTE}/abc123"
    assert upload_via_tus(f"{base(galaxy)}/galaxy", KEY, upload) == "abc123"
    assert [p for _, p, _ in galaxy.hits] == [
        f"/galaxy{UPLOAD_ROUTE}",
        f"/galaxy{UPLOAD_ROUTE}/abc123",
    ]


@pytest.mark.parametrize(
    "location",
    [
        f"{UPLOAD_ROUTE}/../../admin",
        f"{UPLOAD_ROUTE}/%2e%2e/admin",
        f"{UPLOAD_ROUTE}/..%2fadmin",
        f"{UPLOAD_ROUTE}//abc123",
        f"{UPLOAD_ROUTE}/abc\\..\\admin",
        f"{UPLOAD_ROUTE}/abc123/extra",
        f"{UPLOAD_ROUTE}/",
        f"{UPLOAD_ROUTE}/abc.123",
        "/api/other/abc123",
        f"http://evil.example{UPLOAD_ROUTE}/../x",
        f"//evil.example\\@good{UPLOAD_ROUTE}/abc123",
    ],
)
def test_bad_location_is_refused_once(galaxy, upload, location):
    galaxy.location = location

    with pytest.raises(TusRefusedError, match="is not its resumable-upload route"):
        upload_via_tus(base(galaxy), KEY, upload)

    assert galaxy.methods() == ["POST"]


def test_resume_head_is_rerooted(galaxy, target, upload):
    client = TusClient(f"{base(galaxy)}{UPLOAD_ROUTE}", headers={"x-api-key": KEY})
    GalaxyTusUploader(
        file_path=upload,
        client=client,
        url=f"{base(target)}{UPLOAD_ROUTE}/abc123",
        galaxy_url=base(galaxy),
    )
    assert galaxy.methods() == ["HEAD"]
    assert galaxy.hits[0][1] == f"{UPLOAD_ROUTE}/abc123"
    assert target.hits == []


def test_resume_head_redirect_is_refused(galaxy, target, upload):
    galaxy.responses["HEAD"] = (307, {"Location": f"{base(target)}/x"})
    client = TusClient(f"{base(galaxy)}{UPLOAD_ROUTE}", headers={"x-api-key": KEY})
    with pytest.raises(TusRefusedError, match="Galaxy answered 307"):
        GalaxyTusUploader(
            file_path=upload,
            client=client,
            url=f"{base(galaxy)}{UPLOAD_ROUTE}/abc123",
            galaxy_url=base(galaxy),
        )
    assert galaxy.methods() == ["HEAD"]
    assert target.hits == []


def test_resume_bad_url_is_refused_before_any_request(galaxy, upload):
    client = TusClient(f"{base(galaxy)}{UPLOAD_ROUTE}", headers={"x-api-key": KEY})
    with pytest.raises(TusRefusedError):
        GalaxyTusUploader(
            file_path=upload,
            client=client,
            url=f"{base(galaxy)}{UPLOAD_ROUTE}/../admin",
            galaxy_url=base(galaxy),
        )
    assert galaxy.hits == []


def test_retry_head_redirect_is_refused(galaxy, target, upload):
    galaxy.responses["PATCH"] = (500, {})
    galaxy.responses["HEAD"] = (302, {"Location": f"{base(target)}/x"})
    client = TusClient(f"{base(galaxy)}{UPLOAD_ROUTE}", headers={"x-api-key": KEY})
    uploader = GalaxyTusUploader(
        file_path=upload, client=client, retries=2, retry_delay=0, galaxy_url=base(galaxy)
    )
    with pytest.raises(TusRefusedError, match="Galaxy answered 302"):
        uploader.upload()
    assert galaxy.methods() == ["POST", "PATCH", "HEAD"]
    assert target.hits == []


def test_redirect_target_is_stripped_and_capped():
    assert (
        redirect_target("https://u:p@h.example/a/b?sig=x#f", "http://g/") == "https://h.example/a/b"
    )
    assert redirect_target("/rel?q=1", "http://g:8080/api/x") == "http://g:8080/rel"
    long = redirect_target("https://h.example/" + "a" * 300, "http://g/")
    assert len(long) == 203
    assert long.endswith("...")


def test_upload_path_in_keeps_query_drops_fragment():
    prefix = f"{UPLOAD_ROUTE}/"
    assert upload_path_in(f"http://x{UPLOAD_ROUTE}/id_1-a?q=1#f", prefix) == (
        f"{UPLOAD_ROUTE}/id_1-a?q=1"
    )
    assert upload_path_in(f"{UPLOAD_ROUTE}/id", prefix) == f"{UPLOAD_ROUTE}/id"


def _gi_for(server: FakeServer) -> Mock:
    gi = Mock()
    gi.base_url = base(server)
    gi.key = KEY
    gi.config.get_version.return_value = {"version_major": "26.1"}
    gi.tools.post_to_fetch.return_value = {"outputs": [{"id": "d1"}]}
    return gi


def test_upload_file_reports_redirect_in_its_own_wording(galaxy, target, upload):
    galaxy.responses["POST"] = (
        301,
        {"Location": f"https://user:pw@{target.httpd.server_address[0]}:{target.port}/x?k=1"},
    )
    with patch.dict(galaxy_state, {"connected": True, "gi": _gi_for(galaxy)}):
        with pytest.raises(ValueError) as caught:
            upload_file_fn(upload, "h1")
    assert str(caught.value) == (
        "Failed to upload file: Galaxy answered 301 and redirects are not followed; "
        f"Galaxy redirected to https://127.0.0.1:{target.port}/x -- check GALAXY_URL"
    )
    assert target.hits == []


@pytest.mark.parametrize(
    ("status", "hint"),
    [
        (401, "Authentication failed - check your API key"),
        (403, "Permission denied - check your account permissions"),
    ],
)
def test_upload_file_auth_failure(galaxy, upload, status, hint):
    galaxy.responses["POST"] = (status, {})
    with patch.dict(galaxy_state, {"connected": True, "gi": _gi_for(galaxy)}):
        with pytest.raises(ValueError) as caught:
            upload_file_fn(upload, "h1")
    assert str(caught.value) == (
        f"Failed to upload file: Attempt to retrieve create file url with status {status} ({hint})"
    )
    assert galaxy.methods() == ["POST"]


def test_upload_file_succeeds_through_reroot(galaxy, target, upload):
    galaxy.location = f"{base(target)}{UPLOAD_ROUTE}/sess42"
    gi = _gi_for(galaxy)
    with patch.dict(galaxy_state, {"connected": True, "gi": gi}):
        result = upload_file_fn(upload, "h1")
    assert result.success is True
    gi.tools.post_to_fetch.assert_called_once_with(upload, "h1", "sess42")
    assert galaxy.received == PAYLOAD
    assert target.hits == []
