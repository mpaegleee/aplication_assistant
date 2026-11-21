"""Bounded, semantic InHire adapter. No guessed answers or generic AI clicks."""

import re
import unicodedata

from playwright.async_api import Error as BrowserError


def normalize(value):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFD", value.lower())
            if unicodedata.category(c) != "Mn"
        ).split()
    ).strip(" :*?")


# Equivalent prompts share an explicitly supplied answer. Contract and period matter.
ANSWER_GROUPS = (
    {
        "pretensao salarial como clt",
        "qual sua pretensao salarial clt",
        "pretensao salarial clt",
    },
    {"qual sua ultima remuneracao", "ultima remuneracao"},
    {
        "possui certificacao psm i",
        "possui certificacao certificacao psm i (professional scrum master i)",
    },
)


def answer_for(label, profile, *, allow_summary=False):
    key = normalize(label)
    saved = [
        a["answer"]
        for a in profile.get("answers", [])
        if normalize(a["question"]) == key
    ]
    if saved:
        return saved[0] if len(set(saved)) == 1 else None
    for group in ANSWER_GROUPS:
        if key in group:
            answers = {
                a["answer"]
                for a in profile.get("answers", [])
                if normalize(a["question"]) in group
            }
            return answers.pop() if len(answers) == 1 else None
    if allow_summary and profile.get("confirmed"):
        category = {
            "experiencia profissional": "experience",
            "formacao academica": "education",
            "cursos e certificacoes": "course",
            "competencias": "skill",
        }.get(key)
        if category:
            summary = "\n".join(
                fact["text"]
                for fact in profile.get("facts", [])
                if fact.get("category") == category
            )
            # Leave large or ambiguous fields pending rather than silently truncating facts.
            return summary if 0 < len(summary) <= 2000 else None
    return {
        "cidade": profile.get("city"),
        "cidade atual": profile.get("city"),
        "perfil do linkedin": profile.get("linkedin_url"),
        "celular": profile.get("phone"),
        "nome": profile.get("name"),
        "full name": profile.get("name"),
        "nome completo": profile.get("name"),
        "seu nome completo": profile.get("name"),
        "email": profile.get("email"),
        "e-mail": profile.get("email"),
        "seu melhor email": profile.get("email"),
        "seu melhor e-mail": profile.get("email"),
        "celular com ddd": profile.get("phone"),
        "telefone": profile.get("phone"),
        "numero de celular": profile.get("phone"),
        "phone number": profile.get("phone"),
        "mobile phone number": profile.get("phone"),
        "linkedin": profile.get("linkedin_url"),
    }.get(key)


def share_authorized(url, profile):
    from urllib.parse import urlsplit
    from .connectors import platform_for

    question = "Autorizar envio de dados para " + (urlsplit(url).hostname or "")
    if any(
        normalize(a["question"]) == normalize(question)
        for a in profile.get("answers", [])
    ):
        return normalize(answer_for(question, profile) or "") == "sim"
    return platform_for(url) == profile.get("authorized_portal")


