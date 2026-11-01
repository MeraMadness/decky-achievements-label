"""Offline tests with synthetic data. Run:  python3 -I tests/test_providers.py  (from the plugin folder)"""
import json
import os
import socket
import ssl
import struct
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers import config, core, lastgood, madness, paths, retro, rpcs3, shortcuts, titles, vdf  # noqa: E402


def vdf_str(key, val):
    return b"\x01" + key.encode() + b"\0" + val.encode() + b"\0"


def vdf_int(key, val):
    return b"\x02" + key.encode() + b"\0" + struct.pack("<I", val)


def vdf_dict(key, body):
    return b"\x00" + key.encode() + b"\0" + body + b"\x08"


def make_shortcuts(entries):
    body = b"".join(
        vdf_dict(str(i), vdf_int("appid", e["appid"]) + vdf_str("AppName", e["name"]) + vdf_str("Exe", e["exe"]) +
                 vdf_str("LaunchOptions", e.get("opts", "")) +
                 vdf_dict("tags", b"".join(vdf_str(str(j), t) for j, t in enumerate(e.get("tags", [])))))
        for i, e in enumerate(entries))
    return vdf_dict("shortcuts", body) + b"\x08"


def make_tropusr(unlocked_ids, all_ids):
    esz = 0x20
    header = bytearray(0x60)
    struct.pack_into(">I", header, 8, 1)                                   # one table
    struct.pack_into(">IIIIQ", header, 0x30, 6, esz, 0, len(all_ids), 0x60)  # type 6, records at 0x60
    recs = bytearray()
    for tid in all_ids:
        rec = bytearray(esz + 16)
        struct.pack_into(">II", rec, 16, tid, 1 if tid in unlocked_ids else 0)
        recs += rec
    return bytes(header) + bytes(recs)


