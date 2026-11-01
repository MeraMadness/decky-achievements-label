"""User settings: ~/.config/achievements-label/config.json

{
  "retroachievements": { "user": "", "api_key": "" },
  "overrides": { "Some Game": "ra-console:21" }
}

Override values: "none" | "ra:<game id>" | "ra-console:<console id>" | "rpcs3:<NPWR id>" | "madness".
Keys are a game's name (any case) or its Steam app id as text.
"""
import json
import os

from . import paths

DEFAULT = {"retroachievements": {"user": "", "api_key": ""}, "overrides": {}}


def path():
    return os.path.join(paths.config_dir(), "config.json")


def load():
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return json.loads(json.dumps(DEFAULT))
    cfg = json.loads(json.dumps(DEFAULT))
    if isinstance(data, dict):
        ra = data.get("retroachievements")
        if isinstance(ra, dict):
            cfg["retroachievements"].update({k: str(v) for k, v in ra.items() if k in ("user", "api_key")})
        ov = data.get("overrides")
        if isinstance(ov, dict):
            cfg["overrides"] = {str(k): str(v) for k, v in ov.items()}
    return cfg


def ensure_exists():
    """Create the template on first run so users can see what to fill in."""
    p = path()
    if os.path.exists(p):
        return
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(DEFAULT, f, indent=2)
            f.write("\n")
        os.chmod(p, 0o600)  # holds an API key
        if os.geteuid() == 0:  # keep it the user's file, not root's
            st = os.stat(paths.user_home())
            os.chown(os.path.dirname(p), st.st_uid, st.st_gid)
            os.chown(p, st.st_uid, st.st_gid)
    except OSError:
        pass


def override_for(cfg, name, appid):
    ov = cfg.get("overrides", {})
    if appid is not None and str(appid) in ov:
        return ov[str(appid)].strip().lower()
    low = (name or "").strip().lower()
    for k, v in ov.items():
        if k.strip().lower() == low:
            return v.strip().lower()
    return None
