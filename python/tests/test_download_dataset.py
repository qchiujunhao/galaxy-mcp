"""download_dataset fetches /display directly and never treats a redirect as content."""

import os
import stat
from unittest.mock import Mock, patch

import pytest
import responses
from responses import matchers

from galaxy_mcp import http_security, server

from .test_helpers import connect_fn, download_dataset_fn, galaxy_state

GALAXY = "https://approved.example/galaxy"
DATASET = "d" * 16
SHOW = f"{GALAXY}/api/datasets/{DATASET}"
DISPLAY = f"{GALAXY}/api/datasets/{DATASET}/display"
DOWNLOAD = f"{GALAXY}/api/histories/h1/contents/{DATASET}/download"
CONTENT = b"chr1\t100\t200\nchr2\t300\t400\n"


@pytest.fixture
def galaxy(monkeypatch):
    monkeypatch.setattr(server, "normalized_galaxy_url", f"{GALAXY}/")
    monkeypatch.setattr(server, "extra_allowed_galaxy_urls", ())
    monkeypatch.setattr(server, "auth_provider", None)
    monkeypatch.setattr(server, "_get_current_session_id", lambda: "download-test")
    # Pin connect to the configured URL the way an HTTP caller sees it.
    monkeypatch.setattr(server, "remote_caller_possible", lambda: True)
    monkeypatch.setenv(http_security.ALLOW_LOCAL_FILES_ENV, "1")
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        mock.get(f"{GALAXY}/api/users/current", json={"id": "user-1"})
        mock.get(
            SHOW,
            json={
                "id": DATASET,
                "name": "regions",
                "state": "ok",
                "extension": "bed",
                "file_ext": "bed",
                "download_url": f"/api/histories/h1/contents/{DATASET}/download",
            },
        )
        # Galaxy 26.2+'s download_url: a 302 to /display, which the tool must not go near.
        mock.get(DOWNLOAD, status=302, headers={"Location": f"{DISPLAY}?to_ext=bed"})
        assert connect_fn(api_key="secret-key").success
        yield mock
    server._session_connections.pop("download-test", None)


def _serves_display(mock, **kwargs):
    mock.get(DISPLAY, match=[matchers.query_param_matcher({"to_ext": "bed"})], **kwargs)


def test_in_memory_reads_display(galaxy):
    _serves_display(galaxy, body=CONTENT)
    result = download_dataset_fn(DATASET)
    assert result.success
    assert result.data["content_available"]
    assert result.data["file_size"] == len(CONTENT)
    display = [c for c in galaxy.calls if c.request.url.startswith(DISPLAY)]
    assert len(display) == 1
    assert display[0].request.headers["x-api-key"] == "secret-key"


def test_file_path_streams_display(galaxy, tmp_path):
    _serves_display(galaxy, body=CONTENT)
    target = tmp_path / "out.bed"
    result = download_dataset_fn(DATASET, file_path=str(target))
    assert result.success
    assert target.read_bytes() == CONTENT
    assert result.data["file_size"] == len(CONTENT)


def test_download_route_is_never_used(galaxy):
    _serves_display(galaxy, body=CONTENT)
    download_dataset_fn(DATASET)
    assert not [c for c in galaxy.calls if "/download" in c.request.url]
    assert len([c for c in galaxy.calls if c.request.url.startswith(DISPLAY)]) == 1


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("to_file", [False, True])
def test_redirect_is_an_error_and_not_followed(galaxy, tmp_path, status, to_file):
    location = "https://attacker.example/steal"
    _serves_display(galaxy, status=status, headers={"Location": location})
    galaxy.get(location, body=b"should never be fetched")
    target = tmp_path / "out.bed"
    with pytest.raises(ValueError, match=f"HTTP {status} \\(redirects are not followed\\)"):
        download_dataset_fn(DATASET, file_path=str(target) if to_file else None)
    assert not target.exists()
    assert all(c.request.url.startswith(f"{GALAXY}/") for c in galaxy.calls)


@pytest.mark.parametrize("status", [204, 403, 500])
def test_other_non_200_is_an_error(galaxy, tmp_path, status):
    _serves_display(galaxy, status=status, body=b"")
    target = tmp_path / "out.bed"
    with pytest.raises(ValueError, match=f"HTTP {status}"):
        download_dataset_fn(DATASET, file_path=str(target))
    assert not target.exists()


def test_missing_dataset_reads_as_not_found(galaxy):
    _serves_display(galaxy, status=404)
    with pytest.raises(ValueError, match="not found"):
        download_dataset_fn(DATASET)


@pytest.mark.parametrize("header", ["X-Accel-Redirect", "X-Sendfile", "x-accel-redirect"])
def test_proxy_offload_is_an_error(galaxy, tmp_path, header):
    _serves_display(galaxy, body=b"", headers={header: "/_x_accel_redirect/files/x.dat"})
    target = tmp_path / "out.bed"
    with pytest.raises(ValueError, match="Connect through the proxy"):
        download_dataset_fn(DATASET, file_path=str(target))
    assert not target.exists()


def test_json_error_includes_err_msg(galaxy):
    _serves_display(
        galaxy, status=409, json={"err_msg": "Dataset is still being produced", "err_code": 0}
    )
    with pytest.raises(ValueError, match="HTTP 409: Dataset is still being produced"):
        download_dataset_fn(DATASET)


def test_non_json_error_body_is_not_echoed(galaxy):
    _serves_display(galaxy, status=500, body="PRIVATE_UPSTREAM_BODY", content_type="text/html")
    with pytest.raises(ValueError, match="HTTP 500") as error:
        download_dataset_fn(DATASET)
    assert "PRIVATE_UPSTREAM_BODY" not in str(error.value)


