"""Capacidades explícitas: uma preferência não torna um conector disponível."""

from urllib.parse import urlsplit

PLATFORMS = ["feed", "company", "greenhouse", "lever", "linkedin", "gupy", "indeed"]
DESTINATIONS = [
    "inhire",
    "email",
    "company",
    "greenhouse",
    "lever",
    "linkedin",
    "gupy",
    "indeed",
]
CONNECTORS = [
    {
        "id": "inhire",
        "name": "InHire",
        "discovery": False,
        "submission": True,
        "reason": "Formulário direto experimental: respostas exatas, autorização de dados por empresa e comprovante do portal. Validado em ambiente de teste.",
    },
    {
        "id": "feed",
        "name": "Feeds RSS/JSON",
        "discovery": True,
        "submission": False,
        "reason": "Fontes configuradas pelo usuário.",
    },
    {
        "id": "company",
        "name": "Páginas de empresas",
        "discovery": True,
        "submission": False,
        "reason": "Consulta pública de páginas JobPosting; formulário assistido.",
    },
    {
        "id": "greenhouse",
        "name": "Greenhouse",
        "discovery": True,
        "submission": False,
        "reason": "Consulta de quadros públicos. Envio ainda assistido.",
    },
    {
        "id": "lever",
        "name": "Lever",
        "discovery": True,
        "submission": False,
        "reason": "Consulta de quadros públicos. Envio ainda assistido.",
    },
    {
        "id": "linkedin",
        "name": "LinkedIn",
        "discovery": True,
        "submission": True,
        "experimental": True,
        "reason": "Busca experimental de vagas e publicações com sessão salva. Formulário automático experimental opcional; exige validação no portal real.",
    },
    {
        "id": "gupy",
        "name": "Gupy",
        "discovery": True,
        "submission": True,
        "experimental": True,
        "reason": "Leitura experimental de páginas de empresas configuradas como fontes; formulário de candidatura experimental, sem criação automática de conta.",
    },
    {
        "id": "indeed",
        "name": "Indeed",
        "discovery": True,
        "submission": True,
        "experimental": True,
        "reason": "Busca experimental por sessão no navegador; verificações exigem intervenção. Formulário automático experimental opcional.",
    },
    {
        "id": "email",
        "name": "E-mail",
        "discovery": False,
        "submission": True,
        "reason": "SMTP TLS, instruções verificadas, limites e confirmação do servidor.",
    },
]


def platform_for(url, fallback="company"):
    host = (urlsplit(url).hostname or "").lower()
    for domain, platform in [
        ("inhire.app", "inhire"),
        ("linkedin.com", "linkedin"),
        ("gupy.io", "gupy"),
        ("indeed.com", "indeed"),
        ("indeed.com.br", "indeed"),
        ("greenhouse.io", "greenhouse"),
        ("lever.co", "lever"),
    ]:
        if host == domain or host.endswith("." + domain):
            return platform
    return fallback


def source_platform(source):
    if source.get("kind") in ["greenhouse", "lever"]:
        return source["kind"]
    platform = platform_for(source.get("url", ""), source.get("kind", "feed"))
    return "company" if platform == "inhire" else platform


def source_address(source):
    kind = source.get("kind", "feed")
    board = source.get("board", "")
    if kind == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    if kind == "lever":
        return f"https://api.lever.co/v0/postings/{board}?mode=json"
    return source["url"]
