---
description: Atlas — find fresh jobs, score them, prep your best CVs, open the dashboard
---

You are running **Atlas**. The user typed `/atlas`. Do the WHOLE pipeline in one go,
then report a single clean summary. The user should not run any other command.
Full rules are in `AGENTS.md`; this is the run order.

## 1. First run only
If `config.yaml` does NOT exist, onboard first (see AGENTS.md "first run"):
provision `uv`, ask the ~5 setup questions in one friendly message, read their CV,
expand roles into `expanded_keywords`. Then continue to step 2.

## 2. Fetch (fetch-on-open)
```bash
uv run python -m scripts.fetch --if-stale 24
```
This skips automatically if the data is still fresh (<24h) — that's intended, not a
failure. If it does fetch and returns 0 jobs, tell the user plainly (LinkedIn may be
rate-limiting, retry in an hour). Relay the one-line summary.

## 3. Score the new jobs (you do this — you are the engine)
Pull and score every unscored job in batches of 25:
```bash
uv run python -m scripts.db_write next-batch 25
```
Judge each 0–100 against the user's profile (roles, seniority, cities, contracts).
Reject (score 0) any job whose `language_flags` names a language they don't speak.
Write each batch back:
```bash
uv run python -m scripts.db_write save-scores '<json>'
```
Repeat until no unscored jobs remain. (Skip this step if step 2 fetched nothing new.)

## 4. Auto-prep the top matches
For the top 3 unworked jobs scoring ≥ 80, generate the CV + cover letter now
(see AGENTS.md "Generate" — re-angle bullets, never invent; render_letter + render_cv).
CV generation is instant (DOCX links now, PDF upgrades in the background), so this is cheap.

## 5. Open the dashboard
```bash
uv run python -m scripts.serve --open
```
Run it in the background so the conversation continues. It prints the URL.

## 6. Report ONE summary
e.g. "X fresh roles, Y strong matches (80+), your top 3 already have CV + letter ready.
Dashboard's open at <url>." Nothing else for the user to do — they live in the dashboard now.
