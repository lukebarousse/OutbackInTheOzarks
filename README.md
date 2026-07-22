# Team Run1 — Outback in the Ozarks 205 Race Guide

Static two-page site + print PDF for the 2026 OTO 205-mile relay.

| File | What it is |
|---|---|
| `index.html` | **Home: the legs page.** All 36 legs by exchange section, sticky leg-jump bar, runner filter, beta + stats per leg |
| `overview.html` | Dashboard: course steepness chart, section table, runner planner, all-legs table, night rules |
| `print.html` | Everything on one page with QR codes — print this (Cmd+P) to regenerate the PDF |
| `run1-oto-guide.pdf` | The print version, pre-rendered |
| `builder/` | Python generator (`data.py` = all leg data, `build.py` = HTML/SVG builder) |

## Deploy to GitHub Pages

1. Push this repo to GitHub (public)
2. Settings → Pages → Deploy from branch → `main` / root
3. Live at `https://YOURUSERNAME.github.io/OutbackInTheOzarks/` (or add a custom domain like run1.run via Settings → Pages → Custom domain + a CNAME record at your registrar)

## Updating

- **Runner names:** edit the `RUNNERS` const near the bottom of `index.html` and `overview.html` (e.g. `{1:"Luke", 2:"Jake", ...}`) — filter buttons and leg cards pick the names up automatically. Or set them in `builder/build.py` and rebuild.
- **Rebuild from source:** `pip install qrcode pillow` then `python3 builder/build.py` (run from `builder/`; outputs land in `builder/out/`, copy to repo root).
- **Elevation profiles:** `builder/elev.json` holds per-leg distance/elevation arrays pulled from the official Strava routes (July 2026); `build.py` bakes them in as SVG charts. `builder/elev_meta.json` carries the 2026 route distances used for the 🔄 route-change flags on legs 1, 8, 30, 31.

## Data sources

Leg beta, ratings and surface notes: our 2025 runner's notes. Distances/gain/mile markers: the team's 2025 Strava sheet. Leg names, Strava routes, exchange stations and rules: outbackintheozarks.com. Leg start/exchange coordinates (`builder/starts.json`, the 📍 map links): the race's official "Google Maps Exchange Zones" My Maps, exported as KML July 2026 and sanity-checked against leg distances + reverse-geocoded landmarks. Not an official race document.
