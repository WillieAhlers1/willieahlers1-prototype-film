"""Create a prototype with a validated workspace brand snapshot."""
import argparse
import shutil
from pathlib import Path

from brand import BrandError, install_brand, load_brand


def create(workspace, name):
    if not name or Path(name).name != name or name in {".", ".."} or any(c in name for c in "\\/:"):
        raise BrandError("Prototype name must be a single directory name")
    workspace = Path(workspace).resolve()
    manifest = workspace / ".prototype-film" / "brand.json"
    load_brand(manifest)
    output = workspace / "working" / name
    if output.exists():
        raise BrandError(f"Prototype already exists; edit in place rather than overwrite: {output}")
    skill = Path(__file__).resolve().parent
    output.mkdir(parents=True)
    shutil.copytree(skill / "kit", output / "kit",
                    ignore=shutil.ignore_patterns("brand", "fonts", "photos", "__pycache__"))
    shutil.copy2(skill / "starter.html", output / "prototype.html")
    install_brand(manifest, output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    try:
        print("Prototype initialized:", create(args.workspace, args.name))
    except (BrandError, OSError) as exc:
        parser.exit(1, f"Prototype initialization failed: {exc}\n")


if __name__ == "__main__":
    main()
