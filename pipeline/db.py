"""
SQLite store for Atlas. Stdlib only.
Ported from job_machine/integrations/db.py, adapted to the dataclass models
(no pydantic) and the new fields: score_reason, matched_keywords,
language_flags, plus the generation_requested status used by the dashboard.
"""
from __future__ import annotations
import sqlite3
from dataclasses import fields
from pathlib import Path
from pipeline.models import JobListing, ApplicationStatus

DB_PATH = Path(__file__).parent.parent / "data" / "atlas.db"

# The columns we persist, in order. Mirrors JobListing minus `id` (autoincrement).
_COLS = [
    "source", "external_id", "title", "company", "location", "url",
    "description", "contract_type", "posted_at", "scraped_at",
    "relevance_score", "score_reason", "matched_keywords", "language_flags",
    "status", "tailored_cv_path", "cover_letter_path", "notes",
]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source          TEXT NOT NULL,
                external_id     TEXT NOT NULL,
                title           TEXT NOT NULL,
                company         TEXT NOT NULL,
                location        TEXT,
                url             TEXT NOT NULL,
                description     TEXT,
                contract_type   TEXT,
                posted_at       TEXT,
                scraped_at      TEXT NOT NULL,
                relevance_score INTEGER DEFAULT 0,
                score_reason    TEXT,
                matched_keywords TEXT,
                language_flags  TEXT,
                status          TEXT DEFAULT 'new',
                tailored_cv_path  TEXT,
                cover_letter_path TEXT,
                notes           TEXT,
                UNIQUE(source, external_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT NOT NULL,
                finished_at TEXT,
                jobs_found  INTEGER DEFAULT 0,
                jobs_queued INTEGER DEFAULT 0,
                errors      TEXT
            )
        """)


def upsert_job(job: JobListing) -> int:
    """Insert a job, or refresh its mutable fields if (source, external_id) exists.
    Returns the row id. Does NOT clobber user-tracking fields (status, notes,
    tailored_cv_path) on conflict — those belong to the user, not the scraper."""
    placeholders = ", ".join("?" for _ in _COLS)
    collist = ", ".join(_COLS)
    values = [getattr(job, c) for c in _COLS]
    with get_conn() as conn:
        cur = conn.execute(f"""
            INSERT INTO jobs ({collist})
            VALUES ({placeholders})
            ON CONFLICT(source, external_id) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                description=excluded.description,
                scraped_at=excluded.scraped_at
            RETURNING id
        """, values)
        return cur.fetchone()[0]


def update_job(job_id: int, **kwargs) -> None:
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {sets} WHERE id=?", list(kwargs.values()) + [job_id])


def get_jobs(status: str | None = None, min_score: int = 0) -> list[JobListing]:
    query = "SELECT * FROM jobs WHERE relevance_score >= ?"
    params: list = [min_score]
    if status:
        query += " AND status=?"
        params.append(status)
    # Deterministic ordering: score desc, then id desc — avoids the link-mismatch
    # bug from job_machine where score ties reordered rows between queries.
    query += " ORDER BY relevance_score DESC, id DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_job(r) for r in rows]


def get_job(job_id: int) -> JobListing | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def jobs_awaiting_generation() -> list[JobListing]:
    """Drained by /generate — rows the dashboard's Generate button enqueued."""
    return get_jobs(status=ApplicationStatus.GENERATION_REQUESTED.value)


def _row_to_job(row: sqlite3.Row) -> JobListing:
    d = dict(row)
    valid = {f.name for f in fields(JobListing)}
    return JobListing(**{k: v for k, v in d.items() if k in valid})
