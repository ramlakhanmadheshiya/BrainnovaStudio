#!/usr/bin/env python3
"""Builds the Brainnova Studio site into dist/ from games.json.

    python3 build.py            build dist/
    python3 build.py --serve    build, then serve on http://localhost:8800/BrainnovaStudio/games/

Every page and every button comes from games.json. A game's "status" decides
what it shows, so changing one word there (and pushing) moves a game from
"Coming soon" to "Play early" to "Get it on Google Play":

    development     Coming soon. No web play, no testing page link.
    closed-testing  Play early (testing page) + Play in browser.
    published       Get it on Google Play + Play in browser.

The site is served at theramlakhan.com/BrainnovaStudio/ (GitHub Pages of the
BrainnovaStudio repo). Each game's own build stays at theramlakhan.com/<slug>/.
"""

import datetime
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

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
    data["games"].sort(key=lambda g: (ORDER[g["status"]], _neg_date(g["_date"])))
    return data


def _neg_date(s):
    return -datetime.date.fromisoformat(s).toordinal()


def nice_date(s):
    if not s:
        return ""
    d = datetime.date.fromisoformat(s)
    return f"{d.day} {d.strftime('%b %Y')}"


def links(studio, g):
    """Every URL a game can point to, in one place."""
    base = studio["base"]
    pkg = g["package"]
    return {
        "store": f"https://play.google.com/store/apps/details?id={pkg}",
        "optin": f"https://play.google.com/apps/testing/{pkg}",
        "group": f"https://groups.google.com/g/{studio['testers_group']}",
        "test": f"{base}/test/{g['slug']}/",
        "play": f"{base}/play/{g['slug']}/",
        "engine": f"/{g['slug']}/play/",
        "site": f"/{g['slug']}/",
        "icon": f"{base}/media/{g['slug']}/icon.svg",
    }


# --------------------------------------------------------------------------- shared bits

ICONS = {
    "play": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.4-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5Z" fill="currentColor"/></svg>',
    "gplay": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.6 2.3 13.4 12l-9.8 9.7a1.6 1.6 0 0 1-.6-1.3V3.6c0-.5.2-1 .6-1.3Z" fill="#00d3ff"/><path d="m16.8 8.6-3.4 3.4-9.8-9.7c.4-.3 1-.4 1.6-.1l11.6 6.4Z" fill="#00f076"/><path d="m16.8 15.4-11.6 6.4c-.6.3-1.2.2-1.6-.1l9.8-9.7 3.4 3.4Z" fill="#ff3a44"/><path d="M20.5 10.6c1 .6 1 2.2 0 2.8l-3.7 2-3.4-3.4 3.4-3.4 3.7 2Z" fill="#ffd500"/></svg>',
    "flask": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6M10 3v6.2L4.6 18.4A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.4-2.6L14 9.2V3"/><path d="M7.5 15h9"/></svg>',
    "browser": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18"/><path d="m10.5 12.5 4 2.5-4 2.5z" fill="currentColor"/></svg>',
    "hammer": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 12-8.4 8.4a2 2 0 0 1-2.8-2.8L12.2 9"/><path d="m17.6 14.6 4-4-6.2-6.2a4 4 0 0 0-5.6 0l-.8.8 7.8 7.8 2.4-2.4"/></svg>',
    "info": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "check": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
    "share": '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3M7.5 7.5 12 3l4.5 4.5"/><path d="M5 12v6.5A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V12"/></svg>',
}

