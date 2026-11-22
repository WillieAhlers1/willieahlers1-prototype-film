import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "film" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from planlib import Plan


class PacingTests(unittest.TestCase):
    def make_plan(self, text, duration, segment_duration):
        cfg = {"crossfade_s": 0.6, "pacing": {}, "home": ""}
        plan = Plan.__new__(Plan)
        plan.cfg = cfg
        plan.X = cfg["crossfade_s"]
        plan.C = {"a": {"src": [0, duration], "dur": duration, "text": text}}
        plan.segs = [{"name": "P1", "kind": "proto", "dur": segment_duration,
                      "cues": [("a", 0)], "steps": [duration + 1]}]
        return plan

    def test_measures_voiced_and_whole_film_without_stretching(self):
        plan = self.make_plan(" ".join(["word"] * 28), 10.12, 14)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report = plan.report_pacing()
        self.assertAlmostEqual(report["spoken_wpm"], 166.0079, places=2)
        self.assertEqual(report["film_wpm"], 120)
        self.assertEqual(plan.segs[0]["dur"], 14)
        self.assertIn("reading", output.getvalue())

    def test_rejects_fast_film_and_invalid_audio(self):
        plan = self.make_plan(" ".join(["word"] * 30), 2, 4)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            plan.report_pacing()
        plan.C["a"]["src"] = [0, 0.2]
        with self.assertRaisesRegex(ValueError, "audio range"):
            plan.report_pacing()

    def test_static_silence_report(self):
        plan = self.make_plan("hello", 1, 10)
        plan.segs[0]["steps"] = [2]
        with contextlib.redirect_stdout(io.StringIO()):
            report = plan.report_pacing()
        self.assertEqual(report["static_silence"], [("P1", 2, 10)])


class BrowserCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import playwright.async_api
            from filmcfg import ffmpeg
            cls.ffmpeg = ffmpeg({})
        except (ImportError, SystemExit):
            raise unittest.SkipTest("Playwright and ffmpeg are required")
        edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        if not edge.exists():
            raise unittest.SkipTest("test browser unavailable")
        cls.browser = str(edge)

    def setUp(self):
        self.d = ROOT / (".pacing-test-" + uuid.uuid4().hex)
        self.d.mkdir()
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "graphics.html").write_text("""
          <style>body{margin:0;background:white} #box{width:24px;height:24px;background:blue}
          @keyframes move {from{transform:translateX(0px)} to{transform:translateX(60px)}}
          .move{animation:move 1s linear forwards}</style>
          <div id="box"></div><script>
          window.start=()=>{box.className='move';setTimeout(()=>box.style.background='red',200);
            document.body.animate([{opacity:1},{opacity:1}],{duration:300}).onfinish=()=>document.body.style.background='black'};
          </script>""", encoding="utf-8")
        with wave.open(str(self.d / "music.wav"), "wb") as w:
            w.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            w.writeframes(b"\0\0" * 8000 * 3)
        with wave.open(str(self.d / "narr.wav"), "wb") as w:
            w.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            w.writeframes(b"\0\0" * 8000)
        (self.d / "fonts").mkdir()
        (self.d / "brand").mkdir()
        (self.d / "brand" / "brand.json").write_text(json.dumps(
            {"palette": {"foreground": "#123456", "background": "#abcdef"}}), encoding="utf-8")
        self.plan = {"total": 1.0, "X": 0.0, "segments": [
            {"name": "G1", "kind": "gfx", "seg": "night", "params": {}, "dur": 1.0, "start": 0,
             "cues": [["a", 0.1]]}],
            "cues": [{"id": "a", "at": 0.1, "src": [0, 0.4], "text": "Hello there."}]}
        (self.d / "plan.json").write_text(json.dumps(self.plan), encoding="utf-8")
        cfg = {"tmp": "work", "capture": {"chrome": self.browser, "width": 96, "height": 64,
                                           "fps": 10, "gfx_settle_ms": 0},
               "graphics": {"file": "graphics.html"}, "captions": {"enabled": True, "font": "Arial",
                                                                     "fontsdir": "fonts"}}
        (self.d / "film.json").write_text(json.dumps(cfg), encoding="utf-8")

    def test_frame_clock_and_self_contained_preview(self):
        command = [sys.executable, str(SCRIPTS / "record.py"), "G1", "--preview", "0.6"]
        r = subprocess.run(command, cwd=self.d, text=True, capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("capture mode: frame-clock", r.stdout)
        preview = self.d / "work" / "preview" / "G1"
        meta = json.loads((preview / "frames_G1" / "meta.json").read_text())
        self.assertEqual(meta["frame_count"], 6)
        self.assertEqual(meta["ts"], [i / 10 for i in range(6)])
        self.assertEqual(json.loads((self.d / "plan.json").read_text()), self.plan)
        self.assertTrue((preview / "preview.mp4").is_file())
        self.assertIn("Hello there.", (preview / "film.ass").read_text(encoding="utf-8"))
        self.assertIn("&H00563412", (preview / "film.ass").read_text(encoding="utf-8"))
        self.assertFalse((self.d / "work" / "G1.mp4").exists())
        # Decode frames to check that both the CSS animation and virtual timeout progressed.
        def pixels(n):
            r = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(preview / "frames_G1" / f"{n:06}.jpg"),
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
            return r.stdout
        images = [pixels(n) for n in (1, 2, 4, 6)]
        self.assertGreater(len(set(images)), 2)
        def red_at(image, x, y):
            i = (y * 96 + x) * 3
            return image[i] > 170 and image[i + 1] < 80 and image[i + 2] < 80
        self.assertTrue(red_at(images[-1], 40, 10), "CSS animation must move on the virtual clock")
        self.assertFalse(red_at(images[0], 40, 10))
        self.assertLess(images[-1][(50 * 96 + 90) * 3], 40, "animation finish callback must fire")
        repeat = subprocess.run([sys.executable, str(SCRIPTS / "record.py"), "G1"], cwd=self.d,
                                text=True, capture_output=True, timeout=120)
        self.assertEqual(repeat.returncode, 0, repeat.stdout + repeat.stderr)
        full = self.d / "work" / "frames_G1"
        for n in range(1, 7):
            self.assertEqual((preview / "frames_G1" / f"{n:06}.jpg").read_bytes(),
                             (full / f"{n:06}.jpg").read_bytes(), f"frame {n} differs between runs")
        # An integral duration is encoded with exactly duration * fps frames, not an extra frame.
        check = subprocess.run([self.ffmpeg, "-i", str(preview / "G1.mp4"), "-f", "null", "-"],
                               capture_output=True, text=True)
        self.assertRegex(check.stderr, r"frame=\s*6")

    def test_real_engine_driven_warmup_and_steps(self):
        proto = self.d / "proto"
        proto.mkdir()
        shutil.copytree(ROOT / "assets" / "kit", proto / "kit")
        html = (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<script>window.PROTOTYPE_BRAND={schema_version:1,approved:true,asset_permissions:true,name:"Test",'
            'palette:{accent:"#008800",background:"#ffffff",foreground:"#222222",muted:"#eeeeee"},'
            'typography:{family:"Arial",files:[],system_font:true},text_only:true};</script>'
            '<script src="kit/proto-style.js"></script></head>'
            '<body data-concept="Concept demo - Fictitious data"><main class="stage">'
            '<section class="scene zoom" id="ask">'
            '<h1 style="position:absolute;left:100px;top:100px">People decide</h1>'
            '<p data-beat="1" style="position:absolute;left:100px;top:300px;font-size:32px">'
            'Agents prepare the work for review.</p></section>'
            '<section class="scene zoom" id="close"><h1>One team, a whole outcome</h1></section>'
            '</main><script src="kit/proto.js"></script></body></html>')
        (proto / "prototype.html").write_text(html, encoding="utf-8")
        config = json.loads((self.d / "film.json").read_text())
        config["prototype"] = {"dir": "proto", "file": "prototype.html"}
        config["capture"].update(width=1920, height=1080)
        (self.d / "film.json").write_text(json.dumps(config), encoding="utf-8")
        self.plan["segments"] = [{"name": "P1", "kind": "proto", "hash": "#ask", "driven": True,
                                   "dur": 0.55, "start": 0, "steps": [0.2], "cues": []}]
        (self.d / "plan.json").write_text(json.dumps(self.plan), encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPTS / "record.py"), "P1"], cwd=self.d,
                           text=True, capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        frames = self.d / "work" / "frames_P1"
        meta = json.loads((frames / "meta.json").read_text())
        self.assertEqual(meta["frame_count"], 6)
        self.assertTrue((frames / "000002.jpg").read_bytes() != (frames / "000006.jpg").read_bytes(),
                        "driven step should change the real prototype")
        encode = subprocess.run([sys.executable, str(SCRIPTS / "assemble.py"), "segs", "P1"], cwd=self.d,
                                text=True, capture_output=True, timeout=120)
        self.assertEqual(encode.returncode, 0, encode.stdout + encode.stderr)
        check = subprocess.run([self.ffmpeg, "-i", str(self.d / "work" / "P1.mp4"), "-f", "null", "-"],
                               capture_output=True, text=True)
        self.assertRegex(check.stderr, r"frame=\s*6")
        self.plan["segments"][0]["dur"] = 0.7
        (self.d / "plan.json").write_text(json.dumps(self.plan), encoding="utf-8")
        encode = subprocess.run([sys.executable, str(SCRIPTS / "assemble.py"), "segs", "P1"], cwd=self.d,
                                text=True, capture_output=True, timeout=120)
        self.assertNotEqual(encode.returncode, 0)
        self.assertIn("re-record", encode.stdout + encode.stderr)

    def test_animated_image_requires_explicit_compatibility(self):
        with (self.d / "graphics.html").open("a", encoding="utf-8") as f:
            f.write('<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7">')
        r = subprocess.run([sys.executable, str(SCRIPTS / "record.py"), "G1"], cwd=self.d,
                           text=True, capture_output=True, timeout=120)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--capture-mode compatibility", r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
