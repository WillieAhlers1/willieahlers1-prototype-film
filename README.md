# prototype-film

A skill for any brand: build a clickable, self-contained concept HTML prototype, then optionally a narrated,
captioned 1080p MP4. Branding is approved once per workspace and reused, not requested for every concept.
Nothing connects to real systems; simulated business data remains fictitious and labelled.

## Install and set up

Install this folder as `prototype-film`, or ZIP its contents with `SKILL.md` at the archive root for Claude Cowork.
There is no automatic installation hook: invoke brand setup after installing, or let first use start onboarding.
See [brand setup](references/brand-setup.md) for the approved intake manifest.

```text
python <skill>/assets/brand_setup.py setup --workspace <workspace> --intake <intake.json> --approve
python <skill>/assets/brand_setup.py validate --workspace <workspace>
python <skill>/assets/init_prototype.py --workspace <workspace> --name <concept>
```

Pass approval only after reviewing identity, source materials and asset permissions.
For a later change, repeat setup with `--update`; existing output snapshots remain reproducible.
`.prototype-film/` is private workspace state and is ignored by Git. Do not store credentials there.
Generated `working/` concepts are ignored too because their snapshots can contain approved private materials.
Share or version them only deliberately after reviewing their contents and permissions.
Different workspaces have independent brands; skill updates never overwrite them.

## Workflow

- One prefilled concept confirmation, separate from branding: business shift, work owner, signature moment,
  human decisions, assumption to test and interface choice.
- Story-specific scenes and optional small-team/whole-outcome narratives; accurate product shells remain distinct
  from presenting-brand frames.
- Prototype checks, offline packing and film readiness; narration comes from scene notes.
- Saved offline Kokoro voice, or optional Azure `en-GB-OliviaNeural` (FTG preset) with explicit cloud consent.
  Kokoro cannot reproduce Olivia. Credentials come from the authorized environment, not files.
- Measured pacing: about 166 spoken words/minute and at most 160 over the complete film, with readable screens.
- Frame-clock recording where supported, explicit compatibility mode, and short previews before full rendering.
- Frame-clock captures support static assets/timers/Web Animations, not media decoding or animated image formats.
- Line-specific narration edits, captions, original music, contact-sheet review and approval-gated cleanup.

Start with [SKILL.md](SKILL.md). Detailed guides live in [references](references).
Pipeline commands are in [film/scripts/README.md](film/scripts/README.md).

## Validation

```text
python -m unittest discover -s tests -v
```

Browser integration tests require Python Playwright and Chromium/Edge. Film rendering also requires numpy,
scipy, Pillow and ffmpeg with libx264/aac/libass. Voice tests using a real engine need Kokoro models or an
authorized Azure service; unit tests do not make cloud requests. Run checks before marking a phase complete.
Do not claim voice listening, visual acceptance or service availability based only on unit tests.
The two-brand end-to-end test renders actual captioned 1080p MP4s with synthetic local test audio; this verifies
pipeline synchronization and encoding, not the quality or availability of a real voice service.

## Existing Tredence installations

Use `brand_setup.py import-tredence --output <review-folder>` to create a reviewable intake from bundled legacy
assets. Confirm permissions, set `asset_permissions` to true, and approve setup into the workspace.
Legacy examples are explicit historical fixtures, not templates for other brands.
Existing `.tredence`, `TREDENCE_HOME` and film configuration remain compatibility inputs for runtime models and
voice profiles; see [voice migration](references/voice.md). Do not delete/redownload models just to rename state.

The skill is `prototype-film`, hosted in
[WillieAhlers1/willieahlers1-prototype-film](https://github.com/WillieAhlers1/willieahlers1-prototype-film).
For existing clones, update the remote explicitly rather than relying on redirects:

```text
git remote set-url origin https://github.com/WillieAhlers1/willieahlers1-prototype-film.git
```

Voice: Kokoro-82M (Apache-2.0) via kokoro-onnx; optional Azure service. Legacy Poppins fonts: SIL OFL.
User-supplied assets/fonts must have approved use and embedding permissions.
