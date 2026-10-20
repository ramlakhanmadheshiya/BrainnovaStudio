# Brainnova Studio

The games site at **https://theramlakhan.com/BrainnovaStudio/games/**.

- `games.json` is the only thing to edit: every card, button and page comes from it.
  Each game's `status` is `development`, `closed-testing` or `published`.
- `python3 build.py --serve` previews it on http://localhost:8800/BrainnovaStudio/games/
  (add `?as=android`, `?as=apple` or `?as=other` to see another device).
- Pushing to `main` publishes it (`.github/workflows/pages.yml`).
- Usually you don't touch this repo by hand: `../studio.py` does it. See `../RULES_FOR_MAKING_GAME.md`.

| URL | What |
| --- | --- |
| `/BrainnovaStudio/games/` | every game, same buttons in the same order |
| `/BrainnovaStudio/test/<game>/` | "Play early": join closed testing in three steps |
| `/BrainnovaStudio/play/<game>/` | play in the browser (loads the game's own build from `/<game>/play/`) |
| `/BrainnovaStudio/games.json` | where every game stands, read by the play page |

`.github/workflows/engine.yml` builds the slim Godot web engine the games export with.
