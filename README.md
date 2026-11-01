# betterSteam

Decky Loader plugins that bring the **Achievements** column back to Steam's Big Picture game bar
(Valve removed the text), including for games that are not on Steam.

| Folder | What it is | Needs |
|---|---|---|
| [`achievements-label`](achievements-label) | **The main plugin.** Draws the column (`2 / 69` + progress bar) from Steam's own data. Works alone for Steam games. | Decky Loader |
| [`achievements-label-providers`](achievements-label-providers) | **Optional add-on.** Supplies numbers for RPCS3 trophies, RetroAchievements and EXE games, with no other software. | `achievements-label` |

Install the first one, or both. Download the zips from the [latest release](../../releases/latest) (or copy the folders from this repo) into `~/homebrew/plugins/` and restart Decky Loader
(`sudo systemctl restart plugin_loader`, or `sudo rc-service plugin_loader restart` on OpenRC).

The plugins talk through a tiny hook, `window.__achievementsLabel.providers`, documented in
`achievements-label/README.md`; anyone can write another provider.

## Status and limits

Built and tested on one machine (Linux desktop, English Steam). The plugins rely on private Steam internals, so a Steam
update can break them (the column then disappears instead of showing wrong numbers). Read each plugin's README for details.

## License

[GPL-3.0](LICENSE). Not affiliated with Valve or Steam.
