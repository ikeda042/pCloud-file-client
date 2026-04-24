"""OAuth 2.0 helpers for pCloud apps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .errors import PCloudError, PCloudHTTPError

AUTHORIZE_URL = "https://my.pcloud.com/oauth2/authorize"
DEFAULT_API_HOST = "api.pcloud.com"


@dataclass(frozen=True)
class OAuthToken:
    """A pCloud OAuth bearer token and the API host it belongs to."""

    access_token: str
    token_type: str = "bearer"
    uid: Optional[int] = None
    hostname: Optional[str] = None
    locationid: Optional[int] = None


@dataclass(frozen=True)
class AuthorizationResult:
    """Parsed parameters returned by pCloud's OAuth redirect."""

    code: Optional[str] = None
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    uid: Optional[int] = None
    state: Optional[str] = None
    hostname: Optional[str] = None
    locationid: Optional[int] = None

    def token(self) -> OAuthToken:
        """Return an ``OAuthToken`` for implicit-flow redirects."""

        if not self.access_token:
            raise ValueError("authorization response does not include an access_token")
        return OAuthToken(
            access_token=self.access_token,
            token_type=self.token_type or "bearer",
            uid=self.uid,
            hostname=self.hostname,
            locationid=self.locationid,
        )


def build_authorize_url(
    client_id: str,
    *,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    response_type: str = "code",
    force_reapprove: bool = False,
    permissions: Optional[Iterable[str]] = None,
) -> str:
    """Build the pCloud authorization URL for code or implicit token flow."""

    if response_type not in {"code", "token"}:
        raise ValueError("response_type must be 'code' or 'token'")

    params: dict[str, Any] = {
        "client_id": client_id,
        "response_type": response_type,
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri
    if state:
        params["state"] = state
    if force_reapprove:
        params["force_reapprove"] = 1
    if permissions:
        params["permissions"] = ",".join(permissions)

    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def parse_authorization_response(redirect_url: str) -> AuthorizationResult:
    """Parse a pCloud OAuth redirect URL from code or implicit token flow."""

    parsed = urlparse(redirect_url)
    values = _first_values(parse_qs(parsed.query))
    values.update(_first_values(parse_qs(parsed.fragment)))

    return AuthorizationResult(
        code=values.get("code"),
        access_token=values.get("access_token"),
        token_type=values.get("token_type"),
        uid=_optional_int(values.get("uid")),
        state=values.get("state"),
        hostname=values.get("hostname"),
        locationid=_optional_int(values.get("locationid")),
    )


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    *,
    api_host: str = DEFAULT_API_HOST,
    hostname: Optional[str] = None,
    locationid: Optional[int] = None,
    session: Optional[requests.Session] = None,
    timeout: float = 30.0,
) -> OAuthToken:
    """Exchange an OAuth authorization code for a pCloud bearer token."""

    http = session or requests.Session()
    endpoint = f"https://{_clean_host(api_host)}/oauth2_token"
    response = http.get(
        endpoint,
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
        timeout=timeout,
    )

    try:
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise PCloudHTTPError(f"failed to exchange OAuth code: {exc}") from exc
    except ValueError as exc:
        raise PCloudHTTPError("pCloud returned a non-JSON OAuth response") from exc

    _raise_for_result(payload, method="oauth2_token")
    return OAuthToken(
        access_token=str(payload["access_token"]),
        token_type=str(payload.get("token_type", "bearer")),
        uid=_optional_int(payload.get("uid")),
        hostname=hostname or payload.get("hostname") or _clean_host(api_host),
        locationid=locationid or _optional_int(payload.get("locationid")),
    )


def _first_values(values: Mapping[str, list[str]]) -> dict[str, str]:
    return {key: item[0] for key, item in values.items() if item}


def _optional_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _clean_host(host: str) -> str:
    host = host.removeprefix("https://").removeprefix("http://").strip("/")
    if "/" in host:
        raise ValueError("api_host must be a host name, not a URL path")
    return host


def _raise_for_result(payload: Mapping[str, Any], *, method: str) -> None:
    result = payload.get("result", 0)
    if str(result) != "0":
        raise PCloudError.from_payload(payload, method=method)
