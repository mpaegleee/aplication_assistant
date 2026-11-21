from email.message import EmailMessage

import pytest

from assistant.linkedin_alerts import ALERT_SENDER, parse_alert


def email_alert(sender=ALERT_SENDER):
    email = EmailMessage()
    email["From"] = sender
    email["Subject"] = "Seu alerta de vagas no LinkedIn"
    email.set_content("Alertas")
    email.add_alternative(
        """<table><tr><td>
        <a href="https://www.linkedin.com/comm/jobs/view/12345/?trk=private">Agile Coach</a>
        <div>Empresa Teste</div><div>Brasil (Remoto)</div>
        <a href="https://linkedin.com/jobs/view/12345?trackingId=private">Ver vaga</a>
        </td></tr><tr><td>
        <a href="https://www.linkedin.com/jobs/view/scrum-master-67890/">Scrum Master</a>
        <div>Empresa Dois</div><div>São Paulo, SP</div>
        </td></tr><tr><td>
        <a href="https://linkedin.com.evil.example/jobs/view/333">Link inválido</a>
        <a href="https://www.linkedin.com/jobs/search/?id=1234">Ver todas as vagas</a>
        </td></tr></table>""",
        subtype="html",
    )
    return email.as_bytes()


def test_extracts_only_canonical_vacancy_links_from_alert():
    rows = parse_alert(email_alert())
    assert [(row["url"], row["title"]) for row in rows] == [
        ("https://www.linkedin.com/jobs/view/12345", "Agile Coach"),
        ("https://www.linkedin.com/jobs/view/67890", "Scrum Master"),
    ]
    assert rows[0]["company"] == "Empresa Teste"
    assert rows[0]["country"] == "BR" and rows[0]["modality"] == "Remoto"
    assert rows[0]["published_at"] == ""
    assert rows[1]["source"] == "linkedin_alert"
    assert not parse_alert(email_alert("jobalerts-noreply@linkedin.com.example"))


def test_collect_uses_alerts_without_browser_and_keeps_full_postings(
    app, client, profile, settings, job, monkeypatch
):
    engine = app.state.engine
    settings.update(
        paused=True,
        mode="automatic",
        search_platforms=["linkedin"],
        linkedin_search_method="email",
        imap_enabled=False,
        imap_host="imap.example.com",
        imap_user="test@example.com",
        imap_password="test-only",
        max_jobs_per_run=1,
    )
    app.state.store.put("settings", settings)
    app.state.store.put("profile", profile)
    original, _ = engine.add_job(
        {**job, "url": "https://www.linkedin.com/jobs/view/12345", "archived": True}
    )
    content = email_alert()

    class Mailbox:
        def __init__(self, *args, **kwargs):
            pass

        def login(self, user, password):
            assert user == "test@example.com" and password == "test-only"

        def select(self, folder, readonly):
            assert readonly
            return "OK", []

        def response(self, key):
            return key, [b"100"]

        def uid(self, operation, *args):
            if operation == "search":
                assert args[-2:] == ("FROM", ALERT_SENDER)
                return "OK", [b"1"]
            if args[-1] == "(RFC822.SIZE)":
                return "OK", [f"1 (RFC822.SIZE {len(content)})".encode()]
            assert args[-1] == "(BODY.PEEK[])"
            return "OK", [(b"1", content)]

        def logout(self):
            pass

    monkeypatch.setattr("assistant.mail_sync.imaplib.IMAP4_SSL", Mailbox)
    monkeypatch.setattr(
        engine, "portal_records", lambda *a: pytest.fail("Opened browser")
    )
    monkeypatch.setattr(
        "assistant.ai.AI.analyze", lambda *a: pytest.fail("Analyzed preview")
    )

    assert client.get("/api/state").json()["search_portal_issues"] == {}
    engine.run("collect")
    run = app.state.store.all("runs")[0]
    assert (run["found"], run["imported"], run["duplicates"], run["sent"]) == (
        2,
        1,
        1,
        0,
    )
    assert engine.require_job(original["id"])["description"] == original["description"]
    imported = next(
        j for j in app.state.store.all("jobs") if j["source"] == "linkedin_alert"
    )
    assert imported["pending_code"] == "alert_review"
    assert app.state.store.get("mail_status") is None
    engine.run("collect")
    assert app.state.store.all("runs")[0]["found"] == 0
    assert len(app.state.store.all("jobs")) == 2
