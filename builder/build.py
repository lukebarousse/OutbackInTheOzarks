#!/usr/bin/env python3
"""Build the Run1 OTO race guide site:
   out/index.html    — legs page (home): jump bar, runner/slot filter, leg cards by section
   out/overview.html — dashboard: skyline, sections, planner, all-legs table, rules
   out/print.html    — everything on one page, print CSS -> PDF
Elevation profiles: if out/elev.json exists ({"1": [[mi, ft], ...], ...}), native SVG
profiles are embedded in each leg card.
"""
import base64, io, json, os, html as H
import qrcode
from data import LEGS, NAMES, STRAVA, EXCHANGES, SECTIONS, RACE, TOTAL_MI, TOTAL_GAIN

DIFF = {"Easy": "#0ca30c", "Moderate": "#fab219", "Hard": "#ec835a", "Very Hard": "#d03b3b"}
# deliberately outside the difficulty palette (green/yellow/orange/red)
SURF = {"pavement": "#64748b", "gravel": "#a97142", "trail": "#14919b"}

# starts.json: leg start/exchange coordinates from the race's official
# "Google Maps Exchange Zones" My Maps (mid=1S3rWAD35CEJBqz6sRkXKpyRrL0PEO_w),
# exported as KML July 2026. Key k = exchange zone k = start of leg k+1;
# key 0 = start line, 36 = finish line. Verified against leg distances +
# reverse-geocoded landmarks (Hobbs, Withrow, Elkins, L. Ft. Smith, Devil's Den).
STARTS = json.load(open("starts.json")) if os.path.exists("starts.json") else {}

ELEV, ELEV_META = {}, {}
for p in ("out/elev.json", "elev.json"):
    if os.path.exists(p):
        ELEV = {int(k): v for k, v in json.load(open(p)).items()}
        mp = p.replace("elev.json", "elev_meta.json")
        if os.path.exists(mp):
            ELEV_META = {int(k): v for k, v in json.load(open(mp)).items()}
        break

