"""
scripts/fetch.py — scrape fresh jobs and store them as status=new.
Run by the agent during /atlas:  uv run python -m scripts.fetch [--if-stale [HOURS]]

  --if-stale [HOURS]   fetch-on-open guard: skip entirely if the newest job is
                       younger than HOURS (default 24). Keeps /atlas fast and
                       never re-scrapes LinkedIn when the data is already fresh.

Prints a one-line summary the agent relays to the user.
"""
from __future__ import annotations
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from pipeline import db
from scrapers import aggregate

CONFIG = Path(__file__).parent.parent / "config.yaml"


def _hours_since_newest() -> float | None:
    """Age (in hours) of the freshest job in the DB, or None if empty/unparseable."""
    stamps = [j.scraped_at for j in db.get_jobs() if j.scraped_at]
    if not stamps:
        return None
    try:
        dt = datetime.datetime.fromisoformat(max(stamps))
    except ValueError:
        return None
    now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
    return (now - dt).total_seconds() / 3600


def main() -> int:
    if not CONFIG.exists():
        print("No config.yaml — run /atlas to set up first.")
        return 1
    cfg = yaml.safe_load(CONFIG.read_text())

    # Fetch-on-open guard: skip if the data is still fresh.
    if "--if-stale" in sys.argv:
        i = sys.argv.index("--if-stale")
        threshold = 24.0
        if i + 1 < len(sys.argv) and sys.argv[i + 1].replace(".", "", 1).isdigit():
            threshold = float(sys.argv[i + 1])
        db.init_db()
        age = _hours_since_newest()
        if age is not None and age < threshold:
            print(f"Données fraîches ({age:.0f}h) — pas besoin de re-fetch.")
            return 0

    keywords = cfg.get("expanded_keywords") or cfg.get("target_roles") or []
    locations = cfg.get("locations") or []
    hours = (cfg.get("fetch") or {}).get("hours_old", 24)
    if not keywords or not locations:
        print("config.yaml is missing target_roles/expanded_keywords or locations.")
        return 1

    db.init_db()
    res = aggregate.fetch(
        keywords, locations, hours_old=hours,
        include_remote=bool(cfg.get("include_remote", False)),
    )

    # upsert is idempotent on (source, external_id): new jobs insert, seen jobs
    # just refresh their description/scraped_at without touching user status.
    for job in res.jobs:
        db.upsert_job(job)

    unscored = len(db.get_jobs(status="new"))
    print(res.summary())
    if res.notes:
        print("  " + " ".join(res.notes))
    print(f"  {unscored} jobs awaiting scoring — score them next (batches of 25).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
