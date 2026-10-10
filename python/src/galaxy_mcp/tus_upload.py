"""Galaxy's tus upload, held to the same no-redirect rule as every other request.

tusclient sends every request with requests' default `allow_redirects=True` and the API key
in the headers, so a 3xx re-sent the key to wherever Location pointed. It also dials the
creation reply's Location as given, and Galaxy builds that Location ABSOLUTE from the Host it
saw (or X-Forwarded-Host/Proto behind a proxy) -- which need not be the configured GALAXY_URL.

`GalaxyTusUploader` owns all three requests tusclient makes (creation POST, PATCH, HEAD):
none follows a redirect, a 3xx is a final refusal, and every URL the uploader is handed is
checked to be this Galaxy's upload route and re-rooted onto the configured origin.
"""

import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from tusclient.client import TusClient
from tusclient.exceptions import TusCommunicationError, TusUploadFailed
from tusclient.request import TusRequest, catch_requests_error
from tusclient.uploader import Uploader

UPLOAD_ROUTE = "/api/upload/resumable_upload"
# bioblend's own chunk size for the same upload.
UPLOAD_CHUNK_SIZE = 10**7
REDIRECT_TARGET_MAX = 200

_AUTHORITY = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:)?//[^/?#\\]*")
_UPLOAD_ID = re.compile(r"[A-Za-z0-9_-]+")


class TusRefusedError(Exception):
    """A tus request we will not make or follow. Final: tusclient's retry never sees it,
    since it is not a TusCommunicationError."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def is_redirect_status(status: int) -> bool:
    # 304 is a cache answer to a conditional request, not a redirect.
    return 300 <= status < 400 and status != 304


def redirect_target(location: str, from_url: str) -> str:
    """Where a redirect pointed, fit to show a user: resolved against the request, without
    userinfo, query or fragment (a presigned signature has no business in an error), capped."""
    try:
        parts = urlsplit(urljoin(from_url, location))
        netloc = parts.netloc.rpartition("@")[2]
        shown = urlunsplit((parts.scheme, netloc, parts.path, "", ""))
    except ValueError:
        shown = re.split(r"[?#]", location, maxsplit=1)[0]
    if len(shown) > REDIRECT_TARGET_MAX:
        return f"{shown[:REDIRECT_TARGET_MAX]}..."
    return shown


def redirect_refusal(status: int, location: str | None, from_url: str) -> str:
    where = f"; Galaxy redirected to {redirect_target(location, from_url)}" if location else ""
    return f"Galaxy answered {status} and redirects are not followed{where} -- check GALAXY_URL"


def upload_path_in(location: str, prefix: str) -> str | None:
    """The upload's path and query, if `location` names an upload under `prefix`.

    Decided on the raw string, before anything could collapse a `..` or `%2e%2e` into a path
    that looks fine. Galaxy's upload ids are one plain segment, so anything needing dots,
    slashes, escapes or backslashes to spell is refused. The fragment is dropped; the query
    belongs to the upload and is kept.
    """
    no_fragment = location.split("#", 1)[0]
    authority = _AUTHORITY.match(no_fragment)
    rest = no_fragment[authority.end() :] if authority else no_fragment
    path, sep, query = rest.partition("?")
    if not path.startswith(prefix) or not _UPLOAD_ID.fullmatch(path[len(prefix) :]):
        return None
    return f"{path}{sep}{query}"


class _NoRedirectTusRequest(TusRequest):
    """tusclient's PATCH, minus the redirect following."""

    def perform(self) -> None:
        try:
            chunk = self.file.read(self._content_length)
            self.add_checksum(chunk)
            resp = requests.patch(
                self._url,
                data=chunk,
                headers=self._request_headers,
                verify=self.verify_tls_cert,
                stream=True,
                cert=self.client_cert,
                allow_redirects=False,
            )
            self.status_code = resp.status_code
            self.response_content = resp.content
            self.response_headers = {k.lower(): v for k, v in resp.headers.items()}
        except requests.exceptions.RequestException as error:
            raise TusUploadFailed(error) from error


