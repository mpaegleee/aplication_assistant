import json
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
import pytest
from assistant.ai import AI
from assistant.models import Settings


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_providers_are_authenticated_and_have_no_fixed_models(app, client):
    catalog = client.get("/api/ai/providers").json()["providers"]
    assert {
        "deepseek",
        "openai",
        "openrouter",
        "groq",
        "ollama",
        "lmstudio",
        "custom",
    } <= {p["id"] for p in catalog}
    assert all("models" not in p for p in catalog)
    client.post("/api/logout")
    assert client.get("/api/ai/providers").status_code == 401
    assert (
        client.post(
            "/api/ai/models", json={"ai_url": "https://example.com/v1"}
        ).status_code
        == 401
    )


def test_model_catalog_uses_draft_without_saving_or_sharing_profile(
    app, client, monkeypatch
):
    before = app.state.engine.settings()
    observed = []

    def handler(request):
        observed.append(request)
        assert str(request.url) == "https://api.deepseek.com/models"
        assert request.headers["Authorization"] == "Bearer draft-test-key"
        assert request.content == b""
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "actual-model-b", "name": "Modelo B"},
                    {"id": "actual-model-a"},
                    {"id": "actual-model-a"},
                    {
                        "id": "image-only",
                        "architecture": {"output_modalities": ["image"]},
                    },
                    {"id": "text-embedding-test"},
                    {"bad": "ignored"},
                ]
            },
        )

    transport(monkeypatch, handler)
    response = client.post(
        "/api/ai/models",
        json={"ai_url": "https://api.deepseek.com/", "ai_key": "draft-test-key"},
    )
    assert response.status_code == 200
    assert {m["id"] for m in response.json()["models"]} == {
        "actual-model-a",
        "actual-model-b",
    }
    assert len(observed) == 1 and app.state.engine.settings() == before
    day = datetime.now(ZoneInfo(before["timezone"])).date().isoformat()
    assert app.state.store.count("ai", day) == 0
    assert "draft-test-key" not in response.text


def test_saved_key_only_used_for_exact_saved_endpoint(app, client, monkeypatch):
    settings = app.state.engine.settings()
    settings.update(ai_url="https://saved.example/v1", ai_key="saved-test-key")
    app.state.store.put("settings", settings)
    observed = []

    def handler(request):
        observed.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"data": []})

    transport(monkeypatch, handler)
    assert (
        client.post(
            "/api/ai/models", json={"ai_url": "https://saved.example/v1/"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/ai/models", json={"ai_url": "https://other.example/v1"}
        ).status_code
        == 200
    )
    assert observed == ["Bearer saved-test-key", None]
    assert app.state.engine.settings()["ai_key"] == "saved-test-key"


def test_switching_endpoint_drops_old_key_but_preserves_other_credentials(app, client):
    s = app.state.engine.settings()
    s.update(ai_key="old-test-key", smtp_password="mail-test-secret")
    app.state.store.put("settings", s)
    s.update(ai_url="https://new.example/v1", ai_key="", smtp_password="")
    assert client.put("/api/settings", json=s).status_code == 200
    assert app.state.engine.settings()["ai_key"] == ""
    assert app.state.engine.settings()["smtp_password"] == "mail-test-secret"


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "Chave"),
        (403, "permissões"),
        (402, "saldo"),
        (404, "lista de modelos"),
        (429, "cota"),
        (503, "indisponível"),
    ],
)
def test_provider_errors_are_actionable_and_do_not_echo_secrets(
    app, client, monkeypatch, status, expected
):
    transport(
        monkeypatch,
        lambda request: httpx.Response(
            status, json={"error": {"message": "DO-NOT-ECHO-PRIVATE-DETAILS"}}
        ),
    )
    response = client.post(
        "/api/ai/models",
        json={"ai_url": "https://example.com/v1", "ai_key": "secret-test-key"},
    )
    assert response.status_code == 400 and expected in response.json()["detail"]
    assert "secret-test-key" not in response.text and "DO-NOT-ECHO" not in response.text


def test_local_connection_diagnostic_and_invalid_catalog(app, client, monkeypatch):
    def failed(request):
        raise httpx.ConnectError("private details")

    transport(monkeypatch, failed)
    response = client.post(
        "/api/ai/models", json={"ai_url": "http://localhost:11434/v1"}
    )
    assert (
        "Ollama" in response.json()["detail"]
        and "serviço online" in response.json()["detail"]
    )


def test_invalid_catalog_and_invalid_url(app, client, monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(200, json={"not_data": []}))
    assert (
        client.post(
            "/api/ai/models", json={"ai_url": "https://example.com/v1"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/ai/models", json={"ai_url": "http://external.example/v1"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/ai/models", json={"ai_url": "https://user:secret@example.com/v1"}
        ).status_code
        == 422
    )


def test_completion_retries_only_unsupported_parameters_and_counts_calls(
    app, settings, monkeypatch
):
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if len(seen) == 1:
            return httpx.Response(400, json={"error": {"param": "max_tokens"}})
        if len(seen) == 2:
            return httpx.Response(400, json={"error": {"param": "response_format"}})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok":true}'}}]}
        )

    transport(monkeypatch, handler)
    assert AI(app.state.store).call(settings, "Return JSON", {}) == {"ok": True}
    assert "max_completion_tokens" in seen[1] and "max_tokens" not in seen[1]
    assert "response_format" not in seen[2]
    day = datetime.now(ZoneInfo(settings["timezone"])).date().isoformat()
    assert app.state.store.count("ai", day) == 3


def test_completion_auth_failure_does_not_retry(app, settings, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(401, json={"error": {"message": "private"}})

    transport(monkeypatch, handler)
    with pytest.raises(ValueError, match="Chave"):
        AI(app.state.store).call(settings, "test", {})
    assert len(requests) == 1


def test_fallback_still_requires_valid_json(app, settings, monkeypatch):
    responses = [
        httpx.Response(400, json={"error": {"param": "response_format"}}),
        httpx.Response(
            200, json={"choices": [{"message": {"content": "plain prose, not JSON"}}]}
        ),
    ]
    transport(monkeypatch, lambda request: responses.pop(0))
    with pytest.raises(ValueError, match="formato esperado"):
        AI(app.state.store).call(settings, "JSON", {})
