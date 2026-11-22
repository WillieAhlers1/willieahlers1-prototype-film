import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "assets"))
from brand import BrandError, brand_fingerprint, find_manifest, install_brand, load_brand, validate_brand, write_json
from brand_setup import setup


def fixture(directory, name="Northstar", accent="#663399"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="40">'
        f'<rect width="200" height="40" fill="{accent}"/></svg>', encoding="utf-8")
    (directory / "guide.md").write_text(f"{name}: confident, specific, customer-first.", encoding="utf-8")
    data = {
        "schema_version": 1, "approved": True, "asset_permissions": True, "name": name,
        "palette": {"accent": accent, "background": "#ffffff", "foreground": "#202020", "muted": "#e0e0e0"},
        "typography": {"family": "Arial", "files": [], "system_font": True},
        "text_only": False, "logos": {"primary": "logo.svg"},
        "tagline": "Work, connected", "signoff": "Build what comes next",
        "summary": f"{name} approved identity; content provenance: guide.md.",
        "materials": [{"path": "guide.md", "role": "identity"}], "images": [],
        "pronunciations": {"say": {name: name}, "ipa": {}},
    }
    write_json(directory / "intake.json", data)
    return data


class BrandBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.intake = self.root / "intake"
        self.data = fixture(self.intake)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def test_approval_missing_cancel_and_bad_files_leave_no_success(self):
        with self.assertRaises(BrandError):
            setup(self.workspace, self.intake / "intake.json")
        self.assertFalse((self.workspace / ".prototype-film").exists())
        self.data["logos"]["primary"] = "../outside.svg"
        write_json(self.intake / "intake.json", self.data)
        with self.assertRaises(BrandError):
            setup(self.workspace, self.intake / "intake.json", approve=True)
        self.assertFalse((self.workspace / ".prototype-film" / "brand.json").exists())

    def test_setup_reuse_isolation_and_explicit_update(self):
        setup(self.workspace, self.intake / "intake.json", approve=True)
        manifest = self.workspace / ".prototype-film" / "brand.json"
        self.assertEqual(load_brand(manifest)["name"], "Northstar")
        self.assertEqual(find_manifest(self.workspace / "working" / "demo"), manifest)
        with self.assertRaises(BrandError):
            setup(self.workspace, self.intake / "intake.json", approve=True)
        runtime = manifest.parent / "voice.json"
        runtime.write_text('{"engine":"kokoro","name":"af_heart"}', encoding="utf-8")
        second = self.root / "second"
        second.mkdir()
        fixture(self.intake, "Harbor", "#005566")
        setup(second, self.intake / "intake.json", approve=True)
        self.assertEqual(load_brand(manifest)["name"], "Northstar")
        setup(self.workspace, self.intake / "intake.json", approve=True, update=True)
        self.assertEqual(load_brand(manifest)["name"], "Harbor")
        self.assertTrue(runtime.exists())

    def test_snapshot_survives_removed_uploads_and_disposable_builds(self):
        setup(self.workspace, self.intake / "intake.json", approve=True)
        manifest = self.workspace / ".prototype-film" / "brand.json"
        (self.intake / "logo.svg").unlink()
        output = self.root / "build"
        rendered = install_brand(manifest, output)
        self.assertTrue((output / rendered["logos"]["primary"]).exists())
        self.assertEqual(load_brand(output / "brand" / "brand.json")["name"], "Northstar")
        self.assertIn("window.PROTOTYPE_BRAND", (output / "brand.js").read_text())
        self.assertIn("#663399", (output / "brand.css").read_text())
        (output / "brand.js").unlink()
        install_brand(manifest, output)
        self.assertTrue(manifest.exists())

    def test_invalid_schema_permissions_types_font_and_secrets(self):
        for field, value in [("schema_version", 2), ("approved", False),
                             ("asset_permissions", False), ("text_only", None), ("summary", "")]:
            data = copy.deepcopy(self.data)
            data[field] = value
            with self.subTest(field=field), self.assertRaises(BrandError):
                validate_brand(data, self.intake)
        data = copy.deepcopy(self.data)
        data["speech_key"] = "not-a-real-key"
        with self.assertRaises(BrandError):
            validate_brand(data, self.intake)
        data = copy.deepcopy(self.data)
        data["typography"]["system_font"] = False
        with self.assertRaises(BrandError):
            validate_brand(data, self.intake)
        data = copy.deepcopy(self.data)
        data["materials"] = [{"path": "unknown.xls", "role": "content"}]
        with self.assertRaises(BrandError):
            validate_brand(data, self.intake)

    def test_text_only_and_script_safe_brand_data(self):
        self.data.update({"text_only": True, "logos": {}, "name": "A </script> B"})
        write_json(self.intake / "intake.json", self.data)
        rendered = install_brand(self.intake / "intake.json", self.root / "output")
        self.assertEqual(rendered["name"], "A </script> B")
        self.assertNotIn("</script>", (self.root / "output" / "brand.js").read_text())

    def test_fingerprint_tracks_changed_asset_bytes(self):
        setup(self.workspace, self.intake / "intake.json", approve=True)
        manifest = self.workspace / ".prototype-film" / "brand.json"
        before = brand_fingerprint(manifest)
        logo = manifest.parent / load_brand(manifest)["logos"]["primary"]
        logo.write_text(logo.read_text() + "\n", encoding="utf-8")
        self.assertNotEqual(before, brand_fingerprint(manifest))

    def test_nonlocal_or_executable_svg_rejected_before_setup(self):
        for svg in [
            '<svg><image href="https://example.com/image.png"/></svg>',
            '<svg><style>@import "https://example.com/font.css";</style></svg>',
            '<svg onload="alert(1)"/>',
        ]:
            (self.intake / "logo.svg").write_text(svg, encoding="utf-8")
            with self.subTest(svg=svg), self.assertRaises(BrandError):
                setup(self.workspace, self.intake / "intake.json", approve=True)
            self.assertFalse((self.workspace / ".prototype-film" / "brand.json").exists())


if __name__ == "__main__":
    unittest.main()
