#!/bin/bash
# Sends a game's latest build to the Brainnova Studio site. Run from the game
# repo's root in CI, after the Android and web exports:
#
#   curl -fsSL https://raw.githubusercontent.com/ramlakhanmadheshiya/BrainnovaStudio/main/tools/ship.sh | bash -s -- <slug> <version>
#
# Reads:  build/android/<slug>.apk, build/web/index.{html,pck,...}, web/{help,privacy,images}
#         assets/audio/music/* when the Web preset leaves music out (it's streamed instead)
# Needs:  STUDIO_DEPLOY_KEY (secret: write key for the BrainnovaStudio repo), GODOT_RELEASE
# Does:   1. pushes the build to BrainnovaStudio's branch build/<slug>, which republishes
#            theramlakhan.com/BrainnovaStudio/ (game page, APK, help, privacy, browser play);
#         2. writes ./stubs/: pages for the game's own gh-pages that send the old
#            theramlakhan.com/<slug>/... addresses to the new ones.
set -euo pipefail

slug="$1"
version="${2:-}"
B="${RUNNER_TEMP:-/tmp}/brainnova-bundle"
rm -rf "$B" stubs
mkdir -p "$B/play" "$B/web"

# ---- the APK (for testing builds on a phone)
[ -f "build/android/$slug.apk" ] && cp "build/android/$slug.apk" "$B/"

# ---- the web pack and its engine settings
cp build/web/index.pck "$B/play/"
python3 - build/web/index.html "$B/play/config.json" <<'EOF'
import json, re, sys
m = re.search(r"const\s+GODOT_CONFIG\s*=\s*(\{.*?\});", open(sys.argv[1]).read(), re.S)
json.dump(json.loads(m.group(1)), open(sys.argv[2], "w"))
EOF
if [ -z "${BRAINNOVA_SLIM_ENGINE:-}" ]; then
	# Exported with the stock engine: send it along.
	mkdir -p "$B/play/engine"
	for f in index.js index.wasm index.audio.worklet.js index.audio.position.worklet.js; do
		[ -f "build/web/$f" ] && cp "build/web/$f" "$B/play/engine/"
	done
fi

# ---- music left out of the web pack is streamed: send it as Ogg Vorbis
if grep -A8 'platform="Web"' export_presets.cfg | grep -q 'exclude_filter=.*assets/audio/music'; then
	command -v oggenc >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq vorbis-tools >/dev/null; }
	mkdir -p "$B/play/assets/music"
	for f in assets/audio/music/*.wav assets/audio/music/*.ogg; do
		[ -f "$f" ] || continue
		name="$(basename "${f%.*}")"
		if [[ "$f" == *.ogg ]]; then cp "$f" "$B/play/assets/music/$name.ogg"
		else oggenc -Q -q 4 "$f" -o "$B/play/assets/music/$name.ogg"; fi
	done
	du -sh "$B/play/assets/music"
fi

# ---- help, privacy and screenshots
for d in help privacy images; do
	[ -d "web/$d" ] && cp -R "web/$d" "$B/web/"
done

printf '{"slug": "%s", "version": "%s", "godot": "%s", "built": "%s"}\n' \
	"$slug" "$version" "${GODOT_RELEASE:-}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$B/meta.json"
du -sh "$B"

# ---- push it to build/<slug>
if [ -z "${STUDIO_DEPLOY_KEY:-}" ]; then
	echo "::warning::STUDIO_DEPLOY_KEY is not set, so this build doesn't reach theramlakhan.com/BrainnovaStudio/. Run ./studio.py connect $slug."
else
	key="${RUNNER_TEMP:-/tmp}/studio_key"
	printf '%s\n' "$STUDIO_DEPLOY_KEY" > "$key"
	chmod 600 "$key"
	(
		cd "$B"
		git init -q -b build
		git -c user.name="Brainnova CI" -c user.email="ci@theramlakhan.com" add -A
		git -c user.name="Brainnova CI" -c user.email="ci@theramlakhan.com" commit -q -m "$slug $version"
		GIT_SSH_COMMAND="ssh -i $key -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes" \
			git push -q -f git@github.com:ramlakhanmadheshiya/BrainnovaStudio.git "build:refs/heads/build/$slug"
	)
	# Note the version on main: that push is what republishes the site
	# (a push to build/<slug> alone runs no workflow).
	export GIT_SSH_COMMAND="ssh -i $key -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes"
	site="${RUNNER_TEMP:-/tmp}/brainnova-site"
	rm -rf "$site"
	git clone -q --depth 5 --branch main git@github.com:ramlakhanmadheshiya/BrainnovaStudio.git "$site"
	for attempt in 1 2 3 4 5; do
		mkdir -p "$site/builds"
		cp "$B/meta.json" "$site/builds/$slug.json"
		git -C "$site" add "builds/$slug.json"
		git -C "$site" diff --cached --quiet && break
		git -C "$site" -c user.name="Brainnova CI" -c user.email="ci@theramlakhan.com" commit -q -m "Build: $slug $version"
		git -C "$site" push -q origin main && break
		sleep $((attempt * 3))
		git -C "$site" fetch -q origin main && git -C "$site" reset -q --hard origin/main
	done
	unset GIT_SSH_COMMAND
	rm -f "$key"
	echo "Sent $slug $version to Brainnova Studio: https://theramlakhan.com/BrainnovaStudio/games/$slug/"
fi

# ---- the old addresses on this repo's gh-pages
python3 - "$slug" <<'EOF'
import os, sys
slug = sys.argv[1]
b = "/BrainnovaStudio"
pages = {"": f"{b}/games/{slug}/", "privacy/": f"{b}/games/{slug}/privacy/",
         "help/": f"{b}/games/{slug}/help/", "play/": f"{b}/play/{slug}/"}
for path, to in pages.items():
    os.makedirs("stubs/" + path, exist_ok=True)
    with open(f"stubs/{path}index.html", "w") as f:
        f.write(f'<!doctype html><meta charset="utf-8"><title>Moved</title>'
                f'<link rel="canonical" href="https://theramlakhan.com{to}">'
                f'<meta http-equiv="refresh" content="0; url={to}">'
                f'<script>location.replace("{to}"+location.search+location.hash)</script>'
                f'<a href="{to}">This page moved here</a>\n')
with open("stubs/404.html", "w") as f:
    f.write('<!doctype html><meta charset="utf-8"><title>Moved</title>'
            '<script src="/BrainnovaStudio/assets/route.js"></script>'
            f'<p data-route-miss hidden><a href="{b}/games/">Brainnova Studio games</a></p>\n')
open("stubs/.nojekyll", "w").close()
EOF
