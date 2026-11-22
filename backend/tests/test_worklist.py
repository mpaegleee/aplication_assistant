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
    app.state.store.put("browser_sessions", {"saved_at": "test"}, "linkedin")
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


def test_automatic_queue_reaches_older_jobs(
    app, profile, settings, job, analysis, monkeypatch
):
    settings.update(mode="manual", max_jobs_per_run=1, search_platforms=["company"])
    first = install(app, profile, settings, job, analysis, monkeypatch)
    second = app.state.engine.add_job(
        {**job, "url": "https://example.com/jobs/python"}
    )[0]["id"]
    for expected in (second, first):
        app.state.engine.run()
        assert app.state.store.all("runs")[0]["items"][0]["job_id"] == expected


def test_saved_answer_variants_require_consistent_explicit_answers():
    from assistant.portal_forms import answer_for

    profile = {
        "answers": [{"question": "Pretensão salarial como CLT", "answer": "9000"}]
    }
    assert answer_for("Qual sua pretensão salarial CLT?*", profile) == "9000"
    assert answer_for("Qual sua última remuneração?", profile) is None
    profile["answers"].append({"question": "Pretensão salarial CLT", "answer": "8000"})
    assert answer_for("Qual sua pretensão salarial CLT?", profile) is None


def test_structured_country_from_html_escaped_gupy_posting():
    from assistant.portal_discovery import posting_country
    import html
    import json

    def script(country):
        return html.escape(
            json.dumps(
                {
                    "@type": "JobPosting",
                    "jobLocation": {"address": {"addressCountry": country}},
                }
            )
        )

    assert posting_country([script("Brasil")]) == "BR"
    assert posting_country([script("Brasil"), script("Portugal")]) == "unknown"


def test_scoped_portal_authorization_respects_domain_refusal():
    from assistant.portal_forms import share_authorized

    profile = {
        "authorized_portal": "gupy",
        "answers": [
            {"question": "Autorizar envio de dados para b.gupy.io", "answer": "Não"}
        ],
    }
    assert share_authorized("https://a.gupy.io/jobs/123", profile)
    assert not share_authorized("https://b.gupy.io/jobs/123", profile)
    assert not share_authorized("https://www.linkedin.com/jobs/123", profile)


def test_agile_project_titles_have_distinct_area():
    from assistant.matching import infer_area

    for title in [
        "Agile Master I (Remote)",
        "Scrum Master - Presencial",
        "Especialista em Governança de Projetos (PMO)",
    ]:
        assert infer_area(title) == "Projetos e Agilidade"
    assert not infer_area("Scrum Master e Desenvolvedor")


def test_late_schedule_starts_once_even_after_busy_tick(app, settings, monkeypatch):
    import datetime
    from unittest.mock import Mock

    class Clock(datetime.datetime):
        @classmethod
        def now(cls, zone):
            return cls(2026, 11, 23, 11, 0, tzinfo=zone)

    settings.update(schedule_enabled=True, weekdays=[0], time="09:00")
    app.state.store.put("settings", settings)
    engine = app.state.engine
    monkeypatch.setattr("assistant.engine.datetime", Clock)
    monkeypatch.setattr(
        engine.stop, "wait", Mock(side_effect=[False, False, False, True])
    )
    start = Mock(side_effect=[ValueError("busy"), None])
    monkeypatch.setattr(engine, "start_run", start)
    engine.scheduler()
    assert start.call_count == 2
    assert app.state.store.get("schedule")["last"].startswith("2026-11-23 09:00")


def test_collect_now_works_while_paused_without_sending(
    app, client, profile, settings, job, analysis, monkeypatch
):
    settings.update(paused=True, mode="automatic")
    key = install(app, profile, settings, job, analysis, monkeypatch)
    engine = app.state.engine
    monkeypatch.setattr(
        "assistant.engine.smtp_send", lambda *a: pytest.fail("Unexpected send")
    )
    assert client.post("/api/runs", json={"action": "apply"}).status_code == 400
    response = client.post("/api/runs", json={"action": "collect"})
    assert response.status_code == 200
    engine.thread.join(timeout=5)
    run = app.state.store.all("runs")[0]
    assert run["status"] == "completed"
    assert run["consolidated"] == 1 and run["sent"] == 0
    assert engine.require_job(key)["pending_code"] == "manual_ready"
    assert engine.settings()["paused"]


def test_stale_and_expired_records_are_skipped_before_ai(app, settings, monkeypatch):
    from datetime import date, timedelta

    engine = app.state.engine
    today = date.today()
    spec = {**settings, "max_job_age_days": 7, "include_undated_jobs": False}
    monkeypatch.setattr(
        "assistant.portal_discovery.extract_record",
        lambda *a: pytest.fail("Paid extraction of filtered vacancy"),
    )
    run = {"found": 0, "errors": []}
    entry = {"found": 0}
    engine.import_portal_records(
        [
            {"published_at": (today - timedelta(days=90)).isoformat()},
            {
                "published_at": today.isoformat(),
                "valid_until": (today - timedelta(days=2)).isoformat(),
            },
            {},
        ],
        spec,
        run,
        entry,
        set(),
        lambda: False,
    )
    assert run["found"] == run["skipped_age"] == 3


