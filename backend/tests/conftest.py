import pytest
from fastapi.testclient import TestClient
from assistant.api import create_app
from assistant.models import Profile, Settings, JobInput
from assistant.matching import WEIGHTS


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("AA_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    return create_app(tmp_path / "data", enable_scheduler=False)


@pytest.fixture
def client(app):
    with TestClient(app, headers={"x-aa-request": "1"}) as c:
        assert (
            c.post(
                "/api/setup", json={"password": "test-only-password-123"}
            ).status_code
            == 200
        )
        yield c


@pytest.fixture
def profile():
    return Profile(
        name="Pessoa Teste",
        email="pessoa@example.com",
        areas=["Desenvolvimento"],
        excluded_areas=["Financeiro"],
        roles=["Desenvolvedor Python"],
        facts=[{"id": "f1", "text": "Desenvolvi APIs em Python por três anos."}],
        confirmed=True,
    ).model_dump()


@pytest.fixture
def settings():
    return Settings(
        paused=False,
        ai_consent=True,
        ai_model="modelo-de-teste",
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from="pessoa@example.com",
    ).model_dump()


@pytest.fixture
def job():
    return JobInput(
        title="Desenvolvedor Python",
        company="Empresa Teste",
        description="Desenvolver APIs em Python. Envie seu currículo para vagas@example.com",
        area="Desenvolvimento",
        area_reviewed=True,
        modality="Remoto",
        recipient="vagas@example.com",
    ).model_dump()


@pytest.fixture
def analysis():
    return {
        "criteria": {
            key: {
                "grade": 100,
                "fact_ids": ["f1"],
                "job_quote": "Python",
                "reason": "Correspondência com APIs Python.",
            }
            for key in WEIGHTS
        },
        "confidence": 95,
        "resume_fact_ids": ["f1"],
        "gaps": "",
    }


@pytest.fixture
def prepared(app, profile, settings, job, analysis, monkeypatch):
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    monkeypatch.setattr("assistant.ai.AI.analyze", lambda *args: analysis)
    j, _ = app.state.engine.add_job(job)
    app.state.engine.analyze(j["id"])
    return j["id"]
