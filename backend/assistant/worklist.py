"""Current, factual eligibility projection shared by manual and scheduled workflows."""

from .connectors import CONNECTORS, platform_for
from .engine import TERMINAL
from .mail import email_eligible
from .matching import fingerprint, hard_blocks
from .models import Profile, Settings


def worklist(profile, settings, jobs):
    profile = Profile.model_validate(profile).model_dump()
    settings = Settings.model_validate(settings).model_dump()
    result = []
    summary = {
        "eligible": 0,
        "stale": 0,
        "blocked": 0,
        "below_threshold": 0,
        "archived": 0,
    }
    capabilities = {c["id"]: c for c in CONNECTORS}
    for job in jobs:
        if job.get("archived"):
            summary["archived"] += 1
            continue
        if job["status"] in TERMINAL or job["status"] == "sending":
            continue
        a = job.get("analysis") or {}
        if hard_blocks(profile, job) or a.get("blocks"):
            summary["blocked"] += 1
            continue
        if a.get("fingerprint") != fingerprint(profile, job, settings):
            summary["stale"] += 1
            continue
        if (
            a.get("score") is None
            or a["score"] < settings["threshold"]
            or a.get("confidence", 0) < settings["minimum_confidence"]
        ):
            summary["below_threshold"] += 1
            continue
        destination = (
            "email"
            if email_eligible(job)
            else platform_for(job.get("application_url") or job.get("url", ""))
        )
        result.append(
            {
                "job_id": job["id"],
                "score": a["score"],
                "confidence": a["confidence"],
                "destination": destination,
                "automatic_available": capabilities.get(destination, {}).get(
                    "submission", False
                )
                and (
                    not capabilities.get(destination, {}).get("experimental")
                    or settings["experimental_portal_submission"]
                ),
                "destination_enabled": destination in settings["allowed_destinations"],
            }
        )
    result.sort(key=lambda row: (-row["score"], -row["confidence"], row["job_id"]))
    summary["eligible"] = len(result)
    return {"items": result, "summary": summary}
