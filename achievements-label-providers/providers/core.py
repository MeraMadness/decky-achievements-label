"""Decide which provider answers for a game, and ask it. Blocking: run it in a thread."""
import time

from . import config, lastgood, madness, retro, rpcs3, shortcuts

MADNESS_APPID = madness.APPID

# Latest human-readable problem per source, shown in the plugin's panel.
status = {"retroachievements": "", "rpcs3": "", "last": ""}

# After a network failure RetroAchievements is not contacted again for this long.
BACKOFF_S = 300
_ra_down_until = 0.0


def reset():
    """Forget the backoff (used by tests)."""
    global _ra_down_until
    _ra_down_until = 0.0


def lookup(name, appid=None, fetch=retro._get):
    """{"unlocked", "total", "source"} for a game, or None if no provider knows it."""
    cfg = config.load()
    ov = config.override_for(cfg, name, appid)
    if ov == "none":
        return None

    spec = ov
    if spec is None:
        if appid == MADNESS_APPID:
            spec = "madness"
        else:
            console = retro.guess_console(shortcuts.hint(shortcuts.find(appid, name)))
            spec = "ra-console:%d" % console if console else "rpcs3-auto"

    if spec == "madness":
        return madness.load()
    if spec.startswith("rpcs3:") or spec == "rpcs3-auto":
        path = rpcs3.find(name, spec[6:] if spec.startswith("rpcs3:") else None)
        return rpcs3.load(path) if path else None

    if spec.startswith(("ra:", "ra-console:")):
        ra = cfg["retroachievements"]
        if not ra["user"] or not ra["api_key"]:
            status["retroachievements"] = "Not set up: add user and api_key to " + config.path()
            return None
        key = "%s|%s" % (appid, (name or "").strip().lower())
        global _ra_down_until
        if time.time() < _ra_down_until:  # connection was bad a moment ago: don't hammer it
            return lastgood.get(key)
        try:
            if spec.startswith("ra:"):
                res = retro.lookup(spec_game=int(spec[3:]), user=ra["user"], key=ra["api_key"], fetch=fetch)
            else:
                res = retro.lookup(spec_console=int(spec[11:]), name=name, user=ra["user"], key=ra["api_key"], fetch=fetch)
        except retro.RaAuthError:
            status["retroachievements"] = "RetroAchievements rejected the user / API key"
            return None
        except retro.RaError as e:
            _ra_down_until = time.time() + BACKOFF_S
            status["retroachievements"] = "%s; showing the last known counts, retrying in %d min" % (e, BACKOFF_S // 60)
            return lastgood.get(key)
        except ValueError as e:
            status["retroachievements"] = "Bad override: %s" % e
            return None
        status["retroachievements"] = ""
        if res:
            lastgood.put(key, res)
        return res
    return None
