import os, sys, secrets, threading, time, sqlite3
from pathlib import Path
from contextlib import asynccontextmanager
from io import BytesIO
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import Field
from pypdf import PdfReader
from filelock import FileLock, Timeout
from .models import Model, Profile, Settings, JobInput, AREAS
from .store import Store, now
from .engine import Engine, TERMINAL
from .ai import AI
from .matching import exact_quote
from .sources import public_fetch, read_source
from .mail import parse_followup, email_eligible


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
FOLLOWUP_STATES = {
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
            lock.release()

    app = FastAPI(
        title="Application Assistant",
        version="0.1.0",
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
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'",
            }
        )
        return response

    def auth(request: Request):
        if not store.authenticated(request.cookies.get("aa_session", "")):
            raise HTTPException(401, "Entre com a senha da instalação.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = ", ".join(".".join(str(x) for x in e["loc"][1:]) for e in exc.errors())
        return JSONResponse({"detail": "Confira os campos: " + fields}, status_code=422)

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
        return {"ok": True, "version": "0.1.0"}

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
        for field in ["ai_key", "smtp_password"]:
            settings[field + "_configured"] = bool(settings[field])
            settings[field] = ""
        jobs = store.all("jobs")
        # Large documents and sent profile snapshots are not exposed in list responses.
        for j in jobs:
            j.pop("resume_snapshot", None)
            j.pop("submitted_profile", None)
            j["email_eligible"] = email_eligible(j)
        return {
            "profile": engine.profile(),
            "settings": settings,
            "jobs": jobs,
            "events": store.all("events")[:500],
            "runs": store.all("runs")[:50],
            "followups": store.all("followups")[:100],
            "areas": AREAS,
            "running": engine.running,
            "capabilities": {
                "linkedin": "assisted",
                "gupy": "assisted",
                "email": "smtp",
                "followup": "eml",
            },
            "pdf_imported": bool(store.get("pdf")),
        }

    @app.put("/api/settings", dependencies=[Depends(auth)])
    def settings(payload: Settings):
        with engine.lock:
            old = engine.settings()
            data = payload.model_dump()
            for field in ["ai_key", "smtp_password"]:
                if not data[field]:
                    data[field] = old[field]
            store.put("settings", data)
        return {"ok": True}

    @app.post("/api/settings/clear-secret", dependencies=[Depends(auth)])
    def clear_secret(payload: SecretInput):
        if payload.name not in ["ai_key", "smtp_password"]:
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
        with engine.lock:
            store.put("pdf", {"text": text, "bytes": content.hex(), "at": now()})
            p = engine.profile()
            p["confirmed"] = False
            # Preserve previously imported facts as explicit user-owned facts.
            for fact in p["facts"]:
                if fact["source"] == "pdf":
                    fact["source"] = "manual"
                    fact["evidence"] = ""
            store.put("profile", p)
        return {
            "text": text,
            "message": "PDF importado. Extraia sugestões com IA e revise antes de confirmar.",
        }

    @app.get("/api/profile/pdf-text", dependencies=[Depends(auth)])
    def pdf_text():
        return {"text": store.get("pdf", default={}).get("text", "")}

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
        return engine.analyze(id)

    @app.post("/api/jobs/{id}/approve", dependencies=[Depends(auth)])
    def approve(id: str):
        return engine.approve(id)

    @app.post("/api/jobs/{id}/send", dependencies=[Depends(auth)])
    def send(id: str):
        return engine.send(id)

    @app.get("/api/jobs/{id}/resume", dependencies=[Depends(auth)])
    def resume(id: str):
        return Response(
            engine.pdf(id),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="Curriculo.pdf"'},
        )

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
            if payload.status in FOLLOWUP_STATES and j["status"] not in TERMINAL:
                raise ValueError("Registre o envio antes de acompanhar o retorno.")
            j.update(status=payload.status, updated_at=now())
            store.put("jobs", j, id)
            store.event(id, "Atualização manual: " + payload.note)
            return {"ok": True}

    @app.post("/api/runs", dependencies=[Depends(auth)])
    def run():
        engine.start_run()
        return {"ok": True}

    @app.post("/api/pause", dependencies=[Depends(auth)])
    def pause():
        # Pause must remain available even while a model call holds the engine lock.
        s = engine.settings()
        s["paused"] = True
        store.put("settings", s)
        return {"ok": True}

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
            j["status"] = payload.status
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

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

    return app
