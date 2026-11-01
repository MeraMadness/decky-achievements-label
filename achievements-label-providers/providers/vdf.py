"""Reader for Valve's binary VDF (shortcuts.vdf): type byte, NUL-terminated key, value.
0 = nested dict, 1 = string, 2 = uint32, 7 = uint64, 8 = end of dict."""
import struct


def parse(data):
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b"\0", pos)
        s = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return s

    def read_dict(depth=0):
        nonlocal pos
        if depth > 12:
            raise ValueError("vdf nested too deeply")
        d = {}
        while pos < len(data):
            t = data[pos]
            pos += 1
            if t == 8:
                return d
            key = cstr()
            if t == 0:
                d[key.lower()] = read_dict(depth + 1)
            elif t == 1:
                d[key.lower()] = cstr()
            elif t == 2:
                d[key.lower()] = struct.unpack_from("<I", data, pos)[0]
                pos += 4
            elif t == 7:
                d[key.lower()] = struct.unpack_from("<Q", data, pos)[0]
                pos += 8
            else:
                raise ValueError("unknown vdf type %d" % t)
        return d

    return read_dict()
