"""Achievements Label Providers - backend.

Answers "how many achievements does this game have unlocked?" for games Steam itself has
no data for: RPCS3 trophies, RetroAchievements (needs your own API key), Alice's
MadnessPatch. Pure Python, no other software needed. The Big Picture column is drawn by
the "Achievements Label" plugin; this one only supplies numbers.
"""
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import decky  # provided by Decky Loader
    log = decky.logger
except Exception:  # running outside Decky (tests)
    log = logging.getLogger("achievements-label-providers")

from providers import config, core, rpcs3  # noqa: E402

TTL_FOUND = 90       # seconds a result is reused
TTL_RA = 300         # RetroAchievements is a network call: ask less often
TTL_MISSING = 120    # "nothing found" is remembered for less: setup or data may change


class Plugin:
    async def _main(self):
        self.cache = {}
        self.inflight = {}
        config.ensure_exists()

    async def _unload(self):
        pass

    async def get_progress(self, name: str, appid=None):
        """{"unlocked", "total", "source"} for a game, or None."""
        key = "%s|%s" % (appid, (name or "").strip().lower())
        hit = self.cache.get(key)
        if hit and time.time() < hit[0]:
            return hit[1]

        task = self.inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(self._run(name, appid))
            self.inflight[key] = task
        try:
            result = await task
        finally:
            if self.inflight.get(key) is task:
                self.inflight.pop(key, None)

        ttl = TTL_MISSING if not result else TTL_RA if result.get("source") == "RetroAchievements" else TTL_FOUND
        self.cache[key] = (time.time() + ttl, result)
        return result

    async def _run(self, name, appid):
        try:
            result = await asyncio.to_thread(core.lookup, name, appid)
            log.info("%r (app %s) -> %s", name, appid, result)
            return result
        except Exception:
            log.exception("lookup failed for %r", name)
            return None

    async def get_status(self):
        """For the plugin's panel: what is set up, and the last problem."""
        cfg = config.load()
        ra = cfg["retroachievements"]
        try:
            games = len(await asyncio.to_thread(rpcs3.trophy_dirs))
        except Exception:
            games = 0
        return {
            "ra_configured": bool(ra["user"] and ra["api_key"]),
            "ra_problem": core.status["retroachievements"],
            "rpcs3_games": games,
            "config_path": config.path(),
        }
