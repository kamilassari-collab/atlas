"""
scripts/db_write.py — the agent's read/write interface to the local database.
The agent does the thinking; these subcommands move data in and out of SQLite.

Usage (all via `uv run python -m scripts.db_write <cmd>`):
  next-batch [N]            print up to N unscored jobs as JSON (default 25)
  save-scores '<json>'      write [{id, score, reason, keywords}] back; sets status
  awaiting-generation       print jobs the dashboard queued for /generate, as JSON
  set-cv '<text>'           store the user's CV text (from /setup)
  set-status <id> <status>  manually move a job (used by the dashboard too)
"""
from __future__ import annotations
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from pipeline import db
from pipeline.models import ApplicationStatus

CONFIG = Path(__file__).parent.parent / "config.yaml"
CV_TEXT = Path(__file__).parent.parent / "data" / "cv_text.txt"


def _min_score() -> int:
    if CONFIG.exists():
        return (yaml.safe_load(CONFIG.read_text()) or {}).get("min_score", 65)
    return 65


def _job_brief(j) -> dict:
    return {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "contract_type": j.contract_type,
        "language_flags": j.language_flags,
        "description": (j.description or "")[:300],
    }


def next_batch(n: int = 25) -> None:
    jobs = db.get_jobs(status="new")[:n]
    print(json.dumps([_job_brief(j) for j in jobs], ensure_ascii=False, indent=2))


def save_scores(payload: str) -> None:
    """payload: JSON list of {id, score, reason, keywords}."""
    items = json.loads(payload)
    threshold = _min_score()
    for it in items:
        score = int(it.get("score", 0))
        status = (ApplicationStatus.QUEUED.value if score >= threshold
                  else ApplicationStatus.FILTERED_OUT.value)
        kws = it.get("keywords") or []
        db.update_job(
            int(it["id"]),
            relevance_score=score,
            score_reason=it.get("reason", ""),
            matched_keywords=",".join(kws) if isinstance(kws, list) else str(kws),
            status=status,
        )
    print(f"Saved {len(items)} scores (threshold {threshold}).")


def awaiting_generation() -> None:
    jobs = db.jobs_awaiting_generation()
    out = []
    for j in jobs:
        b = _job_brief(j)
        b["description"] = (j.description or "")[:2000]
        out.append(b)
    print(json.dumps(out, ensure_ascii=False, indent=2))


def set_cv(text: str) -> None:
    CV_TEXT.parent.mkdir(parents=True, exist_ok=True)
    CV_TEXT.write_text(text, encoding="utf-8")
    print(f"Stored CV text ({len(text)} chars) at {CV_TEXT}.")


def set_status(job_id: str, status: str) -> None:
    db.update_job(int(job_id), status=status)
    print(f"Job {job_id} -> {status}")


def main(argv: list[str]) -> int:
    db.init_db()
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]
    if cmd == "next-batch":
        next_batch(int(rest[0]) if rest else 25)
    elif cmd == "save-scores":
        save_scores(rest[0])
    elif cmd == "awaiting-generation":
        awaiting_generation()
    elif cmd == "set-cv":
        set_cv(rest[0])
    elif cmd == "set-status":
        set_status(rest[0], rest[1])
    else:
        print(f"Unknown command: {cmd}\n{__doc__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
