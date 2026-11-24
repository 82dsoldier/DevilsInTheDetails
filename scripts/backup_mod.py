"""Back up the mod as installed: the plugin into the repository, and the plugin and every file the
mod installs to OneDrive (offsite).

The plugin holds work no script can rebuild (the navmesh, anything done in the Creation Kit), so
it's kept in the repository (plugin/DevilsInTheDetails.esp, committed like any other change) and
as a dated copy in OneDrive each time. The mod's other files (meshes, textures, sounds, compiled
scripts) are mirrored to OneDrive; only the ones that changed are copied again.

    python scripts/backup_mod.py [--data "<Fallout 4>/Data"] [--onedrive <folder>]

OneDrive is the personal one ($OneDrive, as Windows sets it), under DevilsInTheDetails/.
"""
import argparse
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "DevilsInTheDetails.esp"
# The mod's folders under Data, and the compiled scripts (named Devils*).
FOLDERS = ["Meshes/DevilsInTheDetails", "Textures/DevilsInTheDetails", "Sound/FX/DevilsInTheDetails",
           "Sound/Voice/DevilsInTheDetails.esp", "Materials/DevilsInTheDetails"]
SCRIPTS = "Scripts/Devils*.pex"


def mirror(src, dst):
    """Copy the files under src that dst lacks or has older; returns how many."""
    n = 0
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        t = dst / f.relative_to(src)
        if not t.exists() or t.stat().st_mtime < f.stat().st_mtime or t.stat().st_size != f.stat().st_size:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=r"C:\Steam\steamapps\common\Fallout 4\Data")
    ap.add_argument("--onedrive", default=os.environ.get("OneDrive"))
    args = ap.parse_args()
    data = Path(args.data)
    plugin = data / PLUGIN

    repo_copy = ROOT / "plugin" / PLUGIN
    repo_copy.parent.mkdir(exist_ok=True)
    shutil.copy2(plugin, repo_copy)
    print(f"plugin -> {repo_copy.relative_to(ROOT)} (commit it)")

    if not args.onedrive:
        raise SystemExit("no OneDrive folder ($OneDrive isn't set): pass --onedrive")
    od = Path(args.onedrive) / "DevilsInTheDetails"
    stamp = time.strftime("%Y-%m-%d_%H%M", time.localtime(plugin.stat().st_mtime))
    dated = od / "plugin" / f"DevilsInTheDetails_{stamp}.esp"
    dated.parent.mkdir(parents=True, exist_ok=True)
    if not dated.exists():
        shutil.copy2(plugin, dated)
    print(f"plugin -> OneDrive {dated.relative_to(od.parent)}")

    copied = 0
    for folder in FOLDERS:
        if (data / folder).exists():
            copied += mirror(data / folder, od / "Data" / folder)
    for f in data.glob(SCRIPTS):
        t = od / "Data" / "Scripts" / f.name
        if not t.exists() or t.stat().st_mtime < f.stat().st_mtime:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            copied += 1
    print(f"mod files -> OneDrive DevilsInTheDetails/Data: {copied} copied (the rest unchanged)")


if __name__ == "__main__":
    main()
