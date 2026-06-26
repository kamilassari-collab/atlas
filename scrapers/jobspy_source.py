"""
JobSpy source — primary scraper (LinkedIn + Indeed + Google + Glassdoor + ZipRecruiter).
This is what makes Atlas work for ALL professions, not just tech/startup:
Indeed and Google Jobs cover nurses, lawyers, retail, trades.

Requires python-jobspy (Python 3.10+). Imported lazily so the kit still loads
on a bare interpreter; the aggregator falls back to linkedin_guest if missing.
"""
from __future__ import annotations
from pipeline.models import JobListing
from pipeline.utils import normalize_contract_type


def available() -> bool:
    try:
        import jobspy  # noqa: F401
        return True
    except Exception:
        return False


def scrape(
    keywords_list: list[str],
    locations: list[str],
    hours_old: int = 24,
    results_per_search: int = 40,
    sites: list[str] | None = None,
) -> list[JobListing]:
    """
    Fetch fresh jobs via JobSpy across keyword × location combos.
    Returns [] if JobSpy is unavailable or every search errors — the
    aggregator decides the fallback.
    """
    try:
        from jobspy import scrape_jobs
    except Exception:
        return []

    sites = sites or ["linkedin", "indeed", "google", "glassdoor", "zip_recruiter"]
    out: list[JobListing] = []
    seen: set[str] = set()

    for kw in keywords_list:
        for loc in locations:
            try:
                df = scrape_jobs(
                    site_name=sites,
                    search_term=kw,
                    location=loc,
                    results_wanted=results_per_search,
                    hours_old=hours_old,
                    description_format="markdown",
                    verbose=0,
                )
            except Exception:
                continue
            if df is None or len(df) == 0:
                continue

            for _, r in df.iterrows():
                ext = str(r.get("id") or r.get("job_url") or "")
                if not ext or ext in seen:
                    continue
                seen.add(ext)
                ctype = r.get("job_type")
                out.append(JobListing(
                    source=f"jobspy:{r.get('site', 'unknown')}",
                    external_id=ext,
                    title=str(r.get("title") or "").strip(),
                    company=str(r.get("company") or "").strip(),
                    location=str(r.get("location") or loc).strip(),
                    url=str(r.get("job_url") or ""),
                    description=str(r.get("description") or ""),
                    contract_type=normalize_contract_type(str(ctype)) if ctype else None,
                    posted_at=str(r.get("date_posted")) if r.get("date_posted") else None,
                ))
    return out
