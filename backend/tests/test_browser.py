import asyncio

import pytest
from assistant.browser import BrowserManager, allowed_url
from assistant.history import metrics
from assistant.portal_forms import answer_for
from starlette.websockets import WebSocketDisconnect


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://audaces.inhire.app/vagas/1", True),
        ("https://audaces.inhire.app.evil.example/vagas/1", False),
        ("http://audaces.inhire.app/vagas/1", False),
        ("https://127.0.0.1/", False),
        ("https://user:pass@audaces.inhire.app/", False),
        ("https://audaces.inhire.app:8765/", False),
    ],
)
def test_portal_urls(url, expected):
    assert allowed_url(url, "inhire") == expected
    assert not allowed_url(url, "unknown")


def test_answers_are_literal_not_inferred(profile):
    profile["minimum_salary"] = 9000
    assert answer_for("Pretensão salarial como CLT *", profile) is None
    assert answer_for("Possui certificação PSM I?", profile) is None
    profile["answers"] = [
        {"question": "Pretensão salarial como CLT", "answer": "12000"}
    ]
    assert answer_for("Pretensão salarial como CLT *", profile) == "12000"
    profile["answers"].append(
        {"question": "Pretensão salarial como CLT", "answer": "10000"}
    )
    assert answer_for("Pretensão salarial como CLT", profile) is None


def test_browser_endpoints_require_auth(app):
    from fastapi.testclient import TestClient

    with TestClient(app, headers={"x-aa-request": "1"}) as client:
        assert client.get("/api/browser").status_code == 401
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "/api/browser/gupy/view", headers={"origin": "http://testserver"}
            ),
        ):
            pass


def test_websocket_requires_origin_and_session(client):
    for headers in (
        {},
        {"origin": "https://evil.example"},
        {"origin": "https://testserver"},
    ):
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect("/api/browser/gupy/view", headers=headers),
        ):
            pass


def test_session_encrypted_filtered_and_not_exported(app, client):
    manager = app.state.engine.browser

    class Context:
        async def storage_state(self, **kwargs):
            assert kwargs == {"indexed_db": True}
            return {
                "cookies": [
                    {
                        "domain": ".linkedin.com",
                        "name": "session",
                        "value": "TOP-SECRET-COOKIE",
                    },
                    {
                        "domain": ".google.com",
                        "name": "session",
                        "value": "GOOGLE-SECRET",
                    },
                ],
                "origins": [
                    {
                        "origin": "https://www.linkedin.com",
                        "localStorage": [{"name": "token", "value": "TOKEN-SECRET"}],
                    }
                ],
            }

    manager.contexts["linkedin"] = Context()
    asyncio.run(manager.save("linkedin"))
    manager.contexts.clear()
    raw = (app.state.store.directory / "assistant.sqlite3").read_bytes()
    assert b"TOP-SECRET-COOKIE" not in raw and b"TOKEN-SECRET" not in raw
    state = app.state.store.get("browser_sessions", "linkedin")
    assert len(state["state"]["cookies"]) == 1
    assert "TOP-SECRET-COOKIE" not in client.get("/api/state").text
    assert "TOP-SECRET-COOKIE" not in client.get("/api/export").text
    assert "TOP-SECRET-COOKIE" not in client.get("/api/browser").text


def test_manual_lease_excludes_automation(app):
    manager = app.state.engine.browser

    class Page:
        def is_closed(self):
            return False

    manager.pages["inhire"] = Page()

    async def scenario():
        await manager.acquire("inhire", "owner")
        with pytest.raises(ValueError):
            await manager.acquire("inhire", "other")
        with pytest.raises(ValueError):
            await manager.control("inhire", "other", {"type": "key", "key": "Enter"})
        with pytest.raises(ValueError):
            await manager.inhire("https://audaces.inhire.app", {}, b"pdf")
        await manager.release("inhire", "other")
        assert manager.leases["inhire"] == "owner"
        await manager.release("inhire", "owner")
        assert not manager.leases

    asyncio.run(scenario())


class FakeBrowser:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    def call(self, coroutine, **kwargs):
        return asyncio.run(coroutine)

    async def inhire(self, url, profile, pdf, submit, intent):
        self.calls += 1
        assert pdf.startswith(b"%PDF")
        if submit:
            intent()
        result = {
            "status": self.outcome if submit else "prepared",
            "reason": "Resultado controlado",
        }
        if self.outcome == "confirmed" and submit:
            result["proof"] = b"fake-png".hex()
        return result


def browser_job(app, profile, settings, job, analysis, monkeypatch):
    settings.update(mode="automatic", allowed_destinations=["inhire"])
    job.update(
        recipient="",
        url="https://audaces.inhire.app/vagas/fixture",
        application_url="https://audaces.inhire.app/vagas/fixture",
        description="Desenvolver APIs em Python.",
    )
    app.state.store.put("profile", profile)
    app.state.store.put("settings", settings)
    monkeypatch.setattr("assistant.ai.AI.analyze", lambda *args: analysis)
    j, _ = app.state.engine.add_job(job)
    app.state.engine.analyze(j["id"])
    return j["id"]


