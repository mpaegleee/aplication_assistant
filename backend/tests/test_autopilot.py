import copy, json
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import pytest
from assistant.ai import AI
from assistant.history import metrics, record_stage
from assistant.mail import email_eligible, prepare_delivery, build_email, parse_followup
from assistant.mail_sync import sync_mail, apply_suggestion
from assistant.models import Settings
from assistant.sources import read_board


def install(app, profile, settings, monkeypatch):
    settings.update(
        mode="automatic", auto_classify_areas=True, threshold=85, interval_seconds=5
    )
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    monkeypatch.setattr(app.state.engine.stop, "wait", lambda delay: False)


def test_twelve_found_seven_eligible_sent_and_next_run_does_not_repeat(
    app, profile, settings, job, analysis, monkeypatch
):
    settings.update(
        sources=[
            {
                "name": "Fonte controlada",
                "url": "https://example.com/feed",
                "enabled": True,
            }
        ],
        allowed_domains=["example.com"],
    )
    install(app, profile, settings, monkeypatch)
    rows = []
    for i in range(12):
        rows.append(
            {
                **job,
                "title": f"Desenvolvedor Python {i}",
                "company": f"Empresa {i}",
                "url": f"https://example.com/jobs/{i}",
                "description": f'Desenvolver APIs Python. Envie seu currículo para vaga{i}@example.com\nAssunto: "Desenvolvedor Sênior {i}"',
                "recipient": "",
            }
        )
    monkeypatch.setattr("assistant.engine.public_fetch", lambda *args: json.dumps(rows))
    calls = []
    sent = []

    def analyze(*args):
        j = args[-1]
        calls.append(j["id"])
        result = copy.deepcopy(analysis)
        if int(j["company"].split()[-1]) >= 7:
            for criterion in result["criteria"].values():
                criterion["grade"] = 0
        return result

    monkeypatch.setattr(AI, "analyze", analyze)
    monkeypatch.setattr("assistant.engine.smtp_send", lambda s, m: sent.append(m))
    app.state.engine.run()
    run = app.state.store.all("runs")[0]
    assert (
        run["found"],
        run["imported"],
        run["analyzed"],
        run["eligible"],
        run["sent"],
        run["pending"],
    ) == (12, 12, 12, 7, 7, 5)
    assert run["status"] == "completed" and len(run["items"]) == 12
    assert len(sent) == 7 and all(
        m.get_payload()[1].get_content_type() == "application/pdf" for m in sent
    )
    assert {str(m["Subject"]) for m in sent} == {
        f"Desenvolvedor Sênior {i}" for i in range(7)
    }
    assert metrics(app.state.store, app.state.engine.settings())["applied"] == 7
    app.state.engine.run()
    assert len(calls) == 12 and len(sent) == 7
    second = app.state.store.all("runs")[0]
    assert second["duplicates"] == 12 and second["sent"] == 0


def test_disabled_search_does_not_fetch_or_use_ai(app, profile, settings, monkeypatch):
    settings.update(
        search_platforms=["linkedin"],
        sources=[{"name": "Fonte", "url": "https://example.com/feed", "enabled": True}],
    )
    install(app, profile, settings, monkeypatch)
    monkeypatch.setattr(
        "assistant.engine.public_fetch",
        lambda *args: pytest.fail("Disabled source fetched"),
    )
    monkeypatch.setattr(
        AI, "analyze", lambda *args: pytest.fail("Disabled source spent AI")
    )
    app.state.engine.run()
    run = app.state.store.all("runs")[0]
    assert (
        run["found"] == 0
        and run["sent"] == 0
        and any("LinkedIn" in e for e in run["errors"])
    )


