import struct, zlib
def records(typ, path="C:/Steam/steamapps/common/Fallout 4/Data/Fallout4.esm"):
    """Every (fid, flags, body) of one top-level type in the master."""
    d = open(path, "rb").read()
    p, typ = 0, typ.encode()
    while True:
        sz = struct.unpack_from("<I", d, p + 4)[0]
        if d[p:p + 4] == b"GRUP":
            if d[p + 8:p + 12] == typ:
                break
            p += sz
        else:
            p += 24 + sz
    stack = [(p + 24, p + sz)]
    while stack:
        p, end = stack.pop()
        while p < end:
            sz = struct.unpack_from("<I", d, p + 4)[0]
            if d[p:p + 4] == b"GRUP":
                stack.append((p + 24, p + sz)); p += sz; continue
            flags, fid = struct.unpack_from("<II", d, p + 8)
            b = d[p + 24:p + 24 + sz]
            yield fid, flags, (zlib.decompress(b[4:]) if flags & 0x40000 else b)
            p += 24 + sz
