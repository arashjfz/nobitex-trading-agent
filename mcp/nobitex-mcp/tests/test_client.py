import base64
import json
from urllib.parse import urlsplit

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from nobitex_mcp.client import NobitexClient, build_query_string
from nobitex_mcp.errors import NobitexAPIError, NobitexAuthError, NobitexReadOnlyError

BASE = "https://testnetapiv2.nobitex.ir"


def make_client(handler, **kwargs):
    return NobitexClient(base_url=BASE, transport=httpx.MockTransport(handler), **kwargs)


def test_query_string_drops_none_and_encodes_types():
    query = build_query_string(
        {"a": 1, "b": None, "c": True, "d": "x y", "e": ["1", "2"], "f": False}
    )
    assert query == "a=1&c=true&d=x+y&e=1&e=2&f=false"


def test_token_auth_header_and_json_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"status": "ok", "value": 1})

    client = make_client(handler, token="secret-token")
    result = client.post("/market/orders/add", body={"type": "buy", "amount": "0.1"})

    assert result == {"status": "ok", "value": 1}
    request = captured["request"]
    assert request.headers["Authorization"] == "Token secret-token"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {"type": "buy", "amount": "0.1"}


def test_ed25519_signature_matches_documented_payload():
    private_key = Ed25519PrivateKey.generate()
    seed_b64 = base64.urlsafe_b64encode(private_key.private_bytes_raw()).decode()
    public_b64 = base64.urlsafe_b64encode(private_key.public_key().public_bytes_raw()).decode()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"status": "ok"})

    client = make_client(
        handler,
        public_key=public_b64,
        private_key=seed_b64,
        auth_mode="key",
    )
    client.get("/market/orders/list", params={"status": "open", "page": 2})

    request = captured["request"]
    raw_path = request.url.raw_path.decode()
    timestamp = request.headers["Nobitex-Timestamp"]
    message = (
        timestamp.encode()
        + b"GET"
        + raw_path.encode()
        + request.content
    )
    signature = base64.urlsafe_b64decode(request.headers["Nobitex-Signature"])
    # Raises InvalidSignature if the payload construction is wrong.
    private_key.public_key().verify(signature, message)
    assert request.headers["Nobitex-Key"] == public_b64
    assert raw_path == "/market/orders/list?status=open&page=2"


def test_api_error_with_http_status():
    def handler(request):
        return httpx.Response(
            422,
            json={"status": "failed", "code": "InvalidOrder", "message": "bad order"},
        )

    client = make_client(handler, token="t")
    with pytest.raises(NobitexAPIError) as exc:
        client.post("/market/orders/add", body={})
    assert exc.value.status_code == 422
    assert exc.value.code == "InvalidOrder"
    assert "bad order" in str(exc.value)


def test_api_error_with_200_failed_status():
    def handler(request):
        return httpx.Response(200, json={"status": "failed", "code": "TooManyRequests", "backOff": 12})

    client = make_client(handler, token="t")
    with pytest.raises(NobitexAPIError) as exc:
        client.get("/market/stats")
    assert exc.value.backoff == 12


def test_auth_required_without_credentials():
    client = make_client(lambda request: httpx.Response(200, json={}))
    with pytest.raises(NobitexAuthError):
        client.get("/users/profile")


def test_public_request_does_not_require_credentials():
    def handler(request):
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"status": "ok"})

    client = make_client(handler)
    assert client.get("/v3/orderbook/BTCUSDT", auth=False) == {"status": "ok"}


def test_read_only_blocks_mutations_but_allows_reads():
    client = make_client(lambda request: httpx.Response(200, json={"status": "ok"}), token="t", read_only=True)

    with pytest.raises(NobitexReadOnlyError):
        client.post("/market/orders/add", body={})

    assert client.get("/users/profile") == {"status": "ok"}
    assert client.post("/users/wallets/list", body={}) == {"status": "ok"}


def test_path_params_and_totp_header():
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(200, json={"status": "ok"})

    client = make_client(handler, token="t")
    client.delete("/address_book/42/delete", totp="123456")
    request = captured["request"]
    assert request.method == "DELETE"
    assert request.url.path == "/address_book/42/delete"
    assert request.headers["X-TOTP"] == "123456"


def test_token_only_endpoint_with_key_gives_actionable_error():
    private_key = Ed25519PrivateKey.generate()
    seed_b64 = base64.urlsafe_b64encode(private_key.private_bytes_raw()).decode()
    public_b64 = base64.urlsafe_b64encode(private_key.public_key().public_bytes_raw()).decode()

    def handler(request):
        return httpx.Response(401, json={"status": "failed", "code": "Unauthorized"})

    client = make_client(handler, public_key=public_b64, private_key=seed_b64, auth_mode="key")
    with pytest.raises(NobitexAPIError) as exc:
        client.get("/apikeys/list")
    assert exc.value.code == "TokenAuthRequired"
    assert "user token" in str(exc.value)


def test_network_error_is_wrapped():
    def handler(request):
        raise httpx.ConnectError("boom")

    client = make_client(handler, token="t")
    with pytest.raises(NobitexAPIError) as exc:
        client.get("/users/profile")
    assert "Network error" in str(exc.value)
