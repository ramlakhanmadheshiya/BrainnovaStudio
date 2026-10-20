#!/bin/bash
# Points a game's Web export preset at the slim Brainnova engine for its Godot
# version (built by .github/workflows/engine.yml). Run from the game repo's root
# in CI, before exporting the web build:
#
#   curl -fsSL https://raw.githubusercontent.com/ramlakhanmadheshiya/BrainnovaStudio/main/tools/slim-engine.sh | bash
#
# Needs GODOT_RELEASE (e.g. 4.7.2-stable). Without a matching release the stock
# engine is used and ship.sh sends the game's own engine along with its build.
set -euo pipefail

url="https://github.com/ramlakhanmadheshiya/BrainnovaStudio/releases/download/engine-${GODOT_RELEASE}/web_nothreads_release.zip"
zip="${RUNNER_TEMP:-/tmp}/web_slim.zip"
if ! curl -fsSL -o "$zip" "$url"; then
	echo "::warning::No slim engine for ${GODOT_RELEASE}; using the stock one. Run BrainnovaStudio's 'Build slim web engine'."
	exit 0
fi
python3 - "$zip" <<'EOF'
import re, sys
s = open("export_presets.cfg").read()
i = s.index('platform="Web"')
j = s.index("custom_template/release=", i)
s = s[:j] + re.sub(r'custom_template/release="[^"]*"', f'custom_template/release="{sys.argv[1]}"', s[j:], count=1)
open("export_presets.cfg", "w").write(s)
EOF
[ -n "${GITHUB_ENV:-}" ] && echo "BRAINNOVA_SLIM_ENGINE=1" >> "$GITHUB_ENV"
echo "Using the slim web engine for ${GODOT_RELEASE}."
