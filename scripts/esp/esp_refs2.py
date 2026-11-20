import struct, zlib, sys
data = open(sys.argv[1], "rb").read()
want = {0x01006479: "old red light", 0x01006478: "old red", 0x0100647A: "old green", 0x0100647B: "old green",
        0x010073B3: "RedPort", 0x010073B4: "RedStbd", 0x010073B5: "GreenPort", 0x010073B6: "GreenStbd",
        0x01005CD3: "interior green", 0x01005CD4: "interior green", 0x01005CD5: "interior red", 0x01005CD6: "interior red"}
def walk(i, end):
    while i < end:
        t = data[i:i+4]; size = struct.unpack_from("<I", data, i+4)[0]
        if t == b"GRUP": walk(i+24, i+size); i += size; continue
        flags, fid = struct.unpack_from("<II", data, i+8)
        b = data[i+24:i+24+size]
        if flags & 0x40000: b = zlib.decompress(b[4:])
        for k, v in want.items():
            if struct.pack("<I", k) in b and k != fid:
                print(t.decode(), hex(fid), "refers to", v, hex(k))
        i += 24 + size
walk(0, len(data))
