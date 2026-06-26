"""
LinkedIn jobs-guest scraper — no login, no API key, no Apify.

Uses the public guest endpoint that LinkedIn serves to logged-out browsers.
Validated 2026-06-11 from a residential IP: HTTP 200 across FR/UK/DE,
~10 cards per page, full 5000+ char descriptions via the detail endpoint.

Run from a user's own machine (residential IP) — that's what keeps it
unblocked. Throttle politely.
"""
from __future__ import annotations
import re
import html
import time
import urllib.request
import urllib.parse
from pipeline.models import JobListing

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "en,fr;q=0.9,de;q=0.8"}

# Time filters LinkedIn understands (seconds): r86400 = 24h, r604800 = 7d
TPR_24H = "r86400"
TPR_7D = "r604800"


def _get(url: str, timeout: int = 15) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def search_page(keywords: str, location: str, tpr: str = TPR_24H, start: int = 0) -> tuple[int, list[JobListing]]:
    """One page of search results (~10 cards). Returns (http_status, jobs)."""
    params = urllib.parse.urlencode(
        {"keywords": keywords, "location": location, "f_TPR": tpr, "start": start}
    )
    status, raw = _get(f"{SEARCH_URL}?{params}")
    if status != 200 or not raw:
        return status, []

    jobs: list[JobListing] = []
    cards = re.split(r'<li>', raw)
    for card in cards:
        title_m = re.search(r'base-search-card__title">\s*(.*?)\s*</h3>', card, re.S)
        comp_m = re.search(r'base-search-card__subtitle">\s*<a[^>]*>\s*(.*?)\s*</a>', card, re.S)
        id_m = re.search(r'data-entity-urn="urn:li:jobPosting:(\d+)"', card)
        loc_m = re.search(r'job-search-card__location">\s*(.*?)\s*</span>', card, re.S)
        time_m = re.search(r'datetime="([^"]+)"', card)
        url_m = re.search(r'base-card__full-link"\s+href="([^"?]+)', card)
        if not (title_m and id_m):
            continue
        jobs.append(JobListing(
            source="linkedin",
            external_id=id_m.group(1),
            title=html.unescape(title_m.group(1).strip()),
            company=html.unescape(comp_m.group(1).strip()) if comp_m else "",
            location=html.unescape(loc_m.group(1).strip()) if loc_m else location,
            url=url_m.group(1) if url_m else f"https://www.linkedin.com/jobs/view/{id_m.group(1)}",
            posted_at=time_m.group(1) if time_m else None,
        ))
    return status, jobs


def fetch_description(job_id: str) -> str:
    """Full job description via the detail endpoint (~5000 chars). Empty on failure."""
    status, raw = _get(DETAIL_URL.format(job_id=job_id))
    if status != 200 or not raw:
        return ""
    m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', raw, re.S)
    return _strip_tags(m.group(1)) if m else ""


def scrape(
    keywords_list: list[str],
    locations: list[str],
    tpr: str = TPR_24H,
    max_pages: int = 1,
    with_descriptions: bool = True,
    delay: float = 1.5,
) -> list[JobListing]:
    """
    Scrape fresh jobs across keyword x location combinations.
    Deduplicates by external_id. Polite throttling via `delay`.
    Returns [] on total failure (caller decides the fallback).
    """
    seen: set[str] = set()
    out: list[JobListing] = []
    for kw in keywords_list:
        for loc in locations:
            for page in range(max_pages):
                status, jobs = search_page(kw, loc, tpr=tpr, start=page * 25)
                if status == 429:
                    # rate limited — back off hard, stop this keyword
                    time.sleep(delay * 6)
                    break
                for j in jobs:
                    if j.external_id in seen:
                        continue
                    seen.add(j.external_id)
                    out.append(j)
                time.sleep(delay)
                if not jobs:
                    break

    if with_descriptions:
        for j in out:
            j.description = fetch_description(j.external_id)
            time.sleep(delay)
    return out


if __name__ == "__main__":
    # Smoke test — run directly to verify the endpoint still works from this machine.
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "operations associate"
    loc = sys.argv[2] if len(sys.argv) > 2 else "Paris, France"
    print(f"Testing LinkedIn guest endpoint: {kw!r} @ {loc!r} (last 24h)...")
    found = scrape([kw], [loc], with_descriptions=False)
    print(f"  {len(found)} fresh jobs:")
    for j in found[:5]:
        print(f"   • {j.title} @ {j.company} ({j.location}) — {j.posted_at}")
    if found:
        d = fetch_description(found[0].external_id)
        print(f"\n  Detail endpoint: {len(d)} char description for '{found[0].title}'")
        print("  ✅ Endpoint healthy" if d else "  ⚠️ Search works but detail endpoint returned nothing")
    else:
        print("  ⚠️ No jobs — endpoint may be rate-limiting or down.")
