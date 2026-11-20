import threading, hashlib, json, secrets, time
from datetime import datetime
from zoneinfo import ZoneInfo
from .models import Profile, Settings
from .store import now
from .matching import hard_blocks, fingerprint, validate_analysis
from .ai import AI
from .sources import canonical_url, public_fetch, read_source
from .documents import resume_pdf
from .mail import email_eligible, build_email, smtp_send

TERMINAL = {
    "sent",
    "uncertain",
    "submitted_manual",
    "receipt",
    "selection",
    "interview",
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

    def add_job(self, data):
        with self.lock:
            data = dict(data)
            data["url"] = canonical_url(data.get("url", ""))
            key = data["url"] or "|".join(
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
            }
            created = self.store.insert("jobs", j, id)
            if created:
                self.store.event(id, "Oportunidade adicionada.")
            return self.store.get("jobs", id), created

    def require_job(self, id):
        j = self.store.get("jobs", id)
        if not j:
            raise ValueError("Vaga não encontrada.")
        return j

    def analyze(self, id):
        with self.lock:
            j = self.require_job(id)
            p = self.profile()
            s = self.settings()
            if j["status"] in TERMINAL or j["status"] == "sending":
                raise ValueError(
                    "Candidatura já enviada, encerrada ou com resultado incerto."
                )
            blockers = hard_blocks(p, j)
            j["approved"] = False
            if blockers:
                j.update(
                    status="blocked",
                    analysis={"blocks": blockers, "score": None, "confidence": None},
                )
            else:
                raw = AI(self.store).analyze(s, p, j)
                analysis = validate_analysis(raw, p, j)
                analysis["blocks"] = []
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
            p, s, a = self.valid_analysis(j)
            if s["paused"]:
                raise ValueError(
                    "Rotina pausada. Retome nas configurações antes de enviar."
                )
            if s["mode"] == "review" and not j.get("approved"):
                raise ValueError("Aprovação necessária para esta candidatura.")
            if not s["email_enabled"] or not s["smtp_host"] or not s["smtp_from"]:
                raise ValueError("Habilite e configure o envio de e-mail.")
            if not email_eligible(j):
                raise ValueError(
                    "Envio assistido: confira o destinatário e as instruções. Assunto, carta ou anexos personalizados precisam de finalização manual."
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
            j.update(status="sent", sent_at=now())
            self.store.put("jobs", j, id)
            self.store.event(
                id,
                "Servidor SMTP aceitou o envio. Isso não comprova entrega ou leitura.",
            )
            return j

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

    def run(self):
        run = {
            "id": secrets.token_hex(12),
            "started_at": now(),
            "status": "running",
            "imported": 0,
            "analyzed": 0,
            "sent": 0,
            "errors": [],
        }
        self.store.put("runs", run, run["id"])
        try:
            s = self.settings()
            for source in s["sources"]:
                if self.stop.is_set() or self.settings()["paused"]:
                    break
                if not source["enabled"]:
                    continue
                try:
                    for data in read_source(
                        public_fetch(source["url"], s["allowed_domains"]), source["url"]
                    )[: s["max_jobs_per_run"]]:
                        _, created = self.add_job(data)
                        run["imported"] += int(created)
                except Exception:
                    run["errors"].append(
                        "Não foi possível importar a fonte: " + source["name"]
                    )
            pending = [
                j for j in self.store.all("jobs") if j["status"] in ["new", "ready"]
            ][: s["max_jobs_per_run"]]
            for j in pending:
                if self.stop.is_set() or self.settings()["paused"]:
                    break
                try:
                    if j["status"] == "new":
                        j = self.analyze(j["id"])
                        run["analyzed"] += 1
                    s = self.settings()
                    if (
                        j["status"] == "ready"
                        and (s["mode"] == "automatic" or j.get("approved"))
                        and s["email_enabled"]
                        and email_eligible(j)
                    ):
                        self.send(j["id"])
                        run["sent"] += 1
                except Exception as e:
                    if isinstance(e, ValueError):
                        run["errors"].append(str(e)[:500])
                    else:
                        run["errors"].append(
                            "Não foi possível processar uma oportunidade."
                        )
                self.store.put("runs", run, run["id"])
                if self.stop.wait(s["interval_seconds"]):
                    break
            run["status"] = (
                "paused"
                if self.settings()["paused"] or self.stop.is_set()
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

    def scheduler(self):
        while not self.stop.wait(10):
            s = self.settings()
            local = datetime.now(ZoneInfo(s["timezone"]))
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