LOGO = """<svg class="logo" viewBox="0 0 32 32" aria-hidden="true">
  <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8f6bff"/><stop offset="1" stop-color="#ff6b5b"/></linearGradient></defs>
  <circle cx="16" cy="16" r="15" fill="url(#lg)"/>
  <g fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" opacity=".95">
    <path d="M9.5 12.5 16 9l6.5 3.5M9.5 12.5 12 20l4 3 4-3 2.5-7.5M12 20l4-6.5 4 6.5M16 9v4.5"/>
  </g>
  <g fill="#fff"><circle cx="16" cy="9" r="1.9"/><circle cx="9.5" cy="12.5" r="1.6"/><circle cx="22.5" cy="12.5" r="1.6"/><circle cx="12" cy="20" r="1.6"/><circle cx="20" cy="20" r="1.6"/><circle cx="16" cy="13.5" r="2.3"/><circle cx="16" cy="23" r="1.4"/></g>
</svg>"""

# Runs before first paint: which device is this, so buttons never flash.
# android = can install from Google Play (phones, tablets, TV, Chromebooks).
# apple   = iPhone, iPad, Mac: full game in the browser, every ad type.
# other   = Windows, Linux, ...: the first levels in the browser.
# ?as=android|apple|other previews another device (kept for this tab).
PLATFORM_JS = """<script>
(function(){var q=new URLSearchParams(location.search).get('as'),s;
try{if(q)sessionStorage.setItem('bn-as',q);s=sessionStorage.getItem('bn-as')}catch(_){s=q}
var u=navigator.userAgent,p='other',d=navigator.userAgentData;
if(/Android|CrOS/i.test(u)||(d&&/Android|Chrome OS/i.test(d.platform||''))||(/Linux/i.test(u)&&navigator.maxTouchPoints>1))p='android';
else if(/iPhone|iPad|iPod|Macintosh/i.test(u))p='apple';
if(s==='android'||s==='apple'||s==='other')p=s;
var h=document.documentElement;h.dataset.platform=p;h.classList.add('js');window.BN_PLATFORM=p})();
</script>"""


def head(studio, title, desc, path, extra=""):
    base = studio["base"]
    url = studio["origin"] + path
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#fbfbfd" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
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


def page(studio, title, desc, path, active, body, scripts="", extra_head=""):
    base = studio["base"]
    return f"""{head(studio, title, desc, path, extra_head)}
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


def actions(studio, g):
    """The same three slots, in the same order, on every card:
       1. Google Play / Play early / Coming soon
       2. Play in browser (hidden on Android, where Google Play is the way)
       3. Details"""
    L = links(studio, g)
    s = g["status"]
    free = studio_web["free_levels"]
    if s == "published":
        first = f'<a class="btn btn-primary" href="{L["store"]}" rel="noopener" data-track="store">{ICONS["gplay"]}<span>Google Play</span></a>'
    elif s == "closed-testing":
        first = f'<a class="btn btn-primary" href="{L["test"]}" data-track="test">{ICONS["flask"]}<span>Play early</span></a>'
    else:
        first = f'<span class="btn btn-primary is-off" aria-disabled="true">{ICONS["hammer"]}<span>Coming soon</span></span>'
    if s == "development":
        web = f'<span class="btn btn-glass is-off web-only" aria-disabled="true">{ICONS["browser"]}<span>Play in browser<small>Soon</small></span></span>'
    else:
        web = (f'<a class="btn btn-glass web-only" href="{L["play"]}" data-engine="{L["engine"]}" data-track="web">{ICONS["browser"]}'
               f'<span>Play in browser<small class="only-apple">Full game</small><small class="only-other">First {free} levels</small></span></a>')
    more = f'<button class="btn btn-ghost" type="button" data-details="{e(g["slug"])}">{ICONS["info"]}<span>Details</span></button>'
    return f'<div class="actions">{first}{web}{more}</div>'


def date_line(g):
    d = g["dates"]
    if g["status"] == "published" and d.get("published"):
        return f'Released <time datetime="{d["published"]}">{nice_date(d["published"])}</time>'
    if g["status"] == "closed-testing" and d.get("testing"):
        return f'Testing since <time datetime="{d["testing"]}">{nice_date(d["testing"])}</time>'
    return f'Started <time datetime="{d["started"]}">{nice_date(d["started"])}</time>'


def card(studio, g, i):
    c = g["colors"]
    L = links(studio, g)
    s = g["status"]
    facts = "".join(f"<li>{e(f)}</li>" for f in g.get("facts", []))
    return f"""<article class="game reveal" data-status="{s}" data-slug="{e(g['slug'])}" style="--g-bg:{c['bg']};--g-accent:{c['accent']};--g-glow:{c['glow']};--i:{i}">
  <div class="game-media" data-tilt>
    <div class="aura" aria-hidden="true"></div>
    {'<div class="blueprint" aria-hidden="true"><span class="scan"></span></div>' if s == 'development' else ''}
    <img class="game-icon" src="{L['icon']}" alt="" width="132" height="132" loading="lazy" decoding="async">
    <span class="badge badge-{s}"><i></i>{STATUS_LABEL[s]}</span>
  </div>
  <div class="game-body">
    <p class="game-date">{date_line(g)}</p>
    <h3>{e(g['name'])}</h3>
    <p class="game-tagline">{e(g['tagline'])}</p>
    <ul class="facts">{facts}</ul>
    {actions(studio, g)}
  </div>
