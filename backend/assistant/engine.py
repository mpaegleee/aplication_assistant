import threading, hashlib, json, secrets, time
from datetime import datetime
from zoneinfo import ZoneInfo
from .models import Profile, Settings
from .store import now
from .matching import hard_blocks, fingerprint, validate_analysis, infer_area
from .ai import AI
from .sources import (
    canonical_url,
    public_fetch,
    read_source,
    read_board,
    application_identity,
)
from .documents import resume_pdf
from .mail import email_eligible, build_email, smtp_send, prepare_delivery
from .connectors import CONNECTORS, platform_for, source_platform, source_address
from .history import record_stage

TERMINAL = {
    "sent",
    "uncertain",
    "submitted_manual",
    "receipt",
    "selection",
    "interview",
    "technical",
    "manager_interview",
    "offer",
    "rejected",
    "withdrawn",
    "closed",
}


class Engine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.running = False
        self.stop = threading.Event()
        self.thread = None
        self.mail_lock = threading.Lock()
        self.mail_thread = None
        self.browser = None

    def recover(self):
        # Called only after acquiring the cross-process installation lock.
        for run in self.store.all("runs"):
            if run.get("status") == "running":
                run.update(status="failed", finished_at=now())
                run["errors"].append("Aplicação encerrada durante a execução anterior.")
                self.store.put("runs", run, run["id"])
        # Never retry interrupted sends after restart.
        for j in self.store.all("jobs"):
            if j.get("status") == "sending":
                j["status"] = "uncertain"
                self.store.put("jobs", j, j["id"])
                self.store.event(
                    j["id"],
                    "Execução interrompida durante envio. Confira manualmente antes de qualquer nova candidatura.",
                )

    def settings(self):
        return Settings.model_validate(
            self.store.get("settings", default={})
        ).model_dump()

    def profile(self):
        return Profile.model_validate(
            self.store.get("profile", default={})
        ).model_dump()

    def add_job(self, data, origin=None):
        with self.lock:
            data = prepare_delivery(data)
            data["url"] = canonical_url(data.get("url", ""))
            data["application_url"] = canonical_url(data.get("application_url", ""))
            key = application_identity(
                data["application_url"] or data["url"]
            ) or "|".join(
                str(data.get(x, "")).lower().strip()
                for x in ["company", "title", "location"]
            )
            id = hashlib.sha256(key.encode()).hexdigest()[:24]
            j = {
                **data,
                "id": id,
                "status": "new",
                "created_at": now(),
                "analysis": None,
                "approved": False,
                "origins": [
                    origin
                    or {
                        "url": data["url"],
                        "platform": "company"
                        if platform_for(data["url"]) == "inhire"
                        else platform_for(data["url"], "company"),
                        "source": data.get("source", "manual"),
                    }
                ],
                "destination": "email"
                if email_eligible(data)
                else platform_for(data.get("application_url") or data["url"]),
            }
            created = self.store.insert("jobs", j, id)
            if not created:
                existing = self.store.get("jobs", id)
                origins = existing.setdefault("origins", [])
                for item in j["origins"]:
                    if item not in origins:
                        origins.append(item)
                if (
                    existing["status"] not in TERMINAL
                    and existing["description"] != data["description"]
                ):
                    existing.update(
                        data,
                        status="new",
                        analysis=None,
                        approved=False,
                        pending_reason="Descrição atualizada pela fonte; nova análise necessária.",
                    )
                self.store.put("jobs", existing, id)
            if created:
                self.store.event(id, "Oportunidade adicionada.")
            return self.store.get("jobs", id), created

    def require_job(self, id):
        j = self.store.get("jobs", id)
        if not j:
            raise ValueError("Vaga não encontrada.")
        return j

    def analyze(self, id, force=False):
        with self.lock:
            j = prepare_delivery(self.require_job(id))
            p = self.profile()
            s = self.settings()
            if j["status"] in TERMINAL or j["status"] == "sending":
                raise ValueError(
                    "Candidatura já enviada, encerrada ou com resultado incerto."
                )
            if not j.get("area_reviewed") and s["auto_classify_areas"]:
                inferred = infer_area(j["title"])
                if inferred:
                    j.update(
                        area=inferred,
                        area_reviewed=True,
                        area_review_method="title_rule",
                    )
                    self.store.event(id, "Área classificada pelo cargo: " + inferred)
            current = fingerprint(p, j, s)
            if not force and (j.get("analysis") or {}).get("fingerprint") == current:
                return j
            blockers = hard_blocks(p, j)
            j["approved"] = False
            if blockers:
                j.update(
                    status="blocked",
                    analysis={
                        "blocks": blockers,
                        "score": None,
                        "confidence": None,
                        "fingerprint": current,
                    },
                )
            else:
                raw = AI(self.store).analyze(s, p, j)
                analysis = validate_analysis(raw, p, j)
                analysis["blocks"] = []
                analysis["threshold_used"] = s["threshold"]
                analysis["confidence_used"] = s["minimum_confidence"]
                analysis["fingerprint"] = fingerprint(p, j, s)
                j["analysis"] = analysis
                j["status"] = (
                    "ready"
                    if analysis["score"] >= s["threshold"]
                    and analysis["confidence"] >= s["minimum_confidence"]
                    else "review"
                )
            self.store.put("jobs", j, id)
            self.store.event(id, "Análise concluída; confira evidências e lacunas.")
            return j

    def valid_analysis(self, j):
        p = self.profile()
        s = self.settings()
        a = j.get("analysis") or {}
        blocks = hard_blocks(p, j)
        if blocks:
            raise ValueError(" ".join(blocks))
        if a.get("fingerprint") != fingerprint(p, j, s):
            raise ValueError("Perfil, vaga ou política mudou. Analise novamente.")
        if (
            a.get("score", -1) < s["threshold"]
            or a.get("confidence", -1) < s["minimum_confidence"]
        ):
            raise ValueError("Aderência ou confiança abaixo do limite configurado.")
        return p, s, a

    def approve(self, id):
        with self.lock:
            j = self.require_job(id)
            if j["status"] in TERMINAL:
                raise ValueError("Candidatura encerrada ou enviada.")
            self.valid_analysis(j)
            j["approved"] = True
            j["status"] = "ready"
            self.store.put("jobs", j, id)
            self.store.event(id, "Usuário aprovou esta versão da candidatura.")
            return j

    def pdf(self, id):
        j = self.require_job(id)
        if j.get("resume_snapshot"):
            return bytes.fromhex(j["resume_snapshot"])
        p, s, a = self.valid_analysis(j)
        return resume_pdf(p, a)

    def send(self, id):
        with self.lock:
            j = self.require_job(id)
            if j["status"] in TERMINAL or j["status"] == "sending":
                raise ValueError(
                    "Candidatura enviada, encerrada ou com resultado incerto; reenvio impedido."
                )
            identity = application_identity(
                j.get("application_url") or j.get("url", "")
            )
            if identity and any(
                other["id"] != id
                and other["status"] in TERMINAL
                and application_identity(
                    other.get("application_url") or other.get("url", "")
                )
                == identity
                for other in self.store.all("jobs")
            ):
                raise ValueError(
                    "Já existe candidatura enviada, encerrada ou incerta para esse destino. Confira o histórico antes de continuar."
                )
            p, s, a = self.valid_analysis(j)
            if s["paused"]:
                raise ValueError(
                    "Rotina pausada. Retome nas configurações antes de enviar."
                )
            if s["mode"] == "review" and not j.get("approved"):
                raise ValueError("Aprovação necessária para esta candidatura.")
            if "email" not in s["allowed_destinations"]:
                raise ValueError("Destino e-mail não autorizado nas configurações.")
            if not s["email_enabled"] or not s["smtp_host"] or not s["smtp_from"]:
                raise ValueError("Habilite e configure o envio de e-mail.")
            if not email_eligible(j):
                raise ValueError(
                    "Envio assistido: confira destinatário, assunto literal e documentos exigidos pelo anúncio."
                )
            pdf = resume_pdf(p, a)
            message_id = "<" + secrets.token_hex(16) + "@application-assistant.local>"
            message = build_email(s, p, j, pdf, message_id)
            day = datetime.now(ZoneInfo(s["timezone"])).date().isoformat()
            if not self.store.reserve("sends", day, s["daily_limit"]):
                raise ValueError("Limite diário de tentativas de envio atingido.")
            j.update(
                status="sending",
                message_id=message_id,
                resume_snapshot=pdf.hex(),
                submitted_profile=p,
                attempted_at=now(),
            )
            self.store.put("jobs", j, id)
            self.store.event(id, "Tentativa de envio SMTP iniciada.")
            try:
                smtp_send(s, message)
            except Exception:
                j.update(status="uncertain")
                self.store.put("jobs", j, id)
                self.store.event(
                    id,
                    "Resultado SMTP incerto. Confira a caixa de enviados e o destinatário; não haverá reenvio automático.",
                )
                raise ValueError(
                    "Resultado do envio incerto. Verifique manualmente; reenvio automático bloqueado."
                )
            j.update(
                destination="email",
                pending_reason="",
                pending_code="",
                submitted_subject=str(message["Subject"]),
            )
            record_stage(j, "sent", "smtp")
            self.store.put("jobs", j, id)
            self.store.event(
                id,
                "Servidor SMTP aceitou o envio. Isso não comprova entrega ou leitura.",
            )
            return j

    def browser_apply(self, id, submit=False):
        with self.lock:
            job = self.store.get("jobs", id)
            if not job:
                raise ValueError("Vaga não encontrada.")
            if job["status"] in TERMINAL or job["status"] == "sending":
                raise ValueError(
                    "Candidatura já tentada ou concluída. Confira o histórico."
                )
            profile, settings, analysis = self.valid_analysis(job)
            if settings["paused"]:
                raise ValueError(
                    "Retome a rotina antes de compartilhar dados com o portal."
                )
            if settings["mode"] == "review" and not job.get("approved"):
                raise ValueError("Aprove esta candidatura antes de preencher o portal.")
            url = job.get("application_url") or job["url"]
            if (
                platform_for(url) != "inhire"
                or "inhire" not in settings["allowed_destinations"]
            ):
                raise ValueError(
                    "Habilite InHire nos destinos. Este fluxo atende formulários diretos InHire."
                )
            from .browser import allowed_url

            if not allowed_url(url, "inhire") or not self.browser:
                raise ValueError("Endereço ou navegador indisponível.")
            identity = application_identity(url)
            for other in self.store.all("jobs"):
                if (
                    other["id"] != id
                    and other["status"] in TERMINAL | {"sending"}
                    and application_identity(
                        other.get("application_url") or other.get("url", "")
                    )
                    == identity
                ):
                    raise ValueError(
                        "Já existe tentativa para esta vaga em outro registro."
                    )
            pdf = resume_pdf(profile, analysis)
            attempted = False

            def intent():
                nonlocal attempted
                # Recheck persisted configuration immediately before the final click.
                current = self.store.get("jobs", id)
                self.valid_analysis(current)
                config = self.settings()
                if (
                    config["paused"]
                    or "inhire" not in config["allowed_destinations"]
                    or (config["mode"] == "review" and not current.get("approved"))
                ):
                    raise ValueError(
                        "Configuração ou aprovação alterada. Envio cancelado."
                    )
                day = datetime.now(ZoneInfo(config["timezone"])).date().isoformat()
                if not self.store.reserve("sends", day, config["daily_limit"]):
                    raise ValueError("Limite diário de tentativas atingido.")
                job.update(
                    status="sending",
                    destination="inhire",
                    attempted_at=now(),
                    browser_attempt=secrets.token_hex(16),
                    resume_snapshot=pdf.hex(),
                    submitted_profile=profile,
                )
                self.store.put("jobs", job, id)
                attempted = True
                self.store.event(id, "Tentativa de envio ao portal iniciada.")

            try:
                result = self.browser.call(
                    self.browser.inhire(url, profile, pdf, submit, intent), timeout=110
                )
            except Exception:
                if attempted:
                    job.update(
                        status="uncertain",
                        pending_reason="Tentativa interrompida. Confira o portal; repetição automática bloqueada.",
                    )
                    self.store.put("jobs", job, id)
                raise
            if result["status"] == "confirmed":
                self.store.put(
                    "browser_proofs",
                    {
                        "image": result.pop("proof"),
                        "at": now(),
                        "attempt": job["browser_attempt"],
                    },
                    id,
                )
                job.update(
                    pending_reason="",
                    pending_code="",
                    destination="inhire",
                    browser_confirmed=True,
                )
                record_stage(job, "receipt", "browser")
                job["sent_at"] = now()
            elif attempted:
                job.update(
                    status="uncertain",
                    pending_code="browser_uncertain",
                    pending_reason=result["reason"],
                )
            else:
                job.update(
                    pending_code="browser_" + result["status"],
                    pending_reason=result["reason"],
                )
            self.store.put("jobs", job, id)
            self.store.event(id, result["reason"])
            return {"status": result["status"], "reason": result["reason"]}

    def start_run(self):
        if self.running:
            raise ValueError("Já existe uma execução em andamento.")
        with self.lock:
            if self.running:
                raise ValueError("Já existe uma execução em andamento.")
            if self.settings()["paused"]:
                raise ValueError("Retome a rotina nas configurações.")
            self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def pending(self, job, code, message):
        if job.get("pending_code") != code or job.get("pending_reason") != message:
            self.store.event(job["id"], message)
        job.update(pending_code=code, pending_reason=message)
        self.store.put("jobs", job, job["id"])
        return code

    def process(self, job):
        settings = self.settings()
        if job["status"] in TERMINAL or job["status"] == "sending":
            return "already_submitted"
        if settings["paused"] or self.stop.is_set():
            return "paused"
        job = self.analyze(job["id"])
        if job["status"] == "blocked":
            return self.pending(job, "blocked", " ".join(job["analysis"]["blocks"]))
        if job["status"] == "review":
            return self.pending(
                job,
                "below_threshold",
                "Aderência ou confiança abaixo do limite configurado.",
            )
        destination = (
            "email"
            if email_eligible(job)
            else platform_for(job.get("application_url") or job.get("url", ""))
        )
        job["destination"] = destination
        if destination not in settings["allowed_destinations"]:
            return self.pending(
                job, "destination_disabled", "Destino não autorizado: " + destination
            )
        if destination == "inhire":
            if settings["mode"] == "review" and not job.get("approved"):
                return self.pending(
                    job, "approval_required", "Esta candidatura aguarda aprovação."
                )
            result = self.browser_apply(job["id"], submit=True)
            return (
                "sent"
                if result["status"] == "confirmed"
                else "browser_" + result["status"]
            )
        if destination != "email":
            return self.pending(
                job,
                "connector_unavailable",
                "Finalização em "
                + destination
                + " aguarda conector autenticado validado; não houve envio.",
            )
        if not settings["email_enabled"]:
            return self.pending(
                job,
                "email_disabled",
                "Habilite o envio SMTP para concluir esta candidatura.",
            )
        if settings["mode"] == "review" and not job.get("approved"):
            return self.pending(
                job,
                "approval_required",
                "Esta candidatura aguarda aprovação conforme o modo escolhido.",
            )
        self.store.put("jobs", job, job["id"])
        self.send(job["id"])
        return "sent"

    def run(self):
        run = {
            "id": secrets.token_hex(12),
            "started_at": now(),
            "status": "running",
            "found": 0,
            "imported": 0,
            "duplicates": 0,
            "analyzed": 0,
            "eligible": 0,
            "sent": 0,
            "pending": 0,
            "errors": [],
            "items": [],
            "sources": [],
        }
        self.store.put("runs", run, run["id"])
        started = time.monotonic()
        limit = self.settings()["run_time_limit_minutes"] * 60

        def interrupted():
            return (
                self.stop.is_set()
                or self.settings()["paused"]
                or time.monotonic() - started >= limit
            )

        try:
            settings = self.settings()
            capabilities = {c["id"]: c for c in CONNECTORS}
            for platform in settings["search_platforms"]:
                if not capabilities[platform]["discovery"]:
                    run["errors"].append(
                        capabilities[platform]["name"]
                        + ": "
                        + capabilities[platform]["reason"]
                    )
            seen = set()
            for source in settings["sources"]:
                if interrupted():
                    break
                platform = source_platform(source)
                if (
                    not source["enabled"]
                    or platform not in settings["search_platforms"]
                ):
                    continue
                if not capabilities[platform]["discovery"]:
                    continue
                entry = {
                    "name": source["name"],
                    "platform": platform,
                    "found": 0,
                    "new": 0,
                    "duplicates": 0,
                    "status": "running",
                }
                run["sources"].append(entry)
                try:
                    address = source_address(source)
                    allowed = list(settings["allowed_domains"])
                    if source.get("kind") == "greenhouse":
                        allowed.append("boards-api.greenhouse.io")
                    if source.get("kind") == "lever":
                        allowed.append("api.lever.co")
                    text = public_fetch(address, allowed)
                    rows = (
                        read_board(text, source)
                        if source.get("kind") in ["greenhouse", "lever"]
                        else read_source(text, address)
                    )
                    for data in rows:
                        if interrupted() or len(seen) >= settings["max_jobs_per_run"]:
                            break
                        entry["found"] += 1
                        run["found"] += 1
                        job, created = self.add_job(
                            data,
                            {
                                "url": data.get("url") or address,
                                "platform": platform,
                                "source": source["name"],
                            },
                        )
                        seen.add(job["id"])
                        entry["new"] += int(created)
                        entry["duplicates"] += int(not created)
                        run["imported"] += int(created)
                        run["duplicates"] += int(not created)
                    entry["status"] = "completed"
                except Exception:
                    entry["status"] = "failed"
                    run["errors"].append(
                        "Falha ao consultar a fonte: " + source["name"]
                    )
                self.store.put("runs", run, run["id"])
            jobs = []
            for job in self.store.all("jobs"):
                if job["status"] in TERMINAL or job["status"] == "sending":
                    continue
                origins = job.get("origins") or [
                    {"platform": platform_for(job.get("url", ""), "company")}
                ]
                if not any(
                    o["platform"] in settings["search_platforms"] for o in origins
                ):
                    continue
                jobs.append(job)
                if len(jobs) >= settings["max_jobs_per_run"]:
                    break
            for index, job in enumerate(jobs):
                if interrupted():
                    break
                item = {
                    "job_id": job["id"],
                    "stage": "analysis",
                    "result": "processing",
                    "at": now(),
                }
                run["items"].append(item)
                self.store.put("runs", run, run["id"])
                try:
                    result = self.process(job)
                    latest = self.require_job(job["id"])
                    run["sent"] += int(result == "sent")
                    run["pending"] += int(
                        result not in ["sent", "already_submitted", "paused"]
                    )
                    item.update(
                        result=result,
                        stage="sent" if result == "sent" else "pending",
                        destination=latest.get("destination", ""),
                    )
                except Exception as exc:
                    latest = self.require_job(job["id"])
                    code = (
                        "uncertain"
                        if latest["status"] == "uncertain"
                        else "execution_error"
                    )
                    detail = (
                        str(exc)[:500]
                        if isinstance(exc, ValueError)
                        else "Não foi possível processar a oportunidade."
                    )
                    self.pending(latest, code, detail)
                    item.update(result=code, stage="pending")
                    run["pending"] += 1
                latest = self.require_job(job["id"])
                analysis = latest.get("analysis") or {}
                run["analyzed"] += int(analysis.get("score") is not None)
                run["eligible"] += int(
                    analysis.get("score") is not None
                    and analysis["score"]
                    >= analysis.get("threshold_used", settings["threshold"])
                    and analysis.get("confidence", 0)
                    >= analysis.get("confidence_used", settings["minimum_confidence"])
                )
                self.store.put("runs", run, run["id"])
                if index < len(jobs) - 1 and self.stop.wait(
                    settings["interval_seconds"]
                ):
                    break
            run["status"] = (
                "paused"
                if self.settings()["paused"] or self.stop.is_set()
                else "time_limit"
                if time.monotonic() - started >= limit
                else "completed"
            )
        except Exception:
            run["status"] = "failed"
            run["errors"].append(
                "Execução interrompida. Confira perfil e configurações."
            )
        finally:
            run["finished_at"] = now()
            self.store.put("runs", run, run["id"])
            self.running = False

    def sync_mail(self):
        if not self.mail_lock.acquire(blocking=False):
            raise ValueError("Leitura de e-mail já está em andamento.")
        try:
            from .mail_sync import sync_mail

            return sync_mail(self.store, self.settings(), self.lock, self.stop)
        finally:
            self.mail_lock.release()

    def scheduler(self):
        while not self.stop.wait(10):
            s = self.settings()
            local = datetime.now(ZoneInfo(s["timezone"]))
            mail_state = self.store.get("mail_status", default={})
            due = (
                time.time() - mail_state.get("last_poll", 0)
                >= s["imap_poll_minutes"] * 60
            )
            if (
                s["imap_enabled"]
                and due
                and not self.mail_lock.locked()
                and not (self.mail_thread and self.mail_thread.is_alive())
            ):
                self.mail_thread = threading.Thread(target=self.sync_mail, daemon=True)
                self.mail_thread.start()
            if (
                s["paused"]
                or not s["schedule_enabled"]
                or local.weekday() not in s["weekdays"]
                or local.strftime("%H:%M") != s["time"]
            ):
                continue
            key = local.date().isoformat() + " " + s["time"] + " " + s["timezone"]
            if (
                self.store.get("schedule", default={}).get("last") == key
                or self.running
            ):
                continue
            self.store.put("schedule", {"last": key})
            try:
                self.start_run()
            except ValueError:
                pass
