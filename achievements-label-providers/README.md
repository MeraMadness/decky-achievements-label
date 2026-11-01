# Achievements Label Providers (Decky plugin)

Add-on for [Achievements Label](../achievements-label). Achievements Label shows an **Achievements** column in Steam's
Big Picture game bar, using Steam's own data. Steam has no data for games that are not on Steam, so this plugin
supplies the numbers for:

| Source | Games | What you need |
|---|---|---|
| **RPCS3 trophies** | PS3 games run through RPCS3 | RPCS3 installed (trophy files are read from disk) |
| **RetroAchievements** | emulated games: PS2, PSP, GBA, SNES, N64, Dreamcast, ... | a free RetroAchievements account and its web API key |
| **MadnessPatch** | Alice: Madness Returns (with [MadnessPatch](https://github.com/Wemino/MadnessPatch)) | the patch installed |

Pure Python, nothing else to install. It draws nothing itself; install **both** plugins.

## Install

1. Install Achievements Label first (see its README).
2. Copy this folder to `~/homebrew/plugins/achievements-label-providers/` and restart Decky Loader.
3. Open Big Picture once; the Decky menu entry "Achievements Label Providers" shows what it found.

## RetroAchievements setup

Get your **username** and **Web API Key** from <https://retroachievements.org/settings> (Keys section), then put them in
`~/.config/achievements-label/config.json` (the plugin creates this file on first start):

```json
{
  "retroachievements": { "user": "YourName", "api_key": "xxxxxxxx" },
  "overrides": {}
}
```

The file is private (`chmod 600`) and the key is never logged or shown in the panel.

### How it finds the console

For games added to Steam as non-Steam shortcuts (for example with **Steam ROM Manager**), the plugin reads
`shortcuts.vdf` and guesses the console from words in the shortcut's **tags**, **executable** and **launch options**:
`PS2`, `pcsx2-qt`, `Game Boy Advance`, `snes9x`, ... Then it matches the game's **title** against RetroAchievements'
game list for that console (the list is cached for a week).

So: keep the Steam shortcut's name close to the real game title, and give it a console tag, or use an emulator whose
name is recognisable. PS3 / RPCS3 games are handled by the trophy reader, not RetroAchievements.

### Overrides (when the guess is wrong)

```json
"overrides": {
  "My Game":    "ra-console:21",
  "1234567890": "ra:4567",
  "Other Game": "none"
}
```

Keys are a game's name (any case) or its Steam app id. Values: `none`, `ra:<RA game id>`, `ra-console:<console id>`,
`rpcs3:<NPWR id>`, `madness`.

## Troubleshooting

- The panel in the Decky menu shows whether RPCS3 games and your RetroAchievements login were found, and the last
  problem (for example "RetroAchievements rejected the user / API key").
- Every lookup is logged in `~/homebrew/logs/achievements-label-providers/`.
- A game with no match is remembered as "nothing" for a couple of minutes; re-open its page after fixing the setup.

## Known limits

- Tested on one setup: Linux desktop (Gentoo, OpenRC), Steam in English, PCSX2 + RPCS3. Not tested on Steam Deck / SteamOS.
- Matching is by **title**, not by ROM hash, so a game with an unusual name may not match; use an override.
- RetroAchievements counts what you have earned in softcore or hardcore mode together.
- GOG, Epic and other launchers are not supported.

## Tests

```sh
python3 -I tests/test_providers.py
```

Offline, with synthetic data (a hand-made `TROPUSR.DAT` and `shortcuts.vdf`, a mocked RetroAchievements API).