# --- what a failed download does to file_path -------------------------------------------------


def _ok_dataset(gi):
    gi.datasets.show_dataset.return_value = {"id": "ds1", "name": "x", "state": "ok"}


def _streams(gi, *chunks, fail=False):
    def body(chunk_size):
        yield from chunks
        if fail:
            raise ConnectionError("connection dropped")

    response = Mock(status_code=200, headers={})
    response.iter_content.side_effect = body
    gi.make_get_request.return_value = response
    return response


def _download(gi, path):
    with patch.dict(galaxy_state, {"connected": True, "gi": gi}):
        return download_dataset_fn("ds1", file_path=str(path))


def _leftovers(directory):
    return [p.name for p in directory.iterdir() if p.name.endswith(".part")]


def test_mid_stream_failure_keeps_existing_file_and_leaves_no_temp(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    response = _streams(mock_galaxy_instance, b"partial", fail=True)
    target = tmp_path / "out.txt"
    target.write_bytes(b"precious")
    with pytest.raises(ValueError, match="connection dropped"):
        _download(mock_galaxy_instance, target)
    assert target.read_bytes() == b"precious"
    assert _leftovers(tmp_path) == []
    response.close.assert_called_once()


def test_mid_stream_failure_creates_nothing(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"partial", fail=True)
    with pytest.raises(ValueError):
        _download(mock_galaxy_instance, tmp_path / "out.txt")
    assert list(tmp_path.iterdir()) == []


def test_success_replaces_existing_file_and_keeps_its_mode(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"new ", b"content")
    target = tmp_path / "out.txt"
    target.write_bytes(b"old")
    target.chmod(0o640)
    assert _download(mock_galaxy_instance, target).data["file_size"] == len(b"new content")
    assert target.read_bytes() == b"new content"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert _leftovers(tmp_path) == []


def test_new_file_gets_umask_mode_not_mkstemp_0600(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"data")
    target = tmp_path / "out.txt"
    _download(mock_galaxy_instance, target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o666 & ~server._UMASK


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_read_only_existing_file_is_refused_and_kept(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"data")
    target = tmp_path / "out.txt"
    target.write_bytes(b"precious")
    target.chmod(0o444)
    with pytest.raises(ValueError, match="not writable"):
        _download(mock_galaxy_instance, target)
    assert target.read_bytes() == b"precious"
    mock_galaxy_instance.make_get_request.assert_not_called()


def test_symlink_to_directory_is_refused_and_kept(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"data")
    (tmp_path / "dir").mkdir()
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "dir")
    with pytest.raises(ValueError, match="is a directory"):
        _download(mock_galaxy_instance, link)
    assert link.is_symlink()
    assert link.resolve() == (tmp_path / "dir").resolve()
    mock_galaxy_instance.make_get_request.assert_not_called()


def test_symlink_to_file_is_written_through(mock_galaxy_instance, tmp_path):
    # Follows the link, as open() did: the link survives and points at the new content.
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"new content")
    real = tmp_path / "real.txt"
    real.write_bytes(b"old")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    _download(mock_galaxy_instance, link)
    assert link.is_symlink()
    assert real.read_bytes() == b"new content"


def test_symlink_target_untouched_on_failure(mock_galaxy_instance, tmp_path):
    _ok_dataset(mock_galaxy_instance)
    _streams(mock_galaxy_instance, b"partial", fail=True)
    real = tmp_path / "real.txt"
    real.write_bytes(b"precious")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    with pytest.raises(ValueError):
        _download(mock_galaxy_instance, link)
    assert link.is_symlink()
    assert real.read_bytes() == b"precious"
    assert _leftovers(tmp_path) == []


def _refused(gi, path, match):
    _ok_dataset(gi)
    _streams(gi, b"data")
    with pytest.raises(ValueError, match=match):
        _download(gi, path)
    gi.make_get_request.assert_not_called()


def test_fifo_is_refused_and_kept(mock_galaxy_instance, tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    _refused(mock_galaxy_instance, fifo, "not a regular file")
    assert stat.S_ISFIFO(fifo.lstat().st_mode)


@pytest.mark.skipif(not os.path.exists("/dev/null"), reason="needs /dev/null")
def test_character_device_is_refused(mock_galaxy_instance, tmp_path):
    # Through a link, so the test never points the tool at /dev/null by name.
    link = tmp_path / "null"
    link.symlink_to("/dev/null")
    _refused(mock_galaxy_instance, link, "not a regular file")
    assert stat.S_ISCHR(os.stat("/dev/null").st_mode)
    assert link.is_symlink()


def test_trailing_separator_is_refused(mock_galaxy_instance, tmp_path):
    _refused(mock_galaxy_instance, f"{tmp_path}/new-name/", "names a directory")
    assert list(tmp_path.iterdir()) == []


def test_symlink_loop_is_refused(mock_galaxy_instance, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.symlink_to(b)
    b.symlink_to(a)
    _refused(mock_galaxy_instance, a, "does not resolve")
    assert a.is_symlink()
    assert b.is_symlink()


def test_missing_directory_is_refused(mock_galaxy_instance, tmp_path):
    _refused(mock_galaxy_instance, tmp_path / "nope" / "out.txt", "does not exist")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_writable_file_in_read_only_directory_is_refused(mock_galaxy_instance, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    target = locked / "out.txt"
    target.write_bytes(b"precious")
    locked.chmod(0o555)
    try:
        _refused(mock_galaxy_instance, target, "directory for .* is not writable")
        assert target.read_bytes() == b"precious"
    finally:
        locked.chmod(0o755)
