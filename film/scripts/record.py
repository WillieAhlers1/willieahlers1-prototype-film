"""Capture a segment on Playwright's virtual frame clock.

Usage: python record.py SEG [--capture-mode frame-clock|compatibility] [--preview SECONDS]
The default writes <tmp>/frames_SEG; compatibility explicitly selects the older wall-clock CDP screencast.
Preview renders a bounded, separate <tmp>/preview/SEG/preview.mp4 with its own plan, mix and captions.
Driven segments use proto.step(); other prototypes use the scheduled keys, and graphics call window.start().
The Node recorder supports compatibility mode only. Virtual time controls timers/RAF; Web Animations are sought
on the frame clock as well. Media decoding and animated image formats are not virtualized.
"""
import asyncio
import argparse
import base64
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from filmcfg import load

HERE = Path(__file__).resolve().parent


def find_docgen_shell():
    root = Path("/opt/docgen-browsers")
    if not root.exists():
        return None
    d = sorted(x for x in os.listdir(root) if x.startswith("chromium_headless_shell-"))
    return str(root / d[-1] / "chrome-headless-shell-linux64" / "chrome-headless-shell") if d else None


async def launch(pw, cfg, args):
    exe = os.environ.get("CHR") or cfg["capture"].get("chrome")
    if exe:
        return await pw.chromium.launch(executable_path=exe, args=args)
    errors = []
    for opts in ({}, {"channel": "msedge"}, {"channel": "chrome"}, {"executable_path": find_docgen_shell()}):
        if "executable_path" in opts and not opts["executable_path"]:
            continue
        try:
            return await pw.chromium.launch(args=args, **opts)
        except Exception as e:  # try the next browser
            errors.append(f"{opts or 'playwright chromium'}: {str(e).splitlines()[0]}")
    raise SystemExit("no browser for Playwright: " + " | ".join(errors) + "  (run: python -m playwright install chromium)")


def page_url(cfg, seg):
    if seg["kind"] == "proto":
        p = Path(cfg["prototype"]["dir"], cfg["prototype"]["file"]).resolve()
        return p.as_uri() + ("?driven" if seg.get("driven") else "") + (seg.get("hash") or "")
    q = urlencode({"seg": seg["seg"], **{k: str(v) for k, v in seg["params"].items()}})
    return Path(cfg["graphics"]["file"]).resolve().as_uri() + "?" + q


def init_script(cfg, rate):
    css = json.dumps(cfg["prototype"].get("film_css") or "")
    return (f"window.__RATE__={rate};" + (HERE / "slowtime.js").read_text(encoding="utf-8") +
            f";(()=>{{const css={css};if(!css)return;const add=()=>{{const s=document.createElement('style');"
            "s.textContent=css;(document.head||document.documentElement).appendChild(s);};"
            "if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',add);else add();})();")


async def record_compatibility(name, cfg, seg, out):
    from playwright.async_api import async_playwright
    C = cfg["capture"]; PR = cfg["prototype"]; K = PR["keys"]; RATE = C["rate"]
    print("capture mode: compatibility (wall-clock CDP screencast; not frame-clock capture)", flush=True)
    shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    async with async_playwright() as pw:
        b = await launch(pw, cfg, ["--force-device-scale-factor=1", "--hide-scrollbars"])
        p = await b.new_page(viewport={"width": C["width"], "height": C["height"]})
        page_errors = []
        p.on("pageerror", lambda error: page_errors.append(str(error)))
        await p.add_init_script(init_script(cfg, RATE))
        await p.goto(page_url(cfg, seg))
        if page_errors:
            raise SystemExit(f"page error during capture: {page_errors[0]}")
        s = await p.context.new_cdp_session(p)
        await s.send("Animation.enable"); await s.send("Animation.setPlaybackRate", {"playbackRate": RATE})
        driven = seg["kind"] == "proto" and seg.get("driven")
        if driven:
            await p.wait_for_function("window.proto && window.proto.driven")
            await p.evaluate("() => proto.ready.then(() => 1)")      # warm-up painted every scene once
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(PR["warmup_s"] if seg["kind"] == "proto" else C["gfx_settle_ms"] / 1000)
        if seg["kind"] == "proto" and not driven and K.get("hide"):
            await p.keyboard.press(K["hide"])          # presenter click cues off
        ts = []; n = 0; pending = set()

        def on_frame(f):
            nonlocal n
            n += 1; ts.append(f["metadata"]["timestamp"])
            (out / f"{n:06d}.jpg").write_bytes(base64.b64decode(f["data"]))
            t = asyncio.ensure_future(s.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]}))
            pending.add(t); t.add_done_callback(pending.discard)

        s.on("Page.screencastFrame", on_frame)
        await s.send("Page.startScreencast", {"format": "jpeg", "quality": C["jpeg_quality"],
                                             "maxWidth": C["width"], "maxHeight": C["height"]})
        await asyncio.sleep(C["pre_roll_ms"] / 1000)
        T0 = time.time()
        if seg["kind"] == "gfx":
            await p.evaluate("() => window.start()")
        elif driven:
            for t in seg.get("steps") or []:
                w = T0 + t / RATE - time.time()
                if w > 0:
                    await asyncio.sleep(w)
                await p.evaluate("() => { proto.step(); }")
        elif seg.get("replay") and K.get("replay"):
            await p.keyboard.press(K["replay"])        # replay the scene opened by #hash from its first beat
        for t in ([] if driven else seg.get("presses") or []):
            w = T0 + t / RATE - time.time()
            if w > 0:
                await asyncio.sleep(w)
            await p.keyboard.press(K["next"])
        end_due = T0 + (seg["dur"] + 0.4) / RATE - time.time()
        if end_due > 0:
            await asyncio.sleep(end_due)
        await s.send("Page.stopScreencast")
        await asyncio.sleep(0.2)
        (out / "meta.json").write_text(json.dumps({"mode": "compatibility", "T0": T0, "ts": ts,
                                                    "dur": seg["dur"], "rate": RATE}), encoding="utf-8")
        print(name, "frames", n, flush=True)
        await b.close()


