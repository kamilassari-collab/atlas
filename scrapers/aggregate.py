"""
Source aggregator — runs the priority chain and dedups.

Priority (design doc, eng-review):
  1. JobSpy  (LinkedIn + Indeed + Google + Glassdoor + ZipRecruiter)
  2. linkedin_guest  (zero-dependency fallback if JobSpy is missing/broken)
  3. free APIs  (Arbeitnow + Remotive — always added for extra coverage)

No silent failures: returns a FetchResult carrying both the jobs and a
human-readable status so /fetch can tell the user what actually happened.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pipeline.models import JobListing
from pipeline.utils import dedup_key, extract_language_requirements
from scrapers import jobspy_source, linkedin_guest, free_apis


@dataclass
class FetchResult:
    jobs: list[JobListing] = field(default_factory=list)
    source_counts: dict = field(default_factory=dict)   # source name -> count
    notes: list[str] = field(default_factory=list)      # human-readable status lines

    @property
    def total(self) -> int:
        return len(self.jobs)

    def summary(self) -> str:
        if not self.jobs:
            return ("No jobs found. LinkedIn may be rate-limiting your IP right now — "
                    "try again in an hour. " + " ".join(self.notes))
        parts = [f"{n} from {s}" for s, n in self.source_counts.items() if n]
        return f"{self.total} fresh jobs ({', '.join(parts)})."


_REMOTE_MARKERS = ("remote", "worldwide", "anywhere", "télétravail", "home office")


def _matches_locations(job_location: str, city_tokens: list[str], include_remote: bool) -> bool:
    loc = (job_location or "").lower()
    if any(t in loc for t in city_tokens):
        return True
    if include_remote and any(m in loc for m in _REMOTE_MARKERS):
        return True
    return False


def fetch(
    keywords_list: list[str],
    locations: list[str],
    hours_old: int = 24,
    with_descriptions: bool = True,
    include_remote: bool = False,
) -> FetchResult:
    res = FetchResult()
    raw: list[JobListing] = []
    # "Paris, France" -> "paris"; used to keep only jobs in the chosen cities.
    city_tokens = [l.split(",")[0].strip().lower() for l in locations if l.strip()]
    if any(t in ("remote", "télétravail") for t in city_tokens):
        include_remote = True

    # 1. JobSpy (primary)
    if jobspy_source.available():
        js = jobspy_source.scrape(keywords_list, locations, hours_old=hours_old)
        res.source_counts["jobspy"] = len(js)
        raw.extend(js)
        if not js:
            res.notes.append("JobSpy returned 0 (sites may be throttling).")
    else:
        res.notes.append("JobSpy not installed — used LinkedIn guest fallback. Run /setup to enable all sources.")

    # 2. linkedin_guest — fallback only when JobSpy gave us nothing
    if not raw:
        tpr = linkedin_guest.TPR_24H if hours_old <= 24 else linkedin_guest.TPR_7D
        lg = linkedin_guest.scrape(
            keywords_list, locations, tpr=tpr,
            with_descriptions=with_descriptions,
        )
        res.source_counts["linkedin_guest"] = len(lg)
        raw.extend(lg)

    # 3. free APIs — Remotive is remote-only, so it's skipped when the user
    #    doesn't want remote jobs; Arbeitnow goes through the city filter below.
    api = free_apis.fetch_all(keywords_list, include_remote=include_remote)
    res.source_counts["free_apis"] = len(api)
    raw.extend(api)

    # Dedup by title|company, keep first (higher-priority source wins),
    # then drop anything outside the chosen cities (CEO feedback: no remote
    # noise unless the user opted in — onboarding question 8).
    seen: set[str] = set()
    dropped_loc = 0
    for j in raw:
        k = dedup_key(j.title, j.company)
        if k in seen or not j.title:
            continue
        seen.add(k)
        if city_tokens and not _matches_locations(j.location, city_tokens, include_remote):
            dropped_loc += 1
            continue
        # Pre-extract language requirements into a flag the scorer always sees.
        langs = extract_language_requirements(j.description)
        if langs:
            j.language_flags = ",".join(langs)
        res.jobs.append(j)

    if dropped_loc:
        res.notes.append(f"{dropped_loc} jobs ignorés (hors villes choisies / remote désactivé).")
    return res
