"""Build a self-contained, separate preview from a segment's recorded prefix."""
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from filmcfg import run_ffmpeg


def render_preview(cfg, plan, seg, frame_dir):
    root = frame_dir.parent.resolve()
    segment_start = seg["start"]
    end = segment_start + seg["dur"]
    cues = []
    for cue in plan["cues"]:
        a, b = cue["src"]
        start = cue["at"]
        lo = max(start, segment_start)
        hi = min(start + b - a, end)
        if hi > lo:
            c = dict(cue, at=round(lo - segment_start, 6),
                     src=[round(a + lo - start, 6), round(a + hi - start, 6)])
            cues.append(c)
    preview_seg = dict(seg, start=0)
    preview_plan = {"total": seg["dur"], "X": 0, "segments": [preview_seg], "cues": cues}
    settings = copy.deepcopy(cfg)
    settings["tmp"] = str(root)
    settings["plan"] = str(root / "plan.json")
    settings["narration"]["audio"] = str(Path(cfg["narration"]["audio"]).resolve())
    settings["music"]["file"] = str(Path(cfg["music"]["file"]).resolve())
    settings["captions"]["file"] = "film.ass"
    fonts = Path(cfg["captions"]["fontsdir"]).resolve()
    if fonts.is_dir():
        shutil.copytree(fonts, root / "fonts", dirs_exist_ok=True)
    else:
        (root / "fonts").mkdir(exist_ok=True)
    settings["captions"]["fontsdir"] = "fonts"
    if Path("brand").is_dir():
        shutil.copytree(Path("brand"), root / "brand", dirs_exist_ok=True)
    settings["mix"]["file"] = "mix.wav"
    settings["output"]["file"] = "preview.mp4"
    if settings.get("ffmpeg") and Path(settings["ffmpeg"]).exists():
        settings["ffmpeg"] = str(Path(settings["ffmpeg"]).resolve())
    if not Path(settings["music"]["file"]).is_file():
        raise SystemExit(f"preview needs music: {settings['music']['file']}")
    if cues and not Path(settings["narration"]["audio"]).is_file():
        raise SystemExit(f"preview needs narration audio: {settings['narration']['audio']}")
    (root / "plan.json").write_text(json.dumps(preview_plan, indent=1), encoding="utf-8")
    config_path = root / "film.json"
    config_path.write_text(json.dumps(settings, indent=1), encoding="utf-8")
    env = dict(os.environ, FILM_CONFIG=str(config_path))
    scripts = Path(__file__).resolve().parent

    def run(script, *args):
        subprocess.run([sys.executable, str(scripts / script), *args], cwd=root, env=env, check=True)

    if settings["captions"].get("enabled", True):
        run("subs.py")
    if cues:
        run("mix.py")
    else:
        run_ffmpeg(settings, ["-loglevel", "error", "-y", "-i", settings["music"]["file"],
                              "-af", f"volume={settings['mix']['music_db']}dB,apad",
                              "-t", str(seg["dur"]), "-ar", "48000", "-ac", "2",
                              "-c:a", "pcm_s16le", str(root / settings["mix"]["file"])])
    run("assemble.py", "all")
    print(f"preview -> {root / 'preview.mp4'}", flush=True)
