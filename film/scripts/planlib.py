"""Helpers for a film's timing plan.

A film's plan script (templates/plan_template.py, or examples/woodgrove-sample/plan.py) creates a Plan,
describes its segments, and calls write(). Segments alternate prototype ("proto") and graphics ("gfx").

- proto(name, hash, replay, scenes): one browser session on the packed prototype opened at `hash`
  ("" = first scene, "#overnight" = that scene). Each scene is a function returning
  (cues, presses, duration): cues = [(cue_id, seconds from scene start)], presses = in-scene → presses
  (seconds from scene start). The → that moves to the next scene is added automatically at the scene boundary.
- gfx(name, seg, params, cues): one graphics.html sequence (`?seg=`), timed by params; params["end"] is its length.
- write(): builds the absolute timeline (segments overlap by the crossfade), asserts no two cues overlap and
  every cue is placed (require_all=False for a partial test plan), writes plan.json and prints the timeline.
"""
import json
import math
import re

from filmcfg import load


class Plan:
    def __init__(self, cfg=None):
        self.cfg = cfg or load()
        self.C = json.load(open(self.cfg["cues"], encoding="utf-8"))
        self.D = {k: v["dur"] for k, v in self.C.items()}
        self.X = self.cfg["crossfade_s"]
        self.segs = []

    def E(self, c, s):
        """End time of cue c when it starts at s."""
        return s + self.D[c]

    def proto(self, name, hash, replay, scenes):
        t = 0.0; presses = []; cues = []; marks = []
        for k, sc in enumerate(scenes):
            if k > 0:
                presses.append(round(t, 3))
            marks.append([sc.__name__, round(t, 3)])
            loc_c, loc_p, dur = sc()
            cues += [(c, round(t + s, 3)) for c, s in loc_c]
            presses += [round(t + p, 3) for p in loc_p]
            t += dur
        self.segs.append(dict(name=name, kind="proto", hash=hash, replay=replay, dur=round(t, 3),
                              presses=presses, cues=cues, scenes=marks))

    def gfx(self, name, seg, params, cues, dur=None):
        dur = params["end"] if dur is None else dur
        self.segs.append(dict(name=name, kind="gfx", seg=seg, params={k: round(v, 3) for k, v in params.items()},
                              dur=round(dur, 3), cues=cues))

    def report_pacing(self):
        """Measure voiced cue audio and the actual complete timeline, without extending either."""
        try:
            import speech
            say, ipa = speech.load_lexicon(home=self.cfg.get("home") or None)
            spoken = lambda text: speech.spoken(text, say, ipa)
        except ImportError:
            spoken = lambda text: text
        cues = []; static = []; offset = 0.0; words = 0; voiced = 0.0
        for i, seg in enumerate(self.segs):
            dur = seg["dur"]
            if not math.isfinite(dur) or dur <= 0:
                raise ValueError(f"{seg['name']}: invalid segment duration {dur}")
            activity = [0.0, dur]
            for cid, at in seg.get("cues", []):
                cue = self.C[cid]; d = cue["dur"]
                if not math.isfinite(at) or not math.isfinite(d) or at < 0 or d <= 0 or at + d > dur + 0.001:
                    raise ValueError(f"{seg['name']}: cue {cid} is outside the segment")
                src = cue.get("src")
                if not src or len(src) != 2 or src[0] < 0 or abs((src[1] - src[0]) - d) > 0.01:
                    raise ValueError(f"cue {cid}: invalid audio range/duration")
                count = len(re.findall(r"[^\W_]+(?:['’][^\W_]+)*", spoken(cue["text"]), re.UNICODE))
                words += count; voiced += d
                cues.append((offset + at, offset + at + d, cid))
                activity.extend((at, at + d))
            if seg["kind"] == "proto":
                activity.extend(seg.get("steps") or seg.get("presses") or [])
                for a, b in zip(sorted(activity), sorted(activity)[1:]):
                    if b - a >= self.cfg["pacing"].get("static_warning_s", 4.0):
                        if not any(start < offset + b and end > offset + a for start, end, _ in cues):
                            static.append((seg["name"], a, b))
            offset += dur - (self.X if i < len(self.segs) - 1 else 0)
        if offset <= 0 or voiced <= 0:
            raise ValueError("pacing requires a positive film duration and voiced cues")
        for a, b in zip(sorted(cues), sorted(cues)[1:]):
            if a[1] > b[0] + 0.001:
                raise ValueError(f"cue {a[2]} overlaps {b[2]}")
        voice_wpm = 60 * words / voiced; film_wpm = 60 * words / offset
        target = self.cfg["pacing"].get("spoken_target_wpm", 166)
        maximum = self.cfg["pacing"].get("film_max_wpm", 160)
        print(f"pacing: {words} spoken words, {voiced:.2f}s voiced; spoken {voice_wpm:.1f} WPM "
              f"(target ~{target:g}), complete film {film_wpm:.1f} WPM (max {maximum:g})")
        print(f"pacing: {offset - voiced:.2f}s non-speech for reading, transitions and settling")
        for name, a, b in static:
            print(f"pacing: possible static silence {name} {a:.2f}-{b:.2f}s ({b-a:.2f}s); review intended holds")
        if film_wpm > maximum + 1e-9:
            raise ValueError(f"complete film {film_wpm:.1f} WPM exceeds {maximum:g}; revise narration or timing")
        return {"words": words, "voiced_s": voiced, "spoken_wpm": voice_wpm,
                "film_wpm": film_wpm, "static_silence": static}

    def write(self, min_gap=0.2, require_all=True):
        X = self.X; t = 0.0; allc = []
        for k, s in enumerate(self.segs):
            s["start"] = round(t, 3)
            allc += [dict(id=c, at=round(t + o, 3), src=self.C[c]["src"], text=self.C[c]["text"]) for c, o in s["cues"]]
            t += s["dur"] - (X if k < len(self.segs) - 1 else 0)
        total = round(t, 3)
        allc.sort(key=lambda c: c["at"])
        for a, b in zip(allc, allc[1:]):
            assert a["at"] + self.D[a["id"]] + min_gap <= b["at"], f"cue {a['id']} runs into {b['id']}"
        unused = sorted(set(self.C) - {c["id"] for c in allc})
        assert not (require_all and unused), f"cues never placed: {unused}"
        json.dump(dict(total=total, X=X, segments=self.segs, cues=allc), open(self.cfg["plan"], "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
        print("total", total, f"({int(total // 60)}:{total % 60:04.1f})")
        for s in self.segs:
            print(s["name"], s["start"], s["dur"], s.get("params", ""), len(s.get("presses", [])))
        print("timeline:")
        for s in self.segs:
            for nm, off in (s.get("scenes") or [[s.get("seg", s["name"]), 0.0]]):
                a = s["start"] + off
                print(f"  {int(a // 60)}:{a % 60:04.1f}  {s['name']} {nm}")
        return total
