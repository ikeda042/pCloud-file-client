"""Synchronous pCloud HTTP JSON API client."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Mapping, Optional, Union

import requests

from .auth import DEFAULT_API_HOST, OAuthToken
from .errors import PCloudError, PCloudHTTPError

JSON = dict[str, Any]
RemotePath = Union[str, PurePosixPath]


class PCloudClient:
    """Small synchronous wrapper around pCloud's HTTP JSON API."""

    def __init__(
        self,
        access_token: str,
        *,
        api_host: str = DEFAULT_API_HOST,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
        user_agent: str = "pcloud-python-client-test/0.1.0",
    ) -> None:
        self.access_token = access_token
        self.api_host = _clean_host(api_host)
        self.base_url = f"https://{self.api_host}"
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": user_agent,
            }
        )

    @classmethod
    def from_oauth_token(
        cls,
        token: OAuthToken,
        *,
        api_host: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
    ) -> "PCloudClient":
        """Create a client from an OAuth token returned by ``exchange_code``."""

        return cls(
            token.access_token,
            api_host=api_host or token.hostname or DEFAULT_API_HOST,
            session=session,
            timeout=timeout,
        )

    @classmethod
    def from_env(cls, *, prefix: str = "PCLOUD_") -> "PCloudClient":
        """Create a client from ``PCLOUD_ACCESS_TOKEN`` and ``PCLOUD_API_HOST``."""

        token = os.environ.get(f"{prefix}ACCESS_TOKEN")
        if not token:
            raise RuntimeError(f"{prefix}ACCESS_TOKEN is required")
        return cls(token, api_host=os.environ.get(f"{prefix}API_HOST", DEFAULT_API_HOST))

    @staticmethod
    def closest_api_host(
        *,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
        fallback: str = DEFAULT_API_HOST,
    ) -> str:
        """Return pCloud's nearest HTTP API host, falling back to ``api.pcloud.com``."""

        http = session or requests.Session()
        try:
            response = http.get(f"https://{fallback}/getapiserver", timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return fallback
        api_hosts = payload.get("api") or []
        return str(api_hosts[0]) if api_hosts else fallback

    def call(self, method: str, **params: Any) -> JSON:
        """Call a raw pCloud method and return the decoded JSON payload."""

        return self._request(method, params=params)

    def userinfo(self) -> JSON:
        """Return metadata for the authenticated pCloud account."""

        return self._request("userinfo")

    def list_folder(
        self,
        *,
        path: Optional[RemotePath] = None,
        folderid: Optional[int] = None,
        recursive: bool = False,
        showdeleted: bool = False,
        nofiles: bool = False,
        noshares: bool = False,
    ) -> JSON:
        """Return folder metadata and contents for ``path`` or ``folderid``."""

        params = _path_or_id(path=path, folderid=folderid, id_name="folderid")
        params.update(
            _bool_params(
                recursive=recursive,
                showdeleted=showdeleted,
                nofiles=nofiles,
                noshares=noshares,
            )
        )
        return self._request("listfolder", params=params)["metadata"]

    def iter_folder(
        self,
        *,
        path: Optional[RemotePath] = None,
        folderid: Optional[int] = None,
        recursive: bool = False,
    ) -> Iterator[JSON]:
        """Yield folder children, optionally flattening a recursive listing."""

        root = self.list_folder(path=path, folderid=folderid, recursive=recursive)
        yield from _walk_contents(root.get("contents", []))

    def stat(self, *, path: Optional[RemotePath] = None, fileid: Optional[int] = None) -> JSON:
        """Return file metadata by path or file id."""

        params = _path_or_id(path=path, folderid=fileid, id_name="fileid")
        return self._request("stat", params=params)["metadata"]

    def create_folder(
        self,
        *,
        path: Optional[RemotePath] = None,
        folderid: Optional[int] = None,
        name: Optional[str] = None,
        exist_ok: bool = False,
    ) -> JSON:
        """Create a folder and return its metadata."""

        if path is not None:
            params = {"path": _normalize_remote_path(path)}
        elif folderid is not None and name:
            params = {"folderid": folderid, "name": name}
        else:
            raise ValueError("provide path or folderid + name")

        method = "createfolderifnotexists" if exist_ok else "createfolder"
        return self._request(method, params=params)["metadata"]

    def ensure_folder(self, path: RemotePath) -> JSON:
        """Create a nested folder path if needed and return the final folder metadata."""

        parts = _remote_parts(path)
        if not parts:
            return self.list_folder(folderid=0)

        parent_id = 0
        metadata: JSON = {}
        for part in parts:
            metadata = self.create_folder(folderid=parent_id, name=part, exist_ok=True)
            parent_id = int(metadata["folderid"])
        return metadata

    def upload_file(
        self,
        local_path: Union[str, Path],
        *,
        remote_dir: RemotePath = "/",
        folderid: Optional[int] = None,
        filename: Optional[str] = None,
        ensure: bool = False,
        rename_if_exists: bool = False,
        nopartial: bool = True,
        mtime: Optional[int] = None,
        ctime: Optional[int] = None,
    ) -> JSON:
        """Upload one local file to pCloud and return its metadata."""

        source = Path(local_path)
        if not source.is_file():
            raise FileNotFoundError(source)

        remote_name = filename or source.name
        params: dict[str, Any] = {"filename": remote_name}
        if ensure:
            folder = self.ensure_folder(remote_dir)
            params["folderid"] = folder["folderid"]
        elif folderid is not None:
            params["folderid"] = folderid
        else:
            params["path"] = _normalize_remote_path(remote_dir)

        params.update(
            _bool_params(
                renameifexists=rename_if_exists,
                nopartial=nopartial,
            )
        )
        if mtime is not None:
            params["mtime"] = int(mtime)
        if ctime is not None:
            if mtime is None:
                raise ValueError("ctime requires mtime")
            params["ctime"] = int(ctime)

        with source.open("rb") as handle:
            payload = self._upload(
                "uploadfile",
                data=params,
                files={"file": (remote_name, handle)},
            )
        metadata = payload.get("metadata") or []
        return metadata[0] if metadata else payload

    def upload_bytes(
        self,
        content: bytes,
        *,
        filename: str,
        remote_dir: RemotePath = "/",
        folderid: Optional[int] = None,
        rename_if_exists: bool = False,
        nopartial: bool = True,
    ) -> JSON:
        """Upload an in-memory byte string."""

        params: dict[str, Any] = {"filename": filename}
        if folderid is not None:
            params["folderid"] = folderid
        else:
            params["path"] = _normalize_remote_path(remote_dir)
        params.update(_bool_params(renameifexists=rename_if_exists, nopartial=nopartial))

        payload = self._upload(
            "uploadfile",
            data=params,
            files={"file": (filename, content)},
        )
        metadata = payload.get("metadata") or []
        return metadata[0] if metadata else payload

    def upload_directory(
        self,
        local_dir: Union[str, Path],
        *,
        remote_dir: RemotePath,
        rename_if_exists: bool = False,
    ) -> list[JSON]:
        """Upload every file under ``local_dir`` while preserving relative paths."""

        root = Path(local_dir)
        if not root.is_dir():
            raise NotADirectoryError(root)

        uploaded: list[JSON] = []
        for source in sorted(path for path in root.rglob("*") if path.is_file()):
            relative_parent = source.parent.relative_to(root).as_posix()
            target_dir = _join_remote(remote_dir, relative_parent)
            uploaded.append(
                self.upload_file(
                    source,
                    remote_dir=target_dir,
                    ensure=True,
                    rename_if_exists=rename_if_exists,
                )
            )
        return uploaded

    def get_file_link(
        self,
        *,
        path: Optional[RemotePath] = None,
        fileid: Optional[int] = None,
        forcedownload: bool = True,
        contenttype: Optional[str] = None,
        maxspeed: Optional[int] = None,
        skipfilename: bool = False,
        https: bool = True,
    ) -> str:
        """Return a temporary direct download URL for a pCloud file."""

        params = _path_or_id(path=path, folderid=fileid, id_name="fileid")
        params.update(_bool_params(forcedownload=forcedownload, skipfilename=skipfilename))
        if contenttype:
            params["contenttype"] = contenttype
        if maxspeed:
            params["maxspeed"] = int(maxspeed)

        payload = self._request("getfilelink", params=params)
        hosts = payload.get("hosts") or []
        if not hosts or "path" not in payload:
            raise PCloudHTTPError("pCloud did not return a usable file link")
        scheme = "https" if https else "http"
        return f"{scheme}://{hosts[0]}{payload['path']}"

    def download_file(
        self,
        *,
        remote_path: Optional[RemotePath] = None,
        fileid: Optional[int] = None,
        local_path: Union[str, Path],
        overwrite: bool = False,
        chunk_size: int = 1024 * 1024,
    ) -> Path:
        """Download a pCloud file to ``local_path``."""

        target = Path(local_path)
        if target.exists() and target.is_dir():
            if remote_path is None:
                raise ValueError(
                    "local_path is a directory; remote_path is required to infer filename"
                )
            target = target / PurePosixPath(str(remote_path)).name
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        url = self.get_file_link(path=remote_path, fileid=fileid, forcedownload=True)
        try:
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PCloudHTTPError(f"failed to download file: {exc}") from exc

        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    handle.write(chunk)
        return target

    def delete_file(
        self,
        *,
        path: Optional[RemotePath] = None,
        fileid: Optional[int] = None,
    ) -> JSON:
        """Delete a file by path or file id and return pCloud's metadata."""

        return self._request(
            "deletefile",
            params=_path_or_id(path=path, folderid=fileid, id_name="fileid"),
        )["metadata"]

    def _request(
        self,
        method: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        http_method: str = "GET",
    ) -> JSON:
        url = f"{self.base_url}/{method}"
        try:
            response = self.session.request(
                http_method,
                url,
                params=dict(params or {}),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise PCloudHTTPError(f"{method}: HTTP request failed: {exc}") from exc
        except ValueError as exc:
            raise PCloudHTTPError(f"{method}: pCloud returned a non-JSON response") from exc

        _raise_for_result(payload, method=method)
        return dict(payload)

    def _upload(
        self,
        method: str,
        *,
        data: Mapping[str, Any],
        files: Mapping[str, Any],
    ) -> JSON:
        url = f"{self.base_url}/{method}"
        try:
            response = self.session.post(
                url,
                data=dict(data),
                files=dict(files),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise PCloudHTTPError(f"{method}: upload failed: {exc}") from exc
        except ValueError as exc:
            raise PCloudHTTPError(f"{method}: pCloud returned a non-JSON response") from exc

        _raise_for_result(payload, method=method)
        return dict(payload)


def _raise_for_result(payload: Mapping[str, Any], *, method: str) -> None:
    result = payload.get("result", 0)
    if str(result) != "0":
        raise PCloudError.from_payload(payload, method=method)


def _bool_params(**items: bool) -> dict[str, int]:
    return {key: 1 for key, enabled in items.items() if enabled}


def _path_or_id(
    *,
    path: Optional[RemotePath],
    folderid: Optional[int],
    id_name: str,
) -> dict[str, Any]:
    if path is not None and folderid is not None:
        raise ValueError(f"provide either path or {id_name}, not both")
    if path is not None:
        return {"path": _normalize_remote_path(path)}
    if folderid is not None:
        return {id_name: int(folderid)}
    raise ValueError(f"provide path or {id_name}")


def _normalize_remote_path(path: RemotePath) -> str:
    value = str(path).replace("\\", "/").strip()
    if not value:
        raise ValueError("remote path cannot be empty")
    if value == "/":
        return "/"
    value = "/" + value.strip("/")
    if "//" in value:
        raise ValueError("remote path cannot contain empty components")
    return value


def _remote_parts(path: RemotePath) -> list[str]:
    normalized = _normalize_remote_path(path)
    if normalized == "/":
        return []
    return [part for part in normalized.strip("/").split("/") if part]


def _join_remote(base: RemotePath, relative: str) -> str:
    normalized_base = _normalize_remote_path(base)
    if relative in {"", "."}:
        return normalized_base
    return _normalize_remote_path(f"{normalized_base}/{relative}")


def _walk_contents(contents: Iterable[Mapping[str, Any]]) -> Iterator[JSON]:
    for item in contents:
        current = dict(item)
        yield current
        nested = current.get("contents")
        if nested:
            yield from _walk_contents(nested)


def _clean_host(host: str) -> str:
    value = host.removeprefix("https://").removeprefix("http://").strip("/")
    if not value or "/" in value:
        raise ValueError("api_host must be a host name, not a URL")
    return value
