"""
scripts/render_letter.py — render a cover letter to PDF (reportlab, local).
The agent writes the letter text; this script only does layout.

Usage:  uv run python -m scripts.render_letter <job_id> '<letter text>'
        (or pass a file path instead of raw text: --file /path/to/letter.txt)

Writes data/outputs/letter_<id>_<company>.pdf, updates the DB row
(cover_letter_path + status=cover_letter_done) and prints the saved path.
"""
from __future__ import annotations
import re
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_RIGHT, TA_JUSTIFY

from pipeline import db

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "outputs"
CONFIG = ROOT / "config.yaml"


def _profile() -> dict:
    if CONFIG.exists():
        return (yaml.safe_load(CONFIG.read_text()) or {}).get("profile", {}) or {}
    return {}


def render(job_id: int, text: str) -> Path:
    job = db.get_job(job_id)
    if job is None:
        raise SystemExit(f"No job with id {job_id}")
    prof = _profile()
    name = prof.get("full_name") or "Candidate"
    email = prof.get("email") or ""

    OUT.mkdir(parents=True, exist_ok=True)
    safe_co = re.sub(r"[^\w]+", "_", job.company)[:24].strip("_") or "company"
    out_path = OUT / f"letter_{job_id}_{safe_co}.pdf"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
                            topMargin=2.5 * cm, bottomMargin=2.5 * cm)
    hname = ParagraphStyle("hname", fontName="Helvetica-Bold", fontSize=10, leading=14)
    hinfo = ParagraphStyle("hinfo", fontName="Helvetica", fontSize=10, leading=14)
    recip = ParagraphStyle("recip", fontName="Helvetica-Bold", fontSize=10, leading=14, alignment=TA_RIGHT)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=15,
                          alignment=TA_JUSTIFY, spaceAfter=10)
    plain = ParagraphStyle("plain", fontName="Helvetica", fontSize=10, leading=14)

    left = [Paragraph(name, hname)]
    if email:
        left.append(Paragraph(email, hinfo))
    right = [Paragraph("Hiring team,", recip), Paragraph(f"{job.company}", recip)]
    head = Table([[left, right]], colWidths=[9 * cm, 7 * cm])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story = [head, Spacer(1, 24)]
    # Strip stray markdown bullets; render **bold** properly.
    clean = re.sub(r"^[\-\*•]\s+", "", text, flags=re.MULTILINE)
    clean = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", clean)
    for para in clean.strip().split("\n\n"):
        para = para.strip().replace("\n", " ")
        if para:
            story.append(Paragraph(para, body))
    story += [Spacer(1, 20), Paragraph(name, plain)]

    doc.build(story)
    out_path.write_bytes(buf.getvalue())

    rel = str(out_path.relative_to(ROOT))
    db.update_job(job_id, cover_letter_path=rel, status="cover_letter_done")
    return out_path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    job_id = int(argv[0])
    if argv[1] == "--file":
        text = Path(argv[2]).read_text(encoding="utf-8")
    else:
        text = argv[1]
    path = render(job_id, text)
    print(f"Lettre PDF : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
