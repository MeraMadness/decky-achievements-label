"""RetroAchievements: console guess, game lookup by title, user progress.

Needs the user's RA username and web API key (retroachievements.org -> Settings -> Keys),
kept in ~/.config/achievements-label/config.json. Never logged.
"""
import json
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from . import paths, titles

API = "https://retroachievements.org/API/"
LIST_TTL = 7 * 86400  # a console's game list changes slowly; refresh weekly


class RaAuthError(Exception):
    """RetroAchievements rejected the username / API key."""


class RaError(Exception):
    """Network or API trouble."""


# --------------------------------------------------------------------------- console guess

# Keyword -> RetroAchievements console id. Order matters: the first needle found wins.
_TABLE = [
    ("playstation 2", 21), ("ps2", 21), ("pcsx2", 21),
    ("playstation portable", 41), ("psp", 41), ("ppsspp", 41),
    ("game boy advance", 5), ("gba", 5), ("mgba", 5), ("visualboyadvance", 5),
    ("game boy color", 6), ("gbc", 6),
    ("game boy", 4), ("gameboy", 4), ("gb", 4), ("gambatte", 4),
    ("super nintendo", 3), ("snes", 3), ("super famicom", 3), ("snes9x", 3), ("bsnes", 3), ("zsnes", 3),
    ("nintendo entertainment system", 7), ("nes", 7), ("famicom", 7), ("fceux", 7), ("nestopia", 7),
    ("nintendo 64", 2), ("n64", 2), ("mupen64", 2), ("simple64", 2), ("project64", 2),
    ("nintendo ds", 18), ("nds", 18), ("melonds", 18), ("desmume", 18),
    ("gamecube", 16),
    ("mega drive", 1), ("megadrive", 1), ("genesis", 1),
    ("master system", 11), ("sms", 11), ("game gear", 15), ("sega cd", 9), ("mega cd", 9), ("32x", 10),
    ("saturn", 39), ("dreamcast", 40), ("flycast", 40), ("redream", 40),
    ("pc engine", 8), ("turbografx", 8), ("tg16", 8),
    ("atari 2600", 25), ("atari 7800", 51), ("lynx", 13), ("jaguar", 17),
    ("neo geo pocket", 14), ("neo geo cd", 56), ("wonderswan", 53), ("virtual boy", 28), ("3do", 43),
    ("arcade", 27), ("mame", 27), ("fbneo", 27),
    ("playstation", 12), ("psx", 12), ("ps1", 12), ("psone", 12), ("duckstation", 12),
]
_NOT_RA = (" ps3 ", " rpcs3 ", " playstation 3 ", " ps4 ", " vita ", " wii ", " switch ")


def guess_console(text):
    """RA console id from words like a Steam ROM Manager tag ("PS2") or an emulator's file
    name ("pcsx2-qt"). Text is lower-cased and non-alphanumerics become spaces. 0 = unknown."""
    if not text:
        return 0
    t = " " + re.sub(r"[^a-z0-9]", " ", text.lower()) + " "
    if any(n in t for n in _NOT_RA):
        return 0
    for needle, cid in _TABLE:
        if (" %s " % needle) in t:
            return cid
    return 0


# --------------------------------------------------------------------------- http

def _ssl_context():
    for cafile in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/cert.pem"):
        if os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def http_get_json(url, timeout=12):
    """GET and parse JSON. Raises RaAuthError on 401/403 and RaError for network trouble.

    Falls back to curl only when Python's TLS is unusable (some bundled Pythons lack CA
    certificates). A timeout or a dead connection fails fast instead: retrying through curl
    would just make a slow link twice as slow."""
    headers = {"User-Agent": "achievements-label/1.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RaAuthError("HTTP %d" % e.code)
        raise RaError("HTTP %d" % e.code)
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLError):
            raise RaError("network unavailable")
    except ssl.SSLError:
        pass
    except (TimeoutError, OSError):
        raise RaError("network unavailable")
    except ValueError:
        raise RaError("not JSON")
    try:
        out = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout), "-A", headers["User-Agent"], "-w", "\n%{http_code}", url],
            capture_output=True, timeout=timeout + 5,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
    except Exception as e:
        raise RaError("network unavailable (%s)" % type(e).__name__)
    body, _, code = out.stdout.decode("utf-8", "replace").rpartition("\n")
    if code in ("401", "403"):
        raise RaAuthError("HTTP " + code)
    if out.returncode != 0 or code != "200":
        raise RaError("curl failed (HTTP %s)" % (code or out.returncode))
    try:
        return json.loads(body)
    except ValueError:
        raise RaError("not JSON")


def _get(endpoint, user, key, **params):
    q = urllib.parse.urlencode(dict(z=user, y=key, **params))
    return http_get_json("%s%s?%s" % (API, endpoint, q))


# --------------------------------------------------------------------------- lookups

def _list_cache(console):
    return os.path.join(paths.cache_dir(), "ra-games-%d.json" % console)


def game_list(console, user, key, fetch=_get):
    path = _list_cache(console)
    try:
        if time.time() - os.path.getmtime(path) < LIST_TTL:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    games = fetch("API_GetGameList.php", user, key, i=console, f=1)
    if isinstance(games, list):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(games, f)
            os.replace(tmp, path)
        except OSError:
            pass
    return games if isinstance(games, list) else []


def find_game(console, name, user, key, fetch=_get):
    """RA game id whose title best matches `name` on that console, or None."""
    best, score = None, 0
    for g in game_list(console, user, key, fetch):
        s = titles.match(name, str(g.get("Title", "")))
        if s > score:
            best, score = g.get("ID"), s
            if s == 2:
                break
    return best


def progress(game_id, user, key, fetch=_get):
    """{"unlocked", "total", "source"} for one game and user, or None."""
    g = fetch("API_GetGameInfoAndUserProgress.php", user, key, g=game_id, u=user)
    achs = g.get("Achievements") if isinstance(g, dict) else None
    if not isinstance(achs, dict) or not achs:
        return None
    got = sum(1 for a in achs.values() if a.get("DateEarned") or a.get("DateEarnedHardcore"))
    return {"unlocked": got, "total": len(achs), "source": "RetroAchievements"}


def lookup(spec_console=None, spec_game=None, name="", user="", key="", fetch=_get):
    gid = spec_game
    if gid is None and spec_console:
        gid = find_game(spec_console, name, user, key, fetch)
    if not gid:
        return None
    return progress(gid, user, key, fetch)
