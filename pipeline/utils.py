"""Small shared helpers — stdlib only."""
from __future__ import annotations
import re

# Languages we can detect a hard requirement for, with surface forms.
_LANG_PATTERNS = {
    "german": r"\b(german|deutsch|deutschkenntnisse|allemand)\b",
    "french": r"\b(french|français|francais)\b",
    "dutch": r"\b(dutch|nederlands|néerlandais)\b",
    "spanish": r"\b(spanish|español|espagnol)\b",
    "italian": r"\b(italian|italiano|italien)\b",
    "english": r"\benglish\b",
}
# A requirement only counts if paired with a demand word nearby.
_REQUIRE = r"(fluent|native|required|mandatory|proficient|courant|maternelle|erforderlich|obligatoire|c1|c2|bilingual|bilingue)"


def extract_language_requirements(description: str) -> list[str]:
    """
    Pull required-language signals from anywhere in the description (not just the
    first 300 chars), so the scorer's 'reject languages the user doesn't speak'
    rule fires even when the requirement sits deep in the posting.
    """
    if not description:
        return []
    text = description.lower()
    found: list[str] = []
    for lang, pat in _LANG_PATTERNS.items():
        for m in re.finditer(pat, text):
            window = text[max(0, m.start() - 60): m.end() + 60]
            if re.search(_REQUIRE, window):
                found.append(lang)
                break
    return found


def normalize_contract_type(raw: str) -> str | None:
    if not raw:
        return None
    r = raw.lower()
    if any(w in r for w in ("intern", "stage", "praktikum", "beca", "trainee")):
        return "internship"
    if any(w in r for w in ("alternance", "apprenti", "apprenticeship", "dual stud")):
        return "alternance"
    if any(w in r for w in ("werkstudent", "working student", "studentische")):
        return "werkstudent"
    if any(w in r for w in ("freelance", "self-employed", "independent")):
        return "freelance"
    if any(w in r for w in ("contract", "cdd", "fixed-term", "temporary", "interim")):
        return "contract"
    if "part" in r:
        return "part-time"
    if any(w in r for w in ("full", "cdi", "permanent", "festanstellung")):
        return "full-time"
    return None


def dedup_key(title: str, company: str) -> str:
    return f"{title.strip().lower()}|{company.strip().lower()}"
