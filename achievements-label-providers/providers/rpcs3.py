"""PS3 trophies from RPCS3's trophy folders.

<home>/.config/rpcs3/dev_hdd0/home/<user>/trophy/NPWRxxxxx_00/
    TROPCONF.SFM  - XML: title and the list of trophies
    TROPUSR.DAT   - big-endian binary: which trophies are unlocked
"""
import html
import os
import re
import struct

from . import paths, titles

ROOTS = (".config/rpcs3/dev_hdd0/home", ".var/app/net.rpcs3.RPCS3/config/rpcs3/dev_hdd0/home")


def trophy_dirs():
    """[(dir, title)] for every game that has trophy data."""
    out = []
    home = paths.user_home()
    for rel in ROOTS:
        root = os.path.join(home, rel)
        if not os.path.isdir(root):
            continue
        for user in sorted(os.listdir(root)):
            tdir = os.path.join(root, user, "trophy")
            if not os.path.isdir(tdir):
                continue
            for d in sorted(os.listdir(tdir)):
                if not d.startswith("NPWR"):
                    continue
                path = os.path.join(tdir, d)
                try:
                    with open(os.path.join(path, "TROPCONF.SFM"), encoding="utf-8", errors="replace") as f:
                        m = re.search(r"<title-name>(.*?)</title-name>", f.read(), re.S)
                except OSError:
                    continue
                if m:
                    out.append((path, html.unescape(m.group(1)).strip()))
    return out


def find(name, spec=None):
    """The trophy dir for a game: an explicit NPWR id, or the best title match."""
    dirs = trophy_dirs()
    if spec:
        return next((d for d, _ in dirs if os.path.basename(d) == spec), None)
    best, score = None, 0
    for d, title in dirs:
        s = titles.match(name, title)
        if s > score:
            best, score = d, s
    return best


def unlocked_ids(usr):
    """Ids of unlocked trophies from a TROPUSR.DAT; table type 6 has one record per trophy."""
    ids = set()
    if len(usr) <= 0x50:
        return ids
    ntab = struct.unpack_from(">I", usr, 8)[0]
    for ti in range(ntab):
        off = 0x30 + ti * 0x20
        if off + 0x20 > len(usr):
            break
        ttype, esz, _, cnt, toff = struct.unpack_from(">IIIIQ", usr, off)
        if ttype != 6:
            continue
        for n in range(cnt):
            at = toff + n * (esz + 16)
            if at + 16 + 24 > len(usr):
                break
            rec = at + 16
            tid, state = struct.unpack_from(">II", usr, rec)
            if state != 0:
                ids.add(tid)
    return ids


def load(path):
    """{"unlocked": n, "total": m, "source": "RPCS3"} or None."""
    try:
        with open(os.path.join(path, "TROPCONF.SFM"), encoding="utf-8", errors="replace") as f:
            conf = f.read()
    except OSError:
        return None
    ids = [int(i) for i in re.findall(r'<trophy id="(\d+)"', conf)]
    if not ids:
        return None
    try:
        with open(os.path.join(path, "TROPUSR.DAT"), "rb") as f:
            got = unlocked_ids(f.read())
    except OSError:
        got = set()
    return {"unlocked": sum(1 for i in ids if i in got), "total": len(ids), "source": "RPCS3"}
