"""Leitura limitada de fontes públicas; conexão ao IP já validado evita DNS rebinding."""

import socket, ipaddress, ssl, http.client, json, re
from urllib.parse import urlsplit, urljoin, urlunsplit, parse_qsl, urlencode
from html.parser import HTMLParser
from defusedxml import ElementTree
from .models import JobInput
from .matching import infer_area

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
        source="JobPosting",
    ).model_dump()


def read_source(text, url):
    if text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        if isinstance(data, list):
            return [
                JobInput.model_validate(
                    {**item, "area_reviewed": False, "source": "JSON"}
                ).model_dump()
                for item in data[:100]
            ]
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
            ).model_dump()
        )
    if not jobs:
        raise ValueError("Feed sem vagas reconhecidas.")
    return jobs
