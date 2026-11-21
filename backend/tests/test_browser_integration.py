"""Actual sandboxed Chromium against in-memory HTTPS fixtures; no real applications."""

import asyncio
import os

import pytest

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
                body='<meta charset="utf-8"><label>Teste<input id="test"></label>',
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
        box = await page.locator("input").bounding_box()
        return box

    box = manager.call(prepare())
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
        ws.send_json({"type": "release"})
        assert until_json() == {"controlled": False}

        async def read():
            return await manager.pages["inhire"].locator("input").input_value()

        assert manager.call(read()) == "Pessoa Teste"
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
