# ⚠️ Retired — but load-bearing. Do not delete this repo.

This was Team Run1's original race guide for the Outback in the Ozarks 205-mile relay.
Active development moved to **[oto-guide](https://github.com/lukebarousse/oto-guide)** — the official
multi-team app at [teamguide.outbackintheozarks.com](https://teamguide.outbackintheozarks.com), where
Run1's roster, paces and leg assignments are now managed (Team settings page, backed by a database).

## What this repo still does (why it must stay alive)

1. **Serves `run1.fun`** via GitHub Pages. The domain's DNS points here; `index.html` and
   `overview.html` are now redirect stubs that forward to
   [teamguide.outbackintheozarks.com/t/run1](https://teamguide.outbackintheozarks.com/t/run1).
   Deleting this repo (or disabling Pages, or removing the `CNAME` file) kills run1.fun.
2. **Serves the printable guide**: [`print.html`](https://run1.fun/print.html) and
   `run1-oto-guide.pdf` — the offline/van version with Run1's roster baked in. The multi-team
   app's print page is generic, so this is still the best paper artifact.

## Maintenance

- **Normally: none.** Leave it alone and run1.fun keeps working.
- **If the redirect target ever changes** (new domain/slug): edit the URLs in `index.html`
  and `overview.html`, push.
- **To reprint with an updated roster/paces** before race day: edit `RUNNERS`/`PLAN` in
  `builder/data.py`, then
  ```bash
  python3 -m venv .venv && .venv/bin/pip install qrcode pillow
  cd builder && ../.venv/bin/python build.py && cp out/print.html ..
  ```
  and regenerate the PDF from `print.html` with headless Chrome. Do **not** copy
  `out/index.html` / `out/overview.html` to the root — that would overwrite the redirects.

## For other teams

Don't fork this. Ask the race director for your team's link on the official app
([oto-guide](https://github.com/lukebarousse/oto-guide)).
