"""Exception types raised by the Nobitex client."""

from __future__ import annotations

from typing import Any


class NobitexError(Exception):
    """Base class for all client errors."""


class NobitexAuthError(NobitexError):
    """Raised when an authenticated endpoint is called without credentials."""


class NobitexReadOnlyError(NobitexError):
    """Raised when a mutating operation is attempted in read-only mode."""


class NobitexAPIError(NobitexError):
    """Raised when the Nobitex API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        payload: Any = None,
        backoff: int | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.payload = payload
        self.backoff = backoff
        self.limit = limit

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"message": self.message}
        if self.status_code is not None:
            data["http_status"] = self.status_code
        if self.code:
            data["code"] = self.code
        if self.backoff is not None:
            data["backoff_seconds"] = self.backoff
        if self.limit is not None:
            data["rate_limit"] = self.limit
        if self.payload is not None:
            data["response"] = self.payload
        return data

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"code={self.code}")
        if self.status_code is not None:
            parts.append(f"http={self.status_code}")
        if self.backoff is not None:
            parts.append(f"retry_after={self.backoff}s")
        return " | ".join(parts)
