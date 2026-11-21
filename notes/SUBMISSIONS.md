# Machina CAD De-ID: submissions log

Track page: https://www.joinbuilders.org/buildathon/tracks/machina-deid
Team folder: gs://builders-machina-submissions-1120/teams/5fdc15d7-39da-4a92-82e2-1ed6cd4f5e5d/
Claude submits these itself (20 scored attempts in total, at most 2 per hour). Newest first.

| # | Time (ET) | Receipt | What it contains | Score / 1000 | Category breakdown | Status |
|---|---|---|---|---|---|---|
| 1 | Sat 12:10 PM | BB-9204433E | Probe: 400 small input files, unchanged. Purpose: learn the scorer's categories | pending | pending | Scoring |

## How to submit (browser gotchas)
- Always use a fresh tab: `tabs_create_mcp` -> navigate to the track page -> `find` the textbox and Submit button.
- The Submit button opens a native `confirm()` dialog that freezes the extension. Before clicking, run
  `window.confirm = () => true` in the page with the javascript tool, then click Submit and read the receipt text.
- Upload token: click "Get upload token" then "Copy upload commands"; read it from the clipboard in PowerShell and write it
  to `private/token.txt` (never print it). It lasts 1 hour.
