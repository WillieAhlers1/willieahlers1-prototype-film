"""Two-brand setup -> packed prototype -> synchronized captioned MP4.

Synthetic local audio verifies pipeline wiring, not a real narrator's sound or pronunciation.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_brand import fixture

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SCRIPTS = ROOT / "film" / "scripts"


class EndToEndTests(unittest.TestCase):
    def run_command(self, command, cwd=None):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        for key in ("FILM_CONFIG", "PROTOTYPE_FILM_HOME", "TREDENCE_HOME"):
            env.pop(key, None)
        result = subprocess.run(command, cwd=cwd or ROOT, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_two_workspaces_generate_offline_prototypes_and_films(self):
        with tempfile.TemporaryDirectory(prefix="prototype-film-e2e-") as directory:
            root = Path(directory)
            for name, accent in (("Northstar", "#663399"), ("Harbor", "#005566")):
                with self.subTest(brand=name):
                    workspace = root / name
                    workspace.mkdir()
                    intake = root / (name + "-intake")
                    fixture(intake, name, accent)
                    self.run_command([sys.executable, str(ASSETS / "brand_setup.py"), "setup",
                                      "--workspace", str(workspace), "--intake", str(intake / "intake.json"),
                                      "--approve"])
                    for concept in ("first", "second"):
                        self.run_command([sys.executable, str(ASSETS / "brand_setup.py"), "validate",
                                          "--workspace", str(workspace)])
                        self.run_command([sys.executable, str(ASSETS / "init_prototype.py"),
                                          "--workspace", str(workspace), "--name", concept])
                    output = workspace / "working" / "first"
                    intro = f"This is a concept from {name}. People and numbers are fictional."
                    action = "The person owns the outcome while agents prepare work for review."
                    html = (
                        '<!doctype html><html><head><meta charset="utf-8">'
                        '<script src="brand.js"></script><script src="kit/proto-style.js"></script>'
                        '<link rel="stylesheet" href="brand.css"></head>'
                        '<body data-concept="Concept demo - Fictitious data"><main class="stage">'
                        f'<section class="scene frame td-content" id="cover" data-note="{intro}">'
                        '<h1 class="td-abs td-title" style="left:50px;top:115px;width:1700px">'
                        'One team, a whole outcome</h1>'
                        f'<p class="td-abs td-lead" style="left:50px;top:300px;width:1700px" '
                        f'data-beat="1" data-hold="3000" data-note="{action}">'
                        'Agents prepare. People decide.</p></section></main>'
                        '<script src="kit/icons.js"></script><script src="kit/proto.js"></script></body></html>'
                    )
                    prototype = output / "prototype.html"
                    prototype.write_text(html, encoding="utf-8")
                    self.run_command([sys.executable, str(ASSETS / "check_prototype.py"), str(prototype)])
                    self.run_command([sys.executable, str(ASSETS / "pack_prototype.py"), str(prototype)])
                    packed = output / "dist" / "first.html"
                    self.run_command([sys.executable, str(ASSETS / "film_ready.py"), str(packed),
                                      "--target", "0:12"])
                    self.assertNotIn("Tredence", packed.read_text(encoding="utf-8"))
                    build = root / (name + "-film")
                    self.run_command([sys.executable, str(SCRIPTS / "new_film.py"), str(build),
                                      "--workspace", str(workspace), "--prototype", str(packed)])
                    cfg = json.loads((build / "film.json").read_text(encoding="utf-8"))
                    cfg.update({"name": name + " integration", "voice": {"engine": "kokoro"},
                                "capture": {"mode": "frame-clock", "fps": 5, "width": 1920, "height": 1080},
                                "graphics": {"file": "graphics.html"},
                                "output": {"file": "film.mp4", "preset": "ultrafast"}})
                    cfg["narration"]["cue_ids"] = []
                    (build / "film.json").write_text(json.dumps(cfg), encoding="utf-8")
                    (build / "narration.txt").write_text(
                        f"@ cover\nHost: {intro}\n@ cover 1\nHost: {action}\n", encoding="utf-8")
                    self.run_command([sys.executable, "check_film.py"], build)
                    # Exercise real cue/cache/audio/mix code without a model download or cloud request.
                    synthetic_voice = (
                        "import voice, re; "
                        "def_synth = 'def synth(engine,text,profile,ipa,home,path):\\n"
                        " n=int(len(re.findall(r\"\\\\b[\\\\w]+\\\\b\",text))*60/166*voice.SR)\\n"
                        " x=voice.np.sin(voice.np.arange(n)*0.08)*5000\\n"
                        " voice.write_wav(path,x)'; "
                        "exec(def_synth); voice.synth=synth; voice.main()"
                    )
                    self.run_command([sys.executable, "-c", synthetic_voice], build)
                    self.run_command([sys.executable, "autoplan.py"], build)
                    plan = json.loads((build / "plan.json").read_text(encoding="utf-8"))
                    self.assertLessEqual(sum(len(c["text"].split()) for c in plan["cues"]) /
                                         plan["total"] * 60, 160)
                    self.run_command([sys.executable, "record_all.py"], build)
                    metadata = json.loads((build / "work" / "frames_P1" / "meta.json").read_text())
                    self.assertEqual(metadata["mode"], "frame-clock")
                    self.assertEqual(metadata["frame_count"], len(metadata["ts"]))
                    self.run_command([sys.executable, "music.py"], build)
                    self.run_command([sys.executable, "mix.py"], build)
                    self.run_command([sys.executable, "subs.py"], build)
                    self.run_command([sys.executable, "assemble.py", "all"], build)
                    film = build / "work" / "film.mp4"
                    self.assertGreater(film.stat().st_size, 1000)
                    import imageio_ffmpeg
                    inspected = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(film)],
                                               capture_output=True, text=True, encoding="utf-8", errors="replace")
                    duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", inspected.stderr)
                    self.assertIsNotNone(duration, inspected.stderr)
                    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
                    self.assertAlmostEqual(seconds, plan["total"], delta=0.25)
                    self.assertIn("1920x1080", inspected.stderr)
                    self.assertIn("Audio: aac", inspected.stderr)
                    self.assertIn("Arial", (build / "film.ass").read_text(encoding="utf-8"))
                    self.assertEqual(json.loads((build / "brand" / "brand.json").read_text())["name"], name)
                    self.assertTrue((workspace / ".prototype-film" / "brand.json").exists())
                    self.assertEqual(json.loads((workspace / "working" / "second" / "brand" /
                                                 "brand.json").read_text())["name"], name)


if __name__ == "__main__":
    unittest.main()
