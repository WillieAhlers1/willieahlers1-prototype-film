"""Pack a prototype into one self-contained HTML file that opens anywhere (double-click, email, OneDrive, Teams).

    python pack_prototype.py working/<name>/prototype.html            # -> working/<name>/dist/<name>.html
    python pack_prototype.py working/<name>/prototype.html out.html   # explicit output path

Inlines <link rel="stylesheet">, <script src>, and every local image referenced by src=, url(...) or data-bg=.
Stops if the prototype would load anything from the network or has lost its concept label, because a demo that
breaks on hotel Wi-Fi, or that could pass for a real product, is worse than no demo.
"""
import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

from brand import BrandError, load_brand, validate_brand, validate_svg

MAX_MB = 15
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("image/svg+xml", ".svg")


def data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as fh:
        data = fh.read()
    if mime == "image/svg+xml":
        try:
            validate_svg(data.decode("utf-8-sig"), path)
        except (BrandError, UnicodeDecodeError) as exc:
            sys.exit(str(exc))
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def local(base, ref):
    ref = ref.strip().strip("'\"")
    if re.match(r"^(data:|#)", ref, re.I):
        return None
    if re.match(r"^(//|[a-z][a-z0-9+.-]*:)", ref, re.I):
        sys.exit(f"External reference is not allowed: {ref}")
    path = os.path.normpath(os.path.join(base, ref.split("?")[0].split("#")[0]))
    if not os.path.isfile(path):
        sys.exit(f"Missing file: {ref} (looked for {path})")
    return path


def inline_urls(text, base):
    def url(m):
        p = local(base, m.group(2))
        return m.group(0) if not p else f"url({data_uri(p)})"
    return re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", url, text)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = os.path.abspath(sys.argv[1])
    base = os.path.dirname(src)
    name = os.path.basename(base) if os.path.basename(src) == "prototype.html" else os.path.splitext(os.path.basename(src))[0]
    out = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(base, "dist", f"{name}.html")
    html = open(src, encoding="utf-8").read()
    scripts = list(re.finditer(r'<script\s+src="([^"]+)"\s*>\s*</script>', html))
    brand_scripts = [m for m in scripts if os.path.basename(m.group(1).replace("\\", "/")) == "brand.js"]
    styles = [m for m in scripts if os.path.basename(m.group(1).replace("\\", "/")) == "proto-style.js"]
    if len(brand_scripts) != 1 or len(styles) != 1 or brand_scripts[0].start() > styles[0].start():
        sys.exit("Load exactly one brand.js before kit/proto-style.js.")
    brand_css = list(re.finditer(r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*/?>', html))
    brand_css = [m for m in brand_css if os.path.basename(m.group(1).replace("\\", "/")) == "brand.css"]
    if len(brand_css) != 1 or brand_css[0].start() < styles[0].start():
        sys.exit("Load exactly one brand.css after kit/proto-style.js.")
    brand_path = local(base, brand_scripts[0].group(1))
    code = Path(brand_path).read_text(encoding="utf-8")
    match = re.fullmatch(r'\s*window\.PROTOTYPE_BRAND\s*=\s*(\{.*\})\s*;\s*', code, re.S)
    if not match:
        sys.exit("Invalid brand.js: expected window.PROTOTYPE_BRAND = <JSON>;")
    try:
        brand = json.loads(match.group(1))
        validate_brand(brand, Path(base))
    except (ValueError, BrandError) as exc:
        sys.exit(f"Invalid embedded brand configuration: {exc}")
    snapshot = Path(base) / "brand" / "brand.json"
    if snapshot.is_file():
        try:
            expected = load_brand(snapshot)
        except BrandError as exc:
            sys.exit(f"Invalid brand snapshot: {exc}")
        expected["logos"] = {key: "brand/" + ref for key, ref in expected.get("logos", {}).items()}
        expected["typography"]["files"] = ["brand/" + ref for ref in expected["typography"]["files"]]
        expected["images"] = ["brand/" + ref for ref in expected.get("images", [])]
        expected["materials"] = [dict(item, path="brand/" + item["path"]) for item in expected.get("materials", [])]
        if brand != expected:
            sys.exit("brand.js does not match the approved brand/brand.json snapshot; reinstall the brand.")

    def embed(ref):
        path = local(base, ref)
        if not path:
            sys.exit(f"Invalid brand asset: {ref}")
        return data_uri(path)

    brand["logos"] = {key: embed(ref) for key, ref in brand.get("logos", {}).items()}
    brand["typography"]["files"] = [embed(ref) for ref in brand["typography"]["files"]]
    brand["images"] = [embed(ref) for ref in brand.get("images", [])]
    brand["materials"] = [dict(item, path=embed(item["path"])) for item in brand.get("materials", [])]
    packed_brand = "window.PROTOTYPE_BRAND = " + json.dumps(brand, ensure_ascii=True).replace("<", "\\u003c") + ";"

    def css(m):
        p = local(base, m.group(1))
        if not p:
            sys.exit(f"External stylesheet: {m.group(1)}.  Prototypes must work offline; copy what you need into kit/.")
        return "<style>\n" + inline_urls(open(p, encoding="utf-8").read(), os.path.dirname(p)) + "\n</style>"
    html = re.sub(r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*/?>', css, html)

    def js(m):
        p = local(base, m.group(1))
        if not p:
            sys.exit(f"External script: {m.group(1)}.  Prototypes must work offline; copy what you need into kit/.")
        code = packed_brand if os.path.abspath(p) == os.path.abspath(brand_path) else open(p, encoding="utf-8").read()
        code = code.replace("</script", "<\\/script")
        return "<script>\n" + code + "\n</script>"
    html = re.sub(r'<script\s+src="([^"]+)"\s*>\s*</script>', js, html)

    def attr(m):
        p = local(base, m.group(2))
        return m.group(0) if not p else f'{m.group(1)}="{data_uri(p)}"'
    html = re.sub(r'\b(src|data-bg|poster)="([^"]+)"', attr, html)
    html = inline_urls(html, base)

    problems = []
    for m in re.finditer(r'(?:src|href)="(https?:)?//[^"]+"|url\((["\']?)(https?:)?//', html):
        problems.append(m.group(0)[:100])
    if problems:
        sys.exit("The prototype still loads from the network (not allowed; it must run offline):\n  " + "\n  ".join(problems))
    concept = re.search(r'<body[^>]*data-concept="([^"]+)"', html)
    if not concept or not re.search(r"concept|illustrative|fictitious|prototype", concept.group(1), re.I):
        sys.exit('The <body> needs data-concept="Concept demo · Fictitious data" (or similar wording that says it is a '
                 "concept with made-up data).")

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    mb = os.path.getsize(out) / 1e6
    print(f"{out}\n  {mb:.2f} MB, single file, no network dependencies, label: {concept.group(1)}")
    if mb > MAX_MB:
        print(f"  Warning: over {MAX_MB} MB.  Use fewer or smaller images (JPG, 1920 px wide at most).")


if __name__ == "__main__":
    main()
