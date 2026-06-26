"""
Data models for Atlas — pure stdlib dataclasses, no pydantic.
Python 3.10+ (uses `X | None` union syntax).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class ApplicationStatus(str, Enum):
    NEW = "new"                              # freshly scraped, not yet scored
    FILTERED_OUT = "filtered_out"            # scored below the user's threshold
    QUEUED = "queued"                        # ready to apply (above threshold)
    GENERATION_REQUESTED = "generation_requested"  # dashboard "Generate" enqueued it
    CV_TAILORED = "cv_tailored"
    COVER_LETTER_DONE = "cover_letter_done"
    APPLIED = "applied"
    INTERVIEW_1 = "interview_1"
    INTERVIEW_2 = "interview_2"
    OFFER = "offer"
    REJECTED = "rejected"
    PAUSED = "paused"
    WITHDRAWN = "withdrawn"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobListing:
    source: str                              # "linkedin" | "arbeitnow" | "remotive" | "jobspy"
    external_id: str                         # unique id on the source platform
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    contract_type: str | None = None         # full-time | werkstudent | internship | ...
    posted_at: str | None = None             # ISO date string
    scraped_at: str = field(default_factory=_utcnow_iso)
    relevance_score: int = 0                 # 0-100, scored by Claude in-conversation
    score_reason: str | None = None
    matched_keywords: str | None = None      # comma-joined
    language_flags: str | None = None        # comma-joined required languages found in desc
    status: str = ApplicationStatus.NEW.value
    tailored_cv_path: str | None = None
    cover_letter_path: str | None = None
    notes: str | None = None
    id: int | None = None

    def to_row(self) -> dict:
        return asdict(self)


@dataclass
class UserProfile:
    """
    Written by /setup from the user's 7 onboarding answers (CEO review D3).
    Replaces job_machine's hardcoded Kamil-specific profile — fully config-driven.
    """
    full_name: str = ""
    email: str = ""
    # 1. target roles — free text, any profession
    target_roles: list[str] = field(default_factory=list)       # ["M&A analyst", "nurse"]
    expanded_keywords: list[str] = field(default_factory=list)  # Claude-expanded adjacent terms (volume multiplier)
    # 2. locations — free text
    locations: list[str] = field(default_factory=list)          # ["Paris, France", "London, United Kingdom", "Remote"]
    # 3. seniority — filters out off-target levels in scoring
    seniority: str = "junior"                                   # internship | junior | mid | senior
    # 4. contract types
    contract_types: list[str] = field(default_factory=list)     # full-time | alternance | internship | werkstudent | freelance
    # 5. languages the user speaks (reject offers requiring a language not in this list)
    languages: list[str] = field(default_factory=list)
    # 6. minimum relevance score threshold
    min_score: int = 65
    # 7. CV — handling depends on upload format (CEO review D2 = Option B)
    cv_text: str = ""                                           # extracted by Claude during /setup
    cv_format: str = "docx"                                     # docx | pdf | text — drives tailoring path
    cv_docx_path: str | None = None                            # set only when an editable DOCX was uploaded
    cv_language: str = "english"
