"""Leitura limitada de fontes públicas; conexão ao IP já validado evita DNS rebinding."""

import socket, ipaddress, ssl, http.client, json, re, base64
from urllib.parse import urlsplit, urljoin, urlunsplit, parse_qsl, urlencode
from html.parser import HTMLParser
from defusedxml import ElementTree
from .models import JobInput
from .matching import infer_area, normalized
from .job_dates import date_string

MAX_BYTES = 2_000_000


def canonical_url(value):
    if not value:
        return ""
    u = urlsplit(value)
    query = urlencode(
        sorted(
            (k, v)
            for k, v in parse_qsl(u.query)
            if not k.lower().startswith("utm_")
            and k.lower() not in ["trk", "trackingid", "ref"]
        )
    )
    return urlunsplit(
        (u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), query, "")
    )


def public_fetch(url, allowed):
    for _ in range(4):
        u = urlsplit(url)
        if (
            u.scheme != "https"
            or not u.hostname
            or u.username
            or u.password
            or (u.port and u.port != 443)
        ):
            raise ValueError("Fonte precisa usar HTTPS na porta padrão.")
        host = u.hostname.encode("idna").decode().lower()
        if host not in allowed:
            raise ValueError("Domínio não autorizado: " + host)
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(
            not ipaddress.ip_address(a[4][0]).is_global for a in addresses
        ):
            raise ValueError("Endereço de rede privada bloqueado.")
        connection = http.client.HTTPSConnection(host, 443, timeout=20)
        try:
            family, kind, proto, _, address = addresses[0]
            sock = socket.socket(family, kind, proto)
            sock.settimeout(20)
            try:
                sock.connect(address)
                connection.sock = ssl.create_default_context().wrap_socket(
                    sock, server_hostname=host
                )
            except BaseException:
                sock.close()
                raise
            connection.request(
                "GET",
                urlunsplit(("", "", u.path or "/", u.query, "")),
                headers={
                    "User-Agent": "ApplicationAssistant/0.1 (+self-hosted job assistant)",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in [301, 302, 303, 307, 308]:
                url = urljoin(url, response.getheader("Location", ""))
                continue
            if response.status != 200:
                raise ValueError("Fonte respondeu HTTP " + str(response.status))
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("Fonte excedeu 2 MB.")
            return body.decode("utf-8-sig", errors="replace")
        finally:
            connection.close()
    raise ValueError("Redirecionamentos demais na fonte.")


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def strip_html(value):
    t = Text()
    t.feed(str(value))
    return " ".join(t.parts)


class JobPostingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.buffer = ""
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.active = True
            self.buffer = ""

    def handle_data(self, data):
        if self.active:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.scripts.append(self.buffer)
            self.active = False


def walk_json(value):
    if isinstance(value, list):
        for x in value:
            yield from walk_json(x)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
            yield value
        if "@graph" in value:
            yield from walk_json(value["@graph"])


def posting(raw, url):
    organization = raw.get("hiringOrganization", {})
    location = raw.get("jobLocation", {})
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address", {}) if isinstance(location, dict) else {}
    country = address.get("addressCountry", "") if isinstance(address, dict) else ""
    if isinstance(country, dict):
        country = country.get("name", "")
    if country and str(country).upper() not in ["BR", "BRASIL", "BRAZIL"]:
        return None
    title = strip_html(raw.get("title", ""))[:200]
    description = strip_html(raw.get("description", ""))[:40000]
    # No recipient inferred from arbitrary addresses in the page.
    return JobInput(
        title=title,
        company=(
            organization.get("name", "Empresa não informada")
            if isinstance(organization, dict)
            else str(organization)
        )[:200],
        url=raw.get("url") or url,
        description=description,
        area=infer_area(title),
        area_reviewed=False,
        location=str(address.get("addressLocality", ""))[:150]
        if isinstance(address, dict)
        else "",
        modality="Remoto"
        if raw.get("jobLocationType") == "TELECOMMUTE"
        else "Não informado",
        published_at=date_string(raw.get("datePosted")),
        valid_until=date_string(raw.get("validThrough")),
        source="JobPosting",
        country="BR" if country else "unknown",
    ).model_dump()


def read_source(text, url):
    if text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        if isinstance(data, list):
            jobs = []
            for item in data[:100]:
                if not isinstance(item, dict) or item.get("country", "unknown") not in [
                    "BR",
                    "unknown",
                ]:
                    continue
                item = dict(item)
                item["published_at"] = date_string(
                    item.pop("datePosted", item.get("published_at"))
                )
                item["valid_until"] = date_string(
                    item.pop("validThrough", item.get("valid_until"))
                )
                try:
                    jobs.append(
                        JobInput.model_validate(
                            {
                                **item,
                                "area_reviewed": False,
                                "source": "JSON",
                                "country": item.get("country", "unknown"),
                            }
                        ).model_dump()
                    )
                except ValueError:
                    continue
            if data and not jobs:
                raise ValueError("Feed sem vagas válidas para análise no Brasil.")
            return jobs
        return [j for item in walk_json(data) if (j := posting(item, url))]
    parser = JobPostingParser()
    parser.feed(text)
    jobs = []
    for script in parser.scripts:
        try:
            for raw in walk_json(json.loads(script)):
                item = posting(raw, url)
                if item:
                    jobs.append(item)
        except (ValueError, TypeError):
            continue
    if jobs:
        return jobs[:100]
    try:
        root = ElementTree.fromstring(text)
    except Exception:
        raise ValueError("Nenhuma vaga JobPosting, RSS ou JSON reconhecida.")
    for node in list(root.findall(".//item"))[:100]:
        title = strip_html(node.findtext("title", ""))[:200]
        description = strip_html(node.findtext("description", ""))[:40000]
        if len(description) < 20:
            description = title + " — importe a descrição completa para analisar."
        jobs.append(
            JobInput(
                title=title,
                company="Revisar empresa",
                url=node.findtext("link", "").strip(),
                description=description,
                area=infer_area(title),
                source="RSS",
                published_at=date_string(node.findtext("pubDate")),
                country="unknown",
            ).model_dump()
        )
    if not jobs:
        raise ValueError("Feed sem vagas reconhecidas.")
    return jobs


def read_board(text, source):
    """Adaptadores de leitura documentados; nunca enviam candidaturas."""
    data = json.loads(text)
    kind = source.get("kind", "feed")
    rows = (
        data.get("jobs", [])
        if kind == "greenhouse" and isinstance(data, dict)
        else data
    )
    if not isinstance(rows, list):
        raise ValueError("Quadro de vagas não retornou uma lista.")
    jobs = []
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        if kind == "greenhouse":
            title = row.get("title", "")
            description = strip_html(row.get("content", ""))
            url = row.get("absolute_url", "")
            application_url = url
            location = (row.get("location") or {}).get("name", "")
        elif kind == "lever":
            title = row.get("text", "")
            categories = row.get("categories") or {}
            description = row.get("descriptionPlain") or strip_html(
                row.get("description", "")
            )
            for item in row.get("lists", []):
                description += (
                    "\n"
                    + str(item.get("text", ""))
                    + " "
                    + strip_html(item.get("content", ""))
                )
            description += "\n" + strip_html(row.get("additional", ""))
            url = row.get("hostedUrl", "")
            application_url = row.get("applyUrl", "") or url
            location = categories.get("location", "")
        else:
            raise ValueError("Tipo de quadro não suportado.")
        if not url or len(description.strip()) < 20:
            continue
        location = str(location)[:150]
        modality = (
            "Remoto"
            if re.search(r"remot[eo]|anywhere|worldwide", location, re.I)
            or row.get("workplaceType") == "remote"
            else "Não informado"
        )
        jobs.append(
            JobInput(
                title=str(title)[:200],
                company=source["name"],
                url=url,
                application_url=application_url,
                description=description[:40000],
                location=location,
                modality=modality,
                source=kind,
                published_at=date_string(
                    row.get("first_published")
                    if kind == "greenhouse"
                    else row.get("createdAt")
                ),
                country="BR"
                if re.search(
                    r"\b(brasil|brazil|sao paulo|rio de janeiro|brasilia|belo horizonte|curitiba|porto alegre|recife|florianopolis|fortaleza|salvador|manaus|vitoria|goiania|campinas)\b",
                    normalized(location),
                )
                else "unknown",
            ).model_dump()
        )
    return jobs


def application_identity(url):
    """Normaliza identificadores públicos conhecidos; URLs genéricas mantêm query significativa."""
    value = canonical_url(url)
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if host.endswith(".inhire.app"):
        match = re.search(r"/vagas/([a-fA-F0-9-]{36})(?:/|$)", parsed.path)
        if match:
            return "inhire:" + host + ":" + match.group(1).lower()
    if host == "gupy.io" or host.endswith(".gupy.io"):
        match = re.search(r"/jobs/(\d+)(?:/|$)", parsed.path)
        if match:
            return "gupy:" + match.group(1)
        encoded = re.search(r"/job/([A-Za-z0-9_+=-]{1,300})(?:/|$)", parsed.path)
        if encoded:
            try:
                token = encoded.group(1)
                payload = json.loads(
                    base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
                )
                job_id = str(payload.get("jobId", ""))
                if re.fullmatch(r"[1-9][0-9]{0,15}", job_id):
                    return "gupy:" + job_id
            except (ValueError, TypeError, AttributeError):
                pass
    if host == "jobs.lever.co" or host.endswith(".jobs.lever.co"):
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return "lever:" + parts[0] + ":" + parts[1]
    return value
