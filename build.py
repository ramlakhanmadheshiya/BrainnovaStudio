#!/usr/bin/env python3
"""Builds the Brainnova Studio site into dist/ from games.json and the games' builds.

    python3 build.py                  build dist/ (uses .bundles/ if present)
    python3 build.py --fetch          first download every game's latest build into .bundles/
    python3 build.py --serve          build, then preview on http://localhost:8800/BrainnovaStudio/games/

Everything is served under theramlakhan.com/BrainnovaStudio/:

    games/                    every game, same buttons in the same order
    games/<slug>/             the game's page (+ help/, privacy/, <slug>.apk)
    test/<slug>/              "Play early": join closed testing in three steps
    play/<slug>/              play in the browser
    engine/<godot>/           the shared Godot web engine (one download for every game)
    games.json                where every game stands

A game's "status" in games.json decides every button:

    development     Coming soon. No browser play, no testing page link.
    closed-testing  Play early (testing page) + Play in browser.
    published       Get it on Google Play + Play in browser.

Each game's CI pushes its latest build (APK, web pack, help and privacy pages) to
this repo's branch build/<slug> with tools/ship.sh; the Pages workflow fetches
those branches (--fetch) and builds the site from them.
"""

import datetime
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
BUNDLES = ROOT / ".bundles"
CACHE = ROOT / ".cache"
REPO = "ramlakhanmadheshiya/BrainnovaStudio"

STATUSES = ("development", "closed-testing", "published")
ORDER = {"published": 0, "closed-testing": 1, "development": 2}

e = html.escape


def load():
    data = json.loads((ROOT / "games.json").read_text())
    seen = set()
    for g in data["games"]:
        assert g["status"] in STATUSES, f"{g['slug']}: unknown status {g['status']!r}"
        assert g["slug"] not in seen, f"duplicate slug {g['slug']}"
        seen.add(g["slug"])
        assert (ROOT / "media" / g["slug"] / "icon.svg").exists(), f"{g['slug']}: media/{g['slug']}/icon.svg missing"
        d = g["dates"]
        # The date a card shows: the latest milestone it has reached.
        g["_date"] = d.get("published") or d.get("testing") or d["started"]
    data["games"].sort(key=lambda g: (ORDER[g["status"]], -datetime.date.fromisoformat(g["_date"]).toordinal()))
    return data


def nice_date(s):
    if not s:
        return ""
    d = datetime.date.fromisoformat(s)
    return f"{d.day} {d.strftime('%b %Y')}"