def test_ats_destination_not_misrepresented_as_sent(app, prepared):
    engine = app.state.engine
    j = engine.require_job(prepared)
    j.update(
        recipient="",
        description="Desenvolver APIs em Python em equipe.",
        application_url="https://empresa.gupy.io/jobs/123",
    )
    app.state.store.put("jobs", j, prepared)
    settings = engine.settings()
    settings["allowed_destinations"] = ["gupy"]
    settings["mode"] = "automatic"
    app.state.store.put("settings", settings)
    assert engine.process(j) == "connector_unavailable"
    latest = engine.require_job(prepared)
    assert (
        latest["destination"] == "gupy"
        and latest["status"] != "sent"
        and latest["pending_reason"]
    )


def test_external_destinations_are_distinct_from_search_permission(app, prepared):
    settings = app.state.engine.settings()
    settings["allowed_destinations"] = []
    app.state.store.put("settings", settings)
    assert (
        app.state.engine.process(app.state.engine.require_job(prepared))
        == "destination_disabled"
    )


def test_job_dedup_by_application_destination_preserves_origins(app, job):
    first = {
        **job,
        "url": "https://www.linkedin.com/posts/test",
        "application_url": "https://empresa.gupy.io/jobs/123",
    }
    second = {
        **job,
        "url": "https://www.indeed.com/viewjob?jk=abc",
        "application_url": "https://empresa.gupy.io/jobs/123",
    }
    j, new = app.state.engine.add_job(first)
    j2, new2 = app.state.engine.add_job(second)
    assert new and not new2 and j["id"] == j2["id"] and len(j2["origins"]) == 2


def test_area_rules_reject_sales_before_model(app, profile, settings, job, monkeypatch):
    install(app, profile, settings, monkeypatch)
    job.update(title="Vendedor comercial", area="", area_reviewed=False)
    monkeypatch.setattr(
        AI, "analyze", lambda *args: pytest.fail("Wrong profession reached AI")
    )
    j, _ = app.state.engine.add_job(job)
    assert app.state.engine.process(j) == "blocked"


def test_email_subject_must_be_literal_and_bounded(job, profile, settings):
    job["description"] = (
        'Desenvolver APIs Python. Envie seu currículo para vagas@example.com\nAssunto: "Desenvolvedor Sênior"'
    )
    prepared = prepare_delivery(job)
    assert prepared["email_subject"] == "Desenvolvedor Sênior" and email_eligible(
        prepared
    )
    assert (
        str(
            build_email(settings, profile, prepared, b"%PDF", "<test@local>")["Subject"]
        )
        == "Desenvolvedor Sênior"
    )
    prepared["email_subject"] = "Invented"
    assert not email_eligible(prepared)
    job["description"] = "Envie currículo para vagas@example.com. Assunto: {seu nome}"
    assert not email_eligible(prepare_delivery(job))


def test_multiple_recipients_require_review(job):
    job["description"] = (
        "Envie seu currículo para vagas@example.com ou outro@example.com."
    )
    assert not email_eligible(prepare_delivery(job))
    job["instructions_reviewed"] = True
    assert email_eligible(prepare_delivery(job))


def test_metric_cohort_counts_current_technical_and_manager_stages(app, job):
    for i, status in enumerate(["technical", "manager_interview", "receipt"]):
        j = {
            **job,
            "id": str(i),
            "status": "sent",
            "destination": "email",
            "message_id": str(i),
        }
        record_stage(j, "sent", "smtp")
        record_stage(j, status, "manual")
        app.state.store.put("jobs", j, j["id"])
    old = {
        **job,
        "id": "old",
        "status": "technical",
        "sent_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
    }
    app.state.store.put("jobs", old, "old")
    result = metrics(app.state.store, app.state.engine.settings())
    assert result["applied"] == 3 and result["responses"] == 3
    assert (
        result["current"]["technical"] == 1
        and result["current"]["manager_interview"] == 1
    )


def reply(job, subject="Teste técnico"):
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = job["recipient"]
    m["In-Reply-To"] = job["message_id"]
    m["Message-ID"] = "<reply@local>"
    m.set_content("Você avançou. " + subject)
    return m.as_bytes()


