import os, sys, secrets, threading, time, sqlite3
from pathlib import Path
from typing import Literal
from contextlib import asynccontextmanager
from io import BytesIO
import secrets
from urllib.parse import quote, urlsplit
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import Field
from pypdf import PdfReader
from filelock import FileLock, Timeout
from .models import Model, Profile, Settings, JobInput, AREAS, AIConnection
from .providers import PROVIDERS
from .connectors import CONNECTORS, source_platform
from .history import record_stage, metrics, STAGES
from .store import Store, now
from .engine import Engine, TERMINAL
from .ai import AI
from .matching import exact_quote
from .sources import public_fetch, read_source
from .mail import parse_followup, email_eligible
from .browser import BrowserManager
from .browser_api import install_browser_routes
from .worklist import worklist
from .documents import resume_contacts, resume_docx, resume_pdf


def data_directory():
    if os.environ.get("AA_DATA_DIR"):
        return Path(os.environ["AA_DATA_DIR"])
    if sys.platform == "win32":
        return (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "Application Assistant"
        )
    return Path.home() / ".application-assistant"


class Password(Model):
    password: str = Field(min_length=12, max_length=256)
    setup_token: str = Field(default="", max_length=256)


class ResumeFocus(Model):
    focus: str = Field(min_length=2, max_length=150)


