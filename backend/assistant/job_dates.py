"""Read publication and closing dates without an AI call."""

import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .matching import normalized

MONTHS = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()


def date_string(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return ""
    if isinstance(value, str) and value.strip():
        value = value.strip()
        try:
            if re.fullmatch(r"\d{4}-\d\d-\d\d(?:[T ].*)?", value):
                return date.fromisoformat(value[:10]).isoformat()
            return parsedate_to_datetime(value).date().isoformat()
        except (ValueError, TypeError, OverflowError):
            pass
    return ""


def visible_job_date(text):
    """Only inspect the visible heading, where portals show publication metadata."""
    header = normalized(" ".join(text.splitlines()[:14]))
    date_match = re.search(r"publicad[ao] em (\d{1,2}) de (\w+) de (\d{4})", header)
    if date_match:
        day, month, year = date_match.groups()
        try:
            return date(
                int(year), [normalized(m) for m in MONTHS].index(month) + 1, int(day)
            ).isoformat()
        except ValueError:
            pass
    relative = re.search(
        r"(?:há|ha|publicado ha)\s+(\d{1,3})\s+(minuto|hora|dia|semana|mes)(?:s|es)?\b",
        header,
    )
    if not relative:
        relative = re.search(
            r"\b(\d{1,3})\s+(minuto|hora|dia|semana|mes)(?:s|es)?\s+atras\b", header
        )
    if relative:
        amount, unit = relative.groups()
        days = {"minuto": 0, "hora": 0, "dia": 1, "semana": 7, "mes": 30}[unit]
        return (
            datetime.now(timezone.utc).date() - timedelta(days=int(amount) * days)
        ).isoformat()
    return ""


def outside_window(data, settings, today, *, require_date=False):
    expires = date_string(data.get("valid_until"))
    if expires and date.fromisoformat(expires) < today:
        return "Inscrições encerradas segundo a fonte."
    published = date_string(data.get("published_at"))
    if not published:
        if require_date and not settings.get("include_undated_jobs", True):
            return "Fonte sem data de publicação verificável."
        return ""
    age = (today - date.fromisoformat(published)).days
    if age > settings.get("max_job_age_days", 30):
        return "Publicação fora do período de busca."
    if age < -1:
        return "Data de publicação futura informada pela fonte."
    return ""
