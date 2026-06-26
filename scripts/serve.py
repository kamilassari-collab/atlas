"""
scripts/serve.py — local dashboard server. Stdlib only, no dependencies.

Serves dashboard/index.html and a tiny JSON API over the user's own SQLite:
  GET  /api/jobs            all scored jobs (feed + kanban read this)
  GET  /api/meta            counts per status + last scrape time
  POST /api/status          {"id": 42, "status": "applied"}  (kanban drag, dropdown,
                            and the Generate button → status=generation_requested)

Run:  uv run python -m scripts.serve [--open]
Tries port 4242 first, walks up if busy, always prints the chosen URL.
"""
from __future__ import annotations
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import db

ROOT = Path(__file__).parent.parent
DASHBOARD = ROOT / "dashboard" / "index.html"
OUTPUTS = ROOT / "data" / "outputs"
BASE_PORT = 4242

MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

# Statuses a user can set from the UI — anything else is rejected.
ALLOWED_STATUSES = {
    "queued", "generation_requested", "cv_tailored", "cover_letter_done",
    "applied", "interview_1", "interview_2", "offer", "rejected",
    "paused", "withdrawn",
}


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # silence per-request noise
        pass

    # -- helpers ------------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # localhost-only tool; keep the API same-origin anyway.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    # -- routes -------------------------------------------------------------
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            if not DASHBOARD.exists():
                self._send(404, b"dashboard/index.html missing", "text/plain")
                return
            self._send(200, DASHBOARD.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/jobs":
            jobs = [j.to_row() for j in db.get_jobs()]
            self._json(200, jobs)
        elif self.path.startswith("/files/"):
            # Serve generated CVs/letters from data/outputs ONLY.
            name = self.path[len("/files/"):]
            target = (OUTPUTS / name).resolve()
            if not str(target).startswith(str(OUTPUTS.resolve())) or not target.is_file():
                self._send(404, b"not found", "text/plain")
                return
            ctype = MIME.get(target.suffix.lower(), "application/octet-stream")
            self._send(200, target.read_bytes(), ctype)
        elif self.path == "/api/meta":
            jobs = db.get_jobs()
            counts: dict[str, int] = {}
            last_scrape = ""
            for j in jobs:
                counts[j.status] = counts.get(j.status, 0) + 1
                if j.scraped_at and j.scraped_at > last_scrape:
                    last_scrape = j.scraped_at
            self._json(200, {"counts": counts, "total": len(jobs), "last_scrape": last_scrape})
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/status":
            self._send(404, b"not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            job_id = int(data["id"])
            status = str(data["status"])
        except (KeyError, ValueError, json.JSONDecodeError):
            self._json(400, {"error": "expected {id: int, status: str}"})
            return
        if status not in ALLOWED_STATUSES:
            self._json(400, {"error": f"status must be one of {sorted(ALLOWED_STATUSES)}"})
            return
        if db.get_job(job_id) is None:
            self._json(404, {"error": f"no job with id {job_id}"})
            return
        db.update_job(job_id, status=status)
        self._json(200, {"ok": True, "id": job_id, "status": status})


def main() -> int:
    db.init_db()
    port = BASE_PORT
    server = None
    for port in range(BASE_PORT, BASE_PORT + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        print(f"No free port in {BASE_PORT}-{BASE_PORT + 19}.")
        return 1

    url = f"http://localhost:{port}"
    print(f"Atlas dashboard → {url}   (Ctrl-C to stop)")
    if "--open" in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