def test_public_job_dates_can_be_parsed_without_ai():
    from assistant.portal_discovery import structured_dates
    from assistant.sources import read_source

    data = structured_dates(
        [
            '{"@type":"JobPosting","datePosted":"2026-10-01","validThrough":"2026-10-31"}'
        ],
        {"text": "Publicado em 01 de outubro de 2026"},
    )
    assert data == {"published_at": "2026-10-01", "valid_until": "2026-10-31"}
    rss = """<rss><channel><item><title>Desenvolvedor Python</title>
      <link>https://empresa.example.com/jobs/p</link>
      <description>Vaga de desenvolvimento de software.</description>
      <pubDate>Thu, 01 Oct 2026 12:00:00 GMT</pubDate>
      </item></channel></rss>"""
    assert (
        read_source(rss, "https://empresa.example.com/feed")[0]["published_at"]
        == "2026-10-01"
    )


def test_missing_portal_sessions_are_reported_once_before_collecting(
    app, client, settings, monkeypatch
):
    settings.update(
        paused=True,
        search_platforms=["linkedin", "indeed"],
        browser_search_queries=["Python", "Agilidade", "PMO"],
    )
    app.state.store.put("settings", settings)
    engine = app.state.engine
    monkeypatch.setattr(
        engine,
        "portal_records",
        lambda *a: pytest.fail("Browser must not open without a session"),
    )
    assert set(client.get("/api/state").json()["search_portal_issues"]) == {
        "linkedin",
        "indeed",
    }
    engine.run("collect")
    run = app.state.store.all("runs")[0]
    assert run["status"] == "blocked" and run["found"] == 0
    assert len(run["errors"]) == 2
    assert [entry["platform"] for entry in run["sources"]] == ["linkedin", "indeed"]


def test_one_connected_portal_is_enough_to_collect(
    app, profile, settings, analysis, monkeypatch
):
    settings.update(
        search_platforms=["linkedin", "indeed"], browser_search_queries=["Python"]
    )
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    app.state.store.put("browser_sessions", {"saved_at": "test"}, "linkedin")
    engine = app.state.engine
    checked = []

    def records(_, platform, query):
        checked.append(platform)
        return [raw_post()]

    monkeypatch.setattr(engine, "portal_records", records)
    monkeypatch.setattr(AI, "call", lambda *args: extracted())
    monkeypatch.setattr(AI, "analyze", lambda *args: copy.deepcopy(analysis))
    engine.run("collect")
    run = app.state.store.all("runs")[0]
    assert checked == ["linkedin"]
    assert run["found"] == 1 and run["sent"] == 0 and run["status"] == "completed"
    assert len(run["errors"]) == 1 and "Indeed" in run["errors"][0]


def test_public_gupy_collects_profile_matches_without_browser_session(
    app, client, profile, settings, analysis, monkeypatch
):
    import json
    from datetime import date, timedelta
    from urllib.parse import unquote

    profile["roles"] = ["Desenvolvedor Python"]
    settings.update(
        mode="automatic",
        search_platforms=["gupy"],
        allowed_destinations=["gupy"],
        sources=[],
        auto_classify_areas=True,
        max_job_age_days=15,
    )
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    assert client.get("/api/state").json()["configured_sources"] == ["gupy"]
    today = date.today()
    job_url = "https://empresa.gupy.io/jobs/123"
    cards = [
        {
            "jobUrl": job_url,
            "publishedDate": today.isoformat(),
            "workplaceType": "remote",
        },
        {
            "jobUrl": "https://empresa.gupy.io/jobs/456",
            "publishedDate": (today - timedelta(days=20)).isoformat(),
        },
    ]
    posting = {
        "id": 123,
        "status": "published",
        "name": "Desenvolvedor Python",
        "description": "<p>Desenvolver APIs em Python em equipe.</p>",
        "prerequisites": "<p>Experiência com APIs REST.</p>",
        "careerPage": {"name": "Empresa Teste"},
        "addressCountryShortName": "BR",
    }

    def page(props):
        return (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps({"props": {"pageProps": props}})
            + "</script>"
        )

    def fetch(url, allowed):
        if url.startswith("https://portal.gupy.io/"):
            assert "term=Desenvolvedor Python&sortBy=publishedDate" in unquote(url)
            assert allowed == ["portal.gupy.io"]
            return page(
                {
                    "searchFilters": {"term": "Desenvolvedor Python"},
                    "initialJobList": {
                        "data": cards,
                        "pagination": {"total": 2, "limit": 12, "offset": 0},
                    },
                }
            )
        assert url == job_url and allowed == ["empresa.gupy.io"]
        return page({"job": posting})

    monkeypatch.setattr("assistant.gupy.public_fetch", fetch)
    monkeypatch.setattr(AI, "analyze", lambda *args: copy.deepcopy(analysis))
    monkeypatch.setattr(
        app.state.engine,
        "browser_apply",
        lambda *a, **kw: pytest.fail("Sent from collection"),
    )
    app.state.engine.run("collect")
    run = app.state.store.all("runs")[0]
    assert run["found"] == 2 and run["skipped_age"] == 1
    assert run["imported"] == run["eligible"] == 1 and not run["errors"]
    saved = app.state.store.all("jobs")[0]
    assert saved["url"] == job_url and saved["modality"] == "Remoto"
    assert saved["destination"] == "gupy" and saved["country"] == "BR"
    assert "Experiência com APIs REST." in saved["description"]
