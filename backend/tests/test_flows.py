import json, threading
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
import pytest
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from assistant.models import Profile, Settings
from assistant.matching import hard_blocks, validate_analysis
from assistant.store import Store
from assistant.sources import public_fetch, read_source
from assistant.engine import Engine
from assistant.ai import AI
from assistant.mail import email_eligible, parse_followup


def test_auth_required_and_cross_origin(app, client):
    from fastapi.testclient import TestClient

    other = TestClient(app)
    assert other.get("/api/state").status_code == 401
    assert other.get("/api/jobs/no/resume").status_code == 401
    assert (
        client.post(
            "/api/pause", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        other.post(
            "/api/login", json={"password": "test-only-password-123"}
        ).status_code
        == 403
    )
    assert client.get("/api/state", headers={"Host": "evil.example"}).status_code == 400


def test_login_logout(client):
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/state").status_code == 401
    assert (
        client.post("/api/login", json={"password": "wrong-password"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/login", json={"password": "test-only-password-123"}
        ).status_code
        == 200
    )


def test_single_user_setup(client):
    assert (
        client.post("/api/setup", json={"password": "another-password"}).status_code
        == 409
    )


def test_profile_area_blocks_even_perfect_ai(
    app, profile, settings, job, analysis, monkeypatch
):
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    job["area"] = "Financeiro"
    monkeypatch.setattr(
        AI, "analyze", lambda *a: pytest.fail("Blocked jobs must not call model")
    )
    j, _ = app.state.engine.add_job(job)
    j = app.state.engine.analyze(j["id"])
    assert j["status"] == "blocked" and j["analysis"]["score"] is None
    with pytest.raises(ValueError):
        app.state.engine.approve(j["id"])
    with pytest.raises(ValueError):
        app.state.engine.send(j["id"])


def test_unknown_criteria_are_blocked(profile, job):
    job["area_reviewed"] = False
    assert hard_blocks(profile, job)
    profile["confirmed"] = False
    assert any("Confirme" in x for x in hard_blocks(profile, job))
    profile["minimum_salary"] = 5000
    assert any("Remuneração" in x for x in hard_blocks(profile, job))


def test_forged_ai_evidence_rejected(profile, job, analysis):
    analysis["criteria"]["essential"]["fact_ids"] = ["invented"]
    with pytest.raises(ValueError):
        validate_analysis(analysis, profile, job)
    analysis["criteria"]["essential"]["fact_ids"] = ["f1"]
    analysis["criteria"]["essential"]["job_quote"] = "Experiência que não existe"
    with pytest.raises(ValueError):
        validate_analysis(analysis, profile, job)


def test_analysis_weights(profile, job, analysis):
    analysis["criteria"]["essential"]["grade"] = 50
    assert validate_analysis(analysis, profile, job)["score"] == 85


def test_dedup_persists(app, job):
    job["url"] = "https://example.com/jobs/1?utm_source=test"
    j, new = app.state.engine.add_job(job)
    assert new
    job["url"] = "https://example.com/jobs/1"
    j2, new = Engine(app.state.store).add_job(job)
    assert not new and j2["id"] == j["id"]


def test_pdf_import_and_profile_validation(client):
    stream = BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(
        40,
        800,
        "Pessoa Teste - Desenvolvedor Python - Experiencia com APIs e sistemas.",
    )
    canvas.save()
    response = client.post(
        "/api/profile/pdf",
        files={"file": ("curriculo.pdf", stream.getvalue(), "application/pdf")},
    )
    assert response.status_code == 200 and "Python" in response.json()["text"]
    p = Profile(
        name="Teste",
        areas=["Desenvolvimento"],
        roles=["Desenvolvedor"],
        confirmed=True,
        facts=[
            {
                "id": "fake",
                "text": "Inventei um diploma",
                "evidence": "Inventei um diploma",
                "source": "pdf",
            }
        ],
    ).model_dump()
    assert client.put("/api/profile", json=p).status_code == 400
    assert (
        client.post(
            "/api/profile/pdf",
            files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
        ).status_code
        == 400
    )


def test_extraction_only_literal_facts(app, settings, monkeypatch):
    monkeypatch.setattr(
        AI,
        "call",
        lambda *a: {
            "name": "Nome inventado",
            "email": "fake@example.com",
            "facts": [
                {"text": "Python por três anos.", "evidence": "Python por três anos."},
                {"text": "Doutorado", "evidence": "Doutorado"},
            ],
        },
    )
    result = AI(app.state.store).extract(settings, "Experiência: Python por três anos.")
    assert len(result["facts"]) == 1 and result["name"] == "" and result["email"] == ""


def test_resume_only_selected_verified_facts(app, prepared):
    data = app.state.engine.pdf(prepared)
    text = " ".join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert "Python" in text and "Pessoa Teste" in text
    assert "Correspondência" not in text


def test_review_approval_pause_and_snapshot(app, prepared, monkeypatch):
    calls = []
    monkeypatch.setattr("assistant.engine.smtp_send", lambda s, m: calls.append(m))
    with pytest.raises(ValueError, match="Aprovação"):
        app.state.engine.send(prepared)
    app.state.engine.approve(prepared)
    s = app.state.engine.settings()
    s["paused"] = True
    app.state.store.put("settings", s)
    with pytest.raises(ValueError, match="pausada"):
        app.state.engine.send(prepared)
    s["paused"] = False
    app.state.store.put("settings", s)
    j = app.state.engine.send(prepared)
    assert j["status"] == "sent" and len(calls) == 1 and j["resume_snapshot"]
    assert calls[0]["To"] == "vagas@example.com"
    with pytest.raises(ValueError, match="reenvio"):
        app.state.engine.send(prepared)
    assert len(calls) == 1


def test_policy_and_profile_changes_invalidate_approval(app, prepared):
    app.state.engine.approve(prepared)
    p = app.state.engine.profile()
    p["roles"] = ["Engenheiro de software"]
    app.state.store.put("profile", p)
    with pytest.raises(ValueError, match="mudou"):
        app.state.engine.send(prepared)


def test_automatic_mode_without_approval(app, prepared, monkeypatch):
    s = app.state.engine.settings()
    s["mode"] = "automatic"
    app.state.store.put("settings", s)
    monkeypatch.setattr("assistant.engine.smtp_send", lambda *a: None)
    assert app.state.engine.send(prepared)["status"] == "sent"


def test_uncertain_smtp_never_retries(app, prepared, monkeypatch):
    app.state.engine.approve(prepared)

    def fail(*a):
        raise TimeoutError("possibly accepted already")

    monkeypatch.setattr("assistant.engine.smtp_send", fail)
    with pytest.raises(ValueError, match="incerto"):
        app.state.engine.send(prepared)
    assert app.state.engine.require_job(prepared)["status"] == "uncertain"
    with pytest.raises(ValueError, match="reenvio"):
        app.state.engine.send(prepared)


def test_concurrent_sends_are_serialized(app, prepared, monkeypatch):
    app.state.engine.approve(prepared)
    calls = []
    monkeypatch.setattr("assistant.engine.smtp_send", lambda *a: calls.append(1))

    def send():
        try:
            return app.state.engine.send(prepared)["status"]
        except ValueError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert sorted(results) == ["blocked", "sent"] and calls == [1]


def test_secret_redaction_and_encryption(app, client):
    s = app.state.engine.settings()
    s["ai_key"] = "unique-test-secret"
    s["smtp_password"] = "unique-mail-secret"
    assert client.put("/api/settings", json=s).status_code == 200
    data = client.get("/api/state").json()
    assert (
        "unique-test-secret" not in json.dumps(data)
        and data["settings"]["ai_key_configured"]
    )
    assert (
        b"unique-test-secret"
        not in (app.state.store.directory / "assistant.sqlite3").read_bytes()
    )
    s["ai_key"] = ""
    s["smtp_password"] = ""
    client.put("/api/settings", json=s)
    assert app.state.engine.settings()["ai_key"] == "unique-test-secret"
    assert (
        client.post("/api/settings/clear-secret", json={"name": "ai_key"}).status_code
        == 200
    )
    assert app.state.engine.settings()["ai_key"] == ""


def test_counters_atomic_and_persistent(app):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: app.state.store.reserve("sends", "2026-11-20", 3), range(12)
            )
        )
    assert (
        sum(results) == 3
        and Store(app.state.store.directory).count("sends", "2026-11-20") == 3
    )


