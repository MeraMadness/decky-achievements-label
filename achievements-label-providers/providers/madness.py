"""Alice: Madness Returns with MadnessPatch (github.com/Wemino/MadnessPatch), Steam app 19680.

The patch keeps unlocked achievements as bits in
  <prefix>/.../Documents/.../AliceGame/CheckPoint/<profile>/Achievements.txt   ("UnlockFlag=<number>")
and installs the names ("Name|Requirement" per line) next to the game:
  <game>/Binaries/Win32/Achievements/txt/en.txt
"""
import glob
import os
import re

from . import paths

APPID = 19680


def _find():
    assets = unlock = None
    best_t = -1
    for root in paths.steam_roots():
        common = os.path.join(root, "steamapps", "common")
        if assets is None and os.path.isdir(common):
            for d in sorted(os.listdir(common)):
                if d.lower().startswith("alice"):
                    cand = os.path.join(common, d, "Binaries", "Win32", "Achievements")
                    if os.path.isdir(cand):
                        assets = cand
                        break
        users = os.path.join(root, "steamapps", "compatdata", str(APPID), "pfx", "drive_c", "users")
        for sub in ("Documents/My Games/Alice Madness Returns/AliceGame/CheckPoint", "Documents/AliceGame/CheckPoint"):
            for f in glob.glob(os.path.join(users, "*", sub, "*", "Achievements.txt")):
                t = os.path.getmtime(f)
                if t > best_t:
                    unlock, best_t = f, t
    return assets, unlock


def load():
    assets, unlock = _find()
    if not assets or not unlock:
        return None
    try:
        with open(unlock, encoding="utf-8", errors="replace") as f:
            m = re.search(r"UnlockFlag=(\d+)", f.read())
        bits = int(m.group(1)) if m else 0
        with open(os.path.join(assets, "txt", "en.txt"), encoding="utf-8", errors="replace") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()][:64]
    except OSError:
        return None
    if not lines:
        return None
    return {"unlocked": sum((bits >> i) & 1 for i in range(len(lines))), "total": len(lines), "source": "MadnessPatch"}
