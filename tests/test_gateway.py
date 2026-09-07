import asyncio
import os

from fastapi.testclient import TestClient


def test_gateway_health():
    os.environ.pop("GATEWAY_API_KEY", None)
    from gateway.main import app

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["gateway"] == "v1"


def test_gateway_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", "secret")
    from gateway.main import app
    import gateway.main as gateway_main

    gateway_main.GATEWAY_API_KEY = "secret"
    response = TestClient(app).get("/health")

    assert response.status_code == 401
    gateway_main.GATEWAY_API_KEY = None


def test_gateway_rejects_invalid_prediction_payload():
    from gateway.main import app

    response = TestClient(app).post("/predict", json={"arrival_hour": 99})

    assert response.status_code == 422


def test_gateway_distinguishes_authentication_and_authorization(monkeypatch):
    import gateway.main as gateway_main

    monkeypatch.setattr(gateway_main, "GATEWAY_API_KEY", None)
    monkeypatch.setattr(gateway_main, "GATEWAY_API_KEYS", '{"read-key": "readonly"}')
    monkeypatch.setattr(gateway_main, "GATEWAY_REQUIRED_ROLE", "predictor")
    client = TestClient(gateway_main.app)

    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-API-Key": "read-key"}).status_code == 403


def test_gateway_retries_transient_backend_failure(monkeypatch):
    import gateway.main as gateway_main

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise gateway_main.httpx.HTTPStatusError("backend unavailable", request=None, response=self)

        def json(self):
            return {"ready": True}

    class FakeClient:
        calls = 0

        def __init__(self, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, *args, **kwargs):
            FakeClient.calls += 1
            return FakeResponse(503 if FakeClient.calls == 1 else 200)

    monkeypatch.setattr(gateway_main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(gateway_main, "BACKEND_MAX_RETRIES", 1)
    monkeypatch.setattr(gateway_main, "BACKEND_RETRY_BACKOFF_SECONDS", 0)

    result = asyncio.run(gateway_main._backend("GET", "/ready", "retry-test"))

    assert result == {"ready": True}
    assert FakeClient.calls == 2