def test_browser_submission_records_proof_and_blocks_duplicate(
    app, profile, settings, job, analysis, monkeypatch
):
    id = browser_job(app, profile, settings, job, analysis, monkeypatch)
    browser = FakeBrowser("confirmed")
    app.state.engine.browser = browser
    assert app.state.engine.browser_apply(id)["status"] == "prepared"
    assert app.state.store.get("jobs", id)["status"] == "ready"
    assert app.state.engine.browser_apply(id, True)["status"] == "confirmed"
    sent = app.state.store.get("jobs", id)
    assert (
        sent["status"] == "receipt"
        and sent["resume_snapshot"]
        and sent["browser_attempt"]
    )
    assert app.state.store.get("browser_proofs", id)["image"] == b"fake-png".hex()
    assert metrics(app.state.store, settings)["browser_confirmed"] == 1
    with pytest.raises(ValueError):
        app.state.engine.browser_apply(id, True)
    assert browser.calls == 2
    app.state.engine.browser = BrowserManager(app.state.store)


def test_uncertain_browser_result_never_retried(
    app, profile, settings, job, analysis, monkeypatch
):
    id = browser_job(app, profile, settings, job, analysis, monkeypatch)
    browser = FakeBrowser("uncertain")
    app.state.engine.browser = browser
    app.state.engine.browser_apply(id, True)
    assert app.state.store.get("jobs", id)["status"] == "uncertain"
    with pytest.raises(ValueError):
        app.state.engine.browser_apply(id, True)
    assert browser.calls == 1
    app.state.engine.browser = BrowserManager(app.state.store)


def test_review_mode_blocks_data_entry_before_approval(
    app, profile, settings, job, analysis, monkeypatch
):
    id = browser_job(app, profile, settings, job, analysis, monkeypatch)
    settings["mode"] = "review"
    app.state.store.put("settings", settings)
    app.state.engine.analyze(id)
    with pytest.raises(ValueError, match="Aprove"):
        app.state.engine.browser_apply(id)


def test_logout_closes_browser_control(client, app):
    # A connected browser socket cannot outlive the installation login.
    with client.websocket_connect(
        "/api/browser/gupy/view", headers={"origin": "http://testserver"}
    ) as ws:
        assert ws.receive_json().get("error")
        client.post("/api/logout")
        ws.send_json({"type": "acquire"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_portal_identity_ignores_referral_and_tracks_same_job():
    from assistant.sources import application_identity

    first = "https://audaces.inhire.app/vagas/599763e7-c9d1-4a6a-a32b-ec0352aaebe9/titulo?source=linkedin"
    second = "https://audaces.inhire.app/vagas/599763e7-c9d1-4a6a-a32b-ec0352aaebe9/outro-titulo?source=indeed"
    assert application_identity(first) == application_identity(second)
    assert application_identity(
        "https://essentiagroup.gupy.io/job/eyJqb2JJZCI6MTI2NzMyMDEsInNvdXJjZSI6ImxpbmtlZGluIn0=?jobBoardSource=linkedin"
    ) == application_identity("https://essentiagroup.gupy.io/jobs/12673201")


def test_scheduled_queue_processes_inhire_once(
    app, profile, settings, job, analysis, monkeypatch
):
    id = browser_job(app, profile, settings, job, analysis, monkeypatch)
    browser = FakeBrowser("confirmed")
    app.state.engine.browser = browser
    monkeypatch.setattr(app.state.engine.stop, "wait", lambda delay: False)
    app.state.engine.run()
    assert app.state.store.all("runs")[0]["sent"] == 1
    assert app.state.store.get("jobs", id)["browser_confirmed"]
    app.state.engine.run()
    assert browser.calls == 1 and app.state.store.all("runs")[0]["sent"] == 0
    app.state.engine.browser = BrowserManager(app.state.store)


def test_pause_at_final_click_prevents_attempt(
    app, profile, settings, job, analysis, monkeypatch
):
    id = browser_job(app, profile, settings, job, analysis, monkeypatch)

    class PausingBrowser(FakeBrowser):
        async def inhire(self, url, profile, pdf, submit, intent):
            settings["paused"] = True
            app.state.store.put("settings", settings)
            intent()
            pytest.fail("Paused submission proceeded")

    app.state.engine.browser = PausingBrowser("confirmed")
    with pytest.raises(ValueError, match="cancelado"):
        app.state.engine.browser_apply(id, True)
    assert app.state.store.get("jobs", id)["status"] == "ready"
    assert not app.state.store.get("jobs", id).get("browser_attempt")
    app.state.engine.browser = BrowserManager(app.state.store)
