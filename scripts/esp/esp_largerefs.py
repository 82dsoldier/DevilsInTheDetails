"""Put Fallout4.esm's large-reference table (RNAM) back into the plugin's overrides of vanilla
worldspaces (the Commonwealth, which the plugin overrides to hold the barricade door north of
Lexington).

The winning WRLD record's RNAM list tells the engine which large references (big buildings,
structures) to load from afar. An override without it (the CK writes ours without it) wipes the
table for the whole worldspace, and interior-to-Commonwealth loads got slow (the author,
2026-11-25). Safe to rerun; run it after every CK save, with esp_restore_npcs.py.

    python scripts/esp/esp_largerefs.py in.esp out.esp
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from esplib import Rec, parse, walk                              # noqa: E402
from esmscan import records                                      # noqa: E402


def raw_subs(b):
    """(type, raw bytes incl. header and any XXXX prefix) of each subrecord."""
    i, out = 0, []
    while i < len(b):
        t, n = b[i:i+4], struct.unpack_from("<H", b, i+4)[0]
        if t == b"XXXX":
            big = struct.unpack_from("<I", b, i+6)[0]
            t2 = b[i+10:i+14]
            out.append((t2, b[i:i+16+big])); i += 16 + big
        else:
            out.append((t, b[i:i+6+n])); i += 6 + n
    return out


def main(src, dst):
    data = Path(src).read_bytes()
    nodes = parse(data)
    mine = {n.fid: n for n, *_ in walk(nodes)
            if isinstance(n, Rec) and n.type == "WRLD" and n.fid < 0x01000000}
    if not mine:
        print("no vanilla worldspace overrides"); return
    fixed = 0
    for fid, fl, vb in records("WRLD"):
        if fid not in mine:
            continue
        rnam = [r for t, r in raw_subs(vb) if t == b"RNAM"]
        rec = mine[fid]
        subs = raw_subs(rec.body())
        have = sum(t == b"RNAM" for t, _ in subs)
        if have == len(rnam):
            print(f"{fid:08X}: {have} RNAM already"); continue
        rest = [r for t, r in subs if t != b"RNAM"]
        at = 1 if subs and subs[0][0] == b"EDID" else 0      # vanilla order: EDID, RNAM...
        rec.set_body(b"".join(rest[:at] + rnam + rest[at:]))
        print(f"{fid:08X}: RNAM {have} -> {len(rnam)}")
        fixed += 1
    out = b"".join(n.bytes() for n in nodes)
    Path(dst).write_bytes(out)
    print(f"wrote {dst} ({len(out)} bytes, {fixed} fixed)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
