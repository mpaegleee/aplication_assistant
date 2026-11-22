"""Assist the user with first-time candidate setup in their Gupy browser session."""

import re
from datetime import date
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout

from .portal_forms import answer_for, normalize

SIGNUP_FIELDS = {
    "e-mail": "email",
    "email": "email",
    "confirme o e-mail": "confirm_email",
    "confirme seu e-mail": "confirm_email",
    "nome completo": "name",
    "telefone celular com ddd": "phone",
    "numero de celular": "phone",
    "celular": "phone",
    "data de nascimento": "birth_date",
    "cpf": "cpf",
}
SIGNUP_TYPES = {"text", "email", "tel", "date", "number"}


def on_candidate_page(url, path):
    page = urlsplit(url)
    return (
        page.scheme == "https"
        and re.fullmatch(r"[a-z0-9-]+\.gupy\.io", page.netloc) is not None
        and (page.path.rstrip("/") == path or page.path.startswith(path + "/"))
    )


async def check_human_verification(page):
    if await page.locator(
        'iframe[src*="challenges.cloudflare.com"]:visible, '
        'iframe[src*="captcha"]:visible, form#challenge-form:visible'
    ).count():
        raise ValueError("Conclua a verificação humana diretamente na Gupy.")


def signup_value(key, kind, profile):
    if key in ("name", "email"):
        return profile.get(key)
    if key == "phone":
        digits = re.sub(r"\D", "", profile.get("phone", ""))
        if len(digits) in (12, 13) and digits.startswith("55"):
            digits = digits[2:]
        return digits if len(digits) in (10, 11) else None
    if key == "cpf":
        digits = re.sub(r"\D", "", answer_for("CPF", profile) or "")
        return digits if len(digits) == 11 else None
    value = answer_for("Data de nascimento", profile) or ""
    if match := re.fullmatch(r"(\d{2})/([0-9]{2})/([0-9]{4})", value):
        day, month, year = match.groups()
        value = f"{year}-{month}-{day}"
    try:
        birth_date = date.fromisoformat(value)
    except ValueError:
        return None
    return birth_date.isoformat() if kind == "date" else birth_date.strftime("%d/%m/%Y")


async def fill_signup(page, profile):
    if not on_candidate_page(page.url, "/candidates/signup"):
        raise ValueError("Abra a tela Criar conta da Gupy para preencher o cadastro.")
    await check_human_verification(page)
    controls = page.locator("input:visible")
    recognized = []
    entered_emails = set()
    for field in (await controls.element_handles())[:30]:
        meta = await field.evaluate(
            """e => ({kind:e.type, value:e.value, locked:e.readOnly||e.disabled,
                      label:Array.from(e.labels||[]).map(l=>l.innerText.trim()).join(' ')||
                            e.getAttribute('aria-label')||''})"""
        )
        key = SIGNUP_FIELDS.get(normalize(meta["label"]))
        if not key or meta["kind"] not in SIGNUP_TYPES:
            continue
        if key == "email" and meta["value"]:
            entered_emails.add(meta["value"])
        if not meta["value"] and not meta["locked"]:
            recognized.append((field, key, meta))

    filled = 0
    missing = []
    confirmation_email = (
        next(iter(entered_emails))
        if len(entered_emails) == 1
        else profile.get("email")
        if not entered_emails
        else ""
    )
    for field, key, meta in recognized:
        value = (
            confirmation_email
            if key == "confirm_email"
            else signup_value(key, meta["kind"], profile)
        )
        if value:
            await field.fill(value, timeout=2500)
            filled += 1
        else:
            missing.append(meta["label"])
    if not filled and not missing:
        return "Nenhum campo reconhecido em branco nesta etapa. Confira o cadastro na Gupy."
    notice = f"Campos preenchidos com seu perfil: {filled}. Revise e prossiga na Gupy."
    if missing:
        notice += " Dados ainda necessários: " + ", ".join(dict.fromkeys(missing)) + "."
    return notice


async def import_resume(page, pdf):
    if not on_candidate_page(page.url, "/candidates/resume"):
        raise ValueError("Entre na Gupy e abra Meu currículo para importar o PDF.")
    await check_human_verification(page)
    if len(pdf) >= 2_000_000:
        raise ValueError("O currículo base excede 2 MB.")
    section = page.locator(".curriculum-upload:visible")
    if await section.count() != 1:
        raise ValueError("Abra a opção de preenchimento por arquivo em Meu currículo.")
    upload = section.get_by_role(
        "button",
        name=re.compile(
            r"^(buscar|procurar|localizar|selecionar) arquivo$", re.IGNORECASE
        ),
    )
    fields = section.locator('input[type="file"]')
    if await upload.count() != 1 or await fields.count() != 1:
        raise ValueError("O importador de currículo da Gupy não foi reconhecido.")
    try:
        async with page.expect_file_chooser(timeout=3500) as chooser:
            await upload.click(timeout=2500)
    except BrowserTimeout:
        return "A Gupy não abriu o seletor. Confira se há uma confirmação de substituição na tela."
    selection = await chooser.value
    expected = await fields.element_handle(timeout=2500)
    if (
        expected is None
        or selection.is_multiple()
        or not await selection.element.evaluate(
            "(input, expected) => input === expected", expected
        )
        or not on_candidate_page(page.url, "/candidates/resume")
    ):
        raise ValueError("O campo de currículo ou a página mudou. Confira a Gupy.")
    await selection.set_files(
        {"name": "Curriculo-base.pdf", "mimeType": "application/pdf", "buffer": pdf},
        timeout=3500,
    )
    return "PDF enviado ao importador da Gupy. Revise o resultado antes de salvar o currículo."
