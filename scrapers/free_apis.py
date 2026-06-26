"""
Keyless free job APIs — extra coverage, work even when scraping fails.
Arbeitnow (EU jobs) and Remotive (remote jobs). Both public, no auth.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse
from pipeline.models import JobListing
from pipeline.utils import normalize_contract_type

_UA = {"User-Agent": "Atlas/1.0 (+https://github.com/kamilassari-collab/atlas)"}


def _get_json(url: str, timeout: int = 15):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None


def fetch_arbeitnow(keywords: list[str]) -> list[JobListing]:
    data = _get_json("https://www.arbeitnow.com/api/job-board-api")
    if not data or "data" not in data:
        return []
    kw_lower = [k.lower() for k in keywords]
    out: list[JobListing] = []
    for j in data["data"][:100]:
        title = (j.get("title") or "")
        tags = " ".join(j.get("tags") or []) + " " + (j.get("description") or "")[:500]
        hay = (title + " " + tags).lower()
        if kw_lower and not any(k in hay for k in kw_lower):
            continue
        jtypes = j.get("job_types") or []
        out.append(JobListing(
            source="arbeitnow",
            external_id=f"arb_{j.get('slug')}",
            title=title,
            company=j.get("company_name") or "",
            location=j.get("location") or "",
            url=j.get("url") or "",
            description=j.get("description") or "",
            contract_type=normalize_contract_type(jtypes[0]) if jtypes else None,
        ))
    return out


def fetch_remotive(keywords: list[str]) -> list[JobListing]:
    search = " ".join(keywords[:2])
    url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(search)}&limit=50"
    data = _get_json(url)
    if not data or "jobs" not in data:
        return []
    out: list[JobListing] = []
    for j in data["jobs"]:
        out.append(JobListing(
            source="remotive",
            external_id=f"rem_{j.get('id')}",
            title=j.get("title") or "",
            company=j.get("company_name") or "",
            location=j.get("candidate_required_location") or "Remote",
            url=j.get("url") or "",
            description=j.get("description") or "",
            contract_type=normalize_contract_type(j.get("job_type") or "full-time"),
            posted_at=j.get("publication_date"),
        ))
    return out


def fetch_all(keywords: list[str], include_remote: bool = False) -> list[JobListing]:
    out: list[JobListing] = []
    out.extend(fetch_arbeitnow(keywords))
    if include_remote:  # Remotive is remote-only by definition
        out.extend(fetch_remotive(keywords))
    return out
