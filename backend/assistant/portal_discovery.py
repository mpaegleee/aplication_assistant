"""Read-only, bounded portal discovery. Portal layouts remain explicit experimental adapters."""

import hashlib
import html
import json
import re
from urllib.parse import quote, urlsplit

from playwright.async_api import TimeoutError as BrowserTimeout

from .ai import AI
from .matching import exact_quote, normalized
from .models import JobInput
from .sources import application_identity


def posting_country(scripts):
    countries = set()
    for script in scripts:
        try:
            data = json.loads(html.unescape(script))
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            locations = item.get("jobLocation", [])
            for location in locations if isinstance(locations, list) else [locations]:
                address = (
                    location.get("address") if isinstance(location, dict) else None
                )
                country = (
                    address.get("addressCountry") if isinstance(address, dict) else None
                )
                if isinstance(country, str) and country.strip():
                    countries.add(
                        "BR"
                        if normalized(country) in ("br", "brasil", "brazil")
                        else "unknown"
                    )
    return countries.pop() if len(countries) == 1 else "unknown" if countries else ""


async def collect(page, platform, query, limit, posts=True, source_url=None):
    searches = (
        [source_url]
        if source_url
        else (
            [
                f"https://www.linkedin.com/jobs/search/?keywords={quote(query)}&location=Brasil&geoId=106057199"
            ]
            + (
                [
                    f"https://www.linkedin.com/search/results/content/?keywords={quote(query + ' vaga')}&sortBy=date_posted"
                ]
                if posts
                else []
            )
            if platform == "linkedin"
            else [f"https://br.indeed.com/jobs?q={quote(query)}&l=Brasil"]
        )
    )
    if posts and platform == "linkedin" and limit == 1 and not source_url:
        searches.reverse()
    records = []
    seen = set()
    for search in searches:
        if len(records) >= limit:
            break
        await page.goto(search, wait_until="domcontentloaded", timeout=45000)
        if (
            re.search(r"/login|/signin|/checkpoint|/authwall|/account/login", page.url)
            or await page.locator(
                'input[type="password"]:visible, iframe[src*="captcha"]:visible'
            ).count()
        ):
            raise ValueError(
                "Login ou verificação necessária. Abra o portal no navegador interno, entre e libere o controle."
            )
        is_post = "/search/results/content/" in search
        selector = (
            '[data-urn*="activity:"], article'
            if is_post
            else 'a[href*="/jobs/view/"], a[href*="viewjob?"], a[href*="/jobs/"], a[href*="/job/"], a[href*="/vagas/"]'
        )
        direct_job = bool(
            platform == "gupy"
            and source_url
            and application_identity(source_url).startswith("gupy:")
        )
        if not direct_job:
            try:
                await page.locator(selector).first.wait_for(
                    state="attached", timeout=10000
                )
            except BrowserTimeout:
                empty = page.get_by_text(
                    re.compile(
                        r"nenhum resultado|nenhuma vaga|no results|no jobs",
                        re.IGNORECASE,
                    )
                )
                if not await empty.count():
                    raise ValueError(
                        "Resultados não reconhecidos. Confira login, verificações e layout no navegador."
                    ) from None
                continue
        if is_post:
            containers = page.locator('[data-urn*="activity:"], article')
            for i in range(min(await containers.count(), limit * 3)):
                card = containers.nth(i)
                more = card.get_by_role(
                    "button",
                    name=re.compile(
                        r"^(ver mais|see more|…mais|\.\.\.mais)$", re.IGNORECASE
                    ),
                )
                if await more.count() == 1:
                    await more.click()
                data = await card.evaluate(
                    """e => ({text:e.innerText, urn:e.getAttribute('data-urn') || '', links:Array.from(e.querySelectorAll('a[href]')).map(a=>({url:a.href,label:a.innerText}))})"""
                )
                if not re.search(
                    r"\b(vaga|contratando|oportunidade|hiring|curr[ií]culo)\b",
                    data["text"],
                    re.IGNORECASE,
                ):
                    continue
                url = next(
                    (
                        a["url"]
                        for a in data["links"]
                        if "/posts/" in a["url"] or "/feed/update/" in a["url"]
                    ),
                    "",
                )
                if not url and re.fullmatch(r"urn:li:activity:\d+", data["urn"]):
                    url = "https://www.linkedin.com/feed/update/" + data["urn"] + "/"
                if url and url not in seen:
                    records.append(
                        {
                            "url": url,
                            "text": data["text"][:40000],
                            "links": data["links"][:80],
                            "kind": "post",
                            "platform": platform,
                        }
                    )
                    seen.add(url)
                if len(records) >= limit:
                    break
            continue
        urls = await page.locator(selector).evaluate_all(
            "elements => elements.map(a => a.href)"
        )
        urls = list(dict.fromkeys(urls))
        # The source may itself be a vacancy, with no result cards.
        if direct_job or (source_url and not urls):
            urls = [source_url]
        search_cap = min(limit, max(1, limit // 2)) if len(searches) > 1 else limit
        for url in urls:
            host = (urlsplit(url).hostname or "").lower()
            valid = (
                (
                    platform == "linkedin"
                    and host.endswith("linkedin.com")
                    and re.search(r"/jobs/view/(?:[^/]*-)?\d+", url)
                )
                or (platform == "indeed" and "indeed." in host and "viewjob?" in url)
                or (
                    platform == "gupy"
                    and host.endswith(".gupy.io")
                    and re.search(r"/jobs?/[^/]+", url)
                )
            )
            if source_url and platform == "inhire":
                valid = host.endswith(".inhire.app") and "/vagas/" in url
            if not valid or url in seen:
                continue
            seen.add(url)
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if (
                re.search(r"/login|/signin|/checkpoint|/authwall", page.url)
                or await page.locator('input[type="password"]:visible').count()
            ):
                raise ValueError(
                    "A sessão expirou ou o portal exige login. Reabra o navegador interno."
                )
            data = await page.evaluate(
                """() => { const e=document.querySelector('.jobs-details__main-content, .jobsearch-JobComponent, main'); return e ? {text:e.innerText, links:Array.from(e.querySelectorAll('a[href]')).map(a=>({url:a.href,label:a.innerText}))} : {text:'',links:[]}; }"""
            )
            structured = await page.locator(
                'script[type="application/ld+json"]'
            ).evaluate_all(
                "scripts => scripts.slice(0,20).map(e => e.textContent.slice(0,250000))"
            )
            if len(data["text"].strip()) >= 40:
                records.append(
                    {
                        "url": url,
                        "text": data["text"][:40000],
                        "links": data["links"][:80],
                        "kind": "job",
                        "country": posting_country(structured),
                        "platform": platform,
                    }
                )
            if len(records) >= search_cap:
                break
    return records


def extract_record(store, settings, raw):
    """AI extracts literal vacancy facts only; unknown facts remain pending review."""
    key = hashlib.sha256(
        json.dumps(
            [raw, settings["ai_url"], settings["ai_model"]], sort_keys=True
        ).encode()
    ).hexdigest()
    cached = store.get("portal_extractions", key)
    if cached is not None:
        return cached.get("job")
    task = """Identifique UMA vaga no texto de anúncio/publicação. Retorne JSON: {is_job:boolean,title:string,company:string,location:string,modality:string,contract:string,application_url:string}. title/company/location/contract devem ser trechos LITERAIS do texto; desconhecido = string vazia. modality só pode ser um trecho literal que indique remoto, híbrido ou presencial. application_url deve ser exatamente um dos links fornecidos que seja explicitamente destino de candidatura, nunca perfil, curtida, compartilhamento ou link institucional. Sem destino explícito = vazio. Se houver múltiplas vagas sem um cargo específico, is_job=false. Não invente informações. Não resuma nem reescreva os trechos."""
    value = AI(store).call(settings, task, {"text": raw["text"], "links": raw["links"]})
    if not isinstance(value, dict):
        raise ValueError("Resposta de extração inválida.")  # noqa: TRY004 -- provider data error, not caller type error
    if value.get("is_job") is not True:
        store.put("portal_extractions", {"job": None}, key)
        return None
    fields = {}
    for field in ("title", "company", "location", "modality", "contract"):
        text = value.get(field, "")
        fields[field] = (
            text[: 200 if field == "title" else 150]
            if isinstance(text, str) and text and exact_quote(text, raw["text"])
            else ""
        )
    modality = normalized(fields["modality"])
    fields["modality"] = (
        "Remoto"
        if "remot" in modality
        else "Híbrido"
        if "hibrid" in modality
        else "Presencial"
        if "presencial" in modality
        else "Não informado"
    )
    contract = normalized(fields["contract"])
    fields["contract"] = (
        "CLT" if contract == "clt" else "PJ" if contract == "pj" else ""
    )
    application_url = value.get("application_url", "")
    if (
        not isinstance(application_url, str)
        or application_url not in [a["url"] for a in raw["links"]]
        or not application_url.startswith("https://")
    ):
        application_url = ""
    location = normalized(fields["location"])
    country = (
        "BR"
        if re.search(
            r"\b(brasil|brazil|sao paulo|rio de janeiro|brasilia|belo horizonte|curitiba|porto alegre|recife|florianopolis|fortaleza|salvador|manaus|vitoria|goiania|campinas)\b",
            location,
        )
        else "unknown"
    )
    fields["title"] = (
        fields["title"] if len(fields["title"]) >= 3 else "Revisar cargo da publicação"
    )
    fields["company"] = (
        fields["company"] if len(fields["company"]) >= 2 else "Empresa não informada"
    )
    job = JobInput(
        **fields,
        country=raw.get("country") or country,
        url=raw["url"],
        application_url=application_url,
        description=raw["text"],
        source=raw["platform"] + "_" + raw["kind"],
    ).model_dump()
    store.put("portal_extractions", {"job": job}, key)
    return job