class Env(unittest.TestCase):
    """Every test gets a throw-away HOME."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self._old = os.environ.get("HOME")
        os.environ["HOME"] = self.home
        core.reset()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old
        self.tmp.cleanup()

    def write(self, rel, data, mode="w"):
        p = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, mode) as f:
            f.write(data)
        return p


class TitleTests(unittest.TestCase):
    def test_words(self):
        self.assertEqual(titles.words("Final Fantasy X (USA) [!]"), ["final", "fantasy", "x"])
        self.assertEqual(titles.words("The Legend of Zelda"), ["legend", "of", "zelda"])
        self.assertEqual(titles.words("Disney•Pixar Brave"), ["disney•pixar", "brave"])

    def test_match(self):
        self.assertEqual(titles.match("Haunting Ground", "Haunting Ground"), 2)
        self.assertEqual(titles.match("haunting ground (USA)", "Haunting Ground"), 2)
        self.assertEqual(titles.match("Resident Evil", "Resident Evil 4"), 1)
        self.assertEqual(titles.match("Tetris", "Zelda"), 0)
        self.assertEqual(titles.match("", "x"), 0)


class VdfTests(Env):
    def test_shortcuts_roundtrip(self):
        data = make_shortcuts([
            {"appid": 3694795998, "name": "Haunting Ground", "exe": '"/usr/bin/pcsx2-qt"', "opts": "-batch -- rom.iso", "tags": ["PS2"]},
            {"appid": 5, "name": "Other", "exe": "/bin/x"},
        ])
        tree = vdf.parse(data)
        self.assertEqual(tree["shortcuts"]["0"]["appname"], "Haunting Ground")
        self.write(".local/share/Steam/userdata/1/config/shortcuts.vdf", data, "wb")
        items = shortcuts.load_all()
        sc = shortcuts.find(3694795998, "whatever", items)
        self.assertEqual(sc["tags"], ["PS2"])
        self.assertEqual(shortcuts.find(None, "other", items)["appid"], 5)
        self.assertIsNone(shortcuts.find(99, "nope", items))
        self.assertIn("PS2", shortcuts.hint(sc))

    def test_damaged_file_is_ignored(self):
        self.write(".local/share/Steam/userdata/1/config/shortcuts.vdf", b"\x00shortcuts\x00\x00garbage", "wb")
        self.assertEqual(shortcuts.load_all(), [])


class ConsoleGuessTests(unittest.TestCase):
    def test_guess(self):
        g = retro.guess_console
        self.assertEqual(g("PS2 /usr/bin/pcsx2-qt -batch"), 21)
        self.assertEqual(g("/usr/bin/ppsspp"), 41)
        self.assertEqual(g("Game Boy Advance"), 5)
        self.assertEqual(g("snes9x"), 3)
        self.assertEqual(g("rpcs3 --no-gui"), 0)          # PS3 is not on RetroAchievements
        self.assertEqual(g("PlayStation 3"), 0)
        self.assertEqual(g("PlayStation"), 12)
        self.assertEqual(g("notepad"), 0)
        self.assertEqual(g(""), 0)


class Rpcs3Tests(Env):
    CONF = ('<?xml version="1.0"?><trophyconf><title-name>Disney&amp;Pixar Brave</title-name>'
            '<trophy id="0" hidden="no" ttype="P"><name>Platinum</name><detail>All</detail></trophy>'
            '<trophy id="1" hidden="no" ttype="B"><name>A</name><detail>a</detail></trophy>'
            '<trophy id="2" hidden="yes" ttype="S"><name>B</name><detail>b</detail></trophy></trophyconf>')

    def make(self, unlocked):
        base = ".config/rpcs3/dev_hdd0/home/00000001/trophy/NPWR03056_00/"
        self.write(base + "TROPCONF.SFM", self.CONF)
        self.write(base + "TROPUSR.DAT", make_tropusr(unlocked, [0, 1, 2]), "wb")
        return os.path.join(self.home, base.rstrip("/"))

    def test_find_and_load(self):
        d = self.make({1})
        self.assertEqual(rpcs3.find("Disney&Pixar Brave"), d)
        self.assertEqual(rpcs3.find("anything", "NPWR03056_00"), d)
        self.assertIsNone(rpcs3.find("Unrelated Game"))
        self.assertEqual(rpcs3.load(d), {"unlocked": 1, "total": 3, "source": "RPCS3"})

    def test_all_and_none_unlocked(self):
        d = self.make({0, 1, 2})
        self.assertEqual(rpcs3.load(d)["unlocked"], 3)
        d = self.make(set())
        self.assertEqual(rpcs3.load(d)["unlocked"], 0)

    def test_missing_usr_file_means_zero(self):
        d = self.make({1})
        os.remove(os.path.join(d, "TROPUSR.DAT"))
        self.assertEqual(rpcs3.load(d), {"unlocked": 0, "total": 3, "source": "RPCS3"})

    def test_truncated_usr_does_not_crash(self):
        self.assertEqual(rpcs3.unlocked_ids(b"\0" * 10), set())
        self.assertIsInstance(rpcs3.unlocked_ids(make_tropusr({1}, [0, 1, 2])[:0x70]), set)


class MadnessTests(Env):
    def test_load(self):
        self.write(".local/share/Steam/steamapps/common/Alice Madness Returns/Binaries/Win32/Achievements/txt/en.txt",
                   "One|do a\nTwo|do b\n\nThree|do c\n")
        self.write(".local/share/Steam/steamapps/compatdata/19680/pfx/drive_c/users/steamuser/Documents/"
                   "My Games/Alice Madness Returns/AliceGame/CheckPoint/Profile0/Achievements.txt", "UnlockFlag=5\n")
        self.assertEqual(madness.load(), {"unlocked": 2, "total": 3, "source": "MadnessPatch"})  # bits 0 and 2

    def test_not_installed(self):
        self.assertIsNone(madness.load())


class RetroTests(Env):
    def fake(self, calls):
        def fetch(endpoint, user, key, **params):
            calls.append((endpoint, params))
            if endpoint == "API_GetGameList.php":
                return [{"ID": 1, "Title": "Other Game"}, {"ID": 777, "Title": "Haunting Ground"}]
            if endpoint == "API_GetGameInfoAndUserProgress.php":
                return {"Achievements": {"1": {"DateEarned": "2026-01-01 10:00:00"}, "2": {}, "3": {"DateEarnedHardcore": "x"}}}
            raise AssertionError(endpoint)
        return fetch

    def test_lookup_and_list_cache(self):
        calls = []
        f = self.fake(calls)
        res = retro.lookup(spec_console=21, name="Haunting Ground (USA)", user="u", key="k", fetch=f)
        self.assertEqual(res, {"unlocked": 2, "total": 3, "source": "RetroAchievements"})
        retro.lookup(spec_console=21, name="Haunting Ground", user="u", key="k", fetch=f)
        self.assertEqual([c[0] for c in calls].count("API_GetGameList.php"), 1)   # list cached on disk
        self.assertEqual(calls[1][1]["g"], 777)

    def test_no_match(self):
        self.assertIsNone(retro.lookup(spec_console=21, name="Nothing Like It", user="u", key="k", fetch=self.fake([])))

    def test_progress_without_achievements(self):
        self.assertIsNone(retro.progress(5, "u", "k", fetch=lambda *a, **k: {"Achievements": {}}))
        self.assertIsNone(retro.progress(5, "u", "k", fetch=lambda *a, **k: []))


class CoreTests(Env):
    def setup_config(self, **extra):
        cfg = {"retroachievements": {"user": "u", "api_key": "k"}, "overrides": {}}
        cfg.update(extra)
        self.write(".config/achievements-label/config.json", json.dumps(cfg))

    def test_ra_for_ps2_shortcut(self):
        self.setup_config()
        self.write(".local/share/Steam/userdata/1/config/shortcuts.vdf",
                   make_shortcuts([{"appid": 42, "name": "Haunting Ground", "exe": "/usr/bin/pcsx2-qt", "tags": ["PS2"]}]), "wb")
        calls = []
        res = core.lookup("Haunting Ground", 42, fetch=RetroTests.fake(self, calls))
        self.assertEqual(res["source"], "RetroAchievements")
        self.assertEqual(calls[0][1]["i"], 21)

    def test_ra_without_credentials(self):
        self.write(".config/achievements-label/config.json", "{}")
        self.write(".local/share/Steam/userdata/1/config/shortcuts.vdf",
                   make_shortcuts([{"appid": 42, "name": "Haunting Ground", "exe": "pcsx2", "tags": ["PS2"]}]), "wb")
        self.assertIsNone(core.lookup("Haunting Ground", 42))
        self.assertIn("api_key", core.status["retroachievements"])

    def test_ra_auth_error_is_reported(self):
        self.setup_config()
        self.write(".local/share/Steam/userdata/1/config/shortcuts.vdf",
                   make_shortcuts([{"appid": 42, "name": "G", "exe": "pcsx2"}]), "wb")

        def bad(*a, **k):
            raise retro.RaAuthError("HTTP 401")
        self.assertIsNone(core.lookup("G", 42, fetch=bad))
        self.assertIn("rejected", core.status["retroachievements"])

    def test_rpcs3_by_title_when_no_console(self):
        self.setup_config()
        base = ".config/rpcs3/dev_hdd0/home/00000001/trophy/NPWR1_00/"
        self.write(base + "TROPCONF.SFM", Rpcs3Tests.CONF)
        self.write(base + "TROPUSR.DAT", make_tropusr({0}, [0, 1, 2]), "wb")
        self.assertEqual(core.lookup("Disney&Pixar Brave", 7)["source"], "RPCS3")
        self.assertIsNone(core.lookup("Unrelated", 8))

    def test_overrides(self):
        self.setup_config(overrides={"Some Game": "none", "9": "ra:777"})
        self.assertIsNone(core.lookup("some game", 1))
        calls = []
        res = core.lookup("Whatever", 9, fetch=RetroTests.fake(self, calls))
        self.assertEqual(res["total"], 3)
        self.assertEqual(calls[0][1]["g"], 777)

    def test_madness_by_appid(self):
        self.setup_config()
        self.write(".local/share/Steam/steamapps/common/Alice Madness Returns/Binaries/Win32/Achievements/txt/en.txt", "A|x\nB|y\n")
        self.write(".local/share/Steam/steamapps/compatdata/19680/pfx/drive_c/users/u/Documents/AliceGame/CheckPoint/P/Achievements.txt", "UnlockFlag=1")
        self.assertEqual(core.lookup("Alice: Madness Returns", 19680)["unlocked"], 1)

    def test_config_template_is_created_private(self):
        config.ensure_exists()
        p = config.path()
        self.assertTrue(os.path.exists(p))
        self.assertEqual(oct(os.stat(p).st_mode & 0o777), "0o600")
        self.assertEqual(config.load()["retroachievements"], {"user": "", "api_key": ""})

    def test_broken_config_falls_back_to_defaults(self):
        self.write(".config/achievements-label/config.json", "{not json")
        self.assertEqual(config.load()["overrides"], {})


class BadConnectionTests(Env):
    """A poor connection must not make the column vanish or the plugin hammer the network."""

    def setUp(self):
        super().setUp()
        cfg = {"retroachievements": {"user": "u", "api_key": "k"}, "overrides": {}}
        self.write(".config/achievements-label/config.json", json.dumps(cfg))
        self.write(".local/share/Steam/userdata/1/config/shortcuts.vdf",
                   make_shortcuts([{"appid": 42, "name": "Haunting Ground", "exe": "pcsx2", "tags": ["PS2"]}]), "wb")

    @staticmethod
    def offline(*a, **k):
        raise retro.RaError("network unavailable")

    def test_last_known_count_is_kept_when_offline(self):
        good = core.lookup("Haunting Ground", 42, fetch=RetroTests.fake(self, []))
        self.assertEqual(good["total"], 3)
        core.reset()
        self.assertEqual(core.lookup("Haunting Ground", 42, fetch=self.offline), good)   # served from disk
        self.assertIn("last known", core.status["retroachievements"])

    def test_last_known_survives_a_restart(self):
        core.lookup("Haunting Ground", 42, fetch=RetroTests.fake(self, []))
        self.assertEqual(lastgood.get("42|haunting ground")["total"], 3)   # a fresh process reads the same file

    def test_offline_with_nothing_saved_is_none_not_a_crash(self):
        self.assertIsNone(core.lookup("Haunting Ground", 42, fetch=self.offline))

    def test_backoff_stops_further_requests(self):
        calls = []

        def counting(*a, **k):
            calls.append(1)
            raise retro.RaError("network unavailable")
        core.lookup("Haunting Ground", 42, fetch=counting)
        n = len(calls)
        for _ in range(5):
            core.lookup("Haunting Ground", 42, fetch=counting)
        self.assertEqual(len(calls), n)          # no network traffic while backing off

    def test_backoff_ends_and_recovery_updates_the_count(self):
        core.lookup("Haunting Ground", 42, fetch=self.offline)
        core.reset()                              # as if BACKOFF_S had passed
        res = core.lookup("Haunting Ground", 42, fetch=RetroTests.fake(self, []))
        self.assertEqual(res["total"], 3)
        self.assertEqual(core.status["retroachievements"], "")

    def test_auth_error_does_not_start_a_backoff(self):
        def bad(*a, **k):
            raise retro.RaAuthError("HTTP 401")
        core.lookup("Haunting Ground", 42, fetch=bad)
        res = core.lookup("Haunting Ground", 42, fetch=RetroTests.fake(self, []))   # fixed key works at once
        self.assertEqual(res["total"], 3)

    def test_last_known_store_is_bounded(self):
        for i in range(lastgood.MAX_ENTRIES + 20):
            lastgood.put("k%d" % i, {"unlocked": 0, "total": 1, "source": "x"})
        self.assertLessEqual(len(lastgood._load()), lastgood.MAX_ENTRIES)
        self.assertIsNotNone(lastgood.get("k%d" % (lastgood.MAX_ENTRIES + 19)))     # newest kept

    def test_corrupt_store_is_ignored(self):
        self.write(".cache/achievements-label/last-known.json", "{broken")
        self.assertIsNone(lastgood.get("x"))
        lastgood.put("x", {"unlocked": 1, "total": 2, "source": "s"})
        self.assertEqual(lastgood.get("x")["total"], 2)


class HttpFailureTests(unittest.TestCase):
    """Fail fast on a dead or slow link; use curl only for TLS trouble."""

    def run_with(self, exc):
        with mock.patch("urllib.request.urlopen", side_effect=exc), \
             mock.patch("subprocess.run", side_effect=AssertionError("curl must not be used")) as curl:
            with self.assertRaises(retro.RaError):
                retro.http_get_json("https://example.invalid/x")
            curl.assert_not_called()

    def test_timeout_fails_fast(self):
        self.run_with(socket.timeout("timed out"))

    def test_no_route_fails_fast(self):
        self.run_with(urllib.error.URLError(OSError(101, "Network is unreachable")))

    def test_dns_failure_fails_fast(self):
        self.run_with(urllib.error.URLError(socket.gaierror(-3, "Temporary failure in name resolution")))

    def test_connection_reset_fails_fast(self):
        self.run_with(ConnectionResetError())

    def test_http_401_is_an_auth_error(self):
        err = urllib.error.HTTPError("u", 401, "no", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(retro.RaAuthError):
                retro.http_get_json("https://example.invalid/x")

    def test_http_500_is_a_plain_error(self):
        err = urllib.error.HTTPError("u", 500, "boom", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(retro.RaError):
                retro.http_get_json("https://example.invalid/x")

    def test_tls_problem_falls_back_to_curl(self):
        done = mock.Mock(returncode=0, stdout=b'[{"ID": 1}]\n200')
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(ssl.SSLError("bad cert"))), \
             mock.patch("subprocess.run", return_value=done):
            self.assertEqual(retro.http_get_json("https://example.invalid/x"), [{"ID": 1}])

    def test_garbage_body_is_an_error(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = b"<html>captive portal</html>"
        with mock.patch("urllib.request.urlopen", return_value=resp):
            with self.assertRaises(retro.RaError):
                retro.http_get_json("https://example.invalid/x")


class PathTests(Env):
    def test_home_follows_env(self):
        self.assertEqual(paths.user_home(), self.home)


if __name__ == "__main__":
    unittest.main()
