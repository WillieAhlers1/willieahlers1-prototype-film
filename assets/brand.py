"""Validated, local workspace brand bundles shared by prototypes and films."""
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

SCHEMA_VERSION = 1
IMAGE_TYPES = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
FONT_TYPES = {".ttf", ".otf", ".woff", ".woff2"}
MATERIAL_TYPES = IMAGE_TYPES | {".pdf", ".pptx", ".docx", ".txt", ".md", ".json"}


class BrandError(ValueError):
    pass


def asset_path(root, value, allowed=None):
    if not isinstance(value, str) or not value or any(c in value for c in "\\\"'<>\n\r"):
        raise BrandError("Asset paths must be nonempty relative paths using '/' in the manifest")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or ":" in value:
        raise BrandError(f"Asset path must stay inside the brand bundle: {value}")
    resolved = (Path(root) / path).resolve()
    if not resolved.is_relative_to(Path(root).resolve()) or not resolved.is_file():
        raise BrandError(f"Missing or out-of-bundle asset: {value}")
    if allowed and resolved.suffix.lower() not in allowed:
        raise BrandError(f"Unsupported asset type: {value}")
    if resolved.suffix.lower() == ".svg":
        try:
            validate_svg(resolved.read_text(encoding="utf-8-sig"), value)
        except (OSError, UnicodeDecodeError) as exc:
            raise BrandError(f"Cannot read SVG asset {value}: {exc}") from exc
    return resolved


def validate_svg(text, name):
    references = re.findall(
        r'(?:\b(?:xlink:)?href\s*=\s*["\']([^"\']+)|url\(\s*["\']?([^)"\']+))', text, re.I)
    for pair in references:
        reference = next(x for x in pair if x).strip()
        if not reference.startswith(("#", "data:")):
            raise BrandError(f"SVG asset has a non-embedded reference: {reference} in {name}")
    if re.search(r"<\s*script\b|@import\b|\bon\w+\s*=", text, re.I):
        raise BrandError(f"SVG asset must be static and self-contained: {name}")


def _text(data, key, required=False):
    value = data.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise BrandError(f"{key} must be {'nonempty ' if required else ''}text")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise BrandError(f"{key} contains control characters")
    return value


