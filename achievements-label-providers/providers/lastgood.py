"""Remember the last successful result per game, on disk, so a bad connection (or a restart)
does not make the column vanish: the old count keeps showing until a fresh one arrives."""
import json
import os
import time

from . import paths

MAX_ENTRIES = 300


def _path():
    return os.path.join(paths.cache_dir(), "last-known.json")


def _load():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key):
    entry = _load().get(key)
    if isinstance(entry, dict) and isinstance(entry.get("result"), dict):
        return entry["result"]
    return None


def put(key, result):
    data = _load()
    data[key] = {"result": result, "ts": time.time()}
    if len(data) > MAX_ENTRIES:  # drop the oldest
        for k, _ in sorted(data.items(), key=lambda kv: kv[1].get("ts", 0))[: len(data) - MAX_ENTRIES]:
            del data[k]
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _path())
    except OSError:
        pass
