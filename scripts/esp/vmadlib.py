import struct
def ws(b, i):
    n = struct.unpack_from("<H", b, i)[0]; return b[i+2:i+2+n].decode("latin1"), i + 2 + n
def pws(s): s = s.encode("latin1"); return struct.pack("<H", len(s)) + s
SIZES = {1: 8, 3: 4, 4: 4, 5: 1}
def val(b, i, t):
    if t in SIZES: return b[i:i+SIZES[t]], i + SIZES[t]
    if t == 2: s, j = ws(b, i); return b[i:j], j
    if t in (11, 13, 14, 15):
        n = struct.unpack_from("<I", b, i)[0]; j = i + 4 + n * SIZES[t - 10]; return b[i:j], j
    if t == 12:
        n = struct.unpack_from("<I", b, i)[0]; j = i + 4
        for _ in range(n): _, j = ws(b, j)
        return b[i:j], j
    raise ValueError(f"property type {t}")
def parse(b):
    ver, fmt, n = struct.unpack_from("<hhH", b, 0); i = 6; scripts = []
    for _ in range(n):
        name, i = ws(b, i); status = b[i]; np_ = struct.unpack_from("<H", b, i+1)[0]; i += 3; props = []
        for _ in range(np_):
            pn, i = ws(b, i); t, st = b[i], b[i+1]; i += 2; v, i = val(b, i, t); props.append([pn, t, st, v])
        scripts.append([name, status, props])
    return ver, fmt, scripts, b[i:]
def build(ver, fmt, scripts, rest):
    out = struct.pack("<hhH", ver, fmt, len(scripts))
    for name, status, props in scripts:
        out += pws(name) + bytes([status]) + struct.pack("<H", len(props))
        for pn, t, st, v in props: out += pws(pn) + bytes([t, st]) + v
    return out + rest
def obj_array(fids): return struct.pack("<I", len(fids)) + b"".join(struct.pack("<HhI", 0, -1, f) for f in fids)
