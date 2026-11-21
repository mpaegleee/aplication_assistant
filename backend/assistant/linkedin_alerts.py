"""Convert opt-in LinkedIn email alerts into local vacancy previews."""

import re
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .matching import normalized
from .models import JobInput

ALERT_SENDER = "jobalerts-noreply@linkedin.com"
UNKNOWN_COMPANY = "Empresa não informada"
GENERIC = re.compile(
    r"^(?:ver|veja|visualizar|view|see|apply|candidatar(?:-se)?|candidate-se|salvar|save|saiba|show|abrir)\b",
    re.I,
)


def linkedin_job_url(value):
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"www.linkedin.com", "linkedin.com"}
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return ""
    except ValueError:
        return ""
    match = re.fullmatch(
        r"/(?:comm/)?jobs/view/(?:[^/]*-)?([0-9]{1,20})/?", parsed.path
    )
    return f"https://www.linkedin.com/jobs/view/{match[1]}" if match else ""


class AlertHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.buffer = []
        self.links = []
        self.anchor = None
        self.hidden = 0

    def flush(self):
        if line := " ".join("".join(self.buffer).split()):
            self.lines.append(line)
        self.buffer.clear()

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ("br", "p", "div", "td", "tr", "li", "h1", "h2", "h3"):
            self.flush()
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if url := linkedin_job_url(href):
                self.flush()
                self.anchor = (url, len(self.lines), [])

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.hidden:
            self.hidden -= 1
        if self.hidden:
            return
        if tag == "a" and self.anchor:
            url, offset, parts = self.anchor
            self.links.append((url, offset, " ".join("".join(parts).split())))
            self.anchor = None
            self.flush()
        elif tag in ("p", "div", "td", "tr", "li", "h1", "h2", "h3"):
            self.flush()

    def handle_data(self, value):
        if not self.hidden:
            self.buffer.append(value)
            if self.anchor:
                self.anchor[2].append(value)


def parse_alert(content):
    message = BytesParser(policy=default).parsebytes(content)
    if parseaddr(str(message.get("From", "")))[1].lower() != ALERT_SENDER:
        return []
    part = message.get_body(preferencelist=("html", "plain"))
    if not part:
        return []
    body = str(part.get_content())[:500_000]
    if part.get_content_subtype() == "html":
        parser = AlertHTML()
        parser.feed(body)
        parser.flush()
        lines, links = parser.lines, parser.links[:240]
    else:
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        links = [
            (url, index, "")
            for index, line in enumerate(lines)
            for candidate in re.findall(r'https://[^\s<>"\]]+', line)
            if (url := linkedin_job_url(candidate.rstrip(").,;")))
        ][:240]

    jobs = {}
    for index, (url, offset, label) in enumerate(links):
        if url in jobs and jobs[url]["title"] != "Vaga do LinkedIn":
            continue
        next_offset = next(
            (position for dest, position, _ in links[index + 1 :] if dest != url),
            len(lines),
        )
        preview = [
            line
            for line in lines[offset : min(next_offset, offset + 8)]
            if line != label and not GENERIC.match(line) and "https://" not in line
        ]
        title = (
            label
            if 3 <= len(label) <= 200 and not GENERIC.match(label)
            else "Vaga do LinkedIn"
        )
        if title == "Vaga do LinkedIn" and url in jobs:
            continue
        location = next(
            (
                line
                for line in preview
                if re.search(
                    r"\b(brasil|brazil|remot[oa]|hibrid[oa]|presencial)\b|,\s*[A-Z]{2}\b",
                    normalized(line),
                    re.I,
                )
            ),
            "",
        )
        company = (
            next(
                (
                    line
                    for line in preview
                    if line != location and 2 <= len(line) <= 120
                ),
                UNKNOWN_COMPANY,
            )
            if title != "Vaga do LinkedIn"
            else UNKNOWN_COMPANY
        )
        modality = normalized(location)
        jobs[url] = JobInput(
            title=title,
            company=company[:200],
            url=url,
            location=location[:150],
            country="BR" if re.search(r"\b(brasil|brazil)\b", modality) else "unknown",
            modality="Remoto"
            if "remot" in modality
            else "Híbrido"
            if "hibrid" in modality
            else "Presencial"
            if "presencial" in modality
            else "Não informado",
            description=(
                "Prévia de alerta do LinkedIn.\n" + "\n".join([title, *preview])
            )[:40000],
            source="linkedin_alert",
        ).model_dump()
    return list(jobs.values())[:40]
