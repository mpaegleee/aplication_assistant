from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .store import now
from .connectors import platform_for

STAGES = {
    "receipt",
    "selection",
    "technical",
    "interview",
    "manager_interview",
    "offer",
    "rejected",
    "withdrawn",
    "closed",
}
APPLIED = {"sent", "submitted_manual"} | STAGES


def record_stage(job, status, method):
    entry = {"status": status, "at": now(), "method": method}
    history = job.setdefault("stage_history", [])
    if not history or history[-1]["status"] != status:
        history.append(entry)
    job.update(status=status, updated_at=entry["at"])
    if status in ["sent", "submitted_manual"] and not job.get("sent_at"):
        job["sent_at"] = entry["at"]
    return job


def timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def metrics(store, settings, days=15):
    zone = ZoneInfo(settings["timezone"])
    today = datetime.now(zone).date()
    start = datetime.combine(
        today - timedelta(days=days - 1), datetime.min.time(), zone
    )
    jobs = store.all("jobs")
    cohort = []
    for job in jobs:
        at = timestamp(job.get("sent_at"))
        if at and at >= start and job["status"] in APPLIED:
            cohort.append(job)
    current = {stage: sum(j["status"] == stage for j in cohort) for stage in STAGES}
    return {
        "days": days,
        "since": start.isoformat(),
        "applied": len(cohort),
        "smtp_accepted": sum(bool(j.get("message_id")) for j in cohort),
        "reported_manual": sum(
            any(x["status"] == "submitted_manual" for x in j.get("stage_history", []))
            or (j["status"] == "submitted_manual")
            for j in cohort
        ),
        "responses": sum(
            j["status"] in STAGES - {"withdrawn", "closed"}
            or any(
                x["status"] in STAGES - {"withdrawn", "closed"}
                for x in j.get("stage_history", [])
            )
            for j in cohort
        ),
        "current": current,
        "pending": sum(
            bool(j.get("pending_reason")) and j["status"] not in APPLIED for j in jobs
        ),
        "by_destination": {
            destination: sum(
                j.get(
                    "destination",
                    platform_for(j.get("application_url") or j.get("url", "")),
                )
                == destination
                for j in cohort
            )
            for destination in [
                "email",
                "linkedin",
                "gupy",
                "indeed",
                "greenhouse",
                "lever",
                "company",
            ]
        },
    }