</article>"""


# --------------------------------------------------------------------------- pages

def games_page(data):
    studio = data["studio"]
    games = data["games"]
    count = {s: sum(1 for g in games if g["status"] == s) for s in STATUSES}
    chips = [("all", "All", len(games)), ("published", "On Google Play", count["published"]),
             ("closed-testing", "Play early", count["closed-testing"]), ("development", "In the works", count["development"])]
    chip_html = "".join(
        f'<button type="button" role="tab" class="chip" data-filter="{k}" aria-selected="{"true" if k == "all" else "false"}"'
        f'{" hidden" if n == 0 and k != "all" else ""}>{label}<span>{n}</span></button>'
        for k, label, n in chips)
    stats = []
    if count["published"]:
        stats.append(f'<li><b data-count="{count["published"]}">{count["published"]}</b> on Google Play</li>')
    if count["closed-testing"]:
        stats.append(f'<li><b data-count="{count["closed-testing"]}">{count["closed-testing"]}</b> in testing</li>')
    if count["development"]:
        stats.append(f'<li><b data-count="{count["development"]}">{count["development"]}</b> in the works</li>')
    cards = "\n".join(card(studio, g, i) for i, g in enumerate(games))
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
    public = [{k: g[k] for k in ("slug", "name", "tagline", "blurb", "hint", "status", "dates", "colors", "facts", "shots")} | {"links": links(studio, g)} for g in games]
    page_studio = dict(studio, free_levels=data["web"]["free_levels"])
    scripts = f'<script>window.BN_GAMES={json.dumps(public, separators=(",", ":"))};window.BN_STUDIO={json.dumps(page_studio)};</script>'
    return page(studio, "Games · Brainnova Studio", "Every game from Brainnova Studio: play on Google Play, in your browser, or early as a tester.",
                f"{studio['base']}/games/", "games", body, scripts)


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
    c = g["colors"]
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
    body = f"""<section class="test-hero" style="--g-bg:{c['bg']};--g-accent:{c['accent']};--g-glow:{c['glow']}">
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
        rows = "".join(f"""<a class="test-row reveal" href="{links(studio, g)['test']}" style="--g-bg:{g['colors']['bg']};--g-accent:{g['colors']['accent']};--g-glow:{g['colors']['glow']}">
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


def play_page(data, g):
    """The browser-play page. It loads the game's own engine files from
    theramlakhan.com/<slug>/play/, so a game never needs a rebuild for these
    rules to change; see src/assets/play.js."""
    studio = data["studio"]
    L = links(studio, g)
    c = g["colors"]
    base = studio["base"]
    cfg = {
        "studio": studio, "web": data["web"],
        "game": {k: g[k] for k in ("slug", "name", "tagline", "hint", "status", "package")} | {"links": L},
        "games": [{"slug": o["slug"], "name": o["name"], "status": o["status"], "links": links(studio, o)} for o in data["games"]],
    }
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>{e(g['name'])} · Play in browser</title>
<meta name="description" content="Play {e(g['name'])} in your browser. {e(g['tagline'])}">
<meta name="theme-color" content="{c['bg']}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{e(g['name'])}">
<link rel="icon" href="{L['icon']}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{L['icon']}">
<link rel="preload" href="{L['engine']}index.js" as="script">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/play.css">
{PLATFORM_JS}
<script>window.BN_CONFIG={json.dumps(cfg, separators=(",", ":"))};</script>
</head>
<body style="--g-bg:{c['bg']};--g-accent:{c['accent']};--g-glow:{c['glow']}">
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
<a href="{to}">Brainnova Studio games</a>
"""


def not_found(data):
    studio = data["studio"]
    body = f"""<section class="test-hero"><div class="wrap narrow">
<p class="eyebrow">404</p><h1>This page wandered off.</h1>
<p class="lede">It may have moved, or never existed.</p>
<p><a class="btn btn-primary btn-lg" href="{studio['base']}/games/">{ICONS['arrow']}<span>All games</span></a></p>
</div></section>"""
    return page(studio, "Not found · Brainnova Studio", "Page not found.", f"{studio['base']}/404.html", "", body)


# --------------------------------------------------------------------------- build

studio_web = {}


def build():
    data = load()
    studio_web.update(data["web"])
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(SRC / "assets", DIST / "assets")
    shutil.copytree(ROOT / "media", DIST / "media")

    def write(rel, text):
        p = DIST / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    write("index.html", redirect(f"{data['studio']['base']}/games/"))
    write("games/index.html", games_page(data))
    write("test/index.html", test_index_page(data))
    write("404.html", not_found(data))
    for g in data["games"]:
        write(f"test/{g['slug']}/index.html", test_game_page(data, g))
        write(f"play/{g['slug']}/index.html", play_page(data, g))
    # Read by the play page and by anything else that wants to know where a game stands.
    public = {"studio": data["studio"], "web": data["web"],
              "games": [g | {"links": links(data["studio"], g)} for g in data["games"]]}
    for g in public["games"]:
        g.pop("_date", None)
    write("games.json", json.dumps(public, indent=2))
    (DIST / ".nojekyll").touch()
    n = len(data["games"])
    print(f"Built {n} games into {DIST.relative_to(ROOT)}/: " + ", ".join(f"{g['slug']} ({g['status']})" for g in data["games"]))


def serve():
    """Serves dist/ at /BrainnovaStudio/ and each game's web build at /<slug>/play/:
    from its local build/web/ export if there is one, otherwise downloaded once
    from the live site into .cache/engines/."""
    import http.server
    import urllib.request
    games_dir = ROOT.parent
    data = load()
    base = data["studio"]["base"]
    origin = data["studio"]["origin"]
    cache = ROOT / ".cache" / "engines"

    class H(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".js": "text/javascript"}

        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            if path.startswith(base + "/"):
                rel = path[len(base) + 1:]
                p = DIST / rel
                return str(p / "index.html" if p.is_dir() else p)
            for g in data["games"]:
                pre = f"/{g['slug']}/play/"
                if path.startswith(pre):
                    name = path[len(pre):] or "index.html"
                    for d in games_dir.glob(f"game_*/{g['slug']}/build/web"):
                        if (d / name).exists():
                            return str(d / name)
                    local = cache / g["slug"] / name
                    if not local.exists():
                        local.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            req = urllib.request.Request(origin + path, headers={"User-Agent": "Mozilla/5.0 (brainnova-preview)"})
                            with urllib.request.urlopen(req) as r:
                                local.write_bytes(r.read())
                        except Exception:
                            return str(DIST / "__none__")
                    return str(local)
            return str(DIST / "__none__")

    port = 8800
    print(f"Serving on http://localhost:{port}{base}/games/")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()