def test_followup_auto_requires_exact_thread_and_sender_and_never_regresses(
    app, prepared
):
    j = app.state.engine.require_job(prepared)
    j.update(status="sent", message_id="<original@local>")
    record_stage(j, "sent", "smtp")
    app.state.store.put("jobs", j, prepared)
    suggestion = parse_followup(reply(j), [j])
    assert apply_suggestion(app.state.store, suggestion, True)
    assert app.state.engine.require_job(prepared)["status"] == "technical"
    latest = app.state.engine.require_job(prepared)
    late = parse_followup(reply(latest, "Recebemos sua candidatura"), [latest])
    assert not apply_suggestion(app.state.store, late, True)
    foreign = parse_followup(reply(latest, "Entrevista com gestor"), [latest])
    foreign["from"] = "unknown@example.com"
    assert not apply_suggestion(app.state.store, foreign, True)


def test_imap_reads_peek_and_deduplicates_without_marking_read(
    app, prepared, settings, monkeypatch
):
    j = app.state.engine.require_job(prepared)
    j.update(status="sent", message_id="<original@local>")
    app.state.store.put("jobs", j, prepared)
    content = reply(j)
    operations = []

    class Mailbox:
        def __init__(self, *args, **kwargs):
            pass

        def login(self, *args):
            pass

        def select(self, folder, readonly):
            assert readonly
            return "OK", []

        def response(self, key):
            return key, [b"999"]

        def uid(self, operation, *args):
            operations.append((operation, args))
            if operation == "search":
                return "OK", [b"1"]
            if args[-1] == "(RFC822.SIZE)":
                return "OK", [f"1 (RFC822.SIZE {len(content)})".encode()]
            assert args[-1] == "(BODY.PEEK[])"
            return "OK", [(b"1", content)]

        def logout(self):
            pass

    monkeypatch.setattr("assistant.mail_sync.imaplib.IMAP4_SSL", Mailbox)
    settings.update(
        imap_enabled=True,
        imap_host="imap.example.com",
        imap_user="user@example.com",
        imap_password="test-only",
        auto_followup=True,
    )
    first = sync_mail(app.state.store, settings, app.state.engine.lock)
    second = sync_mail(app.state.store, settings, app.state.engine.lock)
    assert first["imported"] == 1 and first["updated"] == 1 and second["imported"] == 0
    assert app.state.engine.require_job(prepared)["status"] == "technical"
    assert len(app.state.store.all("followups")) == 1


def test_imap_secret_redaction_and_endpoint_binding(app, client):
    s = app.state.engine.settings()
    s.update(
        imap_host="imap.example.com",
        imap_user="test@example.com",
        imap_password="imap-secret-test",
    )
    assert client.put("/api/settings", json=s).status_code == 200
    state = client.get("/api/state").json()
    assert (
        state["settings"]["imap_password"] == ""
        and state["settings"]["imap_password_configured"]
    )
    assert "imap-secret-test" not in json.dumps(state)
    s.update(imap_host="different.example.com", imap_password="")
    client.put("/api/settings", json=s)
    assert app.state.engine.settings()["imap_password"] == ""


def test_reusable_answers_are_excluded_from_ai_prompt(
    app, settings, profile, job, analysis, monkeypatch
):
    import httpx

    original = httpx.Client
    profile["answers"] = [{"question": "CPF", "answer": "sensitive-test-identifier"}]

    def handler(request):
        assert "sensitive-test-identifier" not in request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(analysis)}}]}
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    AI(app.state.store).analyze(settings, profile, job)


