import smtplib, ssl, re, secrets
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from email.utils import formatdate
from .matching import normalized


def email_eligible(job):
    recipient = job.get("recipient", "")
    description = job.get("description", "")
    text = normalized(description)
    # Instructions this connector cannot honor require assisted submission.
    if re.search(
        r"\b(assunto|subject|carta de apresentacao|pretensao salarial|portfolio)\b",
        text,
    ):
        return False
    if re.search(
        r"\bnao\s+(envie|enviar|encaminhe|encaminhar)|vaga\s+(encerrada|fechada|preenchida)|processo seletivo encerrado",
        text,
    ):
        return False
    addresses = re.findall(r"[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,.)]+", description)
    return bool(
        recipient
        and recipient.lower() in [a.lower() for a in addresses]
        and re.search(
            r"\b(envie|enviar|encaminhe|encaminhar)\b", normalized(description)
        )
        and re.search(r"\b(curriculo|candidatura|cv)\b", normalized(description))
    )


def build_email(settings, profile, job, pdf, message_id):
    message = EmailMessage()
    message["From"] = settings["smtp_from"]
    message["To"] = job["recipient"]
    message["Subject"] = "Candidatura: " + job["title"]
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = message_id
    message.set_content(
        f"Olá,\n\nEncaminho meu currículo para a vaga de {job['title']} na {job['company']}.\n\nFico à disposição para conversar.\n\n{profile['name']}\n{profile.get('email', '')}\n{profile.get('phone', '')}"
    )
    message.add_attachment(
        pdf, maintype="application", subtype="pdf", filename="Curriculo.pdf"
    )
    return message


def smtp_send(settings, message):
    context = ssl.create_default_context()
    if settings["smtp_security"] == "ssl":
        client = smtplib.SMTP_SSL(
            settings["smtp_host"], settings["smtp_port"], timeout=30, context=context
        )
    else:
        client = smtplib.SMTP(settings["smtp_host"], settings["smtp_port"], timeout=30)
    try:
        if settings["smtp_security"] == "starttls":
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        if settings["smtp_user"]:
            client.login(settings["smtp_user"], settings["smtp_password"])
        refused = client.send_message(message)
        if refused:
            raise ValueError("Destinatário recusado pelo servidor SMTP.")
    finally:
        # A QUIT failure must not turn an accepted DATA into an unconfirmed send.
        try:
            client.quit()
        except Exception:
            client.close()


def parse_followup(data, jobs):
    message = BytesParser(policy=default).parsebytes(data)
    part = message.get_body(preferencelist=("plain",))
    body = part.get_content() if part else ""
    text = (str(message.get("Subject", "")) + "\n" + str(body))[:30000]
    references = " ".join(
        str(message.get(k, "")) for k in ["In-Reply-To", "References"]
    )
    sent = [
        j
        for j in jobs
        if j.get("status")
        in [
            "sent",
            "receipt",
            "selection",
            "interview",
            "offer",
            "rejected",
            "uncertain",
            "submitted_manual",
        ]
    ]
    exact = [j for j in sent if j.get("message_id") and j["message_id"] in references]
    candidates = exact or [
        j
        for j in sent
        if normalized(j["company"]) in normalized(text)
        and normalized(j["title"]) in normalized(text)
    ]
    status = "selection"
    if re.search(
        r"nao (seguiremos|avancaremos)|não (seguiremos|avançaremos)|outros candidatos|reprovad|não foi selecionad",
        text,
        re.I,
    ):
        status = "rejected"
    elif re.search(r"entrevista|interview", text, re.I):
        status = "interview"
    elif re.search(r"proposta de (trabalho|contrata)|carta.proposta", text, re.I):
        status = "offer"
    elif re.search(
        r"(recebemos|recebida).{0,40}(candidatura|currículo|curriculo)", text, re.I
    ):
        status = "receipt"
    return {
        "id": secrets.token_hex(12),
        "subject": str(message.get("Subject", ""))[:300],
        "from": str(message.get("From", ""))[:300],
        "excerpt": text[:3000],
        "candidates": [j["id"] for j in candidates],
        "suggested_status": status,
        "confirmed": False,
    }
