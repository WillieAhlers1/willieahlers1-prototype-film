"""Approve a brand intake once per workspace; never modify the installed skill."""
import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path

from brand import (BrandError, SCHEMA_VERSION, asset_path, load_brand,
                   referenced_assets, validate_brand, write_json)


def setup(workspace, intake_path, approve=False, update=False):
    if not approve:
        raise BrandError("Setup requires explicit user approval; pass --approve only after confirmation")
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise BrandError(f"Workspace directory does not exist: {workspace}")
    intake = Path(intake_path).resolve()
    try:
        data = json.loads(intake.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrandError(f"Cannot read intake {intake}: {exc}") from exc
    if not isinstance(data, dict):
        raise BrandError("Brand intake must be a JSON object")
    data = copy.deepcopy(data)
    data["approved"] = True
    data = validate_brand(data, intake.parent)
    home = workspace / ".prototype-film"
    destination = home / "brand.json"
    if destination.exists() and not update:
        raise BrandError("Brand already configured; use validate to reuse, or --update after approval")
    home.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brand-setup-", dir=home) as temp:
        staging = Path(temp) / "bundle"
        staging.mkdir()
        remap = {}
        for index, relative in enumerate(sorted(referenced_assets(data))):
            source = asset_path(intake.parent, relative)
            # A dedicated asset subtree cannot overwrite runtime state or the manifest.
            new_path = f"brand/assets/{index:03d}-{source.name}"
            target = staging / new_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            remap[relative] = new_path
        data["logos"] = {k: remap[v] for k, v in data.get("logos", {}).items()}
        data["images"] = [remap[v] for v in data.get("images", [])]
        data["typography"]["files"] = [remap[v] for v in data["typography"]["files"]]
        data["materials"] = [dict(m, path=remap[m["path"]]) for m in data.get("materials", [])]
        write_json(staging / "brand.json", data)
        load_brand(staging / "brand.json")
        assets = home / "brand"
        backup = Path(temp) / "previous-brand"
        if assets.exists():
            assets.rename(backup)
        try:
            if (staging / "brand").exists():
                (staging / "brand").rename(assets)
            (staging / "brand.json").replace(destination)
        except OSError:
            if assets.exists():
                shutil.rmtree(assets)
            if backup.exists():
                backup.rename(assets)
            raise
    return load_brand(destination)


def legacy_intake(output):
    kit = Path(__file__).resolve().parent / "kit"
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for source, relative in [
        (kit / "brand" / "wordmark-orange.svg", "logo.svg"),
        (kit / "brand" / "wordmark-white.svg", "logo-light.svg"),
        (kit / "fonts" / "Poppins-Regular.ttf", "Poppins-Regular.ttf"),
    ]:
        if not source.is_file():
            raise BrandError(f"Legacy asset not found: {source}")
        shutil.copy2(source, output / relative)
    data = {
        "schema_version": SCHEMA_VERSION, "name": "Tredence", "approved": False,
        "asset_permissions": False, "text_only": False,
        "palette": {"accent": "#fe5000", "background": "#ffffff",
                    "foreground": "#404041", "muted": "#e6e7e8"},
        "typography": {"family": "Poppins", "files": ["Poppins-Regular.ttf"], "system_font": False},
        "logos": {"primary": "logo.svg", "light": "logo-light.svg"},
        "tagline": "#BeyondPossible", "signoff": "#BeyondPossible",
        "summary": "Explicit legacy Tredence identity import; review assets and messaging before approval.",
        "images": [], "materials": [], "pronunciations": {"say": {}, "ipa": {}},
    }
    write_json(output / "intake.json", data)
    return output / "intake.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("setup")
    start.add_argument("--workspace", required=True)
    start.add_argument("--intake", required=True)
    start.add_argument("--approve", action="store_true")
    start.add_argument("--update", action="store_true")
    check = commands.add_parser("validate")
    check.add_argument("--workspace", required=True)
    legacy = commands.add_parser("import-tredence")
    legacy.add_argument("--output", required=True, help="explicit directory for reviewable legacy intake")
    args = parser.parse_args()
    try:
        if args.command == "setup":
            data = setup(args.workspace, args.intake, args.approve, args.update)
            print(f"Brand configured and verified: {data['name']}")
        elif args.command == "validate":
            path = Path(args.workspace).resolve() / ".prototype-film" / "brand.json"
            data = load_brand(path)
            print(f"Brand valid; reuse without onboarding: {data['name']}")
        else:
            print("Review permissions and set asset_permissions=true before setup:", legacy_intake(args.output))
    except (BrandError, OSError) as exc:
        parser.exit(1, f"Brand setup failed: {exc}\n")


if __name__ == "__main__":
    main()
