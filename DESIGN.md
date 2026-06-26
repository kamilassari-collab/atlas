# Atlas — Design System (LOCKED)

The visual contract for the Atlas dashboard. User-approved 2026-06-25. Calibrate every
UI change against this. The brief: **premium-simple.** "Free" only sells if it looks
expensive, and restraint is what reads expensive.

## Voice
A calm, premium job command center for AI-native students. Quiet luxury, not loud.
Never cheap, never candy, never template-y.

## Type
**Switzer** (Fontshare, one family, weights 300–700) for everything.
`<link href="https://api.fontshare.com/v2/css?f[]=switzer@300,400,500,600,700&display=swap">`
Do NOT use: DM Sans, Syne, Instrument Serif, Fraunces, Hanken Grotesk, Plus Jakarta,
Onest, Clash Display, Cabinet Grotesk, Inter (all tried and rejected).

## Color — quiet-luxury monochrome
```
--paper  #FAF8F4   warm paper background
--panel  #F1EEE7   subtle panel
--card   #FFFFFF   surfaces
--ink    #16161A   near-black: headings, primary buttons
--tx     #26262B / --tx-2 #6B6B73 / --muted #9B9AA0   text scale
--line   #E7E3DA / --line-2 #F0ECE4   hairlines
--side   #16161A   near-black sidebar
```
**The only color in the UI is the score-tier dot:** sage `--hi #4F7A5E` (80+),
amber `--mid #9A6F2E` (65–79), clay `--lo #9C5544` (<65). No accent color beyond that.
If the user later wants one accent, add it deliberately — never unprompted.

## No emojis
Zero. Use hairline SVG marks (the radar glyph, the Postuler arrow, nav icons).

## Layout
- **Sidebar:** near-black, "Atlas" wordmark + geometric mark + "Job command center".
- **Hero:** "Tes offres, avant tout le monde." + freshness subline.
- **Funnel band (NOT vanity):** fraîches · à postuler · postulé · en entretien. Never "80+ match".
- **Feed = aligned ledger:** hairline-separated rows; columns line up across every card —
  `title · score · statut · CV · Lettre · Postuler`. Score = number + tier dot.
- **Buttons:** one dark (ink) primary per card; ghosts for the rest. Hairline borders.
- **Kanban:** calm columns, small-caps headers + tier dots, no emoji doc links (CV / LM text).

## Motion
Staggered fadeUp on load, subtle pulse on the freshness dot, spinner on generation.
Respects `prefers-reduced-motion`.

## The one-command model
The dashboard is what `/atlas` opens. All copy points to one command: `/atlas` in Claude
Code. The user clicks in the dashboard (track, apply, download) and only talks to the agent
for specific AI requests. Never a multi-step command chase.