def resume_download(content, label, format):
    content_type = (
        "application/pdf"
        if format == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return Response(
        content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{label}.{format}"'},
    )


class RunInput(Model):
    action: Literal["collect", "apply"] = "apply"


class ArchiveInput(Model):
    archived: bool


class URLInput(Model):
    url: str = Field(min_length=8, max_length=2000)


class StatusInput(Model):
    status: str
    note: str = Field(min_length=5, max_length=2000)


class FollowupInput(Model):
    job_id: str
    status: str


class SecretInput(Model):
    name: str


PUBLIC = {"/api/session", "/api/setup", "/api/login", "/api/health"}
FOLLOWUP_STATES = STAGES | {
    "receipt",
    "selection",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
    "closed",
}


def create_app(directory=None, static_dir=None, enable_scheduler=True):
    store = Store(directory or data_directory())
    engine = Engine(store)
    browser = BrowserManager(store)
    engine.browser = browser
    lock = FileLock(str(store.directory / "instance.lock"))

    @asynccontextmanager
    async def lifespan(app):
        try:
            lock.acquire(timeout=0)
        except Timeout:
            raise RuntimeError("Outra instância já está usando estes dados.")
        worker = None
        try:
            if (
                os.environ.get("AA_SERVER") == "1"
                and not store.configured()
                and not os.environ.get("AA_SETUP_TOKEN")
            ):
                raise RuntimeError(
                    "Defina AA_SETUP_TOKEN antes do primeiro acesso ao servidor."
                )
            engine.recover()
            if enable_scheduler:
                worker = threading.Thread(target=engine.scheduler, daemon=True)
                worker.start()
            yield
        finally:
            engine.stop.set()
            if worker:
                worker.join(timeout=11)
            if engine.thread and engine.thread.is_alive():
                engine.thread.join(timeout=120)
            if engine.mail_thread and engine.mail_thread.is_alive():
                engine.mail_thread.join(timeout=60)
            browser.close()
            lock.release()

    app = FastAPI(
        title="Application Assistant",
        version="0.6.2",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    app.state.engine = engine
    hosts = os.environ.get("AA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def security(request, call_next):
        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            if request.headers.get("x-aa-request") != "1":
                return JSONResponse(
                    {"detail": "Cabeçalho de segurança ausente."}, status_code=403
                )
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse(
                    {"detail": "Origem não permitida."}, status_code=403
                )
            if int(request.headers.get("content-length", "0") or 0) > 11_000_000:
                return JSONResponse(
                    {"detail": "Arquivo excede o limite de 10 MB."}, status_code=413
                )
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'",
            }
        )
        return response

    def auth(request: Request):
        if not store.authenticated(request.cookies.get("aa_session", "")):
            raise HTTPException(401, "Entre com a senha da instalação.")

    install_browser_routes(app, browser, engine, auth)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        labels = {
            "ai_url": "Endereço da API de IA",
            "ai_model": "Modelo de IA",
            "allowed_domains": "Domínios autorizados",
            "browser_search_queries": "Termos de busca nos portais",
            "interval_seconds": "Intervalo entre vagas",
            "minimum_confidence": "Confiança mínima",
            "threshold": "Aderência mínima",
            "time": "Horário da agenda",
            "sources": "Fontes de vagas",
            "smtp_from": "E-mail de envio",
            "smtp_port": "Porta SMTP",
            "imap_port": "Porta IMAP",
            "email": "E-mail para contato",
            "linkedin_url": "Endereço público do LinkedIn",
        }
        problems = []
        for error in exc.errors():
            location = error["loc"][1:]
            field = str(location[0]) if location else ""
            label = labels.get(field, field.replace("_", " ").capitalize())
            if (
                field == "sources"
                and len(location) > 1
                and isinstance(location[1], int)
            ):
                label = f"Fonte {location[1] + 1}"
            context = error.get("ctx", {})
            kind = error["type"]
            if kind == "value_error" and isinstance(context.get("error"), ValueError):
                message = str(context["error"])
            elif kind == "greater_than_equal":
                message = f"Informe um valor a partir de {context['ge']}."
            elif kind == "less_than_equal":
                message = f"Informe um valor de até {context['le']}."
            elif kind == "missing":
                message = "Preencha este campo."
            else:
                message = "Confira o valor informado."
            problems.append(f"{label}: {message}" if label else message)
        return JSONResponse(
            {"detail": " ".join(dict.fromkeys(problems))}, status_code=422
        )

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        # Never include provider responses, credentials or personal data in errors/logs.
        return JSONResponse(
            {"detail": "Operação não concluída. Verifique os dados e tente novamente."},
            status_code=500,
        )

    failures = []
    login_lock = threading.Lock()

    def authenticate(payload, response):
        with login_lock:
            current = time.monotonic()
            failures[:] = [x for x in failures if current - x < 300]
            if len(failures) >= 10:
                raise HTTPException(
                    429, "Aguarde cinco minutos para tentar entrar novamente."
                )
            token = store.login(payload.password)
            if not token:
                failures.append(current)
                raise HTTPException(401, "Senha inválida.")
            failures.clear()
        response.set_cookie(
            "aa_session",
            token,
            httponly=True,
            samesite="strict",
            secure=os.environ.get("AA_SECURE_COOKIES") == "1",
            max_age=43200,
            path="/",
        )
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": "0.6.2"}

    @app.get("/api/session")
    def session(request: Request):
        return {
            "configured": store.configured(),
            "authenticated": store.authenticated(request.cookies.get("aa_session", "")),
            "setup_token_required": bool(os.environ.get("AA_SETUP_TOKEN")),
        }

    @app.post("/api/setup")
    def setup(payload: Password, response: Response):
        token = os.environ.get("AA_SETUP_TOKEN", "")
        if token and not secrets.compare_digest(payload.setup_token, token):
            raise HTTPException(403, "Código de configuração inválido.")
        with login_lock:
            if store.configured():
                raise HTTPException(409, "Instalação já configurada.")
            store.create_password(payload.password)
        return authenticate(payload, response)

    @app.post("/api/login")
    def login(payload: Password, response: Response):
        return authenticate(payload, response)

    @app.post("/api/logout", dependencies=[Depends(auth)])
    def logout(request: Request, response: Response):
        store.logout(request.cookies.get("aa_session", ""))
        response.delete_cookie("aa_session")
        return {"ok": True}

    @app.get("/api/state", dependencies=[Depends(auth)])
    def state():
        settings = engine.settings()
        for field in ["ai_key", "smtp_password", "imap_password"]:
            settings[field + "_configured"] = bool(settings[field])
            settings[field] = ""
        jobs = store.all("jobs")
        # Large documents and sent profile snapshots are not exposed in list responses.
        for j in jobs:
            j.pop("resume_snapshot", None)
            j.pop("submitted_profile", None)
            j["email_eligible"] = email_eligible(j)
        pdf = store.get("pdf", default={})
        search_platforms = set(settings["search_platforms"])
        configured_sources = sorted(
            (search_platforms & {"linkedin", "indeed", "gupy"})
            | {
                source_platform(source)
                for source in settings["sources"]
                if source["enabled"] and source_platform(source) in search_platforms
            }
        )
        return {
            "version": "0.6.2",
            "profile": engine.profile(),
            "settings": settings,
            "jobs": jobs,
            "worklist": worklist(engine.profile(), engine.settings(), jobs),
            "events": store.all("events")[:500],
            "runs": store.all("runs")[:50],
            "followups": store.all("followups")[:100],
            "areas": AREAS,
            "running": engine.running,
            "connectors": CONNECTORS,
            "metrics": metrics(store, engine.settings()),
            "mail_status": store.get("mail_status", default={}),
            "capabilities": {
                "linkedin": "assisted",
                "gupy": "assisted",
                "email": "smtp",
                "followup": "eml",
            },
            "configured_sources": configured_sources,
            "linkedin_alert_status": store.get("linkedin_alert_status", default={}),
            "search_portal_issues": {
                platform: issue
                for platform in ("linkedin", "indeed")
                if platform in search_platforms
                and (
                    platform != "linkedin"
                    or settings["linkedin_search_method"] == "browser"
                )
                and (issue := engine.portal_search_issue(platform))
            },
            "pdf_imported": bool(pdf),
            "pdf_filename": pdf.get("filename", "Curriculo.pdf") if pdf else None,
        }

    @app.put("/api/settings", dependencies=[Depends(auth)])
    def settings(payload: Settings):
        with engine.lock:
            old = engine.settings()
            data = payload.model_dump()
            for field in ["ai_key", "smtp_password", "imap_password"]:
                if not data[field]:
                    same = (
                        data["ai_url"] == old["ai_url"]
                        if field == "ai_key"
                        else all(
                            data[k] == old[k]
                            for k in (
                                ["smtp_host", "smtp_user"]
                                if field == "smtp_password"
                                else ["imap_host", "imap_user"]
                            )
                        )
                    )
                    if same:
                        data[field] = old[field]
            store.put("settings", data)
        return {"ok": True}

    @app.post("/api/settings/clear-secret", dependencies=[Depends(auth)])
    def clear_secret(payload: SecretInput):
        if payload.name not in ["ai_key", "smtp_password", "imap_password"]:
            raise ValueError("Segredo inválido.")
        with engine.lock:
            s = engine.settings()
            s[payload.name] = ""
            store.put("settings", s)
        return {"ok": True}

    @app.put("/api/profile", dependencies=[Depends(auth)])
    def profile(payload: Profile):
        with engine.lock:
            data = payload.model_dump()
            original = store.get("pdf", default={}).get("text", "")
            ids = [f["id"] for f in data["facts"]]
            if len(set(ids)) != len(ids):
                raise ValueError("Os fatos precisam ter identificadores únicos.")
            for f in data["facts"]:
                if f["source"] == "pdf" and (
                    f["text"] != f["evidence"]
                    or not exact_quote(f["evidence"], original)
                ):
                    raise ValueError(
                        "Fato do PDF sem evidência literal. Cadastre correções como fato manual."
                    )
            if data["confirmed"] and (
                not data["name"]
                or not data["areas"]
                or not data["roles"]
                or not data["facts"]
            ):
                raise ValueError(
                    "Informe nome, área, cargo e fatos antes de confirmar."
                )
            if set(data["areas"]) & set(data["excluded_areas"]):
                raise ValueError(
                    "Uma área não pode ser desejada e excluída ao mesmo tempo."
                )
            store.put("profile", data)
            store.event(
                "",
                "Perfil atualizado. Análises anteriores exigem nova validação antes de envio.",
            )
        return data

    @app.post("/api/profile/pdf", dependencies=[Depends(auth)])
    async def import_pdf(file: UploadFile = File(...)):
        content = await file.read(10_000_001)
        if len(content) > 10_000_000:
            raise HTTPException(413, "Limite de 10 MB.")
        if not content.startswith(b"%PDF-"):
            raise ValueError("Envie um arquivo PDF válido.")
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 40:
                raise ValueError("PDF protegido ou com mais de 40 páginas.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)[:60000]
        except ValueError:
            raise
        except Exception:
            raise ValueError("Não foi possível ler o PDF.")
        if len(text.strip()) < 50:
            raise ValueError(
                "PDF sem texto legível. Exporte o currículo pelo LinkedIn; imagens precisam de OCR externo."
            )
        filename = Path((file.filename or "").replace("\\", "/")).name
        filename = "".join(char for char in filename if char.isprintable()).strip()[
            :240
        ]
        if not filename.lower().endswith(".pdf"):
            filename = filename + ".pdf" if filename else "Curriculo.pdf"
        with engine.lock:
            store.put(
                "pdf",
                {
                    "text": text,
                    "bytes": content.hex(),
                    "at": now(),
                    "filename": filename,
                },
            )
            p = engine.profile()
            contacts = {
                key: value for key, value in resume_contacts(text).items() if not p[key]
            }
            p.update(contacts)
            p["confirmed"] = False
            # Preserve previously imported facts as explicit user-owned facts.
            for fact in p["facts"]:
                if fact["source"] == "pdf":
                    fact["source"] = "manual"
                    fact["evidence"] = ""
            store.put("profile", p)
        return {
            "text": text,
            "contacts": contacts,
            "message": "PDF importado. Extraia sugestões com IA e revise antes de confirmar.",
        }

    @app.get("/api/profile/pdf", dependencies=[Depends(auth)])
    def download_pdf():
        pdf = store.get("pdf", default={})
        if not pdf.get("bytes"):
            raise HTTPException(404, "Importe o PDF primeiro.")
        filename = quote(pdf.get("filename") or "Curriculo.pdf", safe="")
        return Response(
            bytes.fromhex(pdf["bytes"]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
        )

    @app.get("/api/profile/pdf-text", dependencies=[Depends(auth)])
    def pdf_text():
        return {"text": store.get("pdf", default={}).get("text", "")}

    @app.post("/api/profile/improve", dependencies=[Depends(auth)])
    def improve_profile():
        with engine.lock:
            return AI(store).improve_profile(engine.settings(), engine.profile())

    @app.post("/api/profile/extract", dependencies=[Depends(auth)])
    def extract():
        with engine.lock:
            text = store.get("pdf", default={}).get("text")
            if not text:
                raise ValueError("Importe o PDF primeiro.")
            draft = AI(store).extract(engine.settings(), text)
            if not draft["facts"]:
                raise ValueError(
                    "A IA não extraiu fatos verificáveis. Confira o texto e adicione fatos manualmente."
                )
            return draft

    @app.get("/api/ai/providers", dependencies=[Depends(auth)])
    def providers():
        return {"providers": PROVIDERS}

    @app.post("/api/ai/models", dependencies=[Depends(auth)])
    def list_models(payload: AIConnection):
        saved = engine.settings()
        key = payload.ai_key or (
            saved["ai_key"] if payload.ai_url == saved["ai_url"] else ""
        )
        draft = {**saved, "ai_url": payload.ai_url, "ai_key": key}
        return {"models": AI(store).models(draft)}

    @app.post("/api/ai/test", dependencies=[Depends(auth)])
    def test_ai():
        result = AI(store).call(
            engine.settings(), 'Responda {"ok":true}.', {"teste": "conexão"}
        )
        if result.get("ok") is not True:
            raise ValueError("Modelo não respondeu ao teste JSON.")
        return {"ok": True}

    @app.post("/api/jobs", dependencies=[Depends(auth)])
    def add_job(payload: JobInput):
        job, created = engine.add_job(payload.model_dump())
        return {"job": job, "created": created}

    @app.put("/api/jobs/{id}", dependencies=[Depends(auth)])
    def edit_job(id: str, payload: JobInput):
        with engine.lock:
            old = engine.require_job(id)
            if old["status"] in TERMINAL or old["status"] == "sending":
                raise ValueError("Não altere uma candidatura já enviada ou encerrada.")
            if payload.url != old["url"]:
                raise ValueError(
                    "O link identifica a vaga e não pode ser alterado. Cadastre outra oportunidade."
                )
            old.update(
                payload.model_dump(), status="new", analysis=None, approved=False
            )
            store.put("jobs", old, id)
            store.event(id, "Vaga revisada. Aprovação e análise anteriores removidas.")
            return old

    @app.post("/api/jobs/import-url", dependencies=[Depends(auth)])
    def import_url(payload: URLInput):
        s = engine.settings()
        items = read_source(
            public_fetch(payload.url, s["allowed_domains"]), payload.url
        )
        count = sum(int(engine.add_job(j)[1]) for j in items[:100])
        return {"imported": count}

    @app.post("/api/jobs/{id}/analyze", dependencies=[Depends(auth)])
    def analyze(id: str):
        return engine.analyze(id, force=True)

    @app.post("/api/jobs/{id}/approve", dependencies=[Depends(auth)])
    def approve(id: str):
        return engine.approve(id)

    @app.post("/api/jobs/{id}/send", dependencies=[Depends(auth)])
    def send(id: str):
        return engine.send(id)

    @app.get("/api/jobs/{id}/resume", dependencies=[Depends(auth)])
    def resume(id: str, format: Literal["pdf", "docx"] = "pdf"):
        if format == "pdf":
            return resume_download(engine.pdf(id), "Curriculo", format)
        job = engine.require_job(id)
        if job.get("resume_snapshot") and job.get("submitted_profile"):
            profile, analysis = job["submitted_profile"], job["analysis"]
        else:
            profile, _, analysis = engine.valid_analysis(job)
        return resume_download(resume_docx(profile, analysis), "Curriculo", format)

    @app.post("/api/jobs/{id}/status", dependencies=[Depends(auth)])
    def status(id: str, payload: StatusInput):
        if payload.status not in FOLLOWUP_STATES | {"submitted_manual"}:
            raise ValueError("Estado inválido.")
        with engine.lock:
            j = engine.require_job(id)
            if j["status"] == "sending":
                raise ValueError("Envio em andamento.")
            if payload.status == "submitted_manual" and j["status"] not in TERMINAL:
                p, s, a = engine.valid_analysis(j)
                j["resume_snapshot"] = engine.pdf(id).hex()
                j["submitted_profile"] = p
            if payload.status in FOLLOWUP_STATES and j["status"] not in TERMINAL:
                raise ValueError("Registre o envio antes de acompanhar o retorno.")
            record_stage(j, payload.status, "manual")
            store.put("jobs", j, id)
            store.event(id, "Atualização manual: " + payload.note)
            return {"ok": True}

    @app.post("/api/jobs/{id}/archive", dependencies=[Depends(auth)])
    def archive_job(id: str, payload: ArchiveInput):
        with engine.lock:
            job = engine.require_job(id)
            if job["status"] in TERMINAL or job["status"] == "sending":
                raise ValueError(
                    "Use o histórico para candidaturas já tentadas ou encerradas."
                )
            job["archived"] = payload.archived
            store.put("jobs", job, id)
            store.event(
                id,
                "Vaga arquivada da fila."
                if payload.archived
                else "Vaga restaurada na fila.",
            )
        return {"ok": True}

    @app.post("/api/runs", dependencies=[Depends(auth)])
    def run(payload: RunInput | None = None):
        engine.start_run(payload.action if payload else "apply")
        return {"ok": True}

    @app.post("/api/pause", dependencies=[Depends(auth)])
    def pause():
        # Pause must remain available even while a model call holds the engine lock.
        s = engine.settings()
        s["paused"] = True
        store.put("settings", s)
        return {"ok": True}

    @app.get("/api/profile/resume", dependencies=[Depends(auth)])
    def standard_resume(format: Literal["pdf", "docx"] = "pdf"):
        profile = engine.profile()
        if not profile["confirmed"]:
            raise ValueError("Confirme o perfil antes de gerar o currículo.")
        analysis = {"resume_fact_ids": [f["id"] for f in profile["facts"]]}
        render = resume_pdf if format == "pdf" else resume_docx
        return resume_download(render(profile, analysis), "Curriculo-padrao", format)

    @app.post("/api/profile/resume-versions", dependencies=[Depends(auth)])
    def create_resume_version(payload: ResumeFocus):
        with engine.lock:
            profile = engine.profile()
            if not profile["confirmed"]:
                raise ValueError("Confirme e salve o perfil antes de gerar uma versão.")
            selected = AI(store).choose_resume_facts(
                engine.settings(), profile, payload.focus
            )
            snapshot = {
                **profile,
                "facts": [fact for fact in profile["facts"] if fact["id"] in selected],
            }
            key = secrets.token_hex(12)
            version = {"id": key, "focus": payload.focus, "at": now()}
            store.put(
                "resume_versions",
                {
                    **version,
                    "profile": snapshot,
                    "analysis": {"resume_fact_ids": selected},
                },
                key,
            )
        return version

    @app.get("/api/profile/resume-versions", dependencies=[Depends(auth)])
    def resume_versions():
        return [
            {field: version[field] for field in ("id", "focus", "at")}
            for version in store.all("resume_versions")[:20]
        ]

    @app.get("/api/profile/resume-versions/{id}", dependencies=[Depends(auth)])
    def download_resume_version(id: str, format: Literal["pdf", "docx"] = "pdf"):
        version = store.get("resume_versions", id)
        if not version:
            raise HTTPException(404, "Versão de currículo não encontrada.")
        render = resume_pdf if format == "pdf" else resume_docx
        return resume_download(
            render(version["profile"], version["analysis"]),
            "Curriculo-direcionado",
            format,
        )

    @app.post("/api/followups/sync", dependencies=[Depends(auth)])
    def sync_mail():
        result = engine.sync_mail()
        if result.get("error"):
            raise ValueError(result["error"])
        return result

    @app.post("/api/followups/import", dependencies=[Depends(auth)])
    async def followup(file: UploadFile = File(...)):
        data = await file.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("E-mail excede 2 MB.")
        try:
            suggestion = parse_followup(data, store.all("jobs"))
        except Exception:
            raise ValueError("Não foi possível ler o arquivo .eml.")
        suggestion["created_at"] = now()
        store.put("followups", suggestion, suggestion["id"])
        return suggestion

    @app.post("/api/followups/{id}/confirm", dependencies=[Depends(auth)])
    def confirm_followup(id: str, payload: FollowupInput):
        if payload.status not in FOLLOWUP_STATES:
            raise ValueError("Estado inválido.")
        with engine.lock:
            f = store.get("followups", id)
            if not f or f["confirmed"]:
                raise ValueError("Retorno não encontrado ou já confirmado.")
            j = engine.require_job(payload.job_id)
            if j["status"] not in TERMINAL:
                raise ValueError("Selecione uma candidatura já enviada.")
            record_stage(j, payload.status, "eml_confirmation")
            store.put("jobs", j, j["id"])
            f.update(confirmed=True, job_id=j["id"], status=payload.status)
            store.put("followups", f, id)
            store.event(
                j["id"],
                "Usuário confirmou retorno importado por e-mail: " + payload.status,
            )
            return {"ok": True}

    @app.get("/api/export", dependencies=[Depends(auth)])
    def export():
        import json

        payload = {
            "version": 1,
            "profile": engine.profile(),
            "jobs": store.all("jobs"),
            "events": store.all("events"),
            "runs": store.all("runs"),
            "followups": store.all("followups"),
        }
        return Response(
            json.dumps(payload, ensure_ascii=False),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="Application-Assistant-dados.json"'
            },
        )

    static = Path(
        static_dir
        or os.environ.get(
            "AA_STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist"
        )
    )
    if static.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/favicon.png")
        def favicon():
            return FileResponse(static / "favicon.png", media_type="image/png")

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

    return app
