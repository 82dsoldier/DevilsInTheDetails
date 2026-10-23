"""Read files out of Fallout 4's general (GNRL) .ba2 archives, such as "Fallout4 - Meshes.ba2"
and "Fallout4 - Materials.ba2". Texture archives (DX10) aren't supported.

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
