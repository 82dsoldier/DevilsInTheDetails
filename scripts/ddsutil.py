"""DDS textures with mipmaps.

Pillow writes BC1/BC3 DDS files without mipmaps, and a texture without them shimmers into
moiré at a distance (fine corrugation came out as rings across a hangar ceiling). This writes
every level down to 4 x 4: each compressed by Pillow, the level data joined after one header.
"""
import io
import struct

from PIL import Image

DDSD_MIPMAPCOUNT = 0x20000
DDSCAPS_COMPLEX, DDSCAPS_MIPMAP = 0x8, 0x400000


def save_dds(img, path, pixel_format="DXT1"):
    """Save a PIL image as a BC1 (DXT1) or BC3 (DXT5) DDS with a full mip chain. Its sides
    should be powers of two."""
    levels, w, h = [], img.width, img.height
    while True:
        buf = io.BytesIO()
        img.resize((w, h), Image.LANCZOS).save(buf, format="DDS", pixel_format=pixel_format)
        levels.append(buf.getvalue())
        if w <= 4 or h <= 4:
            break
        w, h = max(4, w // 2), max(4, h // 2)
    first = bytearray(levels[0])
    flags = struct.unpack_from("<I", first, 8)[0]
    struct.pack_into("<I", first, 8, flags | DDSD_MIPMAPCOUNT)
    struct.pack_into("<I", first, 28, len(levels))
    caps = struct.unpack_from("<I", first, 108)[0]
    struct.pack_into("<I", first, 108, caps | DDSCAPS_COMPLEX | DDSCAPS_MIPMAP)
    header = 128 + (20 if first[84:88] == b"DX10" else 0)
    data = bytes(first) + b"".join(lv[header:] for lv in levels[1:])
    with open(path, "wb") as f:
        f.write(data)
