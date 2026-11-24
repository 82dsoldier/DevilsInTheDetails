"""Read files out of Fallout 4's .ba2 archives: general ones (GNRL), such as "Fallout4 -
Meshes.ba2" and "Fallout4 - Materials.ba2", and the texture ones (DX10, "Fallout4 -
Textures*.ba2"), a texture's largest image only (texture()), as a PIL image.

    python scripts/ba2.py list "<Fallout 4>/Data/Fallout4 - Meshes.ba2" "lod.*\\.nif$"
    python scripts/ba2.py extract "<Fallout 4>/Data/Fallout4 - Meshes.ba2" "Financial15_Bld01LOD" out_dir
"""
import re
import struct
import sys
import zlib
from pathlib import Path


def _records(path):
    f = open(path, "rb")
    magic, _, kind, n, names_off = struct.unpack("<4sI4sIQ", f.read(24))
    if magic != b"BTDX" or kind != b"GNRL":
        raise ValueError(f"{path} isn't a general BA2 archive")
    recs = [struct.unpack("<I4sIIQIII", f.read(36)) for _ in range(n)]
    f.seek(names_off)
    names = []
    for _ in range(n):
        (ln,) = struct.unpack("<H", f.read(2))
        names.append(f.read(ln).decode("utf-8", "replace"))
    return f, recs, names


def _data(f, rec):
    _, _, _, _, off, packed, size, _ = rec
    f.seek(off)
    data = f.read(packed or size)
    return zlib.decompress(data) if packed else data


def read(archive, name):
    """The bytes of one file, by its path in the archive (case and slashes don't matter)."""
    want = name.replace("/", "\\").lower()
    f, recs, names = _records(archive)
    with f:
        for rec, nm in zip(recs, names):
            if nm.lower() == want:
                return _data(f, rec)
    raise FileNotFoundError(f"{name} not in {archive}")


DXGI_FOURCC = {71: b"DXT1", 72: b"DXT1", 74: b"DXT3", 77: b"DXT5", 78: b"DXT5", 80: b"ATI1",
               83: b"ATI2"}


def texture(archive, name):
    """A texture's largest image from a DX10 archive, as a PIL image (its name as in the
    archive, case and slashes don't matter)."""
    import io
    from PIL import Image
    want = name.replace("/", "\\").lower()
    with open(archive, "rb") as f:
        magic, _, kind, n, names_off = struct.unpack("<4sI4sIQ", f.read(24))
        if magic != b"BTDX" or kind != b"DX10":
            raise ValueError(f"{archive} isn't a texture BA2 archive")
        recs = []
        for _ in range(n):
            (_, _, _, _, chunks, _, h, w, mips, fmt, _) = struct.unpack("<I4sIBBHHHBBH", f.read(24))
            ch = [struct.unpack("<QIIHHI", f.read(24)) for _ in range(chunks)]
            recs.append((h, w, mips, fmt, ch))
        f.seek(names_off)
        for (h, w, mips, fmt, ch) in recs:
            (ln,) = struct.unpack("<H", f.read(2))
            nm = f.read(ln).decode("utf-8", "replace")
            if nm.lower() != want:
                continue
            off, packed, size, start, end, _ = ch[0]
            f.seek(off)
            data = f.read(packed or size)
            data = zlib.decompress(data) if packed else data
            if fmt == 98 or fmt == 99:                      # BC7: a DX10 DDS header
                hdr = struct.pack("<4sIIIIIII44xII4sIIIII5I", b"DDS ", 124, 0x1007 | 0x20000, h, w, len(data), 0, 1,
                                  32, 4, b"DX10", 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0) + struct.pack("<IIIII", fmt, 3, 0, 1, 0)
            else:
                four = DXGI_FOURCC.get(fmt)
                if four is None:
                    raise ValueError(f"{name}: DXGI format {fmt} not handled")
                hdr = struct.pack("<4sIIIIIII44xII4sIIIII5I", b"DDS ", 124, 0x1007 | 0x80000, h, w, len(data), 0, 1,
                                  32, 4, four, 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
            return Image.open(io.BytesIO(hdr + data)).convert("RGBA")
    raise FileNotFoundError(f"{name} not in {archive}")


def main():
    cmd, archive, pattern = sys.argv[1:4]
    rx = re.compile(pattern, re.I)
    f, recs, names = _records(archive)
    with f:
        for rec, nm in zip(recs, names):
            if not rx.search(nm):
                continue
            if cmd == "list":
                print(nm)
            else:
                dest = Path(sys.argv[4]) / nm.replace("\\", "/")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(_data(f, rec))
                print(dest)


if __name__ == "__main__":
    main()
