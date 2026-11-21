from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from .connectors import PLATFORMS, DESTINATIONS
import re

AREAS = [
    "Desenvolvimento",
    "Dados",
    "Infraestrutura",
    "Produto e Design",
    "Projetos e Agilidade",
    "Comercial",
    "Marketing",
    "Financeiro",
    "Recursos Humanos",
    "Administrativo",
    "Operações",
    "Saúde",
    "Educação",
    "Jurídico",
    "Engenharia",
    "Outros",
]


LINKEDIN_PREVIEW_SOURCES = {"linkedin_alert", "linkedin_visible"}
LINKEDIN_USER_IMPORTS = LINKEDIN_PREVIEW_SOURCES | {"linkedin_visible_detail"}


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


FactCategory = Literal["experience", "education", "course", "skill", "other"]
FACT_CATEGORIES = {"experience", "education", "course", "skill", "other"}


class Fact(Model):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[\w-]+$")
    text: str = Field(min_length=3, max_length=2000)
    evidence: str = Field(default="", max_length=2000)
    source: Literal["pdf", "manual"] = "manual"
    category: FactCategory = "other"


class SavedAnswer(Model):
    question: str = Field(min_length=3, max_length=300)
    answer: str = Field(min_length=1, max_length=2000)


class Profile(Model):
    name: str = Field(default="", max_length=150)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=50)
    city: str = Field(default="", max_length=150)
    linkedin_url: str = Field(default="", max_length=500)
    areas: list[str] = Field(default_factory=list, max_length=20)
    excluded_areas: list[str] = Field(default_factory=list, max_length=20)
    roles: list[str] = Field(default_factory=list, max_length=30)
    modalities: list[str] = Field(default_factory=lambda: ["Remoto"], max_length=3)
    contracts: list[str] = Field(default_factory=list, max_length=5)
    locations: list[str] = Field(default_factory=list, max_length=30)
    minimum_salary: float = Field(default=0, ge=0, le=1000000)
    facts: list[Fact] = Field(default_factory=list, max_length=300)
    confirmed: bool = False
    answers: list[SavedAnswer] = Field(default_factory=list, max_length=100)

    @field_validator("areas", "excluded_areas")
    @classmethod
    def areas_valid(cls, value):
        if any(x not in AREAS for x in value):
            raise ValueError("Área inválida")
        return value

    @field_validator("linkedin_url")
    @classmethod
    def linkedin_valid(cls, value):
        if value and not re.fullmatch(
            r"https://(www\.)?linkedin\.com/in/[\w%.-]+/?", value
        ):
            raise ValueError("Informe o endereço público do perfil LinkedIn.")
        return value

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        if v and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", v):
            raise ValueError("E-mail inválido")
        return v


class Source(Model):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(default="", max_length=2000)
    enabled: bool = True
    kind: Literal["feed", "company", "greenhouse", "lever"] = "feed"
    board: str = Field(default="", max_length=100, pattern=r"^[a-zA-Z0-9_-]*$")

    @model_validator(mode="after")
    def valid_source(self):
        if self.kind in ["greenhouse", "lever"] and not self.board:
            raise ValueError("Informe o identificador do quadro de vagas.")
        if self.kind not in ["greenhouse", "lever"] and not self.url.startswith(
            "https://"
        ):
            raise ValueError("Informe o endereço HTTPS da fonte.")
        return self


