"""Import vacancy links rendered on the LinkedIn page the user has open."""

import re
from urllib.parse import parse_qs, urlsplit

from .linkedin_alerts import GENERIC, UNKNOWN_COMPANY, linkedin_job_url
from .job_dates import visible_job_date
from .matching import normalized
from .models import JobInput
from .portal_discovery import require_search_access


def search_card_url(value):
    if direct := linkedin_job_url(value):
        return direct
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or url.netloc not in {"www.linkedin.com", "linkedin.com"}
        or not url.path.startswith(("/jobs/search", "/jobs/collections"))
    ):
        return ""
    identifier = parse_qs(url.query).get("currentJobId", [""])[0]
    return (
        f"https://www.linkedin.com/jobs/view/{identifier}"
        if re.fullmatch(r"[0-9]{1,20}", identifier)
        else ""
    )


async def visible_details(page):
    if not linkedin_job_url(page.url):
        return None
    return await page.evaluate(
        """() => {
          const description = document.querySelector('#job-details, .jobs-description__content, .show-more-less-html__markup');
          if (!description || !description.getClientRects().length || description.innerText.trim().length < 50) return null;
          const title = document.querySelector('main h1, h1.top-card-layout__title')?.innerText || '';
          const company = document.querySelector('.job-details-jobs-unified-top-card__company-name, .topcard__org-name-link')?.innerText || '';
          const metadata = document.querySelector('.job-details-jobs-unified-top-card__primary-description-container, .topcard__flavor-row');
          return {url:location.href,title:title.slice(0,200),company:company.slice(0,200),
                  metadata:metadata?.innerText.slice(0,1500) || '',description:description.innerText.trim().slice(0,40000)};
        }"""
    )


async def capture_visible_jobs(page):
    url = urlsplit(page.url)
    if url.scheme != "https" or url.hostname not in {
        "www.linkedin.com",
        "linkedin.com",
    }:
        raise ValueError("Abra uma página de vagas do LinkedIn antes de importar.")
    await require_search_access(page)
    if not url.path.startswith("/jobs/"):
        raise ValueError(
            "Abra os resultados de vagas do LinkedIn ou um anúncio individual."
        )
    candidates = await page.locator(
        'a[href*="/jobs/view/"]:visible, a[href*="currentJobId="]:visible'
    ).evaluate_all(
        """anchors => anchors.slice(0, 240).map(link => {
            const row = link.closest('[data-job-id], [data-occludable-job-id], li') || link;
            const title = link.innerText.trim() || link.getAttribute('aria-label') || '';
            const company = row.querySelector(
                '.job-card-container__primary-description, .artdeco-entity-lockup__subtitle, .base-search-card__subtitle'
            )?.innerText || '';
            const location = row.querySelector(
                '.job-card-container__metadata-item, .artdeco-entity-lockup__caption, .job-search-card__location'
            )?.innerText || '';
            return {url: link.href, title: title.slice(0,200), company: company.slice(0,200), location: location.slice(0,150)};
        })"""
    )
    detail = await visible_details(page)
    if detail:
        candidates.insert(0, detail)
    elif linkedin_job_url(page.url):
        # The user may be reading a detail page that does not link to itself.
        candidates.insert(0, {"url": page.url, "title": ""})
    jobs = {}
    for candidate in candidates:
        target = search_card_url(candidate["url"])
        if not target:
            continue
        title = " ".join(candidate.get("title", "").split())
        title = (
            title
            if len(title) >= 3 and not GENERIC.match(title)
            else "Vaga do LinkedIn"
        )
        company = " ".join(candidate.get("company", "").split())
        location = " ".join(candidate.get("location", "").split())
        if target in jobs and (
            jobs[target]["title"] != "Vaga do LinkedIn" or title == "Vaga do LinkedIn"
        ):
            continue
        metadata = normalized(candidate.get("metadata", ""))
        has_details = bool(candidate.get("description"))
        jobs[target] = JobInput(
            title=title,
            company=company if len(company) >= 2 else UNKNOWN_COMPANY,
            url=target,
            location=location,
            country="BR" if re.search(r"\b(brasil|brazil)\b", metadata) else "unknown",
            modality="Remoto"
            if re.search(r"\b(remoto|remote)\b", metadata)
            else "Híbrido"
            if re.search(r"\b(hibrido|hybrid)\b", metadata)
            else "Presencial"
            if re.search(r"\b(presencial|on-site)\b", metadata)
            else "Não informado",
            published_at=visible_job_date(candidate.get("metadata", "")),
            description=candidate.get("description")
            or "\n".join(
                [
                    "Prévia importada da tela de vagas do LinkedIn.",
                    title,
                    *[value for value in (company, location) if value],
                ]
            ),
            source="linkedin_visible_detail" if has_details else "linkedin_visible",
        ).model_dump()
        if len(jobs) >= 100:
            break
    if not jobs:
        raise ValueError(
            "Nenhum link de vaga foi identificado nesta tela. Abra os resultados de uma pesquisa por vagas do LinkedIn."
        )
    return list(jobs.values())
