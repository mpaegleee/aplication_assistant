import copy

import pytest
from assistant.ai import AI
from assistant.portal_discovery import extract_record
from assistant.worklist import worklist


def install(app, profile, settings, job, analysis, monkeypatch):
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    monkeypatch.setattr(AI, "analyze", lambda *args: copy.deepcopy(analysis))
    id = app.state.engine.add_job(job)[0]["id"]
    app.state.engine.analyze(id)
    return id


def test_manual_schedule_consolidates_without_any_send(
    app, profile, settings, job, analysis, monkeypatch
):
    settings.update(mode="manual", sources=[])
    id = install(app, profile, settings, job, analysis, monkeypatch)
    monkeypatch.setattr(
        "assistant.engine.smtp_send",
        lambda *args: pytest.fail("Manual mode sent an email"),
    )
    app.state.engine.run()
    run = app.state.store.all("runs")[0]
    assert (
        run["action"] == "collect"
        and run["consolidated"] == 1
        and run["sent"] == 0
        and run["pending"] == 0
    )
    saved = app.state.store.get("jobs", id)
    assert saved["status"] == "ready" and not saved.get("resume_snapshot")
    assert saved["pending_code"] == "manual_ready"
    assert worklist(profile, settings, [saved])["summary"]["eligible"] == 1


def test_collect_only_overrides_automatic_then_apply_uses_same_queue(
    app, profile, settings, job, analysis, monkeypatch
):
    settings["mode"] = "automatic"
    id = install(app, profile, settings, job, analysis, monkeypatch)
    calls = []
    monkeypatch.setattr(
        "assistant.engine.smtp_send", lambda *args: calls.append("sent")
    )
    app.state.engine.run("collect")
    assert not calls and app.state.store.all("runs")[0]["consolidated"] == 1
    app.state.engine.run("apply")
    assert calls == ["sent"] and app.state.store.get("jobs", id)["status"] == "sent"
    app.state.engine.run("apply")
    assert calls == ["sent"]


def test_worklist_invalidates_stale_analysis_and_blocks_bad_fit(
    app, profile, settings, job, analysis, monkeypatch
):
    id = install(app, profile, settings, job, analysis, monkeypatch)
    saved = app.state.store.get("jobs", id)
    assert worklist(profile, settings, [saved])["items"][0]["job_id"] == id
    changed = {**profile, "phone": "48999990000"}
    assert worklist(changed, settings, [saved])["summary"]["stale"] == 1
    changed = {**profile, "areas": ["Financeiro"]}
    assert worklist(changed, settings, [saved])["summary"]["blocked"] == 1
    saved["archived"] = True
    assert worklist(profile, settings, [saved])["summary"]["archived"] == 1


def test_archive_excludes_scheduled_and_direct_send(
    app, client, profile, settings, job, analysis, monkeypatch
):
    id = install(app, profile, settings, job, analysis, monkeypatch)
    assert (
        client.post(f"/api/jobs/{id}/archive", json={"archived": True}).status_code
        == 200
    )
    assert client.get("/api/state").json()["worklist"]["summary"]["archived"] == 1
    app.state.engine.run()
    assert app.state.store.all("runs")[0]["items"] == []
    assert client.post(f"/api/jobs/{id}/approve").status_code == 400
    assert client.post(f"/api/jobs/{id}/send").status_code == 400
    assert (
        client.post(f"/api/jobs/{id}/archive", json={"archived": False}).status_code
        == 200
    )
    assert client.get("/api/state").json()["worklist"]["summary"]["eligible"] == 1


def test_run_endpoint_accepts_collect_action(app, client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        app.state.engine, "start_run", lambda action: calls.append(action)
    )
    assert client.post("/api/runs", json={"action": "collect"}).status_code == 200
    assert client.post("/api/runs", json={"action": "send-all"}).status_code == 422
    assert calls == ["collect"]


def raw_post():
    return {
        "platform": "linkedin",
        "kind": "post",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:123/",
        "text": 'Vaga Desenvolvedor Python na Empresa Teste. Remoto, Brasil. Desenvolver APIs em Python. Envie seu currículo para vagas@example.com\nAssunto: "Python Brasil"',
        "links": [{"url": "https://empresa.gupy.io/jobs/123", "label": "Candidate-se"}],
    }


