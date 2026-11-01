"""Non-Steam shortcuts (what Steam ROM Manager writes): name, exe, launch options, tags."""
import glob
import os

from . import paths, vdf


def load_all():
    out = []
    for root in paths.steam_roots():
        for f in glob.glob(os.path.join(root, "userdata", "*", "config", "shortcuts.vdf")):
            try:
                with open(f, "rb") as fh:
                    tree = vdf.parse(fh.read())
            except Exception:
                continue
            entries = tree.get("shortcuts", {})
            for e in entries.values():
                if not isinstance(e, dict):
                    continue
                tags = e.get("tags", {})
                out.append({
                    "appid": e.get("appid"),
                    "name": e.get("appname", ""),
                    "exe": e.get("exe", ""),
                    "opts": e.get("launchoptions", ""),
                    "tags": [v for v in tags.values() if isinstance(v, str)] if isinstance(tags, dict) else [],
                })
    return out


def find(appid=None, name=None, shortcuts=None):
    """The shortcut with this Steam app id (preferred) or exact name, or None."""
    items = load_all() if shortcuts is None else shortcuts
    if appid is not None:
        for s in items:
            if s["appid"] == appid:
                return s
    if name:
        low = name.strip().lower()
        for s in items:
            if s["name"].strip().lower() == low:
                return s
    return None


def hint(shortcut):
    """Text to guess the console from: tags, the executable and its launch options."""
    if not shortcut:
        return ""
    return " ".join(shortcut["tags"] + [shortcut["exe"], shortcut["opts"]])
