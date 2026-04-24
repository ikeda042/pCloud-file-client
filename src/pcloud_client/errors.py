"""Exception types and pCloud result-code handling."""

from __future__ import annotations

from typing import Any, Mapping, Optional

DEFAULT_ERROR_MESSAGES = {
    1000: "Log in required.",
    1001: "No full path or name/folderid provided.",
    1002: "No full path or folderid provided.",
    1004: "Missing required parameter.",
    2000: "Log in failed.",
    2001: "Invalid file/folder name.",
    2002: "A component of parent directory does not exist.",
    2003: "Access denied.",
    2004: "File or folder already exists.",
    2005: "Directory does not exist.",
    2008: "User is over quota.",
    2009: "File not found.",
    2010: "Invalid path.",
    2041: "Connection broken.",
    4000: "Too many login tries from this IP address.",
    5000: "Internal error. Try again later.",
    5001: "Internal upload error.",
    5002: "Internal error, no servers available. Try again later.",
}


class PCloudError(Exception):
    """Raised when pCloud returns a non-zero JSON ``result`` code."""

    def __init__(
        self,
        result: int,
        message: Optional[str] = None,
        *,
        method: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.result = result
        self.method = method
        self.payload = dict(payload or {})
        self.message = message or DEFAULT_ERROR_MESSAGES.get(result, "pCloud API error.")

        prefix = f"{method}: " if method else ""
        super().__init__(f"{prefix}{self.message} (result={result})")

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        method: Optional[str] = None,
    ) -> "PCloudError":
        raw_result = payload.get("result", -1)
        try:
            result = int(raw_result)
        except (TypeError, ValueError):
            result = -1

        message = (
            payload.get("error")
            or payload.get("message")
            or DEFAULT_ERROR_MESSAGES.get(result)
            or "pCloud API error."
        )
        return cls(result, str(message), method=method, payload=payload)


class PCloudHTTPError(Exception):
    """Raised for non-JSON or failed HTTP responses from pCloud/content hosts."""