async def fill_inhire(page, profile, pdf, submit=False, before_submit=None):
    apply = page.get_by_role(
        "button",
        name=re.compile(r"^Candidatar-se (para a vaga|à vaga)$", re.IGNORECASE),
    )
    if (
        not await page.locator('input[type="file"]').count()
        and await apply.count()
        and await apply.first.is_enabled()
    ):
        await apply.first.click()
    # Wait for the actual form, not an arbitrary sleep or an inferred network request.
    try:
        await page.locator('input[type="file"]').first.wait_for(
            state="attached", timeout=12000
        )
    except BrowserError:
        return {
            "status": "pending",
            "reason": "Formulário não reconhecido, login ou verificação necessária. Abra o navegador.",
        }
    if await page.locator(
        'iframe[src*="captcha"], [data-sitekey], input[type="password"]'
    ).count():
        return {
            "status": "pending",
            "reason": "Login ou verificação exige sua intervenção no navegador.",
        }
    fields = await page.locator("input, textarea, select").evaluate_all("""elements => elements.map((e, i) => ({
        index: i, type: e.type, required: e.required || e.getAttribute('aria-required') === 'true',
        visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
        label: Array.from(e.labels || []).map(l => l.innerText).join(' ') || e.getAttribute('aria-label') || e.placeholder || '',
        disabled: e.disabled, value: e.value, accept: e.accept || '',
        group: e.closest('fieldset')?.querySelector('legend')?.innerText || e.closest('[role="radiogroup"]')?.getAttribute('aria-label') || (() => { let p=e.parentElement; for(let n=0;p && n<4;n++,p=p.parentElement) { const q=p.querySelector('p,legend,[data-question]'); if(q && !q.contains(e)) return q.innerText; } return ''; })()
    }))""")
    pending = []
    operations = []
    file_count = 0
    for field in fields:
        if field["disabled"] or field["type"] in (
            "hidden",
            "submit",
            "button",
            "reset",
        ):
            continue
        if field["type"] == "file":
            file_count += 1
            accepted = field["accept"].lower()
            if accepted and not any(
                x in accepted for x in ("pdf", "application/*", "*/*")
            ):
                pending.append("Formato de currículo diferente de PDF")
            else:
                operations.append((field, None))
            continue
        if not field["visible"]:
            continue
        if field["type"] in ("checkbox", "radio"):
            # Explicitly saved literal answer only; never infer consent/availability.
            question = field["group"] or field["label"]
            answer = answer_for(question, profile)
            if (
                answer
                and field["type"] == "radio"
                and normalize(answer)
                in (normalize(field["label"]), normalize(field["value"]))
            ) or (
                answer
                and field["type"] == "checkbox"
                and normalize(answer) in ("sim", "aceito")
            ):
                operations.append((field, True))
            elif not answer:
                pending.append(question or "Confirmação obrigatória sem resposta salva")
            continue
        answer = answer_for(
            field["label"], profile, allow_summary=field["type"] == "textarea"
        )
        if answer:
            operations.append((field, answer))
        else:
            pending.append(field["label"] or "Campo obrigatório não identificado")
    if file_count != 1:
        pending.append("Quantidade de anexos não reconhecida")
    if pending:
        return {
            "status": "pending",
            "reason": "Salve respostas exatas no perfil: "
            + "; ".join(dict.fromkeys(pending))[:1800],
        }
    # An acknowledgement for the exact destination is required before sharing profile data.
    from urllib.parse import urlsplit

    consent_question = "Autorizar envio de dados para " + urlsplit(page.url).hostname
    if not share_authorized(page.url, profile):
        return {
            "status": "pending",
            "reason": "Leia a política do portal e salve no perfil a resposta Sim para: "
            + consent_question,
        }
    for field, value in operations:
        locator = page.locator("input, textarea, select").nth(field["index"])
        if field["type"] == "file":
            await locator.set_input_files(
                {"name": "Curriculo.pdf", "mimeType": "application/pdf", "buffer": pdf}
            )
        elif value is True:
            await locator.check()
        elif field["type"] == "select-one":
            await locator.select_option(label=value)
        else:
            await locator.fill(value)
    button = page.get_by_role(
        "button",
        name=re.compile(r"^Candidatar-se (para a vaga|à vaga)$", re.IGNORECASE),
    ).last
    if not await button.count() or not await button.is_enabled():
        return {
            "status": "pending",
            "reason": "O portal ainda exige campos ou validações. Confira o navegador.",
        }
    if not submit:
        return {
            "status": "prepared",
            "reason": "Dados e currículo preenchidos. O envio ainda não foi realizado.",
        }
    if not before_submit:
        raise ValueError("Envio sem registro de tentativa não permitido.")
    confirmation = page.get_by_text(
        re.compile(
            r"(candidatura (enviada|realizada|recebida) com sucesso|recebemos (a )?sua candidatura|você se candidatou)",
            re.IGNORECASE,
        )
    )
    if await confirmation.count():
        return {
            "status": "pending",
            "reason": "Há uma mensagem anterior de candidatura. Confira o histórico do portal antes de enviar.",
        }
    before_submit()
    try:
        await button.click(timeout=10000)
        await confirmation.first.wait_for(state="visible", timeout=15000)
        return {
            "status": "confirmed",
            "reason": "Portal exibiu confirmação de candidatura.",
            "proof": (await page.screenshot(type="png")).hex(),
        }
    except BrowserError:
        return {
            "status": "uncertain",
            "reason": "Envio iniciado, mas sem confirmação inequívoca. Confira manualmente; não haverá repetição automática.",
        }
