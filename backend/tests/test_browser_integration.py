"""Actual sandboxed Chromium against in-memory HTTPS fixtures; no real applications."""

import asyncio
import os
from contextlib import suppress

import pytest
from playwright.async_api import Error as BrowserError

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="Set RUN_BROWSER_TESTS=1 after installing bundled Chromium",
)

HTML = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><body>
<h1>Vaga controlada</h1><form id="form">
<label>Nome completo *<input name="name" required></label>
<label>Seu melhor email *<input name="email" type="email" required></label>
<label>Celular com DDD *<input name="phone" required></label>
<label>LinkedIn *<input name="linkedin" required></label>
<fieldset><legend>Tem disponibilidade para o modelo híbrido?</legend>
<label>Sim<input type="radio" name="availability" value="Sim" required></label>
<label>Não<input type="radio" name="availability" value="Não"></label></fieldset>
<label>Currículo *<input name="resume" type="file" accept="application/pdf" required></label>
<label>Pretensão salarial como CLT *<input name="salary" required></label>
EXTRA
<button type="submit">Candidatar-se para a vaga</button></form>
<script>document.querySelector('form').onsubmit = e => {e.preventDefault(); document.body.innerHTML = 'CONFIRMATION';};</script>
</body></html>"""


def test_inhire_real_chromium_complete_preflight_upload_and_confirmation():
    from assistant.portal_forms import fill_inhire
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, channel="chromium", chromium_sandbox=True
            )
            page = await browser.new_page()
            html = HTML.replace("EXTRA", "").replace(
                "CONFIRMATION", "Candidatura enviada com sucesso"
            )
            await page.route(
                "https://fixture.inhire.app/**",
                lambda route: route.fulfill(body=html, content_type="text/html"),
            )
            profile = {
                "name": "Pessoa Teste",
                "email": "pessoa@example.com",
                "phone": "48999999999",
                "linkedin_url": "https://www.linkedin.com/in/pessoa",
                "answers": [
                    {
                        "question": "Tem disponibilidade para o modelo híbrido?",
                        "answer": "Sim",
                    },
                    {"question": "Pretensão salarial como CLT", "answer": "12000"},
                    {
                        "question": "Autorizar envio de dados para fixture.inhire.app",
                        "answer": "Sim",
                    },
                ],
            }
            await page.goto("https://fixture.inhire.app/vagas/fixture")
            attempts = []
            # Missing salary must stop before populating contact data or uploading.
            incomplete = {**profile, "answers": profile["answers"][:1]}
            result = await fill_inhire(
                page, incomplete, b"%PDF-fixture", True, lambda: attempts.append("send")
            )
            assert result["status"] == "pending" and not attempts
            assert await page.locator("[name=name]").input_value() == ""
            # Acknowledgement is separately required, before data is shared.
            no_consent = {**profile, "answers": profile["answers"][:2]}
            result = await fill_inhire(page, no_consent, b"%PDF-fixture")
            assert "Autorizar envio" in result["reason"]
            assert await page.locator("[name=email]").input_value() == ""
            result = await fill_inhire(page, profile, b"%PDF-fixture")
            assert result["status"] == "prepared" and not attempts
            assert await page.locator("[name=name]").input_value() == "Pessoa Teste"
            assert (
                await page.locator("[name=resume]").evaluate("(e)=>e.files[0].name")
                == "Curriculo.pdf"
            )
            result = await fill_inhire(
                page, profile, b"%PDF-fixture", True, lambda: attempts.append("send")
            )
            assert result["status"] == "confirmed" and attempts == ["send"]
            assert bytes.fromhex(result["proof"]).startswith(b"\x89PNG")
            # Unknown mandatory question never gets an invented answer.
            html = HTML.replace(
                "EXTRA", "<label>Possui certificação XYZ?<input required></label>"
            ).replace("CONFIRMATION", "Candidatura enviada com sucesso")
            await page.goto("https://fixture.inhire.app/vagas/other")
            result = await fill_inhire(
                page, profile, b"%PDF-fixture", True, lambda: attempts.append("send")
            )
            assert (
                result["status"] == "pending" and "certificação XYZ" in result["reason"]
            )
            assert attempts == ["send"]
            await browser.close()

    asyncio.run(run())


def test_internal_viewer_controls_chromium_and_restores_encrypted_session(app, client):
    from assistant.browser import BrowserManager

    manager = app.state.engine.browser

    async def prepare():
        context = await manager.context("inhire")
        await context.route(
            "https://fixture.inhire.app/**",
            lambda route: route.fulfill(
                body='<meta charset="utf-8"><label>Teste<input id="test"></label><label><input type="checkbox" id="option">Confirmar opção de teste</label>',
                content_type="text/html",
            ),
        )
        page = await context.new_page()
        manager.pages["inhire"] = page
        await page.goto("https://fixture.inhire.app/vagas/1")
        await context.add_cookies(
            [
                {
                    "name": "fixture_auth",
                    "value": "FIXTURE-SESSION-SECRET",
                    "domain": "fixture.inhire.app",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "Lax",
                }
            ]
        )
        await page.evaluate("localStorage.setItem('fixture-token','STORAGE-SECRET')")
        text = await page.locator("#test").bounding_box()
        option = await page.locator("#option").bounding_box()
        return text, option

    box, option = manager.call(prepare())
    with client.websocket_connect(
        "/api/browser/inhire/view", headers={"origin": "http://testserver"}
    ) as ws:
        ws.send_json({"type": "acquire"})

        # Frames and control acknowledgements share the stream.
        def until_json():
            for _ in range(10):
                item = ws.receive()
                if item.get("text"):
                    import json

                    return json.loads(item["text"])
            pytest.fail("Missing control acknowledgement")

        assert until_json() == {"controlled": True}
        ws.send_json({"type": "click", "x": box["x"] + 5, "y": box["y"] + 5})
        ws.send_json({"type": "text", "text": "Pessoa Teste"})
        ws.send_json({"type": "click", "x": option["x"] + 5, "y": option["y"] + 5})
        ws.send_json({"type": "release"})
        assert until_json() == {"controlled": False}

        async def read():
            page = manager.pages["inhire"]
            return await page.locator("#test").input_value(), await page.locator(
                "#option"
            ).is_checked()

        assert manager.call(read()) == ("Pessoa Teste", True)
        image = ws.receive()
        while not image.get("bytes"):
            image = ws.receive()
        assert image["bytes"].startswith(b"\xff\xd8")
    saved = app.state.store.get("browser_sessions", "inhire")
    assert saved["state"]["origins"][0]["localStorage"][0]["value"] == "STORAGE-SECRET"
    raw = (app.state.store.directory / "assistant.sqlite3").read_bytes()
    assert b"FIXTURE-SESSION-SECRET" not in raw
    other = BrowserManager(app.state.store)
    try:

        async def restored():
            context = await other.context("inhire")
            return await context.cookies()

        assert any(
            c["value"] == "FIXTURE-SESSION-SECRET" for c in other.call(restored())
        )
    finally:
        other.close()


def test_read_only_portal_discovery_includes_linkedin_posts():
    from assistant.portal_discovery import collect
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, channel="chromium", chromium_sandbox=True
            )
            page = await browser.new_page()

            async def fixture(route):
                url = route.request.url
                if "/jobs/search/" in url:
                    html = '<main><a href="https://www.linkedin.com/jobs/view/123456/">Desenvolvedor Python</a></main>'
                elif "/search/results/content/" in url:
                    html = '<article data-urn="urn:li:activity:654321">Vaga Python na Empresa Teste, Remoto Brasil. <button onclick="this.insertAdjacentHTML(\'afterend\',\'<p>Envie seu currículo para vagas@example.com. Assunto: Python Brasil</p>\');this.remove()">Ver mais</button><a href="https://empresa.gupy.io/jobs/123">Candidate-se</a></article>'
                else:
                    html = "<main>Desenvolvedor Python — Empresa Teste. Remoto, Brasil. Desenvolver APIs em Python.</main>"
                await route.fulfill(
                    body='<meta charset="utf-8">' + html, content_type="text/html"
                )

            await page.route("https://www.linkedin.com/**", fixture)
            records = await collect(page, "linkedin", "Python", 2, True)
            assert [r["kind"] for r in records] == ["job", "post"]
            assert (
                records[1]["url"]
                == "https://www.linkedin.com/feed/update/urn:li:activity:654321/"
            )
            assert (
                "vagas@example.com" in records[1]["text"]
                and "Assunto: Python Brasil" in records[1]["text"]
            )
            assert records[1]["links"][0]["url"] == "https://empresa.gupy.io/jobs/123"
            await browser.close()

    asyncio.run(run())


def test_manual_upload_targets_bound_job_and_pdf_field(app):
    manager = app.state.engine.browser

    async def run():
        context = await manager.context("linkedin")
        await context.route(
            "https://www.linkedin.com/**",
            lambda route: route.fulfill(
                body='<label>Currículo<input type="file" accept="application/pdf"></label><label>Foto<input type="file" accept="image/png"></label>',
                content_type="text/html",
            ),
        )
        await manager.open(
            "linkedin", "https://www.linkedin.com/jobs/view/123/", "job-123"
        )
        await manager.acquire("linkedin", "owner")
        fields = await manager.file_fields("linkedin", "owner")
        assert len(fields) == 2
        with pytest.raises(ValueError):
            await manager.attach(
                "linkedin", "other", "job-123", fields[0]["id"], b"%PDF-fixture"
            )
        with pytest.raises(ValueError):
            await manager.attach(
                "linkedin", "owner", "wrong-job", fields[0]["id"], b"%PDF-fixture"
            )
        with pytest.raises(ValueError):
            await manager.attach(
                "linkedin", "owner", "job-123", fields[1]["id"], b"%PDF-fixture"
            )
        await manager.attach(
            "linkedin", "owner", "job-123", fields[0]["id"], b"%PDF-fixture"
        )
        assert (
            await manager.pages["linkedin"]
            .locator("input")
            .first.evaluate("e=>e.files[0].name")
            == "Curriculo.pdf"
        )
        await manager.release("linkedin", "owner")

    manager.call(run())
    manager.close()


def test_cross_portal_link_offers_separate_session_handoff(app):
    manager = app.state.engine.browser

    async def run():
        li = await manager.context("linkedin")

        async def original(route):
            await route.fulfill(
                body='<a href="https://empresa.gupy.io/jobs/123">Candidate-se</a>',
                content_type="text/html",
            )

        await li.route("https://www.linkedin.com/**", original)
        # Avoid external DNS/network while exercising the real route guard.
        import socket
        from unittest.mock import patch

        original_resolve = manager.loop.getaddrinfo

        async def public_dns(*args, **kwargs):
            if args[0] == "empresa.gupy.io":
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.1", 443))
                ]
            return await original_resolve(*args, **kwargs)

        # Use a globally routable fixture address; no connection is made (navigation is aborted).
        async def fixture_dns(*args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

        await manager.open(
            "linkedin", "https://www.linkedin.com/jobs/view/123/", "job-123"
        )
        with (
            patch.object(manager.loop, "getaddrinfo", fixture_dns),
            suppress(BrowserError),
        ):
            await (
                manager.pages["linkedin"]
                .get_by_role("link", name="Candidate-se")
                .click(timeout=5000)
            )
        assert manager.handoffs["linkedin"]["platform"] == "gupy"
        gupy = await manager.context("gupy")
        await gupy.route(
            "https://empresa.gupy.io/**",
            lambda route: route.fulfill(
                body="<main>Gupy fixture</main>", content_type="text/html"
            ),
        )
        result = await manager.handoff("linkedin")
        assert result == {"platform": "gupy", "job_id": "job-123"}
        assert (
            manager.job_ids["gupy"] == "job-123"
            and manager.contexts["gupy"] != manager.contexts["linkedin"]
        )

    manager.call(run())
    manager.close()


@pytest.mark.parametrize(
    "platform,domain",
    [
        ("linkedin", "www.linkedin.com"),
        ("gupy", "empresa.gupy.io"),
        ("indeed", "br.indeed.com"),
    ],
)
def test_experimental_wizard_fills_steps_uploads_current_cv_and_confirms(
    platform, domain
):
    from assistant.portal_wizard import fill_wizard
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, channel="chromium", chromium_sandbox=True
            )
            page = await browser.new_page()
            html = """<meta charset="utf-8"><main><label>Nome completo<input required></label><button id="next">Avançar</button></main>