def extracted():
    return {
        "is_job": True,
        "title": "Desenvolvedor Python",
        "company": "Empresa Teste",
        "modality": "Remoto",
        "location": "Brasil",
        "contract": "",
        "application_url": "https://empresa.gupy.io/jobs/123",
    }


def test_post_extract_preserves_text_email_subject_and_caches(
    app, settings, monkeypatch
):
    calls = []

    def call(self, *args):
        calls.append(1)
        return extracted()

    monkeypatch.setattr(AI, "call", call)
    raw = raw_post()
    first = extract_record(app.state.store, settings, raw)
    assert first["description"] == raw["text"] and first["application_url"].endswith(
        "/jobs/123"
    )
    assert extract_record(app.state.store, settings, raw) == first and len(calls) == 1
    job, _ = app.state.engine.add_job(first)
    assert (
        job["recipient"] == "vagas@example.com"
        and job["email_subject"] == "Python Brasil"
    )
    assert job["source"] == "linkedin_post"
    modified = extracted()
    modified.update(
        company="Invented Inc",
        location="Lisboa",
        application_url="https://evil.example/not-present",
    )
    monkeypatch.setattr(AI, "call", lambda *args: modified)
    second = extract_record(app.state.store, {**settings, "ai_model": "other"}, raw)
    assert (
        second["company"] == "Empresa não informada"
        and second["country"] == "unknown"
        and second["application_url"] == ""
    )


def test_portal_selected_queries_and_posts_flow_without_sending(
    app, profile, settings, analysis, monkeypatch
):
    settings.update(
        mode="manual",
        auto_classify_areas=True,
        search_platforms=["linkedin"],
        browser_search_queries=["Python"],
        linkedin_posts_enabled=True,
    )
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    calls = []

    def records(settings, platform, query="", source_url=None):
        calls.append((platform, query))
        return [raw_post()]

    monkeypatch.setattr(app.state.engine, "portal_records", records)
    monkeypatch.setattr(AI, "call", lambda *args: extracted())
    monkeypatch.setattr(AI, "analyze", lambda *args: copy.deepcopy(analysis))
    monkeypatch.setattr(
        "assistant.engine.smtp_send",
        lambda *args: pytest.fail("Discovery submitted an application"),
    )
    app.state.engine.run("collect")
    run = app.state.store.all("runs")[0]
    assert calls == [("linkedin", "Python")]
    assert (
        run["found"] == run["eligible"] == run["consolidated"] == 1 and run["sent"] == 0
    )
    assert app.state.store.all("jobs")[0]["origins"][0]["kind"] == "post"


def test_experimental_portal_submission_requires_flag_and_records_receipt(
    app, profile, settings, job, analysis, monkeypatch
):
    import asyncio

    job.update(
        url="https://empresa.gupy.io/jobs/123",
        application_url="https://empresa.gupy.io/jobs/123",
        recipient="",
        description="Desenvolver APIs em Python em equipe.",
    )
    settings.update(mode="automatic", allowed_destinations=["gupy"])
    id = install(app, profile, settings, job, analysis, monkeypatch)
    assert (
        app.state.engine.process(app.state.engine.require_job(id))
        == "experimental_disabled"
    )

    class Browser:
        def call(self, coro, **kwargs):
            return asyncio.run(coro)

        async def wizard(
            self, platform, url, profile, pdf, submit, intent, job_id=None
        ):
            assert platform == "gupy" and submit and pdf.startswith(b"%PDF")
            intent()
            return {
                "status": "confirmed",
                "reason": "Confirmação de fixture",
                "proof": b"PNG-fixture".hex(),
            }

    app.state.engine.browser = Browser()
    settings["experimental_portal_submission"] = True
    app.state.store.put("settings", settings)
    assert app.state.engine.process(app.state.engine.require_job(id)) == "sent"
    saved = app.state.engine.require_job(id)
    assert saved["destination"] == "gupy" and saved["status"] == "receipt"
    assert saved["browser_attempt"] and saved["resume_snapshot"]
