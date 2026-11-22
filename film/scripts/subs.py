# Writes burned-in ASS captions in the brand font and palette, bottom centre. Each cue is split
# into chunks of at most ~72 characters at sentence ends (then
# commas), and each chunk is timed by its share of the cue's characters. Usage: python subs.py
import json
import re

from filmcfg import load, brand_data

cfg = load(); CP = cfg["captions"]; MAXC = CP["max_chars"]
plan = json.load(open(cfg["plan"], encoding="utf-8"))


def chunks(text):
    """Caption chunks: sentences (then clauses at commas) packed greedily up to MAXC characters; a fragment
    shorter than MINC joins its neighbour, so no caption flashes up for half a second."""
    pieces = []
    for p in re.split(r"(?<=[.:;?])\s+", text.strip()):
        while len(p) > MAXC:
            k = p.rfind(", ", 0, MAXC)
            if k < 30:
                break
            pieces.append(p[:k + 1]); p = p[k + 2:]
        pieces.append(p)
    out = []
    for p in pieces:
        if out and len(out[-1]) + 1 + len(p) <= MAXC:
            out[-1] += " " + p
        else:
            out.append(p)
    MINC = 24; k = 0
    while k < len(out) and len(out) > 1:
        if len(out[k]) < MINC:
            j = k + 1 if k + 1 < len(out) and (k == 0 or len(out[k + 1]) <= len(out[k - 1])) else k - 1
            a, b = sorted((k, j)); out[a:b + 1] = [out[a] + " " + out[b]]; k = 0
        else:
            k += 1
    return out


def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


W, H = cfg["capture"]["width"], cfg["capture"]["height"]
palette = brand_data().get("palette", {})


def ass_color(value, alpha="00"):
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("caption colour must be a hex RGB colour")
    return f"&H{alpha}{value[4:6]}{value[2:4]}{value[0:2]}".upper()


fg = ass_color(palette.get("foreground", "#ffffff"))
bg = ass_color(palette.get("background", "#000000"), "33")
head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{CP['font']},{CP['size']},{fg},{fg},{bg},{bg},0,0,0,0,100,100,0,0,3,14,0,2,{CP['margin_lr']},{CP['margin_lr']},{CP['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
lines = []
for c in plan["cues"]:
    a, b = c["src"]; dur = b - a; ch = chunks(c["text"]); L = sum(len(x) for x in ch); t = c["at"]
    for x in ch:
        d = dur * len(x) / L
        lines.append(f"Dialogue: 0,{ts(t)},{ts(t + d - 0.04)},Cap,,0,0,0,,{x}")
        t += d
open(CP["file"], "w", encoding="utf-8").write(head + "\n".join(lines) + "\n")
print(len(lines), "caption lines ->", CP["file"])
