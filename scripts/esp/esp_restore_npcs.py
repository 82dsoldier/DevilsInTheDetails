"""Put the templated NPC bases (the paratroopers, SSG Brannock) back as they were before a CK save (it rewrites their unused race
field to SynthGen2RaceValentine, among other recalculations): their whole records from a known
good plugin."""
import sys, struct
from esplib import *
src, good, dst = sys.argv[1:4]
BASES = (0x010073D7, 0x010073EB, 0x01012D15, 0x01012D5B)   # the two paratroopers, SSG Brannock, Sergeant Airborne
top = parse(open(src, "rb").read())
old = {n.fid: n for n, *_ in walk(parse(open(good, "rb").read())) if isinstance(n, Rec)}
for n, *_ in walk(top):
    if isinstance(n, Rec) and n.fid in BASES:
        n.set_body(bytes(old[n.fid].body()))
        print(f"{n.fid:08X} restored, RNAM {dict(sublist(n.body()))[b'RNAM'].hex()}")
open(dst, "wb").write(b"".join(n.bytes() for n in top))
