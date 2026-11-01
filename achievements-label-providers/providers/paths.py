"""Where things live. Everything is relative to the *user's* home, not root's."""
import os


def user_home():
    try:
        import decky  # provided by Decky Loader
        home = getattr(decky, "DECKY_USER_HOME", None)
        if home:
            return home
    except Exception:
        pass
    return os.path.expanduser("~")


def config_dir():
    return os.path.join(user_home(), ".config", "achievements-label")


def cache_dir():
    return os.path.join(user_home(), ".cache", "achievements-label")


def steam_roots():
    """Steam installs plus every library folder listed in libraryfolders.vdf."""
    import re
    home = user_home()
    mains = [
        os.path.join(home, ".local/share/Steam"),
        os.path.join(home, ".steam/steam"),
        os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/Steam"),
    ]
    roots = []
    for m in mains:
        if not os.path.isdir(m):
            continue
        real = os.path.realpath(m)
        if real not in roots:
            roots.append(real)
        try:
            with open(os.path.join(m, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="replace") as f:
                for p in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                    p = os.path.realpath(p)
                    if p not in roots and os.path.isdir(p):
                        roots.append(p)
        except OSError:
            pass
    return roots
