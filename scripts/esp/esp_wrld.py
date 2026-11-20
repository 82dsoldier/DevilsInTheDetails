import struct, zlib, sys
data = open(sys.argv[1], "rb").read()
def walk(i, end):
    while i < end:
        t = data[i:i+4].decode("latin1"); size = struct.unpack_from("<I", data, i+4)[0]
        if t == "GRUP": walk(i+24, i+size); i += size; continue
        if t == "WRLD":
            b = data[i+24:i+24+size]
            if struct.unpack_from("<I", data, i+8)[0] & 0x40000: b = zlib.decompress(b[4:])
            n = struct.unpack_from("<H", b, 4)[0]; print(b[6:6+n].rstrip(b"\0").decode())
        i += 24 + size
walk(0, len(data))
