"""Initialize a film with an approved, self-contained brand snapshot."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
from pathlib import Path

FILM = Path(__file__).resolve().parent.parent
SKILL = FILM.parent
sys.path.insert(0, str(SKILL / "assets"))


def find_home(proto=None, workspace=None):
    """Prefer the new workspace home, retaining existing legacy profiles and models."""
    if os.environ.get("PROTOTYPE_FILM_HOME"):
        return os.environ["PROTOTYPE_FILM_HOME"]
    if os.environ.get("TREDENCE_HOME"):
        print("Using legacy TREDENCE_HOME for voice profile and models.")
        return os.environ["TREDENCE_HOME"]
    root = Path(workspace).resolve() if workspace else None
    if root is None and proto:
        for d in Path(proto).resolve().parents:
            if (d / ".prototype-film").is_dir() or (d / ".tredence").is_dir():
                root = d
                break
            if d.name == "working":
                root = d.parent
                break
    if root:
        generic, legacy = root / ".prototype-film", root / ".tredence"
        generic_runtime = any((generic / x).exists() for x in ("voice.json", "kokoro", "lexicon.json"))
        legacy_runtime = any((legacy / x).exists() for x in ("voice.json", "kokoro", "lexicon.json"))
        if legacy_runtime and not generic_runtime:
            print("Using legacy workspace .tredence for voice profile and models.")
            return str(legacy)
        return str(generic)
    legacy = Path.home() / ".tredence"
    generic = Path.home() / ".prototype-film"
    if not generic.exists() and legacy.is_dir():
        print("Using legacy ~/.tredence for voice profile and models.")
        return str(legacy)
    return str(generic)


def fingerprint(path, data, embedded=False):
    """Compare metadata and asset bytes, independent of copied asset paths."""
    data = json.loads(json.dumps(data))
    root = path.parent

    def asset(value):
        if embedded:
            if not isinstance(value, str) or not value.startswith("data:") or ";base64," not in value:
                raise ValueError("packed prototype contains a non-embedded brand asset")
            return hashlib.sha256(base64.b64decode(value.split(",", 1)[1], validate=True)).hexdigest()
        return hashlib.sha256((root / value).read_bytes()).hexdigest()

    typography = data.get("typography", {})
    typography["files"] = [asset(p) for p in typography.get("files", [])]
    data["logos"] = {k: asset(v) for k, v in data.get("logos", {}).items() if v}
    data["images"] = [asset(p) for p in data.get("images", [])]
    data["materials"] = data.get("materials", [])
    for item in data["materials"]:
        item["path"] = asset(item["path"])
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def packed_brand(proto):
    if not proto:
        return None
    html = proto.read_text(encoding="utf-8")
    match = re.search(r"window\.PROTOTYPE_BRAND\s*=\s*", html)
    if not match:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(html[match.end():])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid packed prototype brand: {exc}") from exc
    return data


def prototype_snapshot(proto):
    if not proto:
        return None
    for folder in (proto.parent, proto.parent.parent):
        manifest = folder / "brand" / "brand.json"
        if manifest.is_file():
            return manifest.resolve()
    return None


def portable_embedded(data, validate_brand, validate_svg):
    """Validate packed identity in memory and prepare portable asset paths."""
    data = json.loads(json.dumps(data))
    assets = {}
    extensions = {
        "image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "font/ttf": ".ttf", "font/otf": ".otf", "font/woff": ".woff", "font/woff2": ".woff2",
        "application/font-woff": ".woff", "application/pdf": ".pdf", "text/plain": ".txt",
        "text/markdown": ".md", "application/json": ".json",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }

    def convert(uri):
        if not isinstance(uri, str) or not uri.startswith("data:") or ";base64," not in uri:
            raise ValueError("packed prototype contains a non-embedded brand asset")
        header, payload = uri.split(",", 1)
        mime = header[5:].split(";", 1)[0].lower()
        ext = extensions.get(mime) or mimetypes.guess_extension(mime)
        if not ext:
            raise ValueError(f"unsupported embedded brand asset type: {mime}")
        content = base64.b64decode(payload, validate=True)
        name = "assets/" + hashlib.sha256(content).hexdigest() + ext
        if ext.lower() == ".svg":
            validate_svg(content.decode("utf-8-sig"), name)
        assets[name] = content
        return name

    data["logos"] = {k: convert(v) for k, v in data.get("logos", {}).items()}
    data["images"] = [convert(v) for v in data.get("images", [])]
    data["typography"]["files"] = [convert(v) for v in data["typography"]["files"]]
    data["materials"] = [dict(m, path=convert(m["path"])) for m in data.get("materials", [])]
    def virtual_asset(root, value, allowed=None):
        if value not in assets or (allowed and Path(value).suffix.lower() not in allowed):
            raise ValueError(f"invalid embedded brand asset: {value}")
        return Path(value)

    validate_brand(data, Path("."), resolve_asset=virtual_asset)
    return data, assets


def discover(find_manifest, path):
    if not path:
        return None
    try:
        return Path(find_manifest(path)).resolve()
    except (FileNotFoundError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--prototype")
    ap.add_argument("--workspace")
    ap.add_argument("--brand", help="approved brand manifest or workspace")
    ap.add_argument("--name")
    ap.add_argument("--example")
    ap.add_argument("--force", action="store_true", help="overwrite film inputs and permit brand update")
    ap.add_argument("--update-brand", action="store_true", help="explicitly replace the saved brand snapshot")
    a = ap.parse_args()
    from brand import find_manifest, install_brand, load_brand, validate_brand, validate_svg

    B = Path(a.build_dir).resolve()
    p = Path(a.prototype).resolve() if a.prototype else None
    if p and not p.is_file():
        ap.error(f"prototype not found: {p}")
    ex = FILM / "examples" / a.example if a.example else None
    if ex and not ex.is_dir():
        ap.error(f"example not found: {ex}")
    explicit = discover(find_manifest, a.brand or a.workspace)
    if (a.brand or a.workspace) and not explicit:
        ap.error("approved brand manifest not found")
    snapshot_source = prototype_snapshot(p)
    discovered = discover(find_manifest, p)
    try:
        proto_brand = packed_brand(p)
        selected = explicit or snapshot_source or (None if proto_brand else discovered)
        if not selected and not proto_brand:
            ap.error("supply --workspace or --brand, or use a prototype with a discoverable brand")
        embedded_assets = None
        if selected:
            selected_data = load_brand(selected)
            source_fingerprint = fingerprint(selected, selected_data)
        else:
            selected_data, embedded_assets = portable_embedded(proto_brand, validate_brand, validate_svg)
            source_fingerprint = fingerprint(p, proto_brand, embedded=True)
        if proto_brand and fingerprint(p, proto_brand, embedded=True) != source_fingerprint:
            ap.error("prototype brand does not match the requested brand")
        if snapshot_source and fingerprint(snapshot_source, load_brand(snapshot_source)) != source_fingerprint:
            ap.error("prototype brand snapshot does not match the requested brand")
        if snapshot_source:
            selected = snapshot_source
            selected_data = load_brand(selected)
        if ex and selected_data["name"].strip().casefold() != "tredence":
            ap.error("legacy examples require an explicitly selected Tredence brand")
        if ex and not explicit:
            ap.error("legacy examples require --brand or --workspace with a Tredence brand")
        snapshot = B / "brand" / "brand.json"
        if snapshot.exists() and fingerprint(snapshot, load_brand(snapshot)) != source_fingerprint:
            if not (a.force or a.update_brand):
                ap.error("brand snapshot changed; use --update-brand or --force to replace it")
    except (ValueError, OSError, KeyError, TypeError) as e:
        ap.error(f"invalid brand: {e}")

    B.mkdir(parents=True, exist_ok=True)
    for f in (FILM / "scripts").iterdir():
        if f.suffix in (".py", ".js") and f.name != "new_film.py":
            shutil.copy2(f, B / f.name)
    shutil.copy2(SKILL / "assets" / "brand.py", B / "brand.py")
    (B / "lexicon").mkdir(exist_ok=True)
    shutil.copy2(FILM / "lexicon" / "generic.json", B / "lexicon" / "generic.json")
    if ex:
        shutil.copy2(FILM / "lexicon" / "tredence.json", B / "lexicon" / "tredence.json")
    shutil.copy2(FILM / "templates" / "graphics.html", B / "graphics.html")
    if not snapshot.exists() or a.force or a.update_brand:
        if (B / "brand").exists() and selected != snapshot:
            shutil.rmtree(B / "brand")
        if embedded_assets is not None:
            for name, content in embedded_assets.items():
                target = B / "brand" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(json.dumps(selected_data, indent=2, ensure_ascii=False), encoding="utf-8")
            selected = snapshot
        install_brand(selected, B)
        if (B / "fonts").exists():
            shutil.rmtree(B / "fonts")
    elif not (B / "brand.js").exists() or not (B / "brand.css").exists():
        install_brand(snapshot, B)
    (B / "fonts").mkdir(exist_ok=True)
    for font in load_brand(snapshot)["typography"]["files"]:
        source = snapshot.parent / font
        dest = B / "fonts" / (hashlib.sha256(source.read_bytes()).hexdigest()[:16] + source.suffix)
        if not dest.exists():
            shutil.copy2(source, dest)
    (B / "images").mkdir(exist_ok=True)
    src = {"film.json": FILM / "templates" / "film.json",
           "plan.py": FILM / "templates" / "plan_template.py",
           "narration.txt": FILM / "templates" / "narration-script-template.txt",
           "lexicon.json": FILM / "templates" / "lexicon.json"}
    if ex:
        for f in ex.iterdir():
            if f.is_file() and f.name not in src and f.suffix != ".md":
                shutil.copy2(f, B / f.name)
        if (ex / "images").is_dir():
            shutil.copytree(ex / "images", B / "images", dirs_exist_ok=True)
        src.update({k: ex / k for k in src if (ex / k).exists()})
    for name, source in src.items():
        if a.force or not (B / name).exists():
            shutil.copy2(source, B / name)
            if name == "narration.txt" and not ex:
                narration = (B / name).read_text(encoding="utf-8").replace("<Brand>", selected_data["name"])
                (B / name).write_text(narration, encoding="utf-8")
            print("new", name)
        else:
            print("kept", name)
    cfg = json.loads((B / "film.json").read_text(encoding="utf-8"))
    if p:
        (B / "proto").mkdir(exist_ok=True)
        shutil.copy2(p, B / "proto" / p.name)
        cfg.setdefault("prototype", {}).update({"dir": "proto", "file": p.name})
    if a.name:
        cfg["name"] = a.name
    if not cfg.get("home"):
        manifest_workspace = explicit.parent.parent if explicit and explicit.parent.name == ".prototype-film" else None
        cfg["home"] = find_home(p, a.workspace or manifest_workspace)
    cfg["tmp"] = cfg.get("tmp") or "work"
    (B / "film.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print("build folder ready:", B)
    print("voice home:", cfg["home"])


if __name__ == "__main__":
    main()
