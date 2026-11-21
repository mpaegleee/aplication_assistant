"""Leitura IMAP TLS, sem marcar mensagens como lidas e sem responder e-mails."""

import imaplib, ssl, hashlib, time
from datetime import datetime, timedelta, timezone
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr
from .mail import parse_followup
from .history import record_stage
from .store import now

RANK = {
    "sent": 0,
    "submitted_manual": 0,
    "uncertain": 0,
    "receipt": 1,
    "selection": 2,
    "technical": 3,
    "interview": 4,
    "manager_interview": 5,
    "offer": 6,
}


def apply_suggestion(store, suggestion, auto=False):
    if len(suggestion["candidates"]) != 1 or not suggestion.get("recognized"):
        return False
    job = store.get("jobs", suggestion["candidates"][0])
    if not job:
        return False
    status = suggestion["suggested_status"]
    sender = parseaddr(suggestion["from"])[1].lower()
    # Automatic updates require an exact conversation reference AND the same sender
    # as the application recipient. Company-name matches remain suggestions only.
    if (
        not auto
        or suggestion.get("matched_by") != "thread"
        or sender != job.get("recipient", "").lower()
    ):
        return False
    if job["status"] in ["rejected", "withdrawn", "closed", "offer"]:
        return False
    if status != "rejected" and RANK.get(status, -1) <= RANK.get(job["status"], 0):
        return False
    record_stage(job, status, "email_thread")
    store.put("jobs", job, job["id"])
    suggestion.update(
        confirmed=True, job_id=job["id"], status=status, method="email_thread"
    )
    store.event(
        job["id"], "Etapa identificada em resposta da mesma conversa: " + status
    )
    return True


def sync_mail(store, settings, engine_lock, stop=None, *, on_alert=None):
    from .linkedin_alerts import ALERT_SENDER, parse_alert

    alerts = on_alert is not None
    mode = "linkedin_alert" if alerts else "mail"
    if not alerts and not settings["imap_enabled"]:
        raise ValueError("Habilite a leitura IMAP nas configurações.")
    if (
        not settings["imap_host"]
        or not settings["imap_user"]
        or not settings["imap_password"]
    ):
        raise ValueError("Configure servidor, usuário e senha de aplicativo IMAP.")
    state = store.get(mode + "_status", default={})
    state.update(
        last_poll=time.time(), last_checked_at=now(), error="", imported=0, updated=0
    )
    state["found"] = 0
    store.put(mode + "_status", state)
    connection = None
    try:
        connection = imaplib.IMAP4_SSL(
            settings["imap_host"],
            settings["imap_port"],
            ssl_context=ssl.create_default_context(),
            timeout=10,
        )
        connection.login(settings["imap_user"], settings["imap_password"])
        result, _ = connection.select(settings["imap_folder"], readonly=True)
        if result != "OK":
            raise ValueError("Não foi possível abrir a pasta IMAP configurada.")
        days = settings["max_job_age_days"] if alerts else 15
        date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        criteria = ["SINCE", date]
        if alerts:
            criteria += ["FROM", ALERT_SENDER]
        result, data = connection.uid("search", None, *criteria)
        if result != "OK":
            raise ValueError("Não foi possível consultar mensagens recentes.")
        account = hashlib.sha256(
            (
                settings["imap_host"]
                + "|"
                + settings["imap_user"]
                + "|"
                + settings["imap_folder"]
            ).encode()
        ).hexdigest()
        cursor = store.get(mode + "_cursor", account, default={})
        validity = connection.response("UIDVALIDITY")[1]
        validity = repr(validity)
        last = int(cursor.get("uid", 0)) if cursor.get("validity") == validity else 0
        uids = [u for u in data[0].split() if u.isdigit() and int(u) > last]
        uids = (
            uids[: settings["imap_max_messages"]]
            if last
            else uids[-settings["imap_max_messages"] :]
        )

        def advance(uid):
            store.put(
                mode + "_cursor", {"uid": int(uid), "validity": validity}, account
            )

        for uid in uids:
            if stop and stop.is_set():
                break
            result, meta = connection.uid("fetch", uid, "(RFC822.SIZE)")
            if result != "OK":
                break
            import re

            size = re.search(
                rb"RFC822.SIZE (\d+)",
                b" ".join(x for x in meta if isinstance(x, bytes)),
            )
            if not size:
                break
            if int(size.group(1)) > 2_000_000:
                advance(uid)
                continue
            result, parts = connection.uid("fetch", uid, "(BODY.PEEK[])")
            if result != "OK":
                break
            content = next(
                (
                    x[1]
                    for x in parts
                    if isinstance(x, tuple) and isinstance(x[1], bytes)
                ),
                None,
            )
            if not content or len(content) > 2_000_000:
                advance(uid)
                continue
            identity = hashlib.sha256(content).hexdigest()
            if store.get(mode + "_seen", identity):
                advance(uid)
                continue
            with engine_lock:
                if alerts:
                    for job in parse_alert(content):
                        state["found"] += 1
                        state["imported"] += int(on_alert(job))
                else:
                    suggestion = parse_followup(content, store.all("jobs"))
                    if suggestion["candidates"]:
                        suggestion["created_at"] = now()
                        suggestion["origin"] = "imap"
                        updated = apply_suggestion(
                            store, suggestion, settings["auto_followup"]
                        )
                        store.put("followups", suggestion, suggestion["id"])
                        state["imported"] += 1
                        state["updated"] += int(updated)
                store.put(mode + "_seen", {"at": now()}, identity)
                advance(uid)
    except imaplib.IMAP4.error:
        state["error"] = (
            "O servidor IMAP recusou o acesso. Confira senha de aplicativo, permissões e suporte a IMAP; alguns provedores exigem OAuth."
        )
    except ValueError:
        state["error"] = (
            "Não foi possível interpretar a pasta ou mensagem IMAP. Confira a configuração e tente novamente."
        )
    except Exception:
        state["error"] = (
            "Não foi possível ler a caixa postal. Confira servidor, conexão TLS e disponibilidade do serviço."
        )
    finally:
        if connection:
            try:
                connection.logout()
            except Exception:
                pass
        store.put(mode + "_status", state)
    return state
