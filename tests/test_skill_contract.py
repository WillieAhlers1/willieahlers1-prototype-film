import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_skill_discovery_and_reference_links(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: prototype-film\n"))
        description = re.search(r"^description: '(.+)'$", text, re.M).group(1)
        self.assertLessEqual(len(description), 1024)
        self.assertIn("branding", description)
        self.assertIn("film", description)
        self.assertIn("any brand", description)
        self.assertLess(len(text.splitlines()), 500)
        for relative in re.findall(r"\]\(\./([^)#]+)", text):
            with self.subTest(reference=relative):
                self.assertTrue((ROOT / relative).is_file())
        self.assertIn("One concept confirmation", text)
        self.assertIn("whole-outcome ownership", text)
        self.assertIn("en-GB-OliviaNeural", text)
        self.assertIn("at most 160", text)
        self.assertIn("preview", text)
        for relative in ("references/brand-setup.md", "references/voice.md",
                         "references/film.md", "film/scripts/README.md", "README.md"):
            guide = (ROOT / relative).read_text(encoding="utf-8")
            for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", guide):
                if "://" not in link and not link.startswith("#"):
                    with self.subTest(guide=relative, link=link):
                        self.assertTrue((ROOT / relative).parent.joinpath(link).exists())

    def test_cleanup_refuses_persistent_brand_home_and_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            home = workspace / ".prototype-film"
            home.mkdir()
            (home / "brand.json").write_text("{}", encoding="utf-8")
            proto = workspace / "working" / "demo"
            (proto / "dist").mkdir(parents=True)
            (proto / "dist" / "demo.html").write_text("<html>packed fixture</html>")
            for build in (workspace, home):
                result = subprocess.run([sys.executable, str(ROOT / "assets" / "cleanup.py"),
                                         str(proto), "--build", str(build), "--yes"],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing", result.stderr)
                self.assertTrue((home / "brand.json").exists())


if __name__ == "__main__":
    unittest.main()