def validate_brand(data, root, *, resolve_asset=asset_path):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != SCHEMA_VERSION:
        raise BrandError("Unsupported brand schema_version; expected 1")
    allowed = {"schema_version", "approved", "asset_permissions", "name", "summary", "palette",
               "typography", "text_only", "logos", "tagline", "signoff", "images", "materials",
               "pronunciations"}
    if set(data) - allowed:
        raise BrandError(f"Unknown brand fields (never put credentials here): {', '.join(sorted(set(data) - allowed))}")
    if data.get("approved") is not True or data.get("asset_permissions") is not True:
        raise BrandError("User approval and asset_permissions must both be true")
    _text(data, "name", True)
    _text(data, "summary", True)
    for key in ("tagline", "signoff"):
        _text(data, key)
    palette = data.get("palette")
    if not isinstance(palette, dict):
        raise BrandError("palette must contain accent, background, foreground and muted colors")
    for key in ("accent", "background", "foreground", "muted"):
        if not isinstance(palette.get(key), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", palette[key]):
            raise BrandError(f"palette.{key} must be a six-digit hex color")
    if set(palette) != {"accent", "background", "foreground", "muted"}:
        raise BrandError("palette only supports accent, background, foreground and muted")
    typography = data.get("typography")
    if not isinstance(typography, dict):
        raise BrandError("typography must specify family, files and system_font")
    if set(typography) - {"family", "files", "system_font"}:
        raise BrandError("typography only supports family, files and system_font")
    family = _text(typography, "family", True)
    if not re.fullmatch(r"[A-Za-z0-9 _-]+", family):
        raise BrandError("Font family must contain only letters, numbers, spaces, '_' or '-'")
    files = typography.get("files")
    if not isinstance(files, list) or not isinstance(typography.get("system_font"), bool):
        raise BrandError("typography.files must be a list and system_font a boolean")
    if not files and typography["system_font"] is not True:
        raise BrandError("Supply font files or explicitly approve a system font")
    for file in files:
        resolve_asset(root, file, FONT_TYPES)
    if not isinstance(data.get("text_only"), bool):
        raise BrandError("text_only must be an explicit boolean")
    logos = data.get("logos", {})
    if not isinstance(logos, dict) or any(k not in {"primary", "light", "dark"} for k in logos):
        raise BrandError("logos must contain primary and optional light/dark variants")
    if not data["text_only"] and not logos.get("primary"):
        raise BrandError("Supply a primary logo or explicitly approve text_only")
    for file in logos.values():
        resolve_asset(root, file, IMAGE_TYPES)
    images = data.get("images", [])
    materials = data.get("materials", [])
    if not isinstance(images, list) or not isinstance(materials, list):
        raise BrandError("images and materials must be lists")
    for file in images:
        resolve_asset(root, file, IMAGE_TYPES)
    for material in materials:
        if not isinstance(material, dict) or material.get("role") not in {"identity", "content", "visual"}:
            raise BrandError("Each material needs path and role (identity, content or visual)")
        if set(material) - {"path", "role"}:
            raise BrandError("materials only support path and role; provenance belongs in summary")
        resolve_asset(root, material.get("path"), MATERIAL_TYPES)
    pronunciations = data.get("pronunciations", {"say": {}, "ipa": {}})
    if not isinstance(pronunciations, dict) or set(pronunciations) - {"say", "ipa"}:
        raise BrandError("pronunciations must contain say/ipa dictionaries")
    for kind in ("say", "ipa"):
        entries = pronunciations.get(kind, {})
        if not isinstance(entries, dict) or any(
                not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                for k, v in entries.items()):
            raise BrandError(f"pronunciations.{kind} must map words to nonempty text")
    return copy.deepcopy(data)


def load_brand(path):
    path = Path(path).resolve()
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise BrandError(f"Cannot read brand manifest {path}: {exc}") from exc
    return validate_brand(data, path.parent)


def find_manifest(workspace_or_path):
    path = Path(workspace_or_path).resolve()
    if path.name == "brand.json" and path.is_file():
        return path
    start = path if path.is_dir() else path.parent
    for directory in (start, *start.parents):
        candidate = directory / ".prototype-film" / "brand.json"
        if candidate.is_file():
            return candidate
    raise BrandError(f"No workspace brand configuration found from {path}; run brand_setup.py setup first")


def referenced_assets(data):
    return set(data.get("logos", {}).values()) | set(data.get("images", [])) | set(
        data["typography"]["files"]) | {m["path"] for m in data.get("materials", [])}


def brand_fingerprint(manifest_path):
    path = Path(manifest_path).resolve()
    data = load_brand(path)
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8"))
    for relative in sorted(referenced_assets(data)):
        digest.update(relative.encode("utf-8"))
        digest.update(asset_path(path.parent, relative).read_bytes())
    return digest.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def install_brand(manifest_path, output_dir):
    """Copy only approved assets, retaining a portable manifest and renderer data."""
    source = Path(manifest_path).resolve()
    data = load_brand(source)
    output = Path(output_dir).resolve()
    target = output / "brand"
    target.mkdir(parents=True, exist_ok=True)
    for relative in sorted(referenced_assets(data)):
        src = asset_path(source.parent, relative)
        dst = target / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src != dst.resolve():
            shutil.copy2(src, dst)
    write_json(target / "brand.json", data)
    rendered = copy.deepcopy(data)
    rendered["logos"] = {k: "brand/" + v for k, v in data.get("logos", {}).items()}
    rendered["images"] = ["brand/" + v for v in data.get("images", [])]
    rendered["typography"]["files"] = ["brand/" + v for v in data["typography"]["files"]]
    rendered["materials"] = [dict(m, path="brand/" + m["path"]) for m in data.get("materials", [])]
    payload = json.dumps(rendered, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e")
    (output / "brand.js").write_text("window.PROTOTYPE_BRAND = " + payload + ";\n", encoding="utf-8")
    (output / "brand.css").write_text(brand_css(rendered), encoding="utf-8")
    return rendered


def brand_css(data):
    p = data["palette"]
    family = data["typography"]["family"]
    css = []
    for path in data["typography"]["files"]:
        filename = Path(path).stem.lower()
        weight = next((value for label, value in [
            ("extrabold", 800), ("semibold", 600), ("bold", 700), ("medium", 500),
            ("light", 300), ("thin", 100)] if label in filename), 400)
        style = "italic" if "italic" in filename else "normal"
        css.append(f'@font-face{{font-family:"{family}";src:url("{path}");'
                   f'font-weight:{weight};font-style:{style};font-display:swap}}')
    tokens = "".join(f"--brand-{key}:{value};" for key, value in p.items())
    css.append(f':root{{--brand-font:"{family}",sans-serif;{tokens}}}')
    css.append('.frame,.brand-frame{font-family:var(--brand-font);'
               'background:var(--brand-background);color:var(--brand-foreground)}')
    return "\n".join(css) + "\n"