async def record_clock(name, cfg, seg, out):
    """Capture each output frame explicitly; never treat screencast delivery as a clock."""
    from playwright.async_api import async_playwright
    C = cfg["capture"]; PR = cfg["prototype"]; K = PR["keys"]
    fps = C.get("fps", 30)
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise SystemExit("capture.fps must be a positive integer")
    if not math.isfinite(seg["dur"]) or seg["dur"] <= 0:
        raise SystemExit("segment duration must be positive and finite")
    count = math.ceil(seg["dur"] * fps - 1e-9)
    async with async_playwright() as pw:
        b = await launch(pw, cfg, ["--force-device-scale-factor=1", "--hide-scrollbars"])
        try:
            p = await b.new_page(viewport={"width": C["width"], "height": C["height"]})
            page_errors = []
            p.on("pageerror", lambda error: page_errors.append(str(error)))
            # CSS is applied on navigation, but the slow-time shim is only for compatibility.
            css = json.dumps((PR.get("film_css") or "") +
                             "\n*,*::before,*::after{animation-play-state:paused!important}")
            await p.add_init_script(f"""(() => {{ const css={css}; if (!css) return;
                const animate=Element.prototype.animate;
                Element.prototype.animate=function(...args) {{
                    const animation=animate.apply(this,args); animation.pause(); return animation;
                }};
                const add=()=>{{const s=document.createElement('style');s.textContent=css;
                (document.head||document.documentElement).appendChild(s)}};
                if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',add); else add(); }})()""")
            if not hasattr(p, "clock"):
                raise SystemExit("Playwright page.clock is unavailable; explicitly select --capture-mode compatibility")
            try:
                await p.clock.install(time=0)
                await p.clock.pause_at(0)
            except Exception as e:
                raise SystemExit(f"cannot install deterministic page.clock: {e}; explicitly select --capture-mode compatibility")
            await p.goto(page_url(cfg, seg))
            if page_errors:
                raise SystemExit(f"page error during capture: {page_errors[0]}")
            driven = seg["kind"] == "proto" and seg.get("driven")
            if driven:
                await p.wait_for_function("window.proto && window.proto.driven")
                # Drive warm-up timers and animation frames too; awaiting ready with a paused clock deadlocks.
                for _ in range(120):
                    if await p.evaluate("() => proto.state().ready"):
                        break
                    await p.clock.run_for(1000)
                else:
                    raise SystemExit("prototype did not finish warm-up within 120 virtual seconds")
            else:
                await p.clock.run_for(round(PR["warmup_s"] * 1000) if seg["kind"] == "proto" else C["gfx_settle_ms"])
            if seg["kind"] == "proto" and not driven and K.get("hide"):
                await p.keyboard.press(K["hide"])
            # page.clock controls timers/RAF, not CSS animations. Pause each Web Animation and seek it
            # on the film clock. The observer stamps newly created effects when they first enter a frame.
            await p.evaluate("""() => {
                window.__filmAnimations = new Map();
                window.__filmSyncAnimations = (ms) => {
                    void document.documentElement.offsetWidth;
                    for (const a of document.getAnimations()) {
                        if (!window.__filmAnimations.has(a)) {
                            window.__filmAnimations.set(a, {at: ms, finished: false});
                            a.pause();
                        }
                        const x = window.__filmAnimations.get(a);
                        if (x.finished) continue;
                        const t = Math.max(0, ms - x.at);
                        const end = a.effect.getComputedTiming().endTime;
                        if (Number.isFinite(end) && t >= end) {
                            a.finish();
                            x.finished = true;
                        } else a.currentTime = t;
                    }
                    for (const a of window.__filmAnimations.keys())
                        if (!a.effect || !a.effect.target || !a.effect.target.isConnected)
                            window.__filmAnimations.delete(a);
                    void document.documentElement.offsetWidth;
                };
            }""")
            if seg["kind"] == "gfx":
                await p.evaluate("() => window.start()")
            elif not driven and seg.get("replay") and K.get("replay"):
                await p.keyboard.press(K["replay"])
            events = sorted(seg.get("steps" if driven else "presses") or [])
            if any(not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in events):
                raise SystemExit(f"invalid capture event in {name}")
            shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
            print(f"capture mode: frame-clock ({fps} fps, {count} frames)", flush=True)
            now_ms = 0; event = 0
            for k in range(count):
                frame_ms = round(k * 1000 / fps)
                while event < len(events) and events[event] <= k / fps + 1e-9:
                    event_ms = min(frame_ms, round(events[event] * 1000))
                    if event_ms > now_ms:
                        await p.clock.run_for(event_ms - now_ms); now_ms = event_ms
                    await p.evaluate("(ms) => window.__filmSyncAnimations(ms)", events[event] * 1000)
                    if driven:
                        await p.evaluate("() => { proto.step(); }")
                    else:
                        await p.keyboard.press(K["next"])
                    event += 1
                if frame_ms > now_ms:
                    await p.clock.run_for(frame_ms - now_ms); now_ms = frame_ms
                await p.evaluate("(ms) => window.__filmSyncAnimations(ms)", k * 1000 / fps)
                unsupported = await p.evaluate(r"""() => {
                    if ([...document.querySelectorAll('video,audio')].some(m => !m.paused && !m.ended))
                        return 'playing audio/video';
                    if ([...document.images].some(i => {
                        const src = (i.currentSrc || i.src).toLowerCase();
                        return src.startsWith('data:image/gif') || /\.gif(?:[?#]|$)/.test(src);
                    }))
                        return 'GIF image';
                    return '';
                }""")
                if unsupported:
                    raise SystemExit(f"frame-clock cannot deterministically capture {unsupported}; "
                                     "explicitly select --capture-mode compatibility")
                await p.screenshot(path=str(out / f"{k + 1:06d}.jpg"), type="jpeg", quality=C["jpeg_quality"],
                                   animations="allow")
                if page_errors:
                    raise SystemExit(f"page error during capture: {page_errors[0]}")
            meta = {"mode": "frame-clock", "fps": fps, "frame_count": count, "dur": seg["dur"],
                    "T0": 0, "rate": 1, "ts": [k / fps for k in range(count)]}
            (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            print(name, "frames", count, flush=True)
        finally:
            await b.close()


async def record(name, mode=None, preview=None):
    cfg = load()
    plan = json.load(open(cfg["plan"], encoding="utf-8"))
    seg = next((s for s in plan["segments"] if s["name"] == name), None)
    if not seg:
        raise SystemExit(f"no segment {name} in {cfg['plan']}")
    mode = mode or cfg["capture"].get("mode", "frame-clock")
    if mode not in ("frame-clock", "compatibility"):
        raise SystemExit(f"unsupported capture mode: {mode}")
    if preview is not None:
        if not math.isfinite(preview) or preview <= 0:
            raise SystemExit("preview duration must be positive and finite")
        seg = dict(seg, dur=min(seg["dur"], preview))
        out = Path(cfg["tmp"], "preview", name, f"frames_{name}")
    else:
        out = Path(cfg["tmp"], f"frames_{name}")
    if mode == "compatibility":
        await record_compatibility(name, cfg, seg, out)
    else:
        await record_clock(name, cfg, seg, out)
    return cfg, plan, seg, out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("segment")
    ap.add_argument("--capture-mode", choices=("frame-clock", "compatibility"))
    ap.add_argument("--preview", type=float, help="capture and render a separate bounded preview in tmp/preview")
    args = ap.parse_args()
    result = asyncio.run(record(args.segment, args.capture_mode, args.preview))
    if args.preview is not None:
        from capture_preview import render_preview
        render_preview(*result)
