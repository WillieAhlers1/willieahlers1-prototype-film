"""Brand snapshots render and pack independently without legacy defaults."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "assets"))
from brand import install_brand


class BrandPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix=".brand-prototype-test-", dir=ROOT)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        try:
            cls.browser = cls.pw.chromium.launch(channel="msedge")
        except Exception:
            cls.browser = cls.pw.chromium.launch()
        cls.addClassCleanup(cls.browser.close)

    def create_brand(self, name, accent, font, text_only):
        source = self.root / (name + "-source")
        source.mkdir()
        (source / "mark.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="30">'
            f'<rect width="100" height="30" fill="{accent}"/></svg>', encoding="utf-8")
        manifest = {
            "schema_version": 1, "approved": True, "asset_permissions": True,
            "name": name, "summary": "Approved identity",
            "palette": {"accent": accent, "background": "#ffffff", "foreground": "#111111", "muted": "#555555"},
            "typography": {"family": font, "files": [], "system_font": True},
            "text_only": text_only, "logos": {} if text_only else {"primary": "mark.svg"},
            "tagline": name + " tagline", "signoff": name + " farewell",
            "images": [], "materials": [], "pronunciations": {"say": {}, "ipa": {}},
        }
        manifest_file = source / "brand.json"
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        out = self.root / name
        out.mkdir()
        shutil.copytree(ROOT / "assets" / "kit", out / "kit",
                        ignore=shutil.ignore_patterns("brand", "fonts", "photos"))
        install_brand(manifest_file, out)
        starter = (ROOT / "assets" / "starter.html").read_text(encoding="utf-8")
        starter = re.sub(r"\[\[([^\]\n]+)\]\]", "Sample", starter)
        html = out / "prototype.html"
        html.write_text(starter, encoding="utf-8")
        return manifest_file, html, manifest

    def test_two_brands_render_and_pack_offline(self):
        page = self.browser.new_page(viewport={"width": 1920, "height": 1080})
        self.addCleanup(page.close)
        for name, accent, rgb, font, text_only in [
            ("Northstar", "#005a9c", "rgb(0, 90, 156)", "Arial", False),
            ("Moss", "#306030", "rgb(48, 96, 48)", "Georgia", True),
        ]:
            with self.subTest(name=name):
                manifest_file, html, manifest = self.create_brand(name, accent, font, text_only)
                out = html.parent / "packed.html"
                result = subprocess.run([sys.executable, str(ROOT / "assets" / "pack_prototype.py"),
                                         str(html), str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                packed = out.read_text(encoding="utf-8")
                self.assertNotIn("kit/brand/", packed)
                self.assertNotIn("Poppins", packed)
                self.assertNotIn("BeyondPossible", packed)
                self.assertNotIn("Tredence", packed)
                payload = re.search(r"window\.PROTOTYPE_BRAND\s*=\s*(\{.*?\});", packed).group(1)
                embedded = json.loads(payload)
                self.assertEqual(embedded["name"], name)
                if not text_only:
                    self.assertTrue(embedded["logos"]["primary"].startswith("data:image/svg+xml;base64,"))
                for target in (html, out):
                    requests, errors, local_requests = [], [], []
                    page.on("request", lambda r, requests=requests: requests.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
                    page.on("request", lambda r, local_requests=local_requests: local_requests.append(r.url) if r.url.startswith("file:") else None)
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    page.goto(target.as_uri() + "?driven&instant")
                    page.wait_for_function("window.proto && proto.ready")
                    self.assertEqual(page.locator("#cover .td-ch-tag").inner_text(), manifest["tagline"])
                    self.assertEqual(page.locator("#closing .td-ch-close").inner_text(), manifest["signoff"])
                    self.assertIn(font, page.locator("#cover").evaluate("e => getComputedStyle(e).fontFamily"))
                    self.assertEqual(page.locator("#close .td-hl").evaluate("e => getComputedStyle(e).color"), rgb)
                    self.assertEqual(page.locator("#cover .td-ch-name").count(), int(text_only))
                    self.assertEqual(page.locator("#cover .td-ch-logo").count(), int(not text_only))
                    self.assertFalse(errors)
                    self.assertFalse(requests)
                    if target == out:
                        self.assertEqual(len(local_requests), 1, local_requests)
                result = subprocess.run([sys.executable, str(ROOT / "assets" / "check_prototype.py"),
                                         str(html), "--scene", "close", "--brand", str(manifest_file)],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_packer_rejects_missing_invalid_and_network_brand(self):
        _, html, _ = self.create_brand("Failure", "#005a9c", "Arial", False)
        packer = ROOT / "assets" / "pack_prototype.py"
        def pack():
            return subprocess.run([sys.executable, str(packer), str(html)], capture_output=True, text=True)

        js = html.parent / "brand.js"
        original = js.read_text(encoding="utf-8")
        js.write_text(original.replace('"approved": true', '"approved": false'), encoding="utf-8")
        self.assertNotEqual(pack().returncode, 0)
        js.write_text(original.replace("brand/mark.svg", "https://example.com/mark.svg"), encoding="utf-8")
        self.assertNotEqual(pack().returncode, 0)
        js.write_text(original.replace("Failure tagline", "Changed tagline"), encoding="utf-8")
        self.assertIn("does not match", pack().stderr)
        js.write_text(original, encoding="utf-8")
        logo = html.parent / "brand" / "mark.svg"
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/x.png"/></svg>', encoding="utf-8")
        self.assertIn("non-embedded reference", pack().stderr)
        html.write_text(html.read_text(encoding="utf-8").replace('<script src="brand.js"></script>', ""), encoding="utf-8")
        self.assertNotEqual(pack().returncode, 0)

    def test_style_requires_brand(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((ROOT / "assets" / "starter.html").as_uri())
        self.assertTrue(any("Missing or invalid PROTOTYPE_BRAND" in e for e in errors), errors)

    def test_font_asset_is_embedded(self):
        manifest_file, html, manifest = self.create_brand("Fonted", "#005a9c", "Fixture Font", False)
        shutil.copy2(ROOT / "assets" / "kit" / "fonts" / "Poppins-Regular.ttf", manifest_file.parent / "font.ttf")
        (manifest_file.parent / "guide.txt").write_text("Approved guide", encoding="utf-8")
        manifest["typography"].update({"files": ["font.ttf"], "system_font": False})
        manifest["images"] = ["mark.svg"]
        manifest["materials"] = [{"path": "guide.txt", "role": "identity"}]
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        install_brand(manifest_file, html.parent)
        out = html.parent / "packed.html"
        result = subprocess.run([sys.executable, str(ROOT / "assets" / "pack_prototype.py"), str(html), str(out)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        packed = out.read_text(encoding="utf-8")
        embedded = json.loads(re.search(r"window\.PROTOTYPE_BRAND\s*=\s*(\{.*?\});", packed).group(1))
        self.assertTrue(embedded["typography"]["files"][0].startswith("data:font/ttf;base64,"))
        self.assertTrue(embedded["images"][0].startswith("data:image/svg+xml;base64,"))
        self.assertTrue(embedded["materials"][0]["path"].startswith("data:text/plain;base64,"))
        self.assertIn('src:url(data:font/ttf;base64,', packed)

    def test_checker_detects_other_selected_brand(self):
        _, html, _ = self.create_brand("Rendered", "#005a9c", "Arial", False)
        other, _, _ = self.create_brand("Selected", "#306030", "Georgia", True)
        result = subprocess.run([sys.executable, str(ROOT / "assets" / "check_prototype.py"),
                                 str(html), "--scene", "close", "--brand", str(other)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("embedded brand does not match the selected manifest", result.stdout)


if __name__ == "__main__":
    unittest.main()