def test_ssrf_and_unlisted_sources_blocked(monkeypatch):
    with pytest.raises(ValueError, match="não autorizado"):
        public_fetch("https://example.com", [])
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))]
    )
    with pytest.raises(ValueError, match="privada"):
        public_fetch("https://example.com", ["example.com"])
    with pytest.raises(ValueError):
        public_fetch("http://127.0.0.1", [])


def test_jobposting_parser_requires_area_review():
    html = (
        '<script type="application/ld+json">'
        + json.dumps(
            {
                "@type": "JobPosting",
                "title": "Desenvolvedor Python",
                "hiringOrganization": {"name": "Empresa"},
                "description": "Desenvolver APIs com Python em equipe.",
                "jobLocationType": "TELECOMMUTE",
            }
        )
        + "</script>"
    )
    result = read_source(html, "https://example.com/vaga")
    assert result[0]["area"] == "Desenvolvimento" and not result[0]["area_reviewed"]


def test_email_requires_explicit_instruction(job):
    assert email_eligible(job)
    job["recipient"] = "other@example.com"
    assert not email_eligible(job)
    job["description"] = "Contato: other@example.com. Somos uma empresa de tecnologia."
    assert not email_eligible(job)


def test_followup_is_only_a_suggestion(job):
    message = EmailMessage()
    message["Subject"] = "Entrevista"
    message["In-Reply-To"] = "<original@local>"
    message.set_content("Convite para entrevista.")
    result = parse_followup(
        message.as_bytes(),
        [{**job, "id": "j1", "status": "sent", "message_id": "<original@local>"}],
    )
    assert (
        result["candidates"] == ["j1"]
        and result["suggested_status"] == "interview"
        and not result["confirmed"]
    )


