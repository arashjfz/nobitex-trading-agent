"""HTTP client for the Nobitex API with Token and Ed25519 authentication."""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Mapping
from urllib.parse import quote, urlencode

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import MAINNET_BASE_URL, TESTNET_BASE_URL, Settings, load_settings
from .errors import NobitexAPIError, NobitexAuthError, NobitexError, NobitexReadOnlyError
from .paper import PaperBroker, PaperError

__all__ = [
    "MAINNET_BASE_URL",
    "TESTNET_BASE_URL",
    "NobitexClient",
    "build_query_string",
]

# POST endpoints that only read data and are therefore safe in read-only mode.
_READ_ONLY_POST_PATHS = {
    "/users/wallets/list",
    "/v2/wallets",
    "/users/wallets/balance",
    "/users/limitations",
    "/users/portfolio/last-week-daily-profit",
    "/users/portfolio/last-week-daily-total-profit",
    "/users/portfolio/last-month-total-profit",
    "/users/referral/links-list",
    "/users/referral/referral-status",
    "/users/login-attempts",
    "/security/emergency-cancel/get-code",
    "/market/orders/status",
    "/v2/auth/login",
    "/v2/auth/login/otp",
    "/auth/login/",
    "/auth/logout/",
}


# Endpoints that Nobitex only accepts user-token auth for (API keys are rejected).
_TOKEN_ONLY_PREFIXES = (
    "/apikeys",
    "/security/anti-phishing",
    "/users/login-attempts",
    "/users/referral",
    "/security/validate-address-network",
    "/auth/logout",
)


