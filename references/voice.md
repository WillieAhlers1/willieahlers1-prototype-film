# Voice selection, pronunciation and migration

Voice each narration line separately, with cached audio and exact cue boundaries. Editing a line revoices only
that line. Do not switch to whole-script audio and guess line boundaries from pauses.

## Once per workspace

Offer an audition during setup and save the approved engine/voice in workspace runtime `voice.json`, separate
from `brand.json`. Reuse it until explicitly changed; `film.json.voice` overrides it for one film.
An unavailable audition is pending, not approved. Report the selected engine and voice, not an invented default.

- **Kokoro:** offline, Kokoro-82M via kokoro-onnx; default `af_heart`, with `am_michael`, `am_fenrir`, `bf_emma`,
  `bm_george` and `af_bella` available for comparison. Setup uses `voice.py --setup`; audition uses
  `voice.py --audition`; save a choice with `voice.py --use <voice> [--speed 0.95]`.
- **FTG/Olivia:** optional Azure `en-GB-OliviaNeural`, a British English preset. It needs an authorized compatible
  service and explicit cloud consent. Explain that narration is sent to the service and may incur charges.
  Supply `SPEECH_KEY`/`SPEECH_REGION` through the authorized environment, never the manifest or saved profile.
  Query/test availability through the service only after authorization; a configured voice name does not prove
  that the service offers it.
- **Scratch voices:** SAPI/macOS say are timing drafts, not delivery substitutes. macOS say cannot be called
  from a Cowork Linux sandbox.

Kokoro cannot reproduce Olivia exactly. Never silently substitute an engine or voice when one is unavailable.
Keep existing line caching, pronunciation checks and cue timing with every supported delivery engine.
For Azure exact-phoneme limitations, require respellings or explicit correction rather than claiming Kokoro IPA
works unchanged.

From a film build folder, audition/select the optional preset:

```text
python voice.py --preset olivia --authorize-cloud --audition
python voice.py --use olivia --authorize-cloud
```

The first command makes a real service request: run only with approved cloud consent and authorized credentials.
The second saves the profile/consent for reuse; it does not prove service availability or successful audition.
`--preset ftg` is the equivalent preset alias. Use `--engine`/`--voice` for a one-run override or
`film.json.voice` for a per-film override.

## Kokoro model setup

Install dependencies only after a missing-dependency failure in an environment that supports installation.
`voice.py --setup` downloads the model (~350MB) into `<home>/kokoro/`:

- https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
- https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

If downloads are blocked, ask the user to place these files there; do not claim setup completed.
Keep persistent state in the workspace, not the sandbox's disposable home.

## Pronunciation before every film

`speech.py` normalizes written numbers and abbreviations for the ear; captions keep the written form.
Review every person's name, company, product and acronym before voicing.

Merge generic pronunciations, workspace reusable terms, the approved brand pronunciation snapshot and the
film-specific lexicon with documented later-wins precedence. Generic entries never include an implicit brand.
Use `say` respellings for every engine and `ipa` only where supported:

```json
{"say": {"Coho Winery": "Koho Winery", "OEE": "O E E"}, "ipa": {}}
```

Run `python speech.py` to inspect transformed lines and unresolved "check:" terms.
Ask once about uncertain names and save reusable corrections. Then run `python voice.py`.
If available, `voice.py --listen` transcribes generated lines with offline Whisper and reports discrepancies;
review the flags rather than treating all transcription differences as pronunciation errors.
Never claim a listening check ran when models/tools were unavailable.

## Runtime state

New workspace identity lives in `.prototype-film/brand.json`; runtime models/profile/lexicon are separate.
Use explicit `film.json.home`, `PROTOTYPE_FILM_HOME`, a workspace `.prototype-film`, or `~/.prototype-film`.
To reuse a model/profile from another directory, set its path explicitly in `film.json.home`; no brand-specific
runtime discovery is supported. Preserve model files rather than deleting/redownloading them.
Report which runtime location was selected; changing identity does not require changing the voice profile.
Never copy credentials into the new runtime state.

## Pacing and delivery report

Measure actual narration words and cue/audio duration; target about 166 spoken words/minute.
Complete film pace is a separate measure, at most 160, including readable screen time.
Use bounded natural voice-speed adjustments and honest content revisions, not slowed footage or empty holds.
Show a short preview for new settings and obtain voice/recording approval before the full render.
Report actual voice, settings, rates, audio levels, unresolved words, and listening/user acceptance still pending.
