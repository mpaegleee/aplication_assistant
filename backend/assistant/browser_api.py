import asyncio
import json
import secrets
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from playwright.async_api import Error as BrowserError
from pydantic import Field

from .browser import PORTALS
from .connectors import platform_for
from .engine import TERMINAL
from .models import LINKEDIN_USER_IMPORTS, Model


class OpenBrowser(Model):
    platform: str
    url: str = Field(default="", max_length=2000)


def install_browser_routes(app, manager, engine, auth):
    @app.post("/api/browser/self-test", dependencies=[Depends(auth)])
    def self_test():
        return manager.call(manager.self_test())

    @app.get("/api/browser", dependencies=[Depends(auth)])
    def status():
        return manager.call(manager.status())

    @app.post("/api/browser/open", dependencies=[Depends(auth)])
    def open_browser(payload: OpenBrowser):
        return manager.call(manager.open(payload.platform, payload.url))

    @app.post("/api/jobs/{id}/browser/open", dependencies=[Depends(auth)])
    def open_job(id: str):
        job = engine.require_job(id)
        url = job.get("application_url") or job.get("url", "")
        platform = platform_for(url)
        if job.get("source") not in LINKEDIN_USER_IMPORTS or platform != "linkedin":
            engine.valid_analysis(job)
        if platform not in PORTALS:
            raise ValueError(
                "Este site ainda não tem navegador integrado. Use o link externo da vaga."
            )
        manager.call(manager.open(platform, url, id))
        return {"platform": platform, "job_id": id}

    @app.post("/api/browser/{platform}/handoff", dependencies=[Depends(auth)])
    def handoff(platform: str):
        return manager.call(manager.handoff(platform))

    @app.delete("/api/browser/{platform}", dependencies=[Depends(auth)])
    def forget(platform: str):
        if platform not in PORTALS:
            raise HTTPException(404)
        return manager.call(manager.forget(platform))

    @app.post("/api/jobs/{id}/browser/prepare", dependencies=[Depends(auth)])
    def prepare(id: str):
        return engine.browser_apply(id, submit=False)

    @app.post("/api/jobs/{id}/browser/submit", dependencies=[Depends(auth)])
    def submit(id: str):
        return engine.browser_apply(id, submit=True)

    @app.get("/api/jobs/{id}/browser/proof", dependencies=[Depends(auth)])
    def proof(id: str):
        record = manager.store.get("browser_proofs", id)
        if not record:
            raise HTTPException(404, "Sem comprovante do portal.")
        return Response(bytes.fromhex(record["image"]), media_type="image/png")

    @app.websocket("/api/browser/{platform}/view")
    async def view(ws: WebSocket, platform: str):
        # WebSocket bypasses HTTP middleware: validate both session and exact origin.
        origin = urlsplit(ws.headers.get("origin", ""))
        host = ws.headers.get("host", "")
        expected_scheme = "https" if ws.url.scheme == "wss" else "http"
        token = ws.cookies.get("aa_session", "")
        if (
            platform not in PORTALS
            or origin.netloc != host
            or origin.scheme != expected_scheme
            or not manager.store.authenticated(token)
        ):
            await ws.close(code=1008)
            return
        await ws.accept()
        owner = secrets.token_hex(16)
        send_lock = asyncio.Lock()

        async def notify(value):
            async with send_lock:
                await ws.send_json(value)

        async def call(coro):
            return await asyncio.wrap_future(manager.schedule(coro))

        async def frames():
            while True:
                if not manager.store.authenticated(token):
                    await ws.close(code=1008)
                    return
                try:
                    frame = await call(manager.frame(platform))
                    async with send_lock:
                        await ws.send_bytes(frame)
                except ValueError as exc:
                    await notify({"error": str(exc)})
                except (BrowserError, OSError, RuntimeError):
                    await notify(
                        {"error": "Página indisponível. Abra o portal novamente."}
                    )
                await asyncio.sleep(0.8)

        streamer = asyncio.create_task(frames())
        try:
            while True:
                raw = await ws.receive_text()
                if not manager.store.authenticated(token):
                    await ws.close(code=1008)
                    break
                if len(raw) > 8000:
                    await ws.close(code=1009)
                    break
                try:
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise TypeError("Comando inválido.")
                    if message.get("type") == "acquire":
                        await call(manager.acquire(platform, owner))
                        await notify({"controlled": True})
                    elif message.get("type") == "release":
                        await asyncio.shield(
                            asyncio.wrap_future(
                                manager.schedule(manager.release(platform, owner))
                            )
                        )
                        await notify({"controlled": False})
                    elif message.get("type") == "file-fields":
                        fields = await call(manager.file_fields(platform, owner))
                        await notify({"file_fields": fields})
                    elif message.get("type") == "capture-linkedin":
                        jobs = await call(manager.capture_linkedin(platform, owner))
                        created = await asyncio.to_thread(
                            engine.import_linkedin_page_jobs,
                            jobs,
                            "LinkedIn · tela aberta",
                            "visible",
                        )
                        await notify(
                            {"capture": {"found": len(jobs), "created": created}}
                        )
                    elif message.get("type") == "attach-resume":
                        job_id = str(message.get("job_id", ""))
                        job = engine.require_job(job_id)
                        if (
                            job["status"] in TERMINAL
                            or job["status"] == "sending"
                            or job.get("archived")
                        ):
                            raise ValueError(
                                "Candidatura já tentada, encerrada ou arquivada."
                            )
                        engine.valid_analysis(job)
                        pdf = engine.pdf(job_id)
                        await call(
                            manager.attach(
                                platform,
                                owner,
                                job_id,
                                str(message.get("field_id", "")),
                                pdf,
                            )
                        )
                        await notify(
                            {
                                "notice": "Currículo anexado. Confira os dados e conclua o envio no portal."
                            }
                        )
                    else:
                        await call(manager.control(platform, owner, message))
                except ValueError as exc:
                    await notify({"error": str(exc)})
                except (KeyError, TypeError):
                    await notify(
                        {
                            "error": "Comando indisponível. Confira o controle, a validade da análise e a página do navegador."
                        }
                    )
                except (BrowserError, OSError, RuntimeError):
                    await notify(
                        {"error": "O portal não concluiu a interação. Confira a tela."}
                    )
        except WebSocketDisconnect:
            pass
        finally:
            streamer.cancel()
            await asyncio.gather(streamer, return_exceptions=True)
            await asyncio.shield(
                asyncio.wrap_future(manager.schedule(manager.release(platform, owner)))
            )