<script>
const root=document.querySelector('main');
document.querySelector('#next').onclick=()=>{
 root.innerHTML='<label>Possui PSM I?<input id="answer" required></label><label>Currículo<input type="file" accept="application/pdf"></label><label>Antigo.pdf<input type="radio" name="cv" checked></label><button id="review">Avaliar</button>';
 root.querySelector('input[type=file]').onchange=e=>{const label=document.createElement('label');label.append(e.target.files[0].name);label.innerHTML+='<input type="radio" name="cv">';root.append(label);};
 root.querySelector('#review').onclick=()=>{if(!root.querySelector('#answer').value)return;root.innerHTML='<p>Confira seus dados</p><button id="send">Enviar candidatura</button>';document.querySelector('#send').onclick=()=>{root.innerHTML='<p>Recebemos sua candidatura</p>';};};
};
</script>"""
            await page.route(
                "https://" + domain + "/**",
                lambda route: route.fulfill(body=html, content_type="text/html"),
            )
            await page.goto("https://" + domain + "/fixture")
            profile = {
                "name": "Pessoa Teste",
                "answers": [
                    {
                        "question": "Autorizar envio de dados para " + domain,
                        "answer": "Sim",
                    },
                    {"question": "Possui PSM I?", "answer": "Sim"},
                ],
            }
            attempts = []
            result = await fill_wizard(
                page,
                platform,
                profile,
                b"%PDF-control",
                True,
                lambda: attempts.append("send"),
            )
            assert result["status"] == "confirmed" and attempts == ["send"]
            assert bytes.fromhex(result["proof"]).startswith(b"\x89PNG")
            await browser.close()

    asyncio.run(run())


def test_automatic_run_linkedin_to_gupy_receipt_and_duplicate(
    app, settings, job, profile, analysis, monkeypatch
):
    engine = app.state.engine
    manager = engine.browser
    source = "https://www.linkedin.com/jobs/view/4476691267"
    board = "https://essentiagroup.gupy.io/job/eyJqb2JJZCI6MTI2NzMyMDEsInNvdXJjZSI6ImxpbmtlZGluIn0=?jobBoardSource=linkedin"
    path = "/candidates/jobs/12673201/apply?jobBoardSource=linkedin"
    settings.update(
        mode="automatic",
        search_platforms=["linkedin"],
        allowed_destinations=["linkedin", "gupy"],
        experimental_portal_submission=True,
    )
    app.state.store.put("settings", settings)
    profile["answers"] = [
        {
            "question": "Autorizar envio de dados para essentiagroup.gupy.io",
            "answer": "Sim",
        }
    ]
    app.state.store.put("profile", profile)
    monkeypatch.setattr("assistant.ai.AI.analyze", lambda *args: analysis)
    job.update(
        url=source,
        application_url="",
        recipient="",
        description="Desenvolver APIs em Python.",
    )
    original, _ = engine.add_job(job)
    calls = []

    async def setup():
        li = await manager.context("linkedin")
        await li.route(
            "**/*",
            lambda r: r.fulfill(
                content_type="text/html",
                body=f'<main><a href="{board}">Candidatar-se</a></main>',
            ),
        )
        gupy = await manager.context("gupy")

        async def route(r):
            calls.append(r.request.url)
            content = (
                f'<main><a href="{path}">Candidatar-se</a><a href="{path}">Candidatar-se</a></main>'
                if "/job/" in r.request.url
                else """<main><label>Nome completo<input required></label><label>Currículo<input type=file></label>
                       <button onclick="if(document.querySelector('input').value &amp;&amp; document.querySelector('[type=file]').files.length) this.parentNode.textContent='Recebemos sua candidatura'">Enviar candidatura</button></main>"""
            )
            await r.fulfill(content_type="text/html; charset=utf-8", body=content)

        await gupy.route("**/*", route)

    try:
        manager.call(setup())
        engine.run()
        saved = engine.require_job(original["id"])
        assert saved["status"] == "receipt", saved.get("pending_reason")
        assert saved["attempt_identity"] == "gupy:12673201"
        assert app.state.store.all("runs")[0]["sent"] == 1
        assert app.state.store.get("browser_proofs", original["id"])["image"]
        direct, _ = engine.add_job({**job, "url": board})
        with pytest.raises(ValueError, match="tentativa"):
            engine.process(direct)
        assert len([url for url in calls if "/candidates/jobs/" in url]) == 1
    finally:
        manager.close()


def test_portal_search_reports_human_verification():
    from assistant.portal_discovery import collect
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, channel="chromium", chromium_sandbox=True
            )
            page = await browser.new_page()
            await page.route(
                "https://www.linkedin.com/**",
                lambda route: route.fulfill(
                    body='<meta charset="utf-8"><h1>Executando verificação de segurança</h1>',
                    content_type="text/html",
                ),
            )
            with pytest.raises(ValueError, match="verificação humana"):
                await collect(page, "linkedin", "Agile Coach", 10, posts=False)
            await browser.close()

    asyncio.run(run())


def test_linkedin_capture_adds_only_loaded_links_and_preserves_original(
    app, client, job
):
    import json

    manager = app.state.engine.browser
    original, _ = app.state.engine.add_job(
        {
            **job,
            "url": "https://www.linkedin.com/jobs/view/123?trk=existing",
        }
    )
    visited = []

    async def open_fixture():
        context = await manager.context("linkedin")

        async def fixture(route):
            visited.append(route.request.url)
            if "/jobs/view/456" in route.request.url:
                await route.fulfill(
                    content_type="text/html; charset=utf-8",
                    body="""<main><h1>Scrum Master</h1>
                    <span class="topcard__org-name-link">Empresa Teste</span>
                    <span class="topcard__flavor-row">Brasil · Remoto</span>
                    <div id="job-details">Requisitos: experiência com Scrum, facilitação de equipes distribuídas e melhoria contínua.</div></main>""",
                )
                return
            await route.fulfill(
                content_type="text/html; charset=utf-8",
                body="""<main><ul>
                <li><a href="/jobs/view/123/?trk=listing">Agile Coach</a></li>
                <li><a href="/jobs/search/?currentJobId=456&amp;trackingId=private">Scrum Master</a>
                    <a href="/jobs/view/456/">Ver vaga</a>
                    <p class="artdeco-entity-lockup__subtitle">Empresa Teste</p>
                    <span class="artdeco-entity-lockup__caption">São Paulo</span></li>
                <li hidden><a href="/jobs/view/789/">For a hidden test</a></li>
                <li><a href="https://not-linkedin.example/jobs/view/999/">Outro site</a></li>
                </ul></main>""",
            )

        await context.route("https://www.linkedin.com/**", fixture)
        await manager.open(
            "linkedin", "https://www.linkedin.com/jobs/search/?keywords=Agile"
        )

    manager.call(open_fixture())
    with client.websocket_connect(
        "/api/browser/linkedin/view", headers={"origin": "http://testserver"}
    ) as ws:

        def response():
            for _ in range(10):
                item = ws.receive()
                if item.get("text"):
                    return json.loads(item["text"])
            pytest.fail("No textual response")

        ws.send_json({"type": "acquire"})
        assert response() == {"controlled": True}
        ws.send_json({"type": "capture-linkedin"})
        assert response() == {"capture": {"found": 2, "created": 1}}
        ws.send_json({"type": "capture-linkedin"})
        assert response() == {"capture": {"found": 2, "created": 0}}
        ws.send_json({"type": "release"})
        assert response() == {"controlled": False}
    saved = app.state.store.all("jobs")
    assert len(saved) == 2
    assert saved[0]["url"] == "https://www.linkedin.com/jobs/view/456"
    assert saved[0]["company"] == "Empresa Teste"
    assert saved[0]["analysis"] is None and saved[0]["source"] == "linkedin_visible"
    assert (
        app.state.engine.require_job(original["id"])["description"]
        == original["description"]
    )
    assert len(visited) == 1
    job_id = saved[0]["id"]
    opened = client.post("/api/jobs/" + job_id + "/browser/open")
    assert opened.status_code == 200, opened.text
    with client.websocket_connect(
        "/api/browser/linkedin/view", headers={"origin": "http://testserver"}
    ) as ws:
        ws.send_json({"type": "acquire"})
        assert response() == {"controlled": True}
        ws.send_json({"type": "capture-linkedin"})
        assert response() == {"capture": {"found": 1, "created": 0}}
    updated = app.state.engine.require_job(job_id)
    assert updated["source"] == "linkedin_visible_detail"
    assert "facilitação de equipes" in updated["description"]
    assert updated["country"] == "BR" and updated["modality"] == "Remoto"
    assert updated["analysis"] is None
    assert len(visited) == 2