class Settings(Model):
    search_platforms: list[str] = Field(
        default_factory=lambda: ["feed", "company", "greenhouse", "lever"], max_length=7
    )
    allowed_destinations: list[str] = Field(
        default_factory=lambda: ["email"], max_length=8
    )
    browser_search_queries: list[str] = Field(default_factory=list, max_length=10)
    linkedin_posts_enabled: bool = True
    linkedin_search_method: Literal["browser", "email"] = "browser"
    experimental_portal_submission: bool = False
    share_with_enabled_portals: bool = False
    auto_classify_areas: bool = False
    run_time_limit_minutes: int = Field(default=60, ge=1, le=240)
    mode: Literal["manual", "review", "automatic"] = "review"
    threshold: int = Field(default=80, ge=0, le=100)
    minimum_confidence: int = Field(default=85, ge=50, le=100)
    daily_limit: int = Field(default=10, ge=1, le=100)
    ai_daily_limit: int = Field(default=50, ge=1, le=1000)
    max_job_age_days: Literal[7, 15, 30] = 30
    include_undated_jobs: bool = True
    max_jobs_per_run: int = Field(default=20, ge=1, le=100)
    interval_seconds: int = Field(default=15, ge=5, le=600)
    paused: bool = True
    schedule_enabled: bool = False
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], max_length=7)
    time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "America/Sao_Paulo"
    ai_url: str = Field(default="http://localhost:11434/v1", max_length=1000)
    ai_model: str = Field(default="", max_length=150)
    ai_key: str = Field(default="", max_length=2000)
    ai_consent: bool = False
    allowed_domains: list[str] = Field(default_factory=list, max_length=100)
    sources: list[Source] = Field(default_factory=list, max_length=20)
    smtp_host: str = Field(default="", max_length=254)
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_security: Literal["ssl", "starttls"] = "ssl"
    smtp_user: str = Field(default="", max_length=254)
    smtp_password: str = Field(default="", max_length=2000)
    smtp_from: str = Field(default="", max_length=254)
    email_enabled: bool = False
    imap_enabled: bool = False
    imap_host: str = Field(default="", max_length=254)
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_user: str = Field(default="", max_length=254)
    imap_password: str = Field(default="", max_length=2000)
    imap_folder: str = Field(
        default="INBOX", min_length=1, max_length=100, pattern=r"^[^\r\n]+$"
    )
    imap_poll_minutes: int = Field(default=15, ge=5, le=1440)
    imap_max_messages: int = Field(default=30, ge=1, le=100)
    auto_followup: bool = False

    @field_validator("browser_search_queries")
    @classmethod
    def queries_valid(cls, value):
        if any(not 2 <= len(q.strip()) <= 150 for q in value):
            raise ValueError("Informe termos de busca entre 2 e 150 caracteres.")
        return list(dict.fromkeys(q.strip() for q in value))

    @field_validator("search_platforms", "allowed_destinations")
    @classmethod
    def platforms_valid(cls, value, info):
        choices = PLATFORMS if info.field_name == "search_platforms" else DESTINATIONS
        if any(x not in choices for x in value):
            raise ValueError("Plataforma inválida")
        return list(dict.fromkeys(value))

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, v):
        ZoneInfo(v)
        return v

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("Dia inválido")
        return sorted(set(v))

    @field_validator("allowed_domains")
    @classmethod
    def domains(cls, v):
        if any(
            not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}", d) for d in v
        ):
            raise ValueError("Informe domínios, sem protocolo ou caminho")
        return sorted(set(d.lower() for d in v))

    @field_validator("ai_url")
    @classmethod
    def ai_address(cls, v):
        u = urlsplit(v)
        if u.username or u.password or u.query or u.fragment or not u.hostname:
            raise ValueError("Endereço da IA inválido")
        if u.scheme != "https" and not (
            u.scheme == "http"
            and u.hostname in ["localhost", "127.0.0.1", "host.docker.internal"]
        ):
            raise ValueError("Use HTTPS; HTTP somente para IA local")
        return v.rstrip("/")

    @field_validator("smtp_from")
    @classmethod
    def sender(cls, v):
        return Profile.email_valid(v)


class AIConnection(Model):
    ai_url: str = Field(min_length=8, max_length=1000)
    ai_key: str = Field(default="", max_length=2000)

    @field_validator("ai_url")
    @classmethod
    def address(cls, value):
        return Settings.ai_address(value)


class JobInput(Model):
    published_at: str = Field(default="", max_length=40)
    valid_until: str = Field(default="", max_length=40)
    country: Literal["BR", "unknown"] = "BR"
    title: str = Field(min_length=3, max_length=200)
    company: str = Field(min_length=2, max_length=200)
    url: str = Field(default="", max_length=2000)
    description: str = Field(min_length=20, max_length=40000)
    area: str = ""
    area_reviewed: bool = False
    modality: Literal["Remoto", "Híbrido", "Presencial", "Não informado"] = (
        "Não informado"
    )
    contract: str = Field(default="", max_length=50)
    location: str = Field(default="", max_length=150)
    salary: float | None = Field(default=None, ge=0, le=1000000)
    recipient: str = Field(default="", max_length=254)
    source: str = Field(default="manual", max_length=100)
    application_url: str = Field(default="", max_length=2000)
    email_subject: str = Field(default="", max_length=200, pattern=r"^[^\r\n]*$")
    instructions_reviewed: bool = False

    @field_validator("area")
    @classmethod
    def area_valid(cls, v):
        if v and v not in AREAS:
            raise ValueError("Área inválida")
        return v

    @field_validator("recipient")
    @classmethod
    def recipient_valid(cls, v):
        return Profile.email_valid(v)

    @field_validator("url", "application_url")
    @classmethod
    def valid_url(cls, v):
        if v:
            u = urlsplit(v)
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise ValueError("Use um link HTTPS válido")
        return v
