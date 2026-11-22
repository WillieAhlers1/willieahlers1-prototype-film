# Film scripts (prototype-film)

The pipeline turns an approved, packed concept prototype into a narrated, captioned 1080p MP4.
Brand graphics, font assets and pronunciations come from the approved workspace snapshot.

## Build folder

```text
python <skill>/film/scripts/new_film.py <build> --workspace <workspace> --prototype <packed.html> --name "<Concept> film"
```

Run later commands from `<build>`, a local writable directory outside synced folders.
Scripts/templates refresh; edited film config/narration are kept unless explicitly forced.
A changed brand requires explicit approval before refresh. Keep workspace runtime/model state separate from
disposable frame/encode directories.
Use `--update-brand` after approval to change the snapshot without resetting narration; `--force` also replaces
editable inputs. `--brand <manifest>` is an alternative to `--workspace`, and a standalone packed prototype
contains a recoverable snapshot. No brand-specific examples or imports are provided.

- `brand/brand.json`, referenced assets, `brand.js`, `brand.css`: portable approved identity.
- `graphics.html`, `gfx-data.js`: shared layout and story-specific graphics.
- `proto/`: packed concept HTML.
- `film.json`, `narration.txt`, `lexicon.json`, `plan.json`, `cues.json`: editable source and measured timing.
- `work/`: disposable frames, encodes, mix and final MP4.

## Run order

| Step | Command | Verify |
|---|---|---|
| Narration/config | `python check_film.py` | Fix errors; trace each spoken number to the brief |
| Pronunciation | `python speech.py` | Inspect expanded text and unresolved words |
| Voice | `python voice.py` | Approved engine, cached per-line audio and exact cues |
| Timing | `python autoplan.py` | Measured audio rate, complete-film pace and readable timing |
| Graphics | `python gfx_data.py` | Selected identity and actual approved images |
| Stills | `python stills.py` or `node stills.js` | Inspect every graphic |
| Preview sound bed | `python music.py` | Original ambient score; required before a mixed preview |
| Preview | `python record.py P1 --preview 8` | Separate `work/preview/P1/preview.mp4`; approval for new settings |
| Recording | `python record_all.py [log] [SEG ...]` | Logged clock mode, synchronization, complete frames |
| Music | Reuse preview score; regenerate only if changed | No borrowed tracks |
| Mix | `python mix.py`, `python mix.py --levels` | Actual measured levels |
| Captions | `python subs.py` | Brand font, contrast, accurate written numbers |
| Assembly | `python assemble.py segs`, `python assemble.py final` | Encoded duration, captions and sound |
| Review | `python contact_sheet.py` | Every sheet and final playback |

Re-record/re-encode only affected segments: `python record_all.py work/rec.log P3`;
`python assemble.py segs P3`.
`plan.py`/press schedules and Node recording remain explicit compatibility paths, not a claim of
prototype-clock capture.
Select compatibility explicitly with `--capture-mode compatibility`. Python Playwright frame-clock recording
is the default; Node recording does not claim that capability. Use a separate segment preview to inspect a
signature moment not in the opening.

## Voice and environment

See [voice setup](../../references/voice.md): saved Kokoro offline profiles or optional Azure Olivia with explicit
cloud consent and environment credentials. Do not store keys or silently substitute unavailable voices.
Show narration before voicing; audition new settings; report listening checks not performed.

Python Playwright with Chromium/Edge is preferred. Existing Node Playwright can serve compatibility environments.
ffmpeg needs libx264, aac and libass; `filmcfg.ffmpeg()` checks configured/environment/PATH/imageio sources.
Font paths remain local and relative to avoid Windows filter-path escaping.
Run dependency checks first; only restore missing packages when the host supports installation.

Pacing target: approximately 166 spoken words/minute, at most 160 over the full film.
Evenly spaced frame-clock capture must be verified from timestamps and encoded duration, not inferred from
a constant-fps encoder. Keep recording fallback mode explicit.
