"""Read the public Gupy search and the structured posting on each employer page."""

import json
import re
from urllib.parse import quote, urlsplit

from .job_dates import date_string
from .portal_discovery import structured_postings
from .sources import JobPostingParser, application_identity, posting, public_fetch

PORTAL = "portal.gupy.io"
SEARCH_URL = f"https://{PORTAL}/job-search/"
NEXT_DATA = re.compile(
    r'<script\b[^>]*\bid="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
MODALITIES = {"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial"}


def page_props(markup):
    match = NEXT_DATA.search(markup)
    try:
        props = json.loads(match[1])["props"]["pageProps"] if match else {}
        return props if isinstance(props, dict) else {}
    except (KeyError, TypeError, ValueError):
        return {}


def public_cards(query, interrupted):
    seen = set()
    for page in range(1, 10):
        if interrupted():
            return
        params = f"term={quote(query, safe='')}&sortBy=publishedDate&page={page}"
        markup = public_fetch(SEARCH_URL + params, [PORTAL])
        try:
            props = page_props(markup)
            if props["searchFilters"]["term"] != query:
                raise ValueError
            result = props["initialJobList"]
            cards = result["data"]
            if not isinstance(cards, list):
                raise TypeError
            pagination = result["pagination"]
            has_more = pagination["offset"] + pagination["limit"] < pagination["total"]
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "O portal público não retornou uma lista de vagas reconhecida."
            ) from None

        for card in cards:
            if not isinstance(card, dict):
                continue
            address = card.get("jobUrl")
            if not isinstance(address, str):
                continue
            url = urlsplit(address)
            if (
                url.scheme != "https"
                or not re.fullmatch(r"[a-z0-9-]+\.gupy\.io", url.netloc)
                or not re.fullmatch(
                    r"/(?:jobs/[0-9]+|job/[A-Za-z0-9_+=-]+)/*", url.path
                )
                or not application_identity(address).startswith("gupy:")
            ):
                continue
            identity = application_identity(address)
            if identity in seen:
                continue
            seen.add(identity)
            yield {
                "url": address,
                "published_at": date_string(card.get("publishedDate")),
                "valid_until": date_string(card.get("applicationDeadline")),
                "modality": MODALITIES.get(
                    str(card.get("workplaceType")), "Não informado"
                ),
            }
        if not cards or not has_more:
            break


def employer_posting(markup, address):
    details = page_props(markup).get("job")
    if (
        isinstance(details, dict)
        and application_identity(address) == f"gupy:{details.get('id')}"
    ):
        if details.get("status") != "published":
            raise ValueError("Vaga indisponível para candidatura.")
        description = "\n".join(
            value
            for field in (
                "description",
                "responsibilities",
                "prerequisites",
                "relevantExperiences",
            )
            if isinstance(value := details.get(field), str) and value.strip()
        )
        company = (details.get("careerPage") or {}).get(
            "name"
        ) or "Empresa não informada"
        location = " - ".join(
            details[field]
            for field in ("addressCity", "addressStateShortName")
            if isinstance(details.get(field), str) and details[field]
        )
        raw = {
            "title": details.get("name") or "",
            "description": description,
            "hiringOrganization": {"name": company},
            "jobLocation": {
                "address": {
                    "addressLocality": location,
                    "addressCountry": details.get("addressCountryShortName")
                    or details.get("addressCountry"),
                }
            },
            "datePosted": details.get("publishedAt"),
            "validThrough": details.get("registerEndDate"),
        }
        if job := posting(raw, address):
            job["modality"] = MODALITIES.get(
                str(details.get("workplaceType")), "Não informado"
            )
            return job

    parser = JobPostingParser()
    parser.feed(markup)
    for item in structured_postings(parser.scripts):
        if job := posting(item, address):
            return job
    raise ValueError("Descrição completa indisponível.")


def public_posting(card):
    address = card["url"]
    markup = public_fetch(address, [urlsplit(address).hostname])
    job = employer_posting(markup, address)
    return {
        **job,
        "url": address,
        "published_at": card["published_at"] or job["published_at"],
        "valid_until": min(
            filter(None, (job["valid_until"], card["valid_until"])), default=""
        ),
        "modality": job["modality"]
        if job["modality"] != "Não informado"
        else card["modality"],
        "source": "gupy_public",
    }