def qr_datauri(url, box=4):
    q = qrcode.QRCode(border=2, box_size=box)
    q.add_data(url); q.make(fit=True)
    img = q.make_image(fill_color="#0b0b0b", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def esc(s): return H.escape(s, quote=False)
def fmt_mi(x): return f"{x:,.2f}".rstrip("0").rstrip(".")
def strava_url(n): return f"https://www.strava.com/routes/{STRAVA[n]}"
def ftpmi(l): return l["gain"] / l["dist"]

# ---------------- skyline ----------------
def skyline_svg():
    W, H_, PAD_L, PAD_R, TOP, BOT = 760, 200, 30, 8, 40, 26
    plot_w, plot_h = W - PAD_L - PAD_R, H_ - TOP - BOT
    MAXY = 200.0
    def x(mi): return PAD_L + mi / TOTAL_MI * plot_w
    def y(v): return TOP + plot_h - min(v, MAXY) / MAXY * plot_h
    parts = [f'<svg viewBox="0 0 {W} {H_}" role="img" aria-label="Steepness of each leg, climb feet per mile" style="width:100%;height:auto;display:block">']
    for gv in (50, 100, 150, 200):
        parts.append(f'<line x1="{PAD_L}" y1="{y(gv):.1f}" x2="{W-PAD_R}" y2="{y(gv):.1f}" stroke="var(--grid)" stroke-width="1"/>')
        parts.append(f'<text x="{PAD_L-4}" y="{y(gv)+3:.1f}" text-anchor="end" font-size="8" fill="var(--muted)">{gv}</text>')
    for l in LEGS:
        x0, x1 = x(l["start_mi"]), x(l["end_mi"])
        v = ftpmi(l)
        parts.append(f'<a href="index.html#leg-{l["n"]}"><rect x="{x0+0.7:.1f}" y="{y(v):.1f}" width="{max(x1-x0-1.4,2):.1f}" height="{(TOP+plot_h-y(v)):.1f}" rx="2" fill="{DIFF[l["rating"]]}" stroke="rgba(0,0,0,.28)" stroke-width="0.5"><title>Leg {l["n"]} · {NAMES[l["n"]]} · {fmt_mi(l["dist"])} mi · +{l["gain"]:,} ft · {v:.0f} ft/mi · {l["rating"]}</title></rect></a>')
        parts.append(f'<text x="{(x0+x1)/2:.1f}" y="{TOP+plot_h+9}" text-anchor="middle" font-size="6.2" fill="var(--muted)">{l["n"]}</text>')
    parts.append(f'<line x1="{PAD_L}" y1="{TOP+plot_h}" x2="{W-PAD_R}" y2="{TOP+plot_h}" stroke="var(--axis)" stroke-width="1"/>')
    marks = [(0, "START", False)] + [(k, EXCHANGES[k]["name"].split("—")[0].split("State")[0].strip(), True) for k in sorted(EXCHANGES)] + [(36, "FINISH", False)]
    for k, label, dash in marks:
        mi = 0 if k == 0 else [l for l in LEGS if l["n"] == k][0]["end_mi"]
        xx = x(mi)
        if dash:
            parts.append(f'<line x1="{xx:.1f}" y1="{TOP-14}" x2="{xx:.1f}" y2="{TOP+plot_h}" stroke="var(--ink2)" stroke-width="0.8" stroke-dasharray="3 3"/>')
            parts.append(f'<text x="{xx:.1f}" y="{TOP-11}" text-anchor="middle" font-size="7" fill="var(--muted)">mi {fmt_mi(mi)}</text>')
        anchor = "start" if k == 0 else ("end" if k == 36 else "middle")
        parts.append(f'<text x="{xx:.1f}" y="{TOP-20}" text-anchor="{anchor}" font-size="8" font-weight="700" fill="var(--ink)">{esc(label)}</text>')
    for m in range(0, 226, 25):
        if m > TOTAL_MI: break
        parts.append(f'<text x="{x(m):.1f}" y="{TOP+plot_h+20}" text-anchor="middle" font-size="7.5" fill="var(--muted)">{m} mi</text>')
    parts.append(f'<text x="{PAD_L-22}" y="{TOP-2}" font-size="7.5" fill="var(--muted)">ft/mi</text>')
    parts.append("</svg>")
    return "".join(parts)

# ---------------- per-leg elevation profile ----------------
def profile_svg(n):
    pts = ELEV.get(n)
    if not pts:
        return ""
    W, H_, PL, PR, PT, PB = 620, 120, 40, 8, 8, 18
    pw, ph = W - PL - PR, H_ - PT - PB
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    lo, hi = min(ys), max(ys)
    rng = max(hi - lo, 40)
    lo_pad, hi_pad = lo - rng * 0.06, hi + rng * 0.08
    def X(d): return PL + (d - x0) / max(x1 - x0, 0.01) * pw
    def Y(e): return PT + (hi_pad - e) / (hi_pad - lo_pad) * ph
    path = f"M {X(xs[0]):.1f} {Y(ys[0]):.1f} " + " ".join(f"L {X(d):.1f} {Y(e):.1f}" for d, e in pts[1:])
    area = path + f" L {X(xs[-1]):.1f} {PT+ph} L {X(xs[0]):.1f} {PT+ph} Z"
    parts = [f'<svg viewBox="0 0 {W} {H_}" role="img" aria-label="Elevation profile leg {n}: {lo:.0f} to {hi:.0f} ft" style="width:100%;height:auto;display:block">']
    # y gridlines: round levels
    import math
    step = 100 if rng > 150 else 50
    gv = math.ceil(lo_pad / step) * step
    while gv < hi_pad:
        parts.append(f'<line x1="{PL}" y1="{Y(gv):.1f}" x2="{W-PR}" y2="{Y(gv):.1f}" stroke="var(--grid)" stroke-width="1" stroke-dasharray="3 3"/>')
        parts.append(f'<text x="{PL-4}" y="{Y(gv)+2.5:.1f}" text-anchor="end" font-size="7.5" fill="var(--muted)">{gv:,.0f}</text>')
        gv += step
    parts.append(f'<path d="{area}" fill="color-mix(in srgb, var(--accent) 22%, transparent)"/>')
    parts.append(f'<path d="{path}" fill="none" stroke="var(--accent)" stroke-width="1.6" stroke-linejoin="round"/>')
    # x ticks each mile
    m = 1
    while m < x1:
        parts.append(f'<text x="{X(m):.1f}" y="{PT+ph+11}" text-anchor="middle" font-size="7.5" fill="var(--muted)">{m} mi</text>')
        m += 1
    parts.append(f'<text x="{PL-4}" y="{PT+2}" text-anchor="end" font-size="7" fill="var(--muted)">ft</text>')
    parts.append("</svg>")
    return f'<div class="profile">{"".join(parts)}<div class="proflabel">Elevation profile · {lo:,.0f}–{hi:,.0f} ft <span class="tiny">(current 2026 Strava route)</span></div></div>'

# ---------------- components ----------------
def badge(label, rating):
    c = DIFF[rating]
    return (f'<span class="pill" style="--pc:{c}"><span class="dot"></span>'
            f'<span class="pl">{esc(label)}</span><b>{esc(rating)}</b></span>')

def surface_bar(l):
    seg = ""
    for pct, key in zip(l["surface"], ("pavement", "gravel", "trail")):
        if pct > 0:
            lbl = key if pct >= 22 else ""
            seg += f'<div class="seg" style="flex:{pct};background:{SURF[key]}" title="{pct}% {key}">{lbl}</div>'
    return (f'<div class="surfrow"><div class="surfbar">{seg}</div>'
            f'<div class="surftext">{esc(l["surface_text"])}</div></div>')

STEEP_ZONES = [(50, "Easy"), (100, "Moderate"), (150, "Hard"), (10**9, "Very Hard")]

def meter(l):
    v = ftpmi(l)
    zone = next(name for lim, name in STEEP_ZONES if v < lim)
    return (f'<div class="meterwrap" title="Steepness zones (ft/mi): under 50 easy · 50–100 moderate · 100–150 hard · 150+ very hard">'
            f'<div class="meter zoned"><div class="fill" style="width:{min(v/200,1)*100:.0f}%;background:{DIFF[zone]}"></div></div>'
            f'<span class="mval">{v:.0f} ft/mi</span></div>')

def climb_chips(l):
    return "".join(f'<span class="chip climb">▲ {g}% avg · {d} mi · {e:,} ft</span>' for g, e, d in l["climbs"])

def tag_chips(l):
    return "".join(f'<span class="chip warn">⚠ {esc(t)}</span>' for t in l["tags"])

def leg_card(l):
    n = l["n"]
    slot = (n - 1) % 6 + 1
    team_b = badge("team says", l["team"]) if l["team"] else ""
    src_note = ' <span class="tiny">(rating from our sheet — missing in the note)</span>' if l.get("rating_src") else ""
    foot = f'<div class="footnote">ℹ {esc(l["footnote"])}</div>' if l.get("footnote") else ""
    m = ELEV_META.get(n)
    if m and abs(m["mi"] - l["dist"]) > 0.15:
        foot += (f'<div class="footnote">🔄 <b>2026 route update:</b> Strava now measures this leg at ~{m["mi"]:.1f} mi '
                 f'(our 2025 data: {fmt_mi(l["dist"])} mi / +{l["gain"]:,} ft). The profile below is the current route — '
                 f'expect the stats to shift a bit.</div>')
    url = strava_url(n)
    return f'''
<article class="leg" id="leg-{n}" data-slot="{slot}">
  <div class="leghead">
    <div class="legnum">{n:02d}</div>
    <div class="titleblock">
      <h3>{esc(NAMES[n])}</h3>
      <div class="meta">mile {fmt_mi(l["start_mi"])} → {fmt_mi(l["end_mi"])} · rotation slot {slot} · runner <span class="runner-name" data-slot="{slot}">—</span></div>
    </div>
    <div class="badges">{badge("official", l["rating"])}{team_b}</div>
  </div>
  <div class="statrow">
    <div class="stat"><b>{fmt_mi(l["dist"])}</b> mi</div>
    <div class="stat"><b>+{l["gain"]:,}</b> ft</div>
    {meter(l)}
    {climb_chips(l)}
  </div>
  {profile_svg(n)}
  {surface_bar(l)}
  <p class="beta"><span class="src">2025 team beta</span>{esc(l["beta"])}{src_note}</p>
  <div class="tagrow">{tag_chips(l)}</div>
  {foot}
  <div class="legfoot">
    <a class="stravabtn web-only" href="{url}" target="_blank" rel="noopener">View route on Strava ↗</a>
    {map_links(n)}
    <div class="qrbox print-only"><img src="{qr_datauri(url)}" alt="QR: Strava route leg {n}"><span>Strava route</span></div>
  </div>
</article>'''

def nav_pair(key, label, btn_cls="stravabtn mapbtn"):
    """Google + Apple Maps navigation links (web) + coords (print) for a STARTS point."""
    st = STARTS.get(str(key))
    if not st: return ""
    ll = f'{st["lat"]:.6f},{st["lng"]:.6f}'
    return (f'<a class="{btn_cls} web-only" href="https://www.google.com/maps/dir/?api=1&amp;destination={ll}" '
            f'target="_blank" rel="noopener">📍 {label}Google Maps ↗</a>'
            f'<a class="{btn_cls} web-only" href="https://maps.apple.com/?daddr={ll}" '
            f'target="_blank" rel="noopener">📍 {label}Apple Maps ↗</a>'
            f'<span class="coords print-only">📍 {ll}</span>')

def map_links(n):
    """Navigation links to the leg's start (official exchange-zone coords)."""
    return nav_pair(n - 1, "Start · ")

def banner_exchange_row(i, first_leg):
    """Where this section begins (start line / major exchange), with nav links for the van."""
    if i == 0:
        head, note, key = "🚩 START — LAKE LEATHERWOOD CITY BALLPARK", "mile 0 · race start", "0"
    else:
        ex = EXCHANGES[first_leg - 1]
        mi = [l for l in LEGS if l["n"] == first_leg - 1][0]["end_mi"]
        head = f'🚩 MAJOR EXCHANGE {i} — {esc(ex["name"].upper())}'
        extra = ex["note"].removeprefix(f"Major exchange {i}").strip(" ·")
        note = f'mile {fmt_mi(mi)}' + (f' · {esc(extra)}' if extra else "")
        key = str(first_leg - 1)
    return (f'<div class="secex"><div><b>{head}</b><span>{note}</span></div>'
            f'<div class="mapwrap">{nav_pair(key, "", "bannerbtn")}</div></div>')

def section_block(i, sec):
    a, b = sec["legs"]
    legs = [l for l in LEGS if a <= l["n"] <= b]
    mi = sum(l["dist"] for l in legs); gain = sum(l["gain"] for l in legs)
    origin = "Lake Leatherwood (START)" if i == 0 else SECTIONS[i - 1]["dest"]
    cards = "".join(leg_card(l) for l in legs)
    ex = "" if b in EXCHANGES else (
        '<div class="exchange finish"><span class="flag">🏁</span><div>'
        f'<b>FINISH — PRAIRIE GROVE BATTLEFIELD STATE PARK</b><span>mile {fmt_mi(TOTAL_MI)} · you did the thing</span>'
        f'<div class="mapwrap">{nav_pair(36, "Finish · ")}</div></div></div>')
    return f'''
<section class="chapter" id="sec{i+1}">
  <div class="secbanner">
    <div class="secno">SECTION {i+1}</div>
    <h2>Legs {a}–{b} · {esc(origin)} → {esc(sec["dest"])}</h2>
    <div class="sectotals">{mi:.1f} mi · +{gain:,} ft</div>
    {banner_exchange_row(i, a)}
  </div>
  {cards}
  {ex}
</section>'''

RATING_PTS = {"Easy": 1, "Moderate": 2, "Hard": 3, "Very Hard": 4}

def planner_table():
    slots = []
    for s in range(1, 7):
        legs = [l for l in LEGS if (l["n"] - 1) % 6 + 1 == s]
        mi = sum(l["dist"] for l in legs); gain = sum(l["gain"] for l in legs)
        pts = sum(RATING_PTS[l["team"] or l["rating"]] for l in legs)
        slots.append(dict(s=s, legs=legs, mi=mi, gain=gain, pts=pts))
    avg_mi = sum(x["mi"] for x in slots) / 6
    avg_gain = sum(x["gain"] for x in slots) / 6
    avg_pts = sum(x["pts"] for x in slots) / 6
    for x in slots:
        x["score"] = x["mi"] / avg_mi + x["gain"] / avg_gain + x["pts"] / avg_pts
    top = max(x["score"] for x in slots)
    slots.sort(key=lambda x: -x["score"])
    rows = ""
    for rank, x in enumerate(slots, 1):
        s, legs = x["s"], x["legs"]
        idx = round(100 * x["score"] / top)
        hardest = max(legs, key=lambda l: (RATING_PTS[l["team"] or l["rating"]], l["gain"], ftpmi(l)))
        dots = "".join(
            f'<span class="dotc" style="background:{DIFF[l["team"] or l["rating"]]}" '
            f'title="Leg {l["n"]} · {esc(NAMES[l["n"]])} · {l["team"] or l["rating"]}"></span>'
            for l in legs)
        rows += (f'<tr><td class="c"><b>{rank}</b></td><td class="c"><b>{s}</b></td>'
                 f'<td class="blankcell runner-name" data-slot="{s}">&nbsp;</td>'
                 f'<td>{", ".join(str(l["n"]) for l in legs)}</td><td class="r">{x["mi"]:.1f}</td><td class="r">{x["gain"]:,}</td>'
                 f'<td class="nowrap">{dots}</td>'
                 f'<td><div class="meterwrap"><div class="meter"><div class="fill" style="width:{idx}%"></div></div>'
                 f'<span class="mval">{idx}</span></div></td>'
                 f'<td>Leg {hardest["n"]} · {esc(NAMES[hardest["n"]])} ({hardest["team"] or hardest["rating"]} · +{hardest["gain"]:,} ft)</td></tr>')
    return f'''<div class="tscroll"><table class="tbl">
<thead><tr><th>Rank</th><th>Slot</th><th>Runner</th><th>Legs</th><th class="r">Miles</th><th class="r">Climb ft</th><th>Leg ratings</th><th>Difficulty</th><th>Toughest assignment</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="tiny" style="margin:.6em 0 0">Sorted hardest → easiest. Difficulty = equal parts total miles, total climb, and summed leg ratings (Easy 1 → Very Hard 4, team rating where it differs), scaled so the hardest slot = 100. Rating dots are in leg order<span class="web-only"> — hover for the leg</span>.</p>'''

def watch_panel(legs_href="index.html"):
    return f'''<div class="panel" id="watch">
  <h2>Get your legs on your Garmin watch</h2>
  <p class="tiny" style="margin:.2em 0 .6em">Cell signal is spotty on the course — load your legs as courses <b>before race weekend</b> so the watch can guide you (route line, off-course alerts, climb profile) with no phone needed.</p>
  <ol class="steps">
    <li><b>Link Strava to Garmin (one-time).</b> Garmin Connect app → <i>Settings → Connected Apps → Strava</i> → sign in and enable the <b>Courses</b> permission.</li>
    <li><b>Save each of your legs on Strava.</b> Open the leg's Strava route from its card on the <a href="{legs_href}">Legs page</a> and tap the ☆ <b>star / save</b> icon so it lights up.</li>
    <li><b>Sync your watch</b> with the Garmin Connect app. Starred Strava routes are pushed to the watch automatically and land in <i>Courses</i>.</li>
    <li><b>Race day:</b> start a Run activity → hold <b>UP/MENU</b> → <i>Navigation → Courses</i> → pick your leg → <i>Do Course</i>. (Menu names vary slightly by model.)</li>
  </ol>
  <p class="tiny">Apple Watch has no native course-following — the WorkOutDoors app can import the same routes (export GPX from Strava), or use the map links on each leg card and run from the phone.</p>
</div>'''

def index_table(legs_href="index.html"):
    rows = ""
    for l in LEGS:
        n = l["n"]
        team = f' → {l["team"]}' if l["team"] else ""
        surf = " / ".join(f"{k[0].upper()}{v}%" for v, k in zip(l["surface"], ("pav", "grav", "trail")) if v > 0)
        rows += (f'<tr><td class="c">{n}</td><td><a href="{legs_href}#leg-{n}">{esc(NAMES[n])}</a></td>'
                 f'<td class="r">{fmt_mi(l["dist"])}</td><td class="r">+{l["gain"]:,}</td>'
                 f'<td class="r">{ftpmi(l):.0f}</td><td>{surf}</td>'
                 f'<td><span class="dotc" style="background:{DIFF[l["rating"]]}"></span>{l["rating"]}{team}</td>'
                 f'<td class="r">{fmt_mi(l["start_mi"])}</td></tr>')
        if n in EXCHANGES:
            rows += f'<tr class="exrow"><td colspan="8">🚩 {esc(EXCHANGES[n]["name"])} — mile {fmt_mi(l["end_mi"])}</td></tr>'
    return f'''<div class="tscroll"><table class="tbl small">
<thead><tr><th>#</th><th>Leg</th><th class="r">Mi</th><th class="r">Gain</th><th class="r">ft/mi</th><th>Surface</th><th>Rating (official → team)</th><th class="r">Starts @ mi</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''

# ---------------- shared css ----------------
def css():
    return '''
:root { color-scheme: light;
  --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10); --card:#ffffff; --accent:#2a78d6 }
@media (prefers-color-scheme: dark) {
  :root:not([data-print]) { color-scheme: dark;
    --surface:#1a1a19; --page:#0d0d0d; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.12); --card:#232322; --accent:#3987e5 } }
* { box-sizing:border-box }
html { scroll-behavior:smooth }
body { margin:0; background:var(--page); color:var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", "Liberation Sans", "DejaVu Sans", sans-serif;
  font-size:14px; line-height:1.45; -webkit-print-color-adjust:exact; print-color-adjust:exact }
.wrap { max-width:860px; margin:0 auto; padding:0 16px 48px }
a { color:var(--accent) }
h1,h2,h3 { line-height:1.15; margin:0 }
nav.top { position:sticky; top:0; z-index:9; background:var(--page); border-bottom:1px solid var(--grid); padding:8px 12px 0 }
.navrow { display:flex; gap:4px; overflow-x:auto; font-size:12.5px; white-space:nowrap; padding-bottom:8px; align-items:center }
.navrow a, .navrow button { text-decoration:none; color:var(--ink2); padding:5px 10px; border-radius:99px;
  border:1px solid var(--grid); background:none; font:inherit; font-size:12.5px; cursor:pointer }
.navrow a:hover, .navrow button:hover { background:var(--card) }
.navrow .brand { font-weight:800; color:var(--ink); border:none; padding-left:0 }
.navrow .active { background:var(--ink); color:var(--page); border-color:var(--ink) }
.navrow .rowlabel { font-size:10px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); flex:none }
.navtabs a { font-weight:700 }
.jumprow { display:flex; gap:3px; overflow-x:auto; padding-bottom:8px }
.jumprow a { flex:none; position:relative; width:30px; height:34px; display:flex; align-items:center; justify-content:center;
  padding-bottom:6px; font-size:11.5px; font-weight:700; text-decoration:none; color:var(--ink2);
  border:1px solid var(--grid); border-radius:8px }
.jumprow a .d { position:absolute; bottom:3px; left:50%; transform:translateX(-50%); width:5px; height:5px; border-radius:50% }
.jumprow a:hover { background:var(--card) }
.hero { padding:30px 0 8px }
.hero .kicker { font-weight:800; letter-spacing:.14em; color:var(--accent); font-size:13px }
.hero h1 { font-size:32px; font-weight:800; letter-spacing:-.01em; margin:2px 0 4px }
.hero .sub { color:var(--ink2); font-size:15px }
.statgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:8px; margin:18px 0 }
.tile { background:var(--card); border:1px solid var(--ring); border-radius:10px; padding:10px 12px }
.tile b { display:block; font-size:22px }
.tile span { color:var(--muted); font-size:11.5px; text-transform:uppercase; letter-spacing:.06em }
.panel { background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:14px 16px; margin:14px 0 }
.panel h2 { font-size:16px; margin-bottom:8px }
.legendrow { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:8px; font-size:12px; color:var(--ink2) }
.pill { display:inline-flex; align-items:center; gap:5px; border:1.5px solid var(--pc);
  background:color-mix(in srgb, var(--pc) 13%, transparent); color:var(--ink);
  border-radius:99px; padding:2px 9px 2px 7px; font-size:11.5px; white-space:nowrap }
.pill .dot { width:8px; height:8px; border-radius:50%; background:var(--pc); flex:none }
.pill .pl { color:var(--ink2); font-size:10px; text-transform:uppercase; letter-spacing:.05em }
.chip { display:inline-block; border-radius:6px; padding:2px 7px; font-size:11px; margin:2px 3px 0 0;
  border:1px solid var(--ring); background:var(--surface); color:var(--ink2) }
.chip.climb { border-color:color-mix(in srgb, var(--accent) 45%, transparent); color:var(--ink) }
.dotc { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; outline:1px solid rgba(0,0,0,.2) }
.secbanner { margin:34px 0 12px; padding:14px 16px; border-radius:12px; background:var(--ink); color:var(--page) }
.secbanner .secno { font-size:11px; letter-spacing:.18em; opacity:.7; font-weight:700 }
.secbanner h2 { font-size:19px; margin:2px 0 }
.secbanner .sectotals { font-size:13px; opacity:.85 }
.secex { display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; justify-content:space-between;
  margin-top:11px; padding-top:11px; border-top:1px solid color-mix(in srgb, currentColor 25%, transparent) }
.secex b { display:block; font-size:12.5px; letter-spacing:.05em }
.secex > div > span { font-size:11.5px; opacity:.75 }
.secex .mapwrap { display:flex; gap:7px; flex-wrap:wrap; align-items:center }
.secex .coords { color:inherit; opacity:.7 }
.bannerbtn { display:inline-block; text-decoration:none; font-weight:700; font-size:12px; color:inherit;
  border:1.5px solid color-mix(in srgb, currentColor 45%, transparent); border-radius:8px; padding:4px 11px }
.leg { background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:13px 15px; margin:10px 0 }
.leg.hidden, .hiddenx { display:none !important }
.leghead { display:flex; gap:12px; align-items:flex-start }
.legnum { font-size:26px; font-weight:800; color:var(--accent); line-height:1; padding-top:2px }
.titleblock { flex:1; min-width:0 }
.titleblock h3 { font-size:17px }
.titleblock .meta { font-size:11.5px; color:var(--muted); margin-top:2px }
.badges { display:flex; flex-direction:column; gap:4px; align-items:flex-end }
.statrow { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; margin:10px 0 6px }
.stat { font-size:13px; color:var(--ink2) }
.stat b { font-size:17px; color:var(--ink) }
.meterwrap { display:flex; align-items:center; gap:7px }
.meter { width:70px; height:7px; border-radius:99px; background:var(--grid); overflow:hidden }
.meter .fill { height:100%; background:var(--accent); border-radius:99px }
.meter.zoned { background:linear-gradient(to right,
  var(--grid) 0 24.5%, var(--axis) 24.5% 25.5%, var(--grid) 25.5% 49.5%, var(--axis) 49.5% 50.5%,
  var(--grid) 50.5% 74.5%, var(--axis) 74.5% 75.5%, var(--grid) 75.5% 100%) }
.mval { font-size:11.5px; color:var(--ink2) }
.profile { margin:8px 0 2px; border:1px solid var(--grid); border-radius:8px; padding:6px 8px 4px; background:var(--surface) }
.proflabel { font-size:10.5px; color:var(--muted); margin-top:2px }
.surfrow { margin:7px 0 }
.surfbar { display:flex; gap:2px; height:15px; border-radius:5px; overflow:hidden }
.seg { color:#fff; font-size:9.5px; text-transform:uppercase; letter-spacing:.06em;
  display:flex; align-items:center; justify-content:center; min-width:8px }
.surftext { font-size:11px; color:var(--muted); margin-top:3px }
.beta { margin:8px 0 4px; font-size:13.5px }
.beta .src, .srcbadge { display:inline-block; font-size:9.5px; font-weight:800; letter-spacing:.08em; text-transform:uppercase;
  color:var(--accent); border:1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  border-radius:4px; padding:1px 5px; margin-right:7px; vertical-align:1px }
.tiny { font-size:11px; color:var(--muted) }
.nowrap { white-space:nowrap }
.steps { margin:8px 0 4px 20px; font-size:13.5px }
.steps li { margin:7px 0 }
.footnote { font-size:11.5px; color:var(--ink2); background:var(--surface); border:1px dashed var(--axis);
  border-radius:7px; padding:5px 9px; margin-top:6px }
.legfoot { margin-top:9px; display:flex; flex-wrap:wrap; gap:7px; align-items:center }
.stravabtn { display:inline-block; text-decoration:none; font-weight:700; font-size:12.5px;
  border:1.5px solid var(--accent); border-radius:8px; padding:5px 12px }
.mapbtn { border-color:var(--grid); color:var(--ink2) }
.coords { font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums }
.qrbox { display:flex; align-items:center; gap:8px }
.qrbox img { width:62px; height:62px; image-rendering:pixelated }
.qrbox span { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em }
.qrbox.big img { width:88px; height:88px }
.qrbox.big { flex-direction:column; text-align:center; gap:4px }
.exchange { display:flex; gap:10px; align-items:center; border:1.5px dashed var(--ink2); border-radius:12px;
  padding:10px 14px; margin:12px 0; background:var(--surface) }
.exchange .flag { font-size:20px }
.exchange b { display:block; font-size:13.5px; letter-spacing:.04em }
.exchange span { font-size:12px; color:var(--ink2) }
.exchange.finish { border-style:solid; border-color:var(--ink) }
.exchange .mapwrap { display:flex; gap:7px; flex-wrap:wrap; margin-top:8px }
.tscroll { overflow-x:auto; -webkit-overflow-scrolling:touch }
.tscroll .tbl { min-width:560px }
.tbl { width:100%; border-collapse:collapse; font-size:12.5px }
.tbl th { text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
  border-bottom:1.5px solid var(--axis); padding:5px 7px }
.tbl td { border-bottom:1px solid var(--grid); padding:5px 7px; vertical-align:top }
.tbl .r { text-align:right; font-variant-numeric:tabular-nums }
.tbl .c { text-align:center }
.tbl.small { font-size:11px }
.tbl.small td, .tbl.small th { padding:3.5px 5px }
.exrow td { background:var(--surface); font-weight:700; font-size:10.5px; letter-spacing:.05em }
.blankcell { min-width:110px; border-bottom:1px dotted var(--muted) !important }
.linkrow { display:flex; flex-wrap:wrap; gap:16px; margin-top:10px }
details.legend { margin:12px 0 }
details.legend summary { cursor:pointer; font-weight:700; font-size:13px; color:var(--ink2) }
footer.colophon { margin-top:36px; font-size:11.5px; color:var(--muted); border-top:1px solid var(--grid); padding-top:12px }
.print-only { display:none }
@page { size:letter; margin:0.45in }
@media print {
  :root { color-scheme:light;
    --surface:#fcfcfb; --page:#ffffff; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.14); --card:#ffffff; --accent:#2a78d6 }
  body { font-size:11.5px; background:#fff }
  nav.top, .web-only { display:none !important }
  .print-only { display:flex }
  .wrap { max-width:none; padding:0 }
  .hero { padding-top:4px }
  .hero h1 { font-size:30px }
  .leg, .panel, .exchange { break-inside:avoid }
  .secbanner { break-before:page; margin-top:0; background:#0b0b0b !important; color:#fff !important }
  .cover-end { break-after:page }
  .leg { padding:10px 12px; margin:8px 0 }
  .beta { font-size:11.5px }
  a { text-decoration:none; color:inherit }
  .idx-break { break-before:page }
}
'''

# ---------------- page shells ----------------
# RUNNERS: set names once assignments are decided; the filter buttons + card labels pick them up.
RUNNERS_JS = '''
const RUNNERS = {1:"", 2:"", 3:"", 4:"", 5:"", 6:""};  // e.g. {1:"Luke", 2:"Jake", ...}
document.querySelectorAll('.runner-name').forEach(el => {
  const nm = RUNNERS[el.dataset.slot];
  if (nm) el.textContent = nm;
});
function filterSlot(s, btn) {
  document.querySelectorAll('.leg').forEach(el => {
    el.classList.toggle('hidden', s !== 0 && Number(el.dataset.slot) !== s);
  });
  document.querySelectorAll('.jumprow a').forEach(el => {
    el.classList.toggle('hiddenx', s !== 0 && Number(el.dataset.slot) !== s);
  });
  document.querySelectorAll('.filterbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  window.scrollTo({top: 0});
}
document.querySelectorAll('.filterbtn').forEach(b => {
  const s = Number(b.dataset.slot);
  const nm = RUNNERS[s];
  if (nm) b.textContent = nm;
  b.addEventListener('click', () => filterSlot(s, b));
});
'''

def diff_legend():
    return "".join(f'<span class="pill" style="--pc:{c}"><span class="dot"></span><b>{k}</b></span>' for k, c in DIFF.items())

def how_to_read(compact=False):
    body = f'''
  <p style="margin:.3em 0"><span class="srcbadge">2025 team beta</span>
  Beta boxes, difficulty ratings, surface breakdowns and commentary are from <b>our runner who did this race in 2025</b>.
  Distances, gain, mile markers and climb grades are from the team's 2025 Strava-scraped sheet.</p>
  <p style="margin:.3em 0">🌐 <b>From online:</b> official leg names, Strava routes, exchange stations, dates and night rules
  come from the official race site and 2025 race guide.</p>
  <p style="margin:.3em 0" class="tiny">⚠ Distances/gain on the cards are our 2025 numbers. The elevation profile charts come straight
  from the current 2026 Strava routes (pulled July 2026). Four legs changed for 2026 — <b>1, 8, 30 and 31</b> — those cards carry a
  🔄 route-update flag. When in doubt, the Strava link wins.</p>
  <div class="legendrow">Difficulty: {diff_legend()} · Surface: <span class="dotc" style="background:{SURF["pavement"]}"></span>pavement
  <span class="dotc" style="background:{SURF["gravel"]}"></span>gravel <span class="dotc" style="background:{SURF["trail"]}"></span>trail</div>'''
    if compact:
        return f'<details class="legend"><summary>How to read this guide (sources + legend)</summary><div class="panel" style="margin-top:8px">{body}</div></details>'
    return f'<div class="panel"><h2>How to read this guide</h2>{body}</div>'

def sec_overview_rows(legs_href="index.html"):
    out = ""
    for i, sec in enumerate(SECTIONS):
        a, b = sec["legs"]
        legs = [l for l in LEGS if a <= l["n"] <= b]
        mi = sum(l["dist"] for l in legs); gain = sum(l["gain"] for l in legs)
        out += (f'<tr><td class="c"><a href="{legs_href}#sec{i+1}">{i+1}</a></td><td>{a}–{b}</td>'
                f'<td>{esc(sec["dest"])}</td><td class="r">{mi:.1f}</td>'
                f'<td class="r">+{gain:,}</td><td class="r">{fmt_mi(legs[-1]["end_mi"])}</td></tr>')
    return out

def hero(sub=True):
    tiles = f'''
  <div class="statgrid">
    <div class="tile"><b>{TOTAL_MI:,.1f}</b><span>miles</span></div>
    <div class="tile"><b>36</b><span>legs</span></div>
    <div class="tile"><b>{TOTAL_GAIN:,}</b><span>ft of climbing</span></div>
    <div class="tile"><b>6</b><span>runners · 6 legs each</span></div>
    <div class="tile"><b>5</b><span>major exchanges</span></div>
  </div>''' if sub else ""
    return f'''
<header class="hero">
  <div class="kicker">TEAM RUN1 · RACE GUIDE</div>
  <h1>Outback in the Ozarks · 205-Mile Relay</h1>
  <div class="sub">{esc(RACE["dates"])} · {esc(RACE["start"])} → {esc(RACE["finish"])}</div>
  {tiles}
</header>'''

def rules_panel(with_qr):
    L = RACE["links"]
    qrs = "".join(
        f'<div class="qrbox big"><img src="{qr_datauri(u)}" alt="QR {t}"><span>{t}</span></div>'
        for t, u in [("Official course map", L["course_map"]), ("2025 race guide PDF", L["guide_pdf"]),
                     ("Exchange zones (Google Maps)", L["exchanges_map"])]) if with_qr else ""
    return f'''
<div class="panel" id="rules">
  <h2>Night rules &amp; official links <span class="tiny">(🌐 from the official 2025 race guide)</span></h2>
  <p style="margin:.3em 0">🦺 <b>Nighttime hours = 1 hour before sunset through 1 hour after dawn:</b> reflective vest for anyone
  out of the van, headlamp + rear flashing tail light for runners. In-ear headphones are banned (open-ear audio OK).
  Course is marked with black arrows on bright-yellow signs at each turn, plus yellow flags and reflective tags.</p>
  <p style="margin:.3em 0" class="web-only">
    <a href="{L["course_map"]}" target="_blank" rel="noopener">Official course map + Strava routes ↗</a> ·
    <a href="{L["guide_pdf"]}" target="_blank" rel="noopener">2025 race guide PDF ↗</a> ·
    <a href="{L["exchanges_map"]}" target="_blank" rel="noopener">Exchange zones map ↗</a> ·
    <a href="{L["full_route_map"]}" target="_blank" rel="noopener">Full route map ↗</a>
  </p>
  <div class="linkrow print-only">{qrs}</div>
</div>'''

COLOPHON = '''<footer class="colophon">Built for Team Run1 · beta from our 2025 runner · stats from the team Strava sheet ·
names, routes &amp; rules from outbackintheozarks.com · not an official race document. Go get it. 🤙</footer>'''

def page(title, nav_html, body, script=""):
    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">%F0%9F%8F%83%F0%9F%8F%BB</text></svg>'>
<title>{esc(title)}</title>
<style>{css()}</style></head>
<body>
{nav_html}
<div class="wrap" id="top">
{body}
{COLOPHON}
</div>
{f"<script>{script}</script>" if script else ""}
</body></html>'''

def nav_tabs(active):
    legs_cls = ' class="active"' if active == "legs" else ""
    over_cls = ' class="active"' if active == "overview" else ""
    return (f'<div class="navrow navtabs"><a class="brand" href="index.html">RUN1 · OTO 205</a>'
            f'<a href="index.html"{legs_cls}>Legs</a><a href="overview.html"{over_cls}>Overview</a></div>')

def build_index():
    jump = ""
    for l in LEGS:
        slot = (l["n"] - 1) % 6 + 1
        jump += (f'<a href="#leg-{l["n"]}" data-slot="{slot}" title="{esc(NAMES[l["n"]])}">'
                 f'{l["n"]}<span class="d" style="background:{DIFF[l["rating"]]}"></span></a>')
    filters = '<button class="filterbtn active" data-slot="0">All runners</button>' + "".join(
        f'<button class="filterbtn" data-slot="{s}">Slot {s}</button>' for s in range(1, 7))
    nav = f'''<nav class="top">
  {nav_tabs("legs")}
  <div class="navrow"><span class="rowlabel">Runner</span>{filters}</div>
  <div class="jumprow"><span class="rowlabel" style="align-self:center;margin-right:4px">Leg</span>{jump}</div>
</nav>'''
    sections_html = "".join(section_block(i, s) for i, s in enumerate(SECTIONS))
    body = f'''
{hero(sub=False)}
{how_to_read(compact=True)}
{sections_html}'''
    return page("RUN1 · OTO 205 — Legs", nav, body, RUNNERS_JS)

def build_overview():
    nav = f'''<nav class="top">
  {nav_tabs("overview")}
  <div class="navrow"><span class="rowlabel">Jump to</span><a href="#course">Course chart</a><a href="#sections">Sections</a><a href="#plan">Planner</a><a href="#index">All legs</a><a href="#watch">Watch</a><a href="#rules">Rules</a></div>
</nav>'''
    body = f'''
{hero()}
<div class="panel" id="course">
  <h2>The whole course at a glance — steepness of every leg</h2>
  {skyline_svg()}
  <div class="legendrow">Bar height = climb per mile (ft/mi) · color = official difficulty: {diff_legend()} · tap a bar to open that leg</div>
</div>
<div class="panel" id="sections">
  <h2>Race in six sections</h2>
  <div class="tscroll"><table class="tbl">
    <thead><tr><th>Sec</th><th>Legs</th><th>Runs to</th><th class="r">Miles</th><th class="r">Climb</th><th class="r">Race mi at exchange</th></tr></thead>
    <tbody>{sec_overview_rows()}</tbody></table></div>
</div>
<div class="panel" id="plan">
  <h2>Runner planner — who takes which rotation slot?</h2>
  <p class="tiny" style="margin:.2em 0 .6em">With 6 runners, slot <i>N</i> runs legs <i>N, N+6, N+12, N+18, N+24, N+30</i>.</p>
  {planner_table()}
</div>
<div class="panel" id="index">
  <h2>Every leg on one page</h2>
  {index_table()}
</div>
{watch_panel()}
{rules_panel(with_qr=False)}'''
    return page("RUN1 · OTO 205 — Overview", nav, body, RUNNERS_JS)

def build_print():
    sections_html = "".join(section_block(i, s) for i, s in enumerate(SECTIONS))
    body = f'''
{hero()}
<div class="panel">
  <h2>The whole course at a glance — steepness of every leg</h2>
  {skyline_svg()}
  <div class="legendrow">Bar height = climb per mile (ft/mi) · color = official difficulty: {diff_legend()}</div>
</div>
<div class="panel">
  <h2>Race in six sections</h2>
  <div class="tscroll"><table class="tbl">
    <thead><tr><th>Sec</th><th>Legs</th><th>Runs to</th><th class="r">Miles</th><th class="r">Climb</th><th class="r">Race mi at exchange</th></tr></thead>
    <tbody>{sec_overview_rows("#")}</tbody></table></div>
</div>
{how_to_read()}
<div class="panel" id="plan">
  <h2>Runner planner — who takes which rotation slot?</h2>
  {planner_table()}
</div>
<div class="cover-end"></div>
{sections_html}
<div class="panel idx-break" id="index">
  <h2>Every leg on one page</h2>
  {index_table("#")}
</div>
{watch_panel("#")}
{rules_panel(with_qr=True)}'''
    return page("RUN1 · OTO 205 — Race Guide (print)", "", body)

if __name__ == "__main__":
    os.makedirs("out", exist_ok=True)
    for name, doc in [("index.html", build_index()), ("overview.html", build_overview()), ("print.html", build_print())]:
        with open(f"out/{name}", "w") as f:
            f.write(doc)
        print(f"wrote out/{name} ({len(doc)/1024:.0f} KB)")
    print("elev profiles:", len(ELEV), "legs")