def _scalar_to_query(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_query_string(params: Mapping[str, Any] | None) -> str:
    """Encode query parameters deterministically, dropping ``None`` values."""
    if not params:
        return ""
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            pairs.extend((key, _scalar_to_query(item)) for item in value if item is not None)
        else:
            pairs.append((key, _scalar_to_query(value)))
    return urlencode(pairs)


class NobitexClient:
    """Thin, typed wrapper around the Nobitex HTTP API.

    Supports both authentication schemes documented by Nobitex:

    * user token  -> ``Authorization: Token <token>``
    * Ed25519 API key -> ``Nobitex-Key`` / ``Nobitex-Signature`` / ``Nobitex-Timestamp``
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        token: str | None = None,
        public_key: str | None = None,
        private_key: str | None = None,
        auth_mode: str | None = None,
        read_only: bool | None = None,
        dry_run: bool | None = None,
        user_agent: str | None = None,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if settings is None:
            if any(
                v is not None
                for v in (
                    base_url,
                    token,
                    public_key,
                    private_key,
                    auth_mode,
                    read_only,
                    dry_run,
                    user_agent,
                    timeout,
                )
            ):
                settings = Settings(
                    base_url=(base_url or MAINNET_BASE_URL).rstrip("/"),
                    environment="testnet" if "testnet" in (base_url or "") else "mainnet",
                    token=token,
                    public_key=public_key,
                    private_key=private_key,
                    auth_mode=auth_mode,
                    read_only=bool(read_only),
                    dry_run=bool(dry_run),
                    user_agent=user_agent or "TraderBot/nobitex-mcp-1.0.0",
                    timeout=timeout or 30.0,
                    transport="stdio",
                    host="127.0.0.1",
                    port=8000,
                )
            else:
                settings = load_settings()

        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self.read_only = settings.read_only
        self.dry_run = settings.dry_run
        self.paper = PaperBroker() if settings.dry_run else None
        self.user_agent = settings.user_agent
        self._token = settings.token
        self._public_key = settings.public_key
        self._private_key = settings.private_key
        self._auth_mode = settings.auth_mode
        self._client = httpx.Client(
            timeout=settings.timeout,
            transport=transport,
            headers={"User-Agent": settings.user_agent},
        )

    # ------------------------------------------------------------------ auth
    @property
    def has_credentials(self) -> bool:
        if self._auth_mode == "token":
            return bool(self._token)
        if self._auth_mode == "key":
            return bool(self._public_key and self._private_key)
        return bool(self._token or (self._public_key and self._private_key))

    def _sign(self, timestamp: str, method: str, full_path: str, raw_body: bytes) -> str:
        if not self._private_key:
            raise NobitexAuthError("NOBITEX_PRIVATE_KEY is required for API-key authentication")
        try:
            key_bytes = base64.urlsafe_b64decode(self._private_key)
        except Exception as exc:  # noqa: BLE001 - surface a clear message
            raise NobitexAuthError("NOBITEX_PRIVATE_KEY is not valid URL-safe base64") from exc
        private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
        message = (
            timestamp.encode("utf-8")
            + method.upper().encode("ascii")
            + full_path.encode("utf-8")
            + raw_body
        )
        return base64.urlsafe_b64encode(private_key.sign(message)).decode("ascii")

    def _resolved_auth_mode(self) -> str | None:
        if self._auth_mode is not None:
            return self._auth_mode
        return "token" if self._token else "key"

    def _auth_headers(self, method: str, full_path: str, raw_body: bytes) -> dict[str, str]:
        mode = self._auth_mode
        if mode is None:
            mode = "token" if self._token else "key"

        if mode == "token":
            if not self._token:
                raise NobitexAuthError(
                    "This endpoint requires authentication. Set NOBITEX_TOKEN or an API key."
                )
            return {"Authorization": f"Token {self._token}"}

        if not (self._public_key and self._private_key):
            raise NobitexAuthError(
                "This endpoint requires authentication. Set NOBITEX_PUBLIC_KEY and "
                "NOBITEX_PRIVATE_KEY, or NOBITEX_TOKEN."
            )
        timestamp = str(int(time.time()))
        return {
            "Nobitex-Key": self._public_key,
            "Nobitex-Signature": self._sign(timestamp, method, full_path, raw_body),
            "Nobitex-Timestamp": timestamp,
        }

    # --------------------------------------------------------------- request
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        auth: bool | str = True,
        totp: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Perform an API request and return the decoded JSON response.

        ``auth`` may be ``False`` (public endpoint), ``True`` (use configured
        credentials) or ``"token"`` / ``"key"`` to force a scheme.
        """
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        method = method.upper()

        if self.dry_run and self.paper is not None:
            try:
                simulated = self.paper.handle(
                    method, path, params, body, market_price=self._paper_market_price
                )
            except PaperError as exc:
                raise NobitexAPIError(
                    exc.message,
                    status_code=422,
                    code=exc.code,
                    payload={"status": "failed", "code": exc.code, "message": exc.message, "paper": True},
                ) from exc
            if simulated is not None:
                return simulated
            # Public market-data path: fall through to the live API without auth.
            auth = False

        if self.read_only and method != "GET" and path not in _READ_ONLY_POST_PATHS:
            raise NobitexReadOnlyError(
                f"Blocked mutating request {method} {path}: server is in read-only mode "
                "(NOBITEX_READ_ONLY=true)."
            )

        return self._send(method, path, params=params, body=body, auth=auth, totp=totp, extra_headers=extra_headers)

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        auth: bool | str = True,
        totp: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        query = build_query_string(params)
        full_path = f"{path}?{query}" if query else path
        raw_body = b""
        if body is not None:
            raw_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        headers: dict[str, str] = {}
        if raw_body:
            headers["Content-Type"] = "application/json"
        if totp:
            headers["X-TOTP"] = str(totp)
        if auth:
            if auth == "token":
                if not self._token:
                    raise NobitexAuthError("NOBITEX_TOKEN is required for token authentication")
                headers["Authorization"] = f"Token {self._token}"
            elif auth == "key":
                headers.update(self._auth_headers(method, full_path, raw_body))
            else:
                headers.update(self._auth_headers(method, full_path, raw_body))
        if extra_headers:
            headers.update(extra_headers)

        url = f"{self.base_url}{full_path}"
        try:
            response = self._client.request(
                method,
                url,
                content=raw_body if raw_body else None,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise NobitexAPIError(f"Network error calling {method} {path}: {exc}") from exc

        payload = self._parse_body(response)

        if response.status_code >= 400:
            if (
                response.status_code == 401
                and auth
                and self._resolved_auth_mode() == "key"
                and path.startswith(_TOKEN_ONLY_PREFIXES)
            ):
                raise NobitexAPIError(
                    "This endpoint requires a user token (Authorization: Token ...). "
                    "Nobitex does not accept API-key authentication for this path.",
                    status_code=401,
                    code="TokenAuthRequired",
                    payload=payload,
                )
            raise self._error_from(payload, response.status_code, path)
        if isinstance(payload, dict) and payload.get("status") == "failed":
            raise self._error_from(payload, response.status_code, path)
        if isinstance(payload, dict) and payload.get("s") == "error":
            raise self._error_from(payload, response.status_code, path)
        return payload

    # ----------------------------------------------------------------- paper
    def _paper_market_price(self, symbol: str, side: str) -> Any:
        from decimal import Decimal

        try:
            data = self._send("GET", f"/v3/orderbook/{quote(symbol)}", auth=False)
        except NobitexError:
            return None
        levels = data.get("asks" if side == "ask" else "bids") if isinstance(data, dict) else None
        if not levels:
            return None
        try:
            return Decimal(str(levels[0][0]))
        except (TypeError, ValueError, IndexError):
            return None

    def reset_paper(self) -> None:
        if self.paper is None:
            raise NobitexReadOnlyError("Paper mode is not enabled (NOBITEX_DRY_RUN=true)")
        self.paper.reset()

    def match_paper_orders(self) -> int:
        if self.paper is None:
            raise NobitexReadOnlyError("Paper mode is not enabled (NOBITEX_DRY_RUN=true)")
        return self.paper.match_open_orders()

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _parse_body(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def _error_from(payload: Any, status_code: int, path: str) -> NobitexAPIError:
        code = None
        message = f"Nobitex API error for {path}"
        backoff = None
        limit = None
        if isinstance(payload, dict):
            code = payload.get("code")
            message = payload.get("message") or payload.get("detail") or message
            backoff = payload.get("backOff")
            limit = payload.get("limit")
        elif isinstance(payload, str) and payload:
            message = payload
        return NobitexAPIError(
            message,
            status_code=status_code,
            code=code,
            payload=payload,
            backoff=backoff,
            limit=limit,
        )

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "NobitexClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