def test_read_only_board_adapters(job):
    greenhouse = json.dumps(
        {
            "jobs": [
                {
                    "title": "Desenvolvedor Python",
                    "absolute_url": "https://job-boards.greenhouse.io/test/jobs/123",
                    "content": "Desenvolver APIs Python em equipe.",
                    "location": {"name": "Remoto Brasil"},
                }
            ]
        }
    )
    rows = read_board(greenhouse, {"kind": "greenhouse", "name": "Empresa"})
    assert (
        len(rows) == 1
        and rows[0]["modality"] == "Remoto"
        and not rows[0]["area_reviewed"]
    )
    lever = json.dumps(
        [
            {
                "text": "Desenvolvedor Python",
                "hostedUrl": "https://jobs.lever.co/test/123",
                "applyUrl": "https://jobs.lever.co/test/123/apply",
                "descriptionPlain": "Desenvolver APIs Python em equipe.",
                "categories": {"location": "Brasil"},
                "workplaceType": "remote",
            }
        ]
    )
    assert read_board(lever, {"kind": "lever", "name": "Empresa"})[0][
        "application_url"
    ].endswith("/apply")


def test_profile_rewriting_is_a_draft_never_silently_applied(
    app, client, profile, settings, monkeypatch
):
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    monkeypatch.setattr(
        AI,
        "call",
        lambda *args: {
            "facts": [
                {"id": "f1", "text": "Atuei no desenvolvimento de APIs com Python."}
            ]
        },
    )
    result = client.post("/api/profile/improve")
    assert result.status_code == 200 and not result.json()["confirmed"]
    assert app.state.engine.profile() == profile
    assert result.json()["facts"][0]["evidence"] == profile["facts"][0]["text"]


def test_profile_rewriting_rejects_invented_metrics(
    app, profile, settings, monkeypatch
):
    monkeypatch.setattr(
        AI,
        "call",
        lambda *args: {
            "facts": [{"id": "f1", "text": "Aumentei o desempenho em 90%."}]
        },
    )
    with pytest.raises(ValueError, match="números"):
        AI(app.state.store).improve_profile(settings, profile)


def test_bad_feed_entry_does_not_drop_other_valid_jobs(job):
    from assistant.sources import read_source

    values = [{"title": "invalid"}, {**job, "country": "US"}, job]
    result = read_source(json.dumps(values), "https://example.com/feed")
    assert len(result) == 1 and result[0]["title"] == job["title"]


def test_known_destination_urls_are_normalized_for_dedup(app, job):
    from assistant.sources import application_identity

    assert application_identity(
        "https://jobs.lever.co/company/uuid/apply"
    ) == application_identity("https://jobs.lever.co/company/uuid")
    first = {
        **job,
        "url": "https://origin.example/job/1",
        "application_url": "https://company.gupy.io/jobs/123",
    }
    second = {
        **job,
        "url": "https://different.example/job/1",
        "application_url": "https://portal.gupy.io/jobs/123?utm_source=test",
    }
    one, new = app.state.engine.add_job(first)
    two, new2 = app.state.engine.add_job(second)
    assert new and not new2 and one["id"] == two["id"]


def test_final_send_checks_duplicate_destination_after_edit(app, prepared, monkeypatch):
    first = app.state.engine.require_job(prepared)
    first.update(application_url="https://company.gupy.io/jobs/123")
    app.state.store.put("jobs", first, prepared)
    app.state.engine.analyze(prepared)
    app.state.engine.approve(prepared)
    monkeypatch.setattr("assistant.engine.smtp_send", lambda *args: None)
    app.state.engine.send(prepared)
    second = copy.deepcopy(first)
    second.update(
        id="second-id",
        url="https://another.example/job/1",
        status="ready",
        application_url="https://portal.gupy.io/jobs/123",
    )
    app.state.store.put("jobs", second, "second-id")
    with pytest.raises(ValueError, match="Já existe candidatura"):
        app.state.engine.send("second-id")


def test_manual_analysis_can_be_forced_without_disabling_worker_cache(
    app, prepared, monkeypatch, analysis
):
    calls = []
    monkeypatch.setattr(
        AI, "analyze", lambda *args: calls.append(1) or copy.deepcopy(analysis)
    )
    app.state.engine.analyze(prepared)
    assert not calls
    app.state.engine.analyze(prepared, force=True)
    assert calls == [1]