def test_missing_encryption_key_not_regenerated(app):
    (app.state.store.directory / "vault.key").unlink()
    with pytest.raises(RuntimeError, match="Chave"):
        Store(app.state.store.directory)


def test_ai_error_and_budget(app, settings, monkeypatch):
    import httpx

    def fail(*a, **k):
        raise httpx.ConnectError("do not leak private provider detail")

    monkeypatch.setattr(httpx.Client, "post", fail)
    settings["ai_daily_limit"] = 1
    with pytest.raises(ValueError, match="conectar ao Ollama"):
        AI(app.state.store).call(settings, "test", {})
    with pytest.raises(ValueError, match="Limite"):
        AI(app.state.store).call(settings, "test", {})


def test_rate_limit_login(client):
    client.post("/api/logout")
    for _ in range(10):
        assert (
            client.post("/api/login", json={"password": "wrong-password"}).status_code
            == 401
        )
    assert (
        client.post(
            "/api/login", json={"password": "test-only-password-123"}
        ).status_code
        == 429
    )


def test_restart_recovers_inflight_without_retry(app, prepared):
    j = app.state.engine.require_job(prepared)
    j["status"] = "sending"
    app.state.store.put("jobs", j, prepared)
    app.state.store.put(
        "runs", {"id": "interrupted", "status": "running", "errors": []}, "interrupted"
    )
    recovered = Engine(app.state.store)
    recovered.recover()
    assert recovered.require_job(prepared)["status"] == "uncertain"
    assert app.state.store.get("runs", "interrupted")["status"] == "failed"


def test_actual_ai_protocol(app, settings, profile, job, analysis, monkeypatch):
    import httpx

    original_client = httpx.Client
    observed = []

    def handler(request):
        payload = json.loads(request.content)
        observed.append(payload)
        assert request.url.path == "/v1/chat/completions"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["model"] == "modelo-de-teste"
        assert "smtp_password" not in request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(analysis)}}]}
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    raw = AI(app.state.store).analyze(settings, profile, job)
    assert validate_analysis(raw, profile, job)["score"] == 100 and len(observed) == 1


def test_source_refuses_non_brazil_jobposting():
    html = (
        '<script type="application/ld+json">'
        + json.dumps(
            {
                "@type": "JobPosting",
                "title": "Software developer",
                "hiringOrganization": {"name": "Company"},
                "description": "Develop software systems and services.",
                "jobLocation": {"address": {"addressCountry": "US"}},
            }
        )
        + "</script>"
    )
    with pytest.raises(ValueError):
        read_source(html, "https://example.com/job")


def test_offline_password_reset_invalidates_sessions(app, client):
    app.state.store.create_password("new-local-password", replace=True)
    assert client.get("/api/state").status_code == 401
    assert (
        client.post("/api/login", json={"password": "new-local-password"}).status_code
        == 200
    )


def test_email_custom_instructions_or_negation_need_assistance(job):
    job["description"] += " Informe no assunto o código da vaga."
    assert not email_eligible(job)
    job["description"] = "Não envie seu currículo para vagas@example.com; use o portal."
    assert not email_eligible(job)
    job["description"] = "Vaga encerrada. Envie seu currículo para vagas@example.com."
    assert not email_eligible(job)