def short_hash(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()[:10]


def links(studio, g):
    """Every URL a game can point to, in one place."""
    base = studio["base"]
    pkg = g["package"]
    return {
        "store": f"https://play.google.com/store/apps/details?id={pkg}",
        "optin": f"https://play.google.com/apps/testing/{pkg}",
        "group": f"https://groups.google.com/g/{studio['testers_group']}",
        "page": f"{base}/games/{g['slug']}/",
        "help": f"{base}/games/{g['slug']}/help/",
        "privacy": f"{base}/games/{g['slug']}/privacy/",
        "test": f"{base}/test/{g['slug']}/",
        "play": f"{base}/play/{g['slug']}/",
        "icon": f"{base}/media/{g['slug']}/icon.svg",
    }


# --------------------------------------------------------------------------- shared bits

ICONS = {
    "gplay": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.6 2.3 13.4 12l-9.8 9.7a1.6 1.6 0 0 1-.6-1.3V3.6c0-.5.2-1 .6-1.3Z" fill="#00d3ff"/><path d="m16.8 8.6-3.4 3.4-9.8-9.7c.4-.3 1-.4 1.6-.1l11.6 6.4Z" fill="#00f076"/><path d="m16.8 15.4-11.6 6.4c-.6.3-1.2.2-1.6-.1l9.8-9.7 3.4 3.4Z" fill="#ff3a44"/><path d="M20.5 10.6c1 .6 1 2.2 0 2.8l-3.7 2-3.4-3.4 3.4-3.4 3.7 2Z" fill="#ffd500"/></svg>',
    "flask": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6M10 3v6.2L4.6 18.4A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.4-2.6L14 9.2V3"/><path d="M7.5 15h9"/></svg>',
    "browser": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18"/><path d="m10.5 12.5 4 2.5-4 2.5z" fill="currentColor"/></svg>',
    "hammer": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 12-8.4 8.4a2 2 0 0 1-2.8-2.8L12.2 9"/><path d="m17.6 14.6 4-4-6.2-6.2a4 4 0 0 0-5.6 0l-.8.8 7.8 7.8 2.4-2.4"/></svg>',
    "info": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "back": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>',
    "check": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
    "share": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3M7.5 7.5 12 3l4.5 4.5"/><path d="M5 12v6.5A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V12"/></svg>',
    "download": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7.5 10.5 12 15l4.5-4.5"/><path d="M5 19h14"/></svg>',
    "sun": '<svg class="sun" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/></svg>',
    "moon": '<svg class="moon" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M20.5 14.6A8.5 8.5 0 0 1 9.4 3.5a.6.6 0 0 0-.8-.7A9.5 9.5 0 1 0 21.2 15.4a.6.6 0 0 0-.7-.8Z"/></svg>',
}

LOGO = """<svg class="logo" viewBox="0 0 32 32" aria-hidden="true">
  <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8f6bff"/><stop offset="1" stop-color="#ff6b5b"/></linearGradient></defs>
  <circle cx="16" cy="16" r="15" fill="url(#lg)"/>
  <g fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" opacity=".95">
    <path d="M9.5 12.5 16 9l6.5 3.5M9.5 12.5 12 20l4 3 4-3 2.5-7.5M12 20l4-6.5 4 6.5M16 9v4.5"/>
  </g>
  <g fill="#fff"><circle cx="16" cy="9" r="1.9"/><circle cx="9.5" cy="12.5" r="1.6"/><circle cx="22.5" cy="12.5" r="1.6"/><circle cx="12" cy="20" r="1.6"/><circle cx="20" cy="20" r="1.6"/><circle cx="16" cy="13.5" r="2.3"/><circle cx="16" cy="23" r="1.4"/></g>
</svg>"""

# Runs before first paint, so nothing flashes:
# - the theme the visitor picked (else the system's, via CSS);
# - which device this is:
#   android = can install from Google Play (phones, tablets, TV, Chromebooks);
#   apple   = iPhone, iPad, Mac: full game in the browser, every ad type;
#   other   = Windows, Linux, ...: the first levels in the browser.
#   ?as=android|apple|other previews another device (kept for this tab).
PLATFORM_JS = """<script>
(function(){var h=document.documentElement,q=new URLSearchParams(location.search).get('as'),s,t;
try{t=localStorage.getItem('bn-theme');if(q)sessionStorage.setItem('bn-as',q);s=sessionStorage.getItem('bn-as')}catch(_){s=q}
if(t==='light'||t==='dark')h.dataset.theme=t;
var u=navigator.userAgent,p='other',d=navigator.userAgentData;
if(/Android|CrOS/i.test(u)||(d&&/Android|Chrome OS/i.test(d.platform||''))||(/Linux/i.test(u)&&navigator.maxTouchPoints>1))p='android';
else if(/iPhone|iPad|iPod|Macintosh/i.test(u))p='apple';
if(s==='android'||s==='apple'||s==='other')p=s;
h.dataset.platform=p;h.classList.add('js');window.BN_PLATFORM=p})();
</script>"""


def head(studio, title, desc, path, extra="", robots=""):
    base = studio["base"]
    url = studio["origin"] + path
    robots_tag = f'\n<meta name="robots" content="{robots}">' if robots else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">{robots_tag}
<meta name="theme-color" content="#fbfbfd" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(studio['name'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{base}/assets/logo.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/studio.css">
{PLATFORM_JS}
{extra}
</head>"""


def nav(studio, active):
    base = studio["base"]

    def item(key, label, href):
        cur = ' aria-current="page"' if key == active else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    return f"""<a class="skip" href="#content">Skip to content</a>
<header class="nav" data-nav>
  <div class="wrap nav-inner">
    <a class="brand" href="{base}/games/">{LOGO}<span>Brainnova<b>Studio</b></span></a>
    <nav class="nav-links" aria-label="Site">
      {item('games', 'Games', f'{base}/games/')}
      {item('test', 'Play early', f'{base}/test/')}
      <a href="/">Ramlakhan</a>
      <button class="theme" type="button" data-theme-toggle aria-label="Switch theme">{ICONS['sun']}{ICONS['moon']}</button>
    </nav>
  </div>
</header>"""


def footer(studio):
    base = studio["base"]
    year = datetime.date.today().year
    return f"""<footer class="foot">
  <div class="wrap foot-inner">
    <div class="foot-brand">{LOGO}<div><strong>{e(studio['name'])}</strong><span>Small games with a spark, made by {e(studio['owner'])}.</span></div></div>
    <nav class="foot-links" aria-label="Footer">
      <a href="{base}/games/">Games</a>
      <a href="{base}/test/">Play early</a>
      <a href="mailto:{e(studio['support'])}">{e(studio['support'])}</a>
    </nav>
    <p class="foot-copy">© {year} {e(studio['owner'])}. Made with Godot. Google Play is a trademark of Google LLC.</p>
  </div>
</footer>"""


def page(studio, title, desc, path, active, body, scripts="", extra_head="", robots=""):
    base = studio["base"]
    return f"""{head(studio, title, desc, path, extra_head, robots)}
<body>
{nav(studio, active)}
<main id="content">
{body}
</main>
{footer(studio)}
<script src="{base}/assets/studio.js" defer></script>
{scripts}
</body>
</html>
"""


# --------------------------------------------------------------------------- the buttons

STATUS_LABEL = {"published": "On Google Play", "closed-testing": "Closed testing", "development": "In development"}


def slot_store(g, L):
    s = g["status"]
    if s == "published":
        return f'<a class="btn btn-primary" href="{L["store"]}" rel="noopener">{ICONS["gplay"]}<span>Google Play</span></a>'
    if s == "closed-testing":
        return f'<a class="btn btn-primary" href="{L["test"]}">{ICONS["flask"]}<span>Play early</span></a>'
    return f'<span class="btn btn-primary is-off" aria-disabled="true">{ICONS["hammer"]}<span>Coming soon</span></span>'


def slot_web(g, L, free):
    if g["status"] == "development":
        return f'<span class="btn btn-glass is-off web-only" aria-disabled="true">{ICONS["browser"]}<span>Play in browser<small>Soon</small></span></span>'
    return (f'<a class="btn btn-glass web-only" href="{L["play"]}">{ICONS["browser"]}'
            f'<span>Play in browser<small class="only-apple">Full game</small><small class="only-other">First {free} levels</small></span></a>')


def actions(studio, g, free):
    """The same three slots, in the same order, on every card:
       1. Google Play / Play early / Coming soon
       2. Play in browser (hidden on Android, where Google Play is the way)
       3. Details"""
    L = links(studio, g)
    more = f'<button class="btn btn-ghost" type="button" data-details="{e(g["slug"])}">{ICONS["info"]}<span>Details</span></button>'
    return f'<div class="actions">{slot_store(g, L)}{slot_web(g, L, free)}{more}</div>'


def date_line(g):
    d = g["dates"]
    if g["status"] == "published" and d.get("published"):
        return f'Released <time datetime="{d["published"]}">{nice_date(d["published"])}</time>'
    if g["status"] == "closed-testing" and d.get("testing"):
        return f'Testing since <time datetime="{d["testing"]}">{nice_date(d["testing"])}</time>'
    return f'Started <time datetime="{d["started"]}">{nice_date(d["started"])}</time>'


def style_vars(g, i=None):
    c = g["colors"]
    extra = f";--i:{i}" if i is not None else ""
    return f"--g-bg:{c['bg']};--g-accent:{c['accent']};--g-glow:{c['glow']}{extra}"


def card(studio, g, i, free):
    L = links(studio, g)
    s = g["status"]
    facts = "".join(f"<li>{e(f)}</li>" for f in g.get("facts", []))
    title = e(g["name"]) if s == "development" else f'<a href="{L["page"]}">{e(g["name"])}</a>'
    return f"""<article class="game reveal" data-status="{s}" data-slug="{e(g['slug'])}" style="{style_vars(g, i)}">
  <div class="game-media" data-tilt>
    <div class="aura" aria-hidden="true"></div>
    {'<div class="blueprint" aria-hidden="true"><span class="scan"></span></div>' if s == 'development' else ''}
    <img class="game-icon" src="{L['icon']}" alt="" width="132" height="132" loading="lazy" decoding="async">
    <span class="badge badge-{s}"><i></i>{STATUS_LABEL[s]}</span>
  </div>
  <div class="game-body">
    <p class="game-date">{date_line(g)}</p>
    <h3>{title}</h3>
    <p class="game-tagline">{e(g['tagline'])}</p>
    <ul class="facts">{facts}</ul>
    {actions(studio, g, free)}
  </div>
</article>"""


# --------------------------------------------------------------------------- pages

def games_page(data):
    studio = data["studio"]
    games = data["games"]
    free = data["web"]["free_levels"]
    count = {s: sum(1 for g in games if g["status"] == s) for s in STATUSES}
    chips = [("all", "All", len(games)), ("published", "On Google Play", count["published"]),
             ("closed-testing", "Play early", count["closed-testing"]), ("development", "In the works", count["development"])]
    chip_html = "".join(
        f'<button type="button" role="tab" class="chip" data-filter="{k}" aria-selected="{"true" if k == "all" else "false"}"'
        f'{" hidden" if n == 0 and k != "all" else ""}>{label}<span>{n}</span></button>'
        for k, label, n in chips)
    stats = []
    for key, label in (("published", "on Google Play"), ("closed-testing", "in testing"), ("development", "in the works")):
        if count[key]:
            stats.append(f'<li><b>{count[key]}</b> {label}</li>')
    cards = "\n".join(card(studio, g, i, free) for i, g in enumerate(games))
    testing = [g for g in games if g["status"] == "closed-testing"]
    early = ""
    if testing:
        first = testing[0]
        early = f"""<section class="early reveal" aria-labelledby="early-title">
  <div class="wrap early-inner">
    <div class="early-copy">
      <p class="eyebrow">Play early</p>
      <h2 id="early-title">Get the games before anyone else.</h2>
      <p>Before a game reaches Google Play it spends two weeks with a small group of testers. Join them, play {e(first['name'])} today, and help it launch.</p>
      <a class="btn btn-primary btn-lg" href="{studio['base']}/test/">{ICONS['flask']}<span>Become a tester</span></a>
    </div>
    <ol class="early-steps" aria-label="How it works">
      <li><b>1</b><span>Join the testers group</span></li>
      <li><b>2</b><span>Opt in on Google Play</span></li>
      <li><b>3</b><span>Install and play</span></li>
    </ol>
  </div>
</section>"""
    body = f"""<section class="hero" aria-labelledby="hero-title">
  <canvas class="field" data-field aria-hidden="true"></canvas>
  <div class="wrap hero-inner">
    <p class="eyebrow reveal">Brainnova Studio · Games</p>
    <h1 id="hero-title" class="reveal"><span>Small games.</span> <span class="nova">Big sparks.</span></h1>
    <p class="lede reveal">Calm, clever puzzle games for Android, made by one person who loves a good “aha”. Play them in your browser, or before they launch.</p>
    <p class="device reveal" data-device aria-live="polite"></p>
    <ul class="stats reveal">{''.join(stats)}</ul>
  </div>
  <p class="hero-tip" aria-hidden="true">Tap anywhere to spark an idea</p>
</section>

<section class="catalog" aria-labelledby="games-title">
  <div class="wrap">
    <div class="catalog-head">
      <h2 id="games-title">All games</h2>
      <div class="chips" role="tablist" aria-label="Filter games">{chip_html}</div>
    </div>
    <div class="grid" data-grid>
{cards}
    </div>
    <p class="empty" data-empty hidden>Nothing here yet. Soon.</p>
  </div>
</section>
{early}
<dialog class="sheet" data-sheet aria-labelledby="sheet-title"><div class="sheet-body" data-sheet-body></div></dialog>"""
    public = [{k: g[k] for k in ("slug", "name", "tagline", "blurb", "hint", "status", "dates", "colors", "facts", "shots")}
              | {"links": links(studio, g)} for g in games]
    page_studio = dict(studio, free_levels=free)
    scripts = f'<script>window.BN_GAMES={json.dumps(public, separators=(",", ":"))};window.BN_STUDIO={json.dumps(page_studio)};</script>'
    return page(studio, "Games · Brainnova Studio", "Every game from Brainnova Studio: play on Google Play, in your browser, or early as a tester.",
                f"{studio['base']}/games/", "games", body, scripts)


def journey(g):
    step = {"development": 0, "closed-testing": 1, "published": 2}[g["status"]]
    d = g["dates"]
    stages = [("Started", d["started"], ""), ("Closed testing", d.get("testing"), "Now" if step >= 1 else "Next"),
              ("Google Play", d.get("published"), "Soon")]
    items = []
    for i, (title, date, idle) in enumerate(stages):
        cls = "done" if i < step else ("now done" if i == step else "")
        items.append(f'<li class="{cls}"><b>{title}</b><span>{e(nice_date(date)) if date else idle}</span></li>')
    return f'<ol class="journey" style="--p:{step / 2}">{"".join(items)}</ol>'


def game_page(data, g, bundle):
    studio = data["studio"]
    L = links(studio, g)
    free = data["web"]["free_levels"]
    s = g["status"]
    shots = "".join(f'<img src="{e(src)}" alt="" loading="lazy" decoding="async">' for src in g["_shots"])
    facts = "".join(f"<li>{e(f)}</li>" for f in g.get("facts", []))
    apk = ""
    if bundle.get("apk") and s != "published":
        apk = (f'<a class="gp-apk" href="{e(bundle["apk"]["url"])}" download>{ICONS["download"]}'
               f'Android APK · v{e(bundle.get("version", ""))} · {bundle["apk"]["mb"]} MB</a>')
    docs = []
    if bundle.get("help"):
        docs.append(f'<a class="btn btn-ghost" href="{L["help"]}">How to play</a>')
    if bundle.get("privacy"):
        docs.append(f'<a class="btn btn-ghost" href="{L["privacy"]}">Privacy</a>')
    docs.append(f'<a class="btn btn-ghost" href="mailto:{e(studio["support"])}?subject={e(g["name"])}">Support</a>')
    if s == "closed-testing":
        docs.insert(0, f'<a class="btn btn-ghost" href="{L["test"]}">Become a tester</a>')
    body = f"""<section class="gp-hero" style="{style_vars(g)}">
  <div class="aura" aria-hidden="true"></div>
  <div class="wrap">
    <img class="gp-icon" src="{L['icon']}" alt="" width="168" height="168">
    <div>
      <span class="badge badge-{s}"><i></i>{STATUS_LABEL[s]}</span>
      <h1>{e(g['name'])}</h1>
      <p class="lede">{e(g['tagline'])}</p>
      <p class="game-date">{date_line(g)}</p>
      <div class="actions">{slot_store(g, L)}{slot_web(g, L, free)}</div>
      {apk}
    </div>
  </div>
</section>
<section class="gp-main">
  <div class="wrap">
    <div class="gp-about reveal">
      <div><h2>About</h2><p>{e(g['blurb'])}</p><ul class="facts">{facts}</ul></div>
      <div class="gp-card">
        <div><h3>How to play</h3><p>{e(g.get('hint') or g['tagline'])}</p></div>
        <div><h3>Journey</h3>{journey(g)}</div>
      </div>
    </div>
    {f'<div class="reveal"><h2>Look inside</h2><div class="gp-shots">{shots}</div></div>' if shots else ''}
    <div class="gp-links reveal">{''.join(docs)}</div>
  </div>
</section>"""
    robots = "noindex" if s == "development" else ""
    extra = f'<meta property="og:image" content="{studio["origin"]}{L["icon"]}">'
    return page(studio, f"{g['name']} · Brainnova Studio", f"{g['name']}: {g['tagline']} {g['blurb']}",
                L["page"], "games", body, extra_head=extra, robots=robots)


def doc_page(data, g, kind, raw):
    """A game's help or privacy page, in the studio's design. The text comes from
    the game repo's web/<kind>/index.html (its <main>)."""
    studio = data["studio"]
    L = links(studio, g)
    m = re.search(r"<main[^>]*>(.*)</main>", raw, re.S)
    inner = m.group(1) if m else raw
    inner = (inner.replace('href="/games/"', f'href="{studio["base"]}/games/"')
             .replace('href="../play/"', f'href="{L["play"]}"')
             .replace('src="../icon.svg"', f'src="{L["icon"]}"')
             .replace('href="../help/"', f'href="{L["help"]}"')
             .replace('href="../privacy/"', f'href="{L["privacy"]}"'))
    other = "privacy" if kind == "help" else "help"
    nav_links = (f'<a class="btn btn-ghost" href="{L["page"]}">{ICONS["back"]}<span>{e(g["name"])}</span></a>'
                 f'<a class="btn btn-ghost" href="{L[other]}">{"Privacy" if other == "privacy" else "How to play"}</a>')
    body = f'<div class="doc-wrap"><article class="doc"><nav class="doc-nav" aria-label="{e(g["name"])}">{nav_links}</nav>{inner}</article></div>'
    title = "Privacy" if kind == "privacy" else "How to play"
    return page(studio, f"{title} · {g['name']} · Brainnova Studio", f"{g['name']}: {title.lower()}.", L[kind], "games", body)


def test_steps(studio, g):
    L = links(studio, g)
    return f"""<ol class="steps" data-steps="{e(g['slug'])}">
  <li class="step" data-step="group">
    <span class="step-n"><b>1</b>{ICONS['check']}</span>
    <div><h3>Join the testers group</h3>
      <p>Use the Google account that's signed in to your Play Store. On a phone, Google may ask you to switch to the desktop site to show the Join button.</p>
      <a class="btn btn-primary" href="{L['group']}" target="_blank" rel="noopener" data-done>Join the group</a></div>
  </li>
  <li class="step" data-step="optin">
    <span class="step-n"><b>2</b>{ICONS['check']}</span>
    <div><h3>Opt in to {e(g['name'])}</h3>
      <p>Tap <em>Become a tester</em> on the page that opens. If it says the test isn't available, give Google a few minutes to see you joined, then try again.</p>
      <a class="btn btn-primary" href="{L['optin']}" target="_blank" rel="noopener" data-done>Opt in</a></div>
  </li>
  <li class="step" data-step="install">
    <span class="step-n"><b>3</b>{ICONS['check']}</span>
    <div><h3>Install from Google Play</h3>
      <p>Keep it installed for two weeks and play now and then. That's what lets {e(g['name'])} launch for everyone.</p>
      <a class="btn btn-primary" href="{L['store']}" target="_blank" rel="noopener" data-done>{ICONS['gplay']}<span>Install</span></a></div>
  </li>
</ol>"""


def test_game_page(data, g):
    studio = data["studio"]
    L = links(studio, g)
    path = L["test"]
    s = g["status"]
    if s == "closed-testing":
        main = f"""<div class="handoff only-desktop reveal" data-qr="{e(studio['origin'] + path)}">
  <div class="qr" data-qr-box aria-label="QR code for this page"></div>
  <div><h3>Testing happens on Android</h3><p>Scan this with your Android phone to open this page there, or follow the steps with the same Google account.</p></div>
</div>
{test_steps(studio, g)}
<div class="progress reveal" aria-live="polite"><div class="bar"><i data-progress></i></div><p data-progress-text>0 of 3 done</p></div>
<section class="invite reveal" aria-labelledby="invite-title">
  <h2 id="invite-title">Bring a friend</h2>
  <p>A game needs a dozen testers to launch. Every friend you bring counts.</p>
  <div class="invite-row"><input readonly value="{e(studio['origin'] + path)}" aria-label="Invite link" data-invite>
  <button class="btn btn-primary" type="button" data-share data-title="Play {e(g['name'])} early" data-text="{e(g['tagline'])} Play it early on Android:">{ICONS['share']}<span>Share</span></button></div>
</section>
<section class="faq reveal" aria-labelledby="faq-title">
  <h2 id="faq-title">Good to know</h2>
  <details><summary>Is it free?</summary><p>Yes. Testing is free, and your progress carries over when the game launches. Updates arrive through Google Play like any app.</p></details>
  <details><summary>iPhone or iPad?</summary><p>Testing is on Android only. On iPhone, iPad and Mac you can play the whole game in your browser instead: <a href="{L['play']}">play {e(g['name'])} in the browser</a>.</p></details>
  <details><summary>The opt-in page says the test isn't available</summary><p>Google can take a few minutes to register new group members. Wait a moment and try again with the same account.</p></details>
  <details><summary>How do I send feedback?</summary><p>Write to <a href="mailto:{e(studio['support'])}">{e(studio['support'])}</a>, or leave private feedback on the game's Google Play page.</p></details>
  <details><summary>Can I leave?</summary><p>Any time: open the opt-in link again and leave the test, or just uninstall the game.</p></details>
</section>"""
        lede = f"{e(g['tagline'])} It's in closed testing on Google Play. Three steps and it's on your phone."
        h1 = f"Play {e(g['name'])} early"
    elif s == "published":
        main = f'<p class="center reveal"><a class="btn btn-primary btn-lg" href="{L["store"]}">{ICONS["gplay"]}<span>Get it on Google Play</span></a></p>'
        lede = f"Testing is over: {e(g['name'])} is out for everyone. Thank you, testers."
        h1 = f"{e(g['name'])} is out"
    else:
        main = f'<p class="center reveal"><a class="btn btn-glass btn-lg" href="{studio["base"]}/games/">{ICONS["arrow"]}<span>See all games</span></a></p>'
        lede = f"{e(g['name'])} is still being made. Testing opens here as soon as it's ready."
        h1 = f"{e(g['name'])} is coming"
    body = f"""<section class="test-hero" style="{style_vars(g)}">
  <div class="wrap narrow">
    <a class="back" href="{studio['base']}/test/">{ICONS['arrow']}<span>All tests</span></a>
    <img class="test-icon reveal" src="{L['icon']}" alt="" width="120" height="120">
    <span class="badge badge-{s} reveal"><i></i>{STATUS_LABEL[s]}</span>
    <h1 class="reveal">{h1}</h1>
    <p class="lede reveal">{lede}</p>
  </div>
</section>
<section class="test-main"><div class="wrap narrow">
{main}
</div></section>"""
    extra = f'<meta property="og:image" content="{studio["origin"]}{L["icon"]}">'
    return page(studio, f"{g['name']} · Play early · Brainnova Studio", f"Play {g['name']} early on Android. {g['tagline']}",
                path, "test", body, extra_head=extra)


def test_index_page(data):
    studio = data["studio"]
    testing = [g for g in data["games"] if g["status"] == "closed-testing"]
    if testing:
        rows = "".join(f"""<a class="test-row reveal" href="{links(studio, g)['test']}" style="{style_vars(g)}">
  <img src="{links(studio, g)['icon']}" alt="" width="72" height="72"><div><h3>{e(g['name'])}</h3><p>{e(g['tagline'])}</p></div>{ICONS['arrow']}</a>""" for g in testing)
    else:
        rows = '<p class="center">No game is in testing right now. The next one is on its way.</p>'
    body = f"""<section class="test-hero">
  <div class="wrap narrow">
    <p class="eyebrow reveal">Play early</p>
    <h1 class="reveal">Be the first to play.</h1>
    <p class="lede reveal">Every Brainnova game spends two weeks with testers before it reaches Google Play. Pick a game, join in three steps, and help it launch. It's free, on Android.</p>
  </div>
</section>
<section class="test-main"><div class="wrap narrow"><div class="test-list">{rows}</div></div></section>"""
    return page(studio, "Play early · Brainnova Studio", "Test Brainnova Studio games on Android before they launch.",
                f"{studio['base']}/test/", "test", body)


def play_page(data, g, bundle, engines):
    """Play in the browser. The engine is shared by every game (engine/<godot>/),
    the game's own pack and streamed assets come from its build (play/<slug>/data/).
    See src/assets/play.js for the device rules."""
    studio = data["studio"]
    L = links(studio, g)
    base = studio["base"]
    play = bundle.get("play")
    engine = None
    if play:
        engine = play.get("engine") or engines.get(bundle.get("godot", ""))
    cfg = {
        "studio": studio, "web": data["web"],
        "game": {k: g[k] for k in ("slug", "name", "tagline", "hint", "status", "package")} | {"links": L},
        "games": [{"slug": o["slug"], "name": o["name"], "status": o["status"], "links": links(studio, o)} for o in data["games"]],
        "build": ({"engine": engine, "pack": play["pack"], "assets": play["assets"], "godot": play["godot"],
                   "version": bundle.get("version", "")} if play and engine else None),
    }
    preload = f'<link rel="preload" href="{engine["js"]}" as="script">' if cfg["build"] else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>{e(g['name'])} · Play in browser</title>
<meta name="description" content="Play {e(g['name'])} in your browser. {e(g['tagline'])}">
<meta name="theme-color" content="{g['colors']['bg']}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{e(g['name'])}">
<link rel="icon" href="{L['icon']}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{L['icon']}">
{preload}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/play.css">
{PLATFORM_JS}
<script>window.BN_CONFIG={json.dumps(cfg, separators=(",", ":"))};</script>
</head>
<body style="{style_vars(g)}">
<canvas id="canvas" tabindex="0">Your browser can't show this game.</canvas>
<noscript>This game needs JavaScript.</noscript>
<div id="bn-loader" class="loader" role="status" aria-live="polite">
  <div class="loader-aura" aria-hidden="true"></div>
  <div class="loader-ring">
    <svg viewBox="0 0 120 120" aria-hidden="true"><circle class="track" cx="60" cy="60" r="54"/><circle class="value" cx="60" cy="60" r="54" pathLength="100" data-ring/></svg>
    <img src="{L['icon']}" alt="" width="84" height="84">
  </div>
  <h1>{e(g['name'])}</h1>
  <p class="loader-tag">{e(g['tagline'])}</p>
  <p class="loader-status" data-status>Getting ready…</p>
  <p class="loader-hint" data-hint>{e(g['hint'])}</p>
  <div class="loader-card" data-card hidden></div>
</div>
<div id="bn-banner" class="banner" hidden></div>
<div id="bn-modal" class="modal" hidden></div>
<script src="{base}/assets/qr.js" defer></script>
<script src="{base}/assets/play.js"></script>
</body>
</html>
"""


def redirect(to):
    return f"""<!doctype html><meta charset="utf-8"><title>Brainnova Studio</title>
<meta http-equiv="refresh" content="0; url={to}"><link rel="canonical" href="{to}">
<script>location.replace("{to}"+location.search+location.hash)</script>
<a href="{to}">Brainnova Studio games</a>
"""


def not_found(data):
    """404 for anything under /BrainnovaStudio/. route.js first tries to read the
    address loosely (any case, with or without dashes) and redirects if it can."""
    studio = data["studio"]
    body = f"""<section class="test-hero" data-route-miss hidden><div class="wrap narrow">
<p class="eyebrow">404</p><h1>This page wandered off.</h1>
<p class="lede">It may have moved, or never existed.</p>
<p><a class="btn btn-primary btn-lg" href="{studio['base']}/games/">{ICONS['arrow']}<span>All games</span></a></p>
</div></section>"""
    route = f'<script src="{studio["base"]}/assets/route.js"></script>'
    return page(studio, "Not found · Brainnova Studio", "Page not found.", f"{studio['base']}/404.html", "", body,
                extra_head=route, robots="noindex")


# --------------------------------------------------------------------------- game builds

def fetch_bundles():
    """Every game's latest build lives on this repo's branch build/<slug>."""
    if BUNDLES.exists():
        shutil.rmtree(BUNDLES)
    BUNDLES.mkdir()
    # No game has sent a build yet on a brand-new repo: fine, nothing to fetch.
    subprocess.run(["git", "fetch", "-q", "--depth=1", "origin", "+refs/heads/build/*:refs/remotes/origin/build/*"], cwd=ROOT, check=False)
    refs = subprocess.run(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/build/"],
                          cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    for ref in refs:
        slug = ref.split("/", 2)[2]
        out = BUNDLES / slug
        out.mkdir()
        tar = subprocess.run(["git", "archive", ref], cwd=ROOT, check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(out)], input=tar, check=True)
        print(f"fetched build/{slug}")


def engine_for(godot):
    """The shared slim engine for a Godot version: dist/engine/<godot>/godot.*"""
    zpath = CACHE / f"engine-{godot}.zip"
    if not zpath.exists():
        CACHE.mkdir(exist_ok=True)
        url = f"https://github.com/{REPO}/releases/download/engine-{godot}/web_nothreads_release.zip"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "brainnova-build"})
            with urllib.request.urlopen(req) as r:
                zpath.write_bytes(r.read())
        except Exception as err:
            print(f"warning: no slim engine for {godot} ({err})")
            return None
    out = DIST / "engine" / godot
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        for name in ("godot.js", "godot.wasm", "godot.audio.worklet.js", "godot.audio.position.worklet.js"):
            (out / name).write_bytes(z.read(name))
    base = f"/BrainnovaStudio/engine/{godot}/"
    return {"js": base + "godot.js", "exe": base + "godot", "wasm": base + "godot.wasm", "wasmSize": (out / "godot.wasm").stat().st_size}


def place_bundle(data, g, engines):
    """Copies a game's build into dist/ and returns what the pages need to know."""
    studio = data["studio"]
    slug = g["slug"]
    src = BUNDLES / slug
    info = {}
    if not src.exists():
        return info
    meta = json.loads((src / "meta.json").read_text()) if (src / "meta.json").exists() else {}
    info["version"] = meta.get("version", "")
    info["godot"] = meta.get("godot", "")
    page_dir = DIST / "games" / slug
    page_dir.mkdir(parents=True, exist_ok=True)
    apk = src / f"{slug}.apk"
    if apk.exists():
        shutil.copy(apk, page_dir / apk.name)
        info["apk"] = {"url": f"{studio['base']}/games/{slug}/{apk.name}", "mb": round(apk.stat().st_size / 1048576)}
    web = src / "web"
    if (web / "images").exists():
        shutil.copytree(web / "images", page_dir / "images", dirs_exist_ok=True)
    for kind in ("help", "privacy"):
        f = web / kind / "index.html"
        if f.exists():
            info[kind] = f.read_text()
    play = src / "play"
    if (play / "index.pck").exists() and (play / "config.json").exists():
        h = short_hash(play / "index.pck")
        data_dir = DIST / "play" / slug / "data" / h
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(play / "index.pck", data_dir / "index.pck")
        url = f"{studio['base']}/play/{slug}/data/{h}/"
        p = {"pack": {"url": url + "index.pck", "size": (play / "index.pck").stat().st_size},
             "assets": {}, "godot": info["godot"], "config": json.loads((play / "config.json").read_text())}
        # Streamed assets (music...): content-hashed names, so they cache forever.
        if (play / "assets").exists():
            for f in sorted((play / "assets").rglob("*")):
                if f.is_file():
                    rel = f.relative_to(play / "assets").as_posix()
                    name = f"{short_hash(f)}-{f.name}"
                    dest = DIST / "play" / slug / "data" / "a" / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(f, dest)
                    p["assets"][rel] = f"{studio['base']}/play/{slug}/data/a/{name}"
        # A build exported without the slim engine brings its own.
        if (play / "engine" / "index.wasm").exists():
            for f in (play / "engine").iterdir():
                shutil.copy(f, data_dir / f.name)
            p["engine"] = {"js": url + "index.js", "exe": url + "index", "wasm": url + "index.wasm",
                           "wasmSize": (play / "engine" / "index.wasm").stat().st_size}
        elif info["godot"] and info["godot"] not in engines:
            engines[info["godot"]] = engine_for(info["godot"])
        info["play"] = p
    return info


# --------------------------------------------------------------------------- build

def build():
    data = load()
    studio = data["studio"]
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(SRC / "assets", DIST / "assets")
    shutil.copytree(ROOT / "media", DIST / "media")
    # The service worker must sit at the site root to cover every page under it.
    shutil.move(str(DIST / "assets" / "sw.js"), DIST / "sw.js")

    def write(rel, text):
        p = DIST / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    engines = {}
    bundles = {g["slug"]: place_bundle(data, g, engines) for g in data["games"]}
    for g in data["games"]:
        shots = [f"{studio['base']}/media/{g['slug']}/{s}" for s in g.get("shots", [])]
        if not shots:
            imgs = sorted((DIST / "games" / g["slug"] / "images").glob("*.jpg")) if (DIST / "games" / g["slug"] / "images").exists() else []
            shots = [f"{studio['base']}/games/{g['slug']}/images/{p.name}" for p in imgs]
        g["_shots"] = shots

    write("index.html", redirect(f"{studio['base']}/games/"))
    write("games/index.html", games_page(data))
    write("test/index.html", test_index_page(data))
    write("404.html", not_found(data))
    for g in data["games"]:
        b = bundles[g["slug"]]
        write(f"games/{g['slug']}/index.html", game_page(data, g, b))
        for kind in ("help", "privacy"):
            if b.get(kind):
                write(f"games/{g['slug']}/{kind}/index.html", doc_page(data, g, kind, b[kind]))
        write(f"test/{g['slug']}/index.html", test_game_page(data, g))
        write(f"play/{g['slug']}/index.html", play_page(data, g, b, engines))
    # Read by the play page, the 404 router and anything else that wants to know where a game stands.
    public = {"studio": studio, "web": data["web"],
              "games": [{k: v for k, v in g.items() if not k.startswith("_")} | {"links": links(studio, g)} for g in data["games"]]}
    write("games.json", json.dumps(public, indent=2))
    (DIST / ".nojekyll").touch()
    print("Built: " + ", ".join(f"{g['slug']} ({g['status']}{', build ' + bundles[g['slug']]['version'] if bundles[g['slug']].get('version') else ''})" for g in data["games"]))


def serve():
    import http.server
    data = load()
    base = data["studio"]["base"]

    class H(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".js": "text/javascript"}

        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            if path.startswith(base + "/"):
                p = DIST / path[len(base) + 1:]
                return str(p / "index.html" if p.is_dir() else p)
            return str(DIST / "__none__")

        def send_error(self, code, message=None, explain=None):
            if code == 404:
                body = (DIST / "404.html").read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().send_error(code, message, explain)

    port = 8800
    print(f"Serving on http://localhost:{port}{base}/games/")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch_bundles()
    build()
    if "--serve" in sys.argv:
        serve()