class GalaxyTusUploader(Uploader):
    """tusclient's Uploader with every request kept on the configured Galaxy.

    `set_url` is the one door every upload URL comes through -- the creation Location, a
    stored URL on resume, or one passed in -- so the route check and re-root live there.
    """

    def __init__(self, *args: Any, galaxy_url: str, **kwargs: Any) -> None:
        base = urlsplit(galaxy_url)
        self._origin = urlunsplit((base.scheme, base.netloc, "", "", ""))
        self._prefix = f"{base.path.rstrip('/')}{UPLOAD_ROUTE}/"
        super().__init__(*args, **kwargs)

    def _refuse(self, where: str) -> TusRefusedError:
        return TusRefusedError(
            f"tus upload refused: Galaxy's upload Location {where} is not its "
            "resumable-upload route, so the API key was not sent to it"
        )

    def _reroot(self, url: str) -> str:
        kept = upload_path_in(url, self._prefix)
        if kept is None:
            raise self._refuse(url)
        target = f"{self._origin}{kept}"
        # Checked again on what is about to be sent, not just on what was asked for.
        sent = urlsplit(target)
        origin = urlunsplit((sent.scheme, sent.netloc, "", "", ""))
        rebuilt = f"{sent.path}?{sent.query}" if sent.query else sent.path
        if origin != self._origin or rebuilt != kept.rstrip("?"):
            raise self._refuse(url)
        return target

    def set_url(self, url: str) -> None:
        super().set_url(self._reroot(url))

    @catch_requests_error
    def create_url(self) -> str:
        # tusclient only creates through a client; the url-only uploader resumes.
        assert self.client is not None
        resp = requests.post(
            self.client.url,
            headers=self.get_url_creation_headers(),
            verify=self.verify_tls_cert,
            cert=self.client_cert,
            allow_redirects=False,
        )
        location = resp.headers.get("location")
        if is_redirect_status(resp.status_code):
            raise TusRefusedError(
                redirect_refusal(resp.status_code, location, self.client.url), resp.status_code
            )
        # tusclient took any reply with a Location; only a 2xx creation names an upload.
        if not 200 <= resp.status_code < 300 or location is None:
            raise TusCommunicationError(
                f"Attempt to retrieve create file url with status {resp.status_code}",
                resp.status_code,
                resp.content,
            )
        if upload_path_in(location, self._prefix) is None:
            raise self._refuse(location)
        return str(location)

    @catch_requests_error
    def get_offset(self) -> int:
        resp = requests.head(
            str(self.url),
            headers=self.get_headers(),
            verify=self.verify_tls_cert,
            cert=self.client_cert,
            allow_redirects=False,
        )
        if is_redirect_status(resp.status_code):
            raise TusRefusedError(
                redirect_refusal(resp.status_code, resp.headers.get("location"), str(self.url)),
                resp.status_code,
            )
        offset = resp.headers.get("upload-offset")
        if offset is None:
            raise TusCommunicationError(
                f"Attempt to retrieve offset fails with status {resp.status_code}",
                resp.status_code,
                resp.content,
            )
        return int(offset)

    def _do_request(self) -> None:
        request = _NoRedirectTusRequest(self)
        self.request = request  # type: ignore[assignment]
        try:
            request.perform()
            status = request.status_code
            if status is not None and is_redirect_status(status):
                raise TusRefusedError(
                    redirect_refusal(
                        status, request.response_headers.get("location"), str(self.url)
                    ),
                    status,
                )
            if status is None or not 200 <= status < 300:
                raise TusUploadFailed("", status, request.response_content)
        except TusUploadFailed as error:
            self._retry_or_cry(error)

    @property
    def upload_session_id(self) -> str:
        """The id Galaxy's fetch API takes: the upload URL's last path segment."""
        path = urlsplit(str(self.url)).path
        return path.rsplit("/", 1)[-1]


def upload_via_tus(
    galaxy_url: str, api_key: str | None, path: str, chunk_size: int = UPLOAD_CHUNK_SIZE
) -> str:
    """Upload `path` to Galaxy over tus and return the session id for the fetch API.

    No URL storage: galaxy_mcp never resumes, so tusclient's HEAD only happens if it retries,
    and that HEAD goes through the same guard as everything else.
    """
    endpoint = f"{galaxy_url.rstrip('/')}{UPLOAD_ROUTE}"
    client = TusClient(endpoint, headers={"x-api-key": api_key} if api_key else {})
    uploader = GalaxyTusUploader(
        file_path=path, client=client, chunk_size=chunk_size, galaxy_url=galaxy_url
    )
    uploader.upload()
    return uploader.upload_session_id
