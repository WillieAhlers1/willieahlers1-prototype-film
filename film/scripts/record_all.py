"""Film the plan, graphics first, logging to one file.

Usage: python record_all.py [--capture-mode frame-clock|compatibility] [logFile] [SEG ...]
For one separate preview: python record_all.py --preview SECONDS logFile SEG
Frame-clock mode requires Python Playwright; Node supports explicit compatibility mode only.
"""
import importlib.util
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from filmcfg import load

HERE = Path(__file__).resolve().parent
cfg = load()
ap = argparse.ArgumentParser()
ap.add_argument("--capture-mode", choices=("frame-clock", "compatibility"),
                default=cfg["capture"].get("mode", "frame-clock"))
ap.add_argument("--preview", type=float, help="render a separate preview of exactly one selected segment")
ap.add_argument("log", nargs="?", default=os.path.join(cfg["tmp"], "rec_all.log"))
ap.add_argument("segments", nargs="*")
args = ap.parse_args()
log = args.log
want = args.segments
if args.preview is not None and len(want) != 1:
    raise SystemExit("--preview requires exactly one segment after the log path")
segs = json.load(open(cfg["plan"], encoding="utf-8"))["segments"]
order = [s["name"] for s in segs if s["kind"] == "gfx"] + [s["name"] for s in segs if s["kind"] != "gfx"]
order = [s for s in order if not want or s in want]
missing = set(want) - set(order)
if missing:
    raise SystemExit("unknown segment(s): " + ", ".join(sorted(missing)))
if importlib.util.find_spec("playwright"):
    cmd = [sys.executable, str(HERE / "record.py")]
else:
    if args.capture_mode != "compatibility":
        raise SystemExit("Python Playwright is required for frame-clock capture; use --capture-mode compatibility explicitly for Node")
    if args.preview is not None:
        raise SystemExit("preview requires Python Playwright")
    cmd = ["node", str(HERE / "record.js")]
with open(log, "a", encoding="utf-8") as L:
    L.write(f"capture mode: {args.capture_mode}\n"); L.flush()
    for s in order:
        L.write(f"start {s} {time.strftime('%H:%M:%S')}\n"); L.flush()
        opts = ["--capture-mode", args.capture_mode]
        if args.preview is not None:
            opts += ["--preview", str(args.preview)]
        r = subprocess.run(cmd + [s] + opts, stdout=L, stderr=subprocess.STDOUT)
        if r.returncode:
            L.write(f"FAILED {s} exit {r.returncode}\n"); L.flush()
            print("FAILED", s, "- see", log); sys.exit(1)
        print("filmed", s, flush=True)
    L.write("ALLDONE\n")
print("ALLDONE ->", log)
