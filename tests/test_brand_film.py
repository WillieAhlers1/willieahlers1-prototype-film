import base64
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "film" / "scripts"
sys.path.insert(0, str(ROOT / "assets"))
import brand


class BrandFilmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT, prefix="film-test-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, PYTHONIOENCODING="utf-8")
        for key in ("PROTOTYPE_FILM_HOME", "FILM_CONFIG", "SPEECH_KEY",
                    "AZURE_SPEECH_KEY", "SPEECH_REGION", "AZURE_SPEECH_REGION", "SPEECH_ENDPOINT"):
            self.env.pop(key, None)

    def make_brand(self, name, accent="#123456", font="Example Sans"):
        root = self.root / name / ".prototype-film"
        root.mkdir(parents=True)
        (root / "logo.svg").write_text(f"<svg>{name}</svg>", encoding="utf-8")
        (root / "light.svg").write_text(f"<svg>{name} light</svg>", encoding="utf-8")
        (root / "font.ttf").write_bytes(name.encode())
        data = {"schema_version": 1, "approved": True, "asset_permissions": True,
                "name": name, "summary": name + " identity", "palette": {
                    "accent": accent, "background": "#101010", "foreground": "#f0e0d0", "muted": "#667788"},
                "typography": {"family": font, "files": ["font.ttf"], "system_font": False},
                "logos": {"primary": "logo.svg", "light": "light.svg"}, "text_only": False,
                "tagline": name + " tagline", "signoff": name + " signoff", "materials": [], "images": [],
                "pronunciations": {"say": {name: name + " spoken"}, "ipa": {"Widget": "wɪdʒɪt"}}}
        (root / "brand.json").write_text(json.dumps(data), encoding="utf-8")
        return root / "brand.json", data

    def init(self, build, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "new_film.py"), str(build), *map(str, args)],
                              text=True, capture_output=True, env=self.env)

    def test_brands_snapshot_captions_and_pronunciations(self):
        for name, color in (("Alpha", "#123456"), ("Beta", "#654321")):
            manifest, data = self.make_brand(name, color, name + " Sans")
            build = self.root / (name + "-build")
            r = self.init(build, "--brand", manifest)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads((build / "brand" / "brand.json").read_text())["name"], name)
            self.assertIn(color, (build / "brand.css").read_text())
            self.assertEqual((build / "brand" / "logo.svg").read_text(), f"<svg>{name}</svg>")
            self.assertIn("concept from " + name, (build / "narration.txt").read_text())
            self.assertEqual(len(list((build / "fonts").iterdir())), 1)
            self.assertIn("brand.js", (build / "graphics.html").read_text())
            self.assertIn("BRAND.logos[darkAccent?'light':'dark']", (build / "graphics.html").read_text())
            (build / "plan.json").write_text(json.dumps({"cues": [{"src": [0, 3], "at": 0, "text": name}]}))
            r = subprocess.run([sys.executable, "subs.py"], cwd=build, env=self.env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            ass = (build / "film.ass").read_text()
            self.assertIn(name + " Sans", ass)
            self.assertIn("&H00D0E0F0", ass)
            self.assertIn("&H33101010", ass)
            r = subprocess.run([sys.executable, "-c",
                                "import speech; print(speech.load_lexicon()[0])"],
                               cwd=build, env=self.env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(name + " spoken", r.stdout)
            self.assertNotIn("Beta spoken" if name == "Alpha" else "Alpha spoken", r.stdout)

    def test_validation_snapshot_update_and_embedded_mismatch(self):
        one, data = self.make_brand("Alpha")
        two, other = self.make_brand("Beta")
        build = self.root / "build"
        bad = self.root / "bad.json"
        bad.write_text(json.dumps(dict(data, approved=False)), encoding="utf-8")
        r = self.init(build, "--brand", bad)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(build.exists())
        r = self.init(build, "--brand", one)
        self.assertEqual(r.returncode, 0, r.stderr)
        (build / "narration.txt").write_text("Host: user edit", encoding="utf-8")
        logo = one.parent / "logo.svg"
        original = logo.read_bytes()
        logo.write_bytes(b"<svg>changed asset at same path</svg>")
        r = self.init(build, "--brand", one)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("snapshot changed", r.stderr)
        self.assertEqual((build / "brand" / "logo.svg").read_bytes(), original)
        logo.write_bytes(original)
        r = self.init(build, "--brand", two)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("snapshot changed", r.stderr)
        self.assertEqual((build / "narration.txt").read_text(), "Host: user edit")
        r = self.init(build, "--brand", two, "--update-brand")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((build / "narration.txt").read_text(), "Host: user edit")
        rendered = brand.install_brand(one, self.root / "prototype")
        for key in ("primary", "light"):
            path = self.root / "prototype" / rendered["logos"][key]
            rendered["logos"][key] = "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()
        path = self.root / "prototype" / rendered["typography"]["files"][0]
        rendered["typography"]["files"][0] = "data:font/ttf;base64," + base64.b64encode(path.read_bytes()).decode()
        packed = self.root / "prototype" / "packed.html"
        packed.write_text("<script>window.PROTOTYPE_BRAND = " + json.dumps(rendered) + ";</script>", encoding="utf-8")
        failed = self.root / "mismatch"
        r = self.init(failed, "--brand", two, "--prototype", packed)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(failed.exists())
        r = self.init(self.root / "matched", "--prototype", packed)
        self.assertEqual(r.returncode, 0, r.stderr)
        standalone = self.root / "standalone.html"
        standalone.write_text(packed.read_text(encoding="utf-8"), encoding="utf-8")
        r = self.init(self.root / "standalone-build", "--prototype", standalone)
        self.assertEqual(r.returncode, 0, r.stderr)
        brand.load_brand(self.root / "standalone-build" / "brand" / "brand.json")
        self.assertEqual((self.root / "standalone-build" / "brand" / "brand.json").exists(), True)

    def test_voice_preset_and_explicit_runtime_home(self):
        manifest, _ = self.make_brand("Alpha")
        workspace = self.root / "Alpha"
        home = self.root / "runtime"
        home.mkdir()
        self.env["PROTOTYPE_FILM_HOME"] = str(home)
        build = self.root / "voice-build"
        r = self.init(build, "--workspace", workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((build / "film.json").read_text())["home"], str(home))
        r = subprocess.run([sys.executable, "voice.py", "--use", "olivia"],
                           cwd=build, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, "voice.py", "--audition"], cwd=build,
                           env=self.env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("explicit consent", r.stderr + r.stdout)
        r = subprocess.run([sys.executable, "voice.py", "--use", "olivia", "--authorize-cloud"],
                           cwd=build, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        profile = json.loads((home / "voice.json").read_text())
        self.assertEqual(profile["name"], "en-GB-OliviaNeural")
        self.assertTrue(profile["cloud_authorized"])
        self.assertNotIn("SPEECH_KEY", profile)
        r = subprocess.run([sys.executable, "voice.py", "--audition"], cwd=build,
                           env=self.env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("needs SPEECH_KEY", r.stderr + r.stdout)
        cfg = json.loads((build / "film.json").read_text())
        cfg["voice"] = {"engine": "kokoro", "name": "bf_emma"}
        (build / "film.json").write_text(json.dumps(cfg))
        r = subprocess.run([sys.executable, "-c",
                            "import voice; from filmcfg import load; c=load(); print(voice.profile(c,voice.home_dir(c))['name'])"],
                           cwd=build, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "bf_emma")

    def test_existing_workspace_profile_is_reused(self):
        manifest, _ = self.make_brand("SavedProfile")
        workspace = manifest.parent.parent
        home = workspace / ".prototype-film"
        (home / "voice.json").write_text('{"engine":"kokoro","name":"bf_emma"}')
        build = self.root / "profile-build"
        r = self.init(build, "--workspace", workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((build / "film.json").read_text())["home"], str(home))
        r = subprocess.run([sys.executable, "-c",
                            "import voice; from filmcfg import load; c=load(); print(voice.profile(c,voice.home_dir(c))['name'])"],
                           cwd=build, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "bf_emma")

    def test_explicit_film_home_precedes_environment_and_survives_refresh(self):
        manifest, _ = self.make_brand("ConfiguredHome")
        build = self.root / "configured-home-build"
        r = self.init(build, "--brand", manifest)
        self.assertEqual(r.returncode, 0, r.stderr)
        home = self.root / "custom-models"
        cfg = json.loads((build / "film.json").read_text())
        cfg["home"] = str(home)
        (build / "film.json").write_text(json.dumps(cfg))
        self.env["PROTOTYPE_FILM_HOME"] = str(self.root / "environment-models")
        r = self.init(build, "--brand", manifest)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((build / "film.json").read_text())["home"], str(home))
        r = subprocess.run([sys.executable, "-c",
                            "from filmcfg import load, runtime_home; print(runtime_home(load()))"],
                           cwd=build, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(Path(r.stdout.strip()), home)

    def test_brand_manifest_selects_workspace_runtime_home(self):
        manifest, _ = self.make_brand("WorkspaceBrand")
        build = self.root / "brand-home-build"
        r = self.init(build, "--brand", manifest)
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = json.loads((build / "film.json").read_text())
        self.assertEqual(Path(cfg["home"]), manifest.parent)
        r = subprocess.run([sys.executable, "voice.py", "--use", "af_heart"], cwd=build,
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((manifest.parent / "voice.json").is_file())

    def test_ftg_preset_is_azure_olivia(self):
        manifest, _ = self.make_brand("PresetBrand")
        build = self.root / "preset-build"
        r = self.init(build, "--brand", manifest)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, "voice.py", "--use", "ftg", "--authorize-cloud"],
                           cwd=build, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        profile = json.loads((manifest.parent / "voice.json").read_text())
        self.assertEqual(profile["engine"], "azure")
        self.assertEqual(profile["name"], "en-GB-OliviaNeural")
        self.assertTrue(profile["cloud_authorized"])

    def test_packed_embedded_external_svg_rejected_before_mutation(self):
        manifest, data = self.make_brand("UnsafeSvg")
        unsafe = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://invalid.example/a.png"/></svg>'
        data["logos"] = {"primary": "data:image/svg+xml;base64," + base64.b64encode(unsafe).decode()}
        data["typography"] = {"family": "Arial", "files": [], "system_font": True}
        packed = self.root / "unsafe-packed.html"
        packed.write_text("<script>window.PROTOTYPE_BRAND = " + json.dumps(data) + ";</script>", encoding="utf-8")
        build = self.root / "unsafe-build"
        r = self.init(build, "--prototype", packed)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("non-embedded reference", r.stderr)
        self.assertFalse(build.exists())

    def test_removed_example_option_is_rejected_before_mutation(self):
        manifest, _ = self.make_brand("OtherBrand")
        build = self.root / "example-build"
        r = self.init(build, "--brand", manifest, "--example", "sample")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unrecognized arguments", r.stderr)
        self.assertFalse(build.exists())

    def test_two_brand_graphics_and_caption_render(self):
        try:
            import imageio_ffmpeg
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("rendering dependencies are unavailable")
        edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        if not edge.exists():
            self.skipTest("local Edge is unavailable")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=str(edge), headless=True)
            for name, color, variant in (("RenderOne", "#123456", "light"),
                                         ("RenderTwo", "#f0e090", "primary")):
                manifest, data = self.make_brand(name, color)
                data["typography"] = {"family": "Arial", "files": [], "system_font": True}
                manifest.write_text(json.dumps(data), encoding="utf-8")
                for logo in ("logo.svg", "light.svg"):
                    (manifest.parent / logo).write_text(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="30">'
                        '<rect width="100" height="30" fill="white"/></svg>', encoding="utf-8")
                build = self.root / (name + "-render")
                r = self.init(build, "--brand", manifest)
                self.assertEqual(r.returncode, 0, r.stderr)
                r = subprocess.run([sys.executable, "gfx_data.py"], cwd=build, env=self.env,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                (build / "plan.json").write_text(json.dumps({"cues": [
                    {"src": [0, 0.4], "at": 0, "text": name + " caption"}]}))
                r = subprocess.run([sys.executable, "subs.py"], cwd=build, env=self.env,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                errors = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto((build / "graphics.html").as_uri() + "?seg=endcard&seek=2")
                page.wait_for_timeout(300)
                self.assertEqual(errors, [])
                self.assertEqual(page.locator("#endcard").evaluate(
                    "(el) => getComputedStyle(el).backgroundColor"),
                    "rgb(" + ", ".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5)) + ")")
                self.assertTrue(page.locator("#brand-logo").get_attribute("src").endswith(
                    "light.svg" if variant == "light" else "logo.svg"))
                self.assertGreater(page.locator("#brand-logo").evaluate("(el) => el.naturalWidth"), 0)
                page.screenshot(path=str(build / "frame.png"))
                page.close()
                r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                                    "-y", "-loop", "1", "-framerate", "5", "-i", "frame.png",
                                    "-vf", "subtitles=film.ass:fontsdir=fonts", "-t", "0.4",
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "preview.mp4"],
                                   cwd=build, env=self.env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertGreater((build / "preview.mp4").stat().st_size, 1000)
            browser.close()

    def test_azure_ssml_and_line_cache_without_network(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            import voice
        finally:
            sys.path.remove(str(SCRIPTS))
        if voice.np is None:
            self.skipTest("numpy is unavailable")
        dest = self.root / "azure.wav"
        with mock.patch.dict(os.environ, {"SPEECH_KEY": "test-key", "SPEECH_REGION": "test-region"}), \
             mock.patch.object(voice.urllib.request, "urlopen", return_value=io.BytesIO(b"wave")) as request:
            with self.assertRaises(SystemExit):
                voice.azure("Widget", {"name": "en-GB-OliviaNeural"}, str(dest), {"Widget": "wɪdʒɪt"})
            request.assert_not_called()
            voice.azure("Widget", {"name": "en-GB-OliviaNeural", "cloud_authorized": True},
                        str(dest), {"Widget": "wɪdʒɪt"})
            ssml = request.call_args.args[0].data.decode()
            self.assertIn('en-GB-OliviaNeural', ssml)
            self.assertIn('<phoneme alphabet=', ssml)
            self.assertIn('wɪdʒɪt', ssml)
        manifest, _ = self.make_brand("VoiceTest")
        build = self.root / "cache-build"
        r = self.init(build, "--brand", manifest)
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = json.loads((build / "film.json").read_text())
        cfg["narration"]["cue_ids"] = []
        cfg["home"] = str(self.root / "voice-home")
        (build / "film.json").write_text(json.dumps(cfg))
        (build / "narration.txt").write_text("Host: VoiceTest first.\nHost: A second line.\n")

        def fake_synth(engine, text, profile, ipa, home, path):
            samples = voice.np.sin(voice.np.arange(4800) * 0.1) * 5000
            voice.write_wav(path, samples)

        old = Path.cwd()
        try:
            os.chdir(build)
            with mock.patch.object(sys, "argv", ["voice.py"]), \
                 mock.patch.object(voice, "synth", side_effect=fake_synth) as synth, \
                 contextlib.redirect_stdout(io.StringIO()):
                voice.main()
                self.assertEqual(synth.call_count, 2)
                voice.main()
                self.assertEqual(synth.call_count, 2)
                (build / "narration.txt").write_text("Host: VoiceTest changed.\nHost: A second line.\n")
                voice.main()
                self.assertEqual(synth.call_count, 3)
            cues = json.loads((build / "cues.json").read_text())
            self.assertEqual(list(cues), ["C01", "C02"])
            self.assertEqual(cues["C01"]["spoken"], "VoiceTest spoken changed.")
        finally:
            os.chdir(old)


if __name__ == "__main__":
    unittest.main()
