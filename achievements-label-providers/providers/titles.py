"""Fuzzy title matching (word-set comparison, ignoring brackets, punctuation and "the")."""


def words(s):
    """Lower-case words of a title without brackets, punctuation and "the":
    "Final Fantasy X (USA)" -> ["final", "fantasy", "x"]."""
    out, cur, depth = [], [], 0

    def flush():
        if cur:
            w = "".join(cur)[:39]
            if w != "the":
                out.append(w)
            cur.clear()

    for ch in s:
        if ch in "([":
            flush()
            depth += 1
        elif ch in ")]" and depth:
            flush()
            depth -= 1
        elif depth == 0 and (ch.isalnum() or ord(ch) >= 0x80):
            cur.append(ch.lower())
        else:
            flush()
    flush()
    return out


def match(a, b):
    """2 = same words, 1 = every word of one is in the other, 0 = no."""
    aw, bw = words(a), words(b)
    if not aw or not bw:
        return 0
    in_b = sum(1 for w in aw if w in bw)
    in_a = sum(1 for w in bw if w in aw)
    if len(aw) == len(bw) and in_b == len(aw):
        return 2
    if in_b == len(aw) or in_a == len(bw):
        return 1
    return 0
