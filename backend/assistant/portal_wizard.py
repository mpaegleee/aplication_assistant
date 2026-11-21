"""Experimental bounded wizard adapter; only literal answers and explicit final actions."""

import hashlib
import json
import re

from playwright.async_api import Error as BrowserError

from .portal_forms import answer_for, normalize

NEXT = re.compile(
    r"^(avançar|continuar|próximo|próxima|next|review|avaliar|revisar)(?: etapa)?$",
    re.IGNORECASE,
)
FINAL = re.compile(
    r"^(enviar candidatura|enviar inscrição|concluir candidatura|submit application|submit your application|submit)$",
    re.IGNORECASE,
)
SUCCESS = re.compile(
    r"(candidatura (enviada|realizada|recebida) com sucesso|recebemos (a )?sua candidatura|você se candidatou|application (was )?(submitted|sent)|your application has been)",
    re.IGNORECASE,
)


async def fill_wizard(page, platform, profile, pdf, submit=False, before_submit=None):
    uploaded = False
    visited = set()
    filename = "Curriculo-AA-" + hashlib.sha256(pdf).hexdigest()[:12] + ".pdf"
    if len(pdf) >= 2_000_000:
        return {"status": "pending", "reason": "Currículo excede 2 MB."}
    if await page.locator(
        'input[type="password"]:visible, iframe[src*="captcha"]:visible, [data-sitekey]:visible'
    ).count():
        return {
            "status": "pending",
            "reason": "Login ou verificação necessária. Use o navegador interno e libere o controle.",
        }
    if platform == "linkedin":
        entry = page.get_by_role(
            "button",
            name=re.compile(r"^(candidatura simplificada|easy apply)", re.IGNORECASE),
        )
        if await entry.count() == 1:
            await entry.click()
    for step in range(15):
        if (
            re.search(r"/login|/signin|/checkpoint|/authwall", page.url)
            or await page.locator(
                'input[type="password"]:visible, iframe[src*="captcha"]:visible'
            ).count()
        ):
            return {
                "status": "pending",
                "reason": "Sessão expirada ou verificação. Abra o portal, entre e libere o controle.",
            }
        from urllib.parse import urlsplit

        domain = urlsplit(page.url).hostname
        if (
            normalize(
                answer_for("Autorizar envio de dados para " + domain, profile) or ""
            )
            != "sim"
        ):
            return {
                "status": "pending",
                "reason": "Leia a política do portal e salve Sim para: Autorizar envio de dados para "
                + domain,
            }
        dialog = page.get_by_role("dialog")
        root = (
            dialog.first
            if await dialog.count() == 1
            else page.locator('main, [role="main"]').first
        )
        if not await root.count():
            return {
                "status": "pending",
                "reason": "Formulário não reconhecido. Abra a etapa de candidatura no navegador.",
            }
        controls = root.locator("input, textarea, select")
        fields = await controls.evaluate_all(
            """elements=>elements.map((e,i)=>({i,type:e.type,required:e.required||e.getAttribute('aria-required')==='true',visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length),disabled:e.disabled||e.readOnly,label:Array.from(e.labels||[]).map(l=>l.innerText).join(' ')||e.getAttribute('aria-label')||e.placeholder||'',group:e.closest('fieldset')?.querySelector('legend')?.innerText||e.closest('[role="radiogroup"]')?.getAttribute('aria-label')||'',value:e.value,accept:e.accept||''}))"""
        )
        signature = hashlib.sha256(
            json.dumps([page.url, fields], sort_keys=True).encode()
        ).hexdigest()
        if signature in visited:
            return {
                "status": "pending",
                "reason": "Etapa não avançou. Confira validações e perguntas no navegador.",
            }
        visited.add(signature)
        if len(fields) > 150:
            return {
                "status": "pending",
                "reason": "Formulário extenso ou desconhecido. Revisão manual necessária.",
            }
        missing = []
        operations = []
        resume_radios = False
        for f in fields:
            if f["disabled"] or f["type"] in ("hidden", "submit", "button", "reset"):
                continue
            if f["type"] == "file":
                if f["accept"] and not any(
                    x in f["accept"].lower() for x in ("pdf", "application/*", "*/*")
                ):
                    if f["required"]:
                        missing.append(f["label"] or "Documento adicional")
                    continue
                operations.append((f, "file"))
                continue
            if not f["visible"]:
                continue
            question = f["group"] or f["label"]
            answer = answer_for(question, profile)
            if f["type"] == "radio":
                if re.search(
                    r"\.(pdf|docx?)(?:\b|$)", f["label"], re.IGNORECASE
                ) or normalize(f["group"]) in ("curriculo", "resume"):
                    resume_radios = True
                    continue
                if answer and normalize(answer) in (
                    normalize(f["label"]),
                    normalize(f["value"]),
                ):
                    operations.append((f, True))
                elif not answer:
                    missing.append(question or "Pergunta de seleção")
            elif f["type"] == "checkbox":
                if answer and normalize(answer) in ("sim", "aceito"):
                    operations.append((f, True))
                elif f["required"]:
                    missing.append(question or "Confirmação obrigatória")
            elif answer:
                operations.append((f, answer))
            elif f["required"] or not f["value"]:
                missing.append(question or "Campo sem identificação")
        if missing:
            return {
                "status": "pending",
                "reason": "Respostas exatas necessárias no perfil: "
                + "; ".join(dict.fromkeys(missing))[:1700],
            }
        if not fields and not uploaded:
            return {
                "status": "pending",
                "reason": "Abra o formulário de candidatura. Nenhum envio será feito a partir de um botão inicial ambíguo.",
            }
        for field, value in operations:
            element = controls.nth(field["i"])
            if field["type"] == "file":
                await element.set_input_files(
                    {"name": filename, "mimeType": "application/pdf", "buffer": pdf}
                )
                uploaded = True
            elif value is True:
                await element.check()
            elif field["type"] == "select-one":
                await element.select_option(label=value)
            else:
                await element.fill(value)
        if resume_radios:
            fresh_resume = root.get_by_role(
                "radio", name=re.compile(re.escape(filename))
            )
            if not uploaded or await fresh_resume.count() != 1:
                return {
                    "status": "pending",
                    "reason": "Selecione o currículo recém-gerado no portal; não foi possível vincular o novo arquivo à seleção de currículo.",
                }
            await fresh_resume.check()
        final = root.get_by_role("button", name=FINAL)
        if await final.count() == 1 and await final.is_visible():
            if not uploaded:
                return {
                    "status": "pending",
                    "reason": "Não foi possível confirmar o anexo do currículo desta tentativa. Não será usado um currículo antigo automaticamente.",
                }
            if not await final.is_enabled():
                return {
                    "status": "pending",
                    "reason": "Portal ainda exige validações antes do envio.",
                }
            if not submit:
                return {
                    "status": "prepared",
                    "reason": "Etapas preenchidas e currículo anexado. Envio final ainda não realizado.",
                }
            confirmation = page.get_by_text(SUCCESS)
            if await confirmation.count():
                return {
                    "status": "pending",
                    "reason": "Há uma mensagem anterior de candidatura. Confira o histórico.",
                }
            before_submit()
            try:
                await final.click(timeout=10000)
                await confirmation.first.wait_for(state="visible", timeout=15000)
                return {
                    "status": "confirmed",
                    "reason": "Portal exibiu uma nova confirmação de candidatura.",
                    "proof": (await page.screenshot(type="png")).hex(),
                }
            except BrowserError:
                return {
                    "status": "uncertain",
                    "reason": "Envio iniciado sem confirmação inequívoca. Confira manualmente; repetição automática bloqueada.",
                }
        next_button = root.get_by_role("button", name=NEXT)
        if await next_button.count() != 1 or not await next_button.is_enabled():
            return {
                "status": "pending",
                "reason": "Próxima etapa não reconhecida. Continue manualmente pelo navegador.",
            }
        await next_button.click()
    return {
        "status": "pending",
        "reason": "Limite de 15 etapas atingido. Continue no navegador.",
    }
