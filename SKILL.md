---
name: prototype-film
description: 'Build branded, clickable art-of-the-possible HTML prototypes and narrated, captioned concept films for any brand. Use to set up or update workspace branding; turn a scenario, notes, deck or whiteboard into a prototype, mockup, storyboard or demo; change or repackage a prototype; or make, revoice or fix a film, video or narrated walkthrough, including pronunciation, pacing, graphics and music. Collect approved branding once per workspace and reuse it. Outputs are offline concept HTML and MP4, not live products or slide decks.'
---

# Branded prototypes and concept films

**The test that matters:** would a business leader leave saying "we have to do this", and would the presenter
show it with a straight face? Bring a specific business idea, not a faster version of a generic task.
Real work has friction, judgement and people on the other side. Full means deep, not long.

Build a **concept, not a product**: scripted, fictitious, offline and always labelled. Never call real systems,
use real customer records, or imply something ships. Brand assets and approved company messaging inform the
identity and story; they do not authorize exposing customer data or inventing claims about a real company.
The prototype comes first; a concept film is optional once the user is happy with it.

## Find the skill and workspace

Everything ships beside this file; call that folder `<skill>`. It can be read-only: never build inside it.
Locate the installed `prototype-film` folder through the host's skill location, not a whole-drive search.
The user-selected workspace holds `.prototype-film/` and `working/<short-name>/`.

- Claude Cowork commands run in its Linux sandbox, not on the Mac itself. Keep persistent files in the shared
  workspace; macOS voices/apps are not reachable there.
- Copilot Cowork may provide Node Playwright and ffmpeg but no package installation. Use the existing Node
  checker/compatibility recorder where supported and report missing capabilities. Do not attempt installs in
  a host that forbids them.
- In a normal local environment, run the smallest existing validation command first; install missing
  dependencies only after an actual missing-dependency failure. Never silently skip checks.

## One-time workspace branding

**Before a new prototype or a direct film request**, validate the workspace configuration:

```text
python <skill>/assets/brand_setup.py validate --workspace <workspace>
```

If valid, read `.prototype-film/brand.json` and its approved summary/materials; do not ask for branding again.
If absent, run onboarding below. If invalid, explain the exact problem and request only the repair needed.
Never fall back to Tredence or another brand. A new workspace requires its own setup.
Read [brand setup](./references/brand-setup.md) for the manifest and supported file types.

1. In one consolidated form, ask for guidelines, logo variants, palette, fonts, photos/illustrations/icons,
   reusable company/product material, audience/tone, tagline/sign-off and pronunciation guidance.
2. Draft the proposed identity and content summary with source provenance. Mark guesses and resolve conflicting
   guidance. Require either a usable logo or approved text-only identity, approved colors, and approved font
   files or an explicit system-font choice. Confirm asset-use/font-embedding rights.
3. Show the proposal and obtain approval. Write a local intake manifest referring to supplied files, then:

```text
python <skill>/assets/brand_setup.py setup --workspace <workspace> --intake <intake.json> --approve
```

Only pass `--approve` after confirmation. Cancelled/failed setup is not complete. Uploaded files are copied into
the workspace bundle; later generation must not depend on temporary attachments or remote URLs.
For "update branding", show changes and run setup with `--update` after approval. Skill upgrades must not overwrite
workspace configuration.

Offer a voice audition during setup when available: Kokoro is offline; the optional FTG preset is
**`en-GB-OliviaNeural`** on a compatible authorized Azure speech service. Explain network, cost and narration
disclosure, obtain explicit consent, and never store credentials in the bundle. Save the selected voice in
workspace runtime state, separate from identity; per-film overrides are allowed.
If audition is unavailable, record it as pending rather than claiming voice approval.
Kokoro cannot reproduce Olivia exactly. See [voice](./references/voice.md).

## Think big, keep it honest

- Explore three ideas before choosing: expected, stretching, and one that changes what the business can be.
  Challenge the pick as their CEO: "Isn't that what we already do, just sooner or for more people?"
- Pin down today's constraint, the new operating model, the measure that moves and its owner, and which steps
  disappear versus where people decide. Show the shift on screen, not only in the closing claim.
- Explore **small-team, whole-outcome ownership**: agents remove hand-offs so people own the outcome end to end.
  It is an option, not a mandatory staffing model. Respect the user's scenario and describe capacity, not job cuts.
- Make the change real at two heights: one person's work and what it means across the business.
- A capability list is not a story. Map must-show items to beats privately, not a checklist on screen.
- Follow approved brand tone, but stay customer-first, outcome-led, specific and non-promotional.
  Every illustrative number needs a basis in the brief; never manufacture brand claims.
- If the user requests a smaller workflow, build that and offer the bigger idea once, in one line.

Read [story and data](./references/story-and-data.md) before the concept card.

## One concept confirmation, not another brand intake

For each new concept, fill these answers from the user's brief and saved materials. Use the form tool if available.
Ask for one confirmation/correction round, marking guesses. Do not reopen an approved brief or branding.

1. **Business change:** what becomes possible, why now, the illustrative measure and its owner.
2. **Work owner:** who owns the outcome, today's hand-offs, and the friction they face.
3. **Signature moment:** the one thing the room must see happen.
4. **Human decisions:** what agents do, what disappears, and what requires a person.
5. **Assumption to test:** the one guess about their work this concept tests.
6. **Interface:** the customer's own AI app or an accurately represented existing product; recommend a choice.

Include the safer and bolder alternatives and any must-show requirements in the brief.
Skip a redundant approval stop if the user explicitly says "just build" or has already supplied/approved the
answers. That skips the stop, not the thinking, factual checks or required safety clarification.
Existing Microsoft shells remain Fluent; don't relabel the custom-app shell as Copilot or invent an unsupported
product shell. Record the choice and any limitation.

## Prototype loop

1. **Brief and concept card.** Save the approved story, format/duration, sources, illustrative assumptions and
   cast/data sheet in `brief.md`. Company/people/records in the simulated work are fictitious and consistent.
2. **Storyboard.** Show, but don't add another approval stop: scene, screen, presenter line, on-screen action,
   click and stop seconds. Beats first, screens second. Give the signature moment a view designed for it.
3. **Initialize** a new prototype:

```text
python <skill>/assets/init_prototype.py --workspace <workspace> --name <short-name>
```

This creates `working/<short-name>/prototype.html`, `kit/`, a portable `brand/` snapshot, `brand.js` and
`brand.css`. The brand script loads before the style kit; the brand stylesheet follows it.
Edit an existing prototype in place rather than initializing over it.
4. **Build.** Replace every `[[placeholder]]`. Use [product look](./references/look-and-feel.md),
   [brand frame](./references/brand-frame.md), [engine](./references/engine.md), and
   [film pacing](./references/film-pacing.md) as needed, not all references up front.
   Preserve `data-concept` on every scene, clean ids, one idea and `data-note` per stop, streamed text that fits
   its line, and a signature `data-hold`. Automatic work chains; decisions wait for clicks.
5. **Check and repair.** Run the checker and review every contact sheet; fix each error, explain any accepted
   warning. Use `--scene <id>` for targeted rechecks. Never pass off a code read as a visual check.
6. **Pack, then verify the packed artifact**, not just the source:

```text
python <skill>/assets/check_prototype.py working/<name>/prototype.html
python <skill>/assets/pack_prototype.py working/<name>/prototype.html
python <skill>/assets/check_prototype.py working/<name>/dist/<name>.html
python <skill>/assets/check_prototype.py working/<name>/dist/<name>.html --motion
python <skill>/assets/film_ready.py working/<name>/dist/<name>.html --target 3:00
```

Use the requested target duration. Open the packed HTML offline; verify logo, fonts, contrast, scene behavior,
notes and navigation. Film readiness drafts narration from the notes.
7. **Deliver** the single HTML with concept/data limits, checks actually run, known issues and the assumption
   being tested. Offer a film through the question tool. Read [QA](./references/qa-and-feedback.md).

## Two looks, kept apart

The presenting brand frames the story; product shells represent where work happens.

- Microsoft products use accurate Fluent layouts, Segoe UI, neutral surfaces and product-specific colors.
  The selected presenting brand does not recolor Teams, Outlook, Dynamics 365 or Power BI.
- The customer's custom app can use approved identity scoped to that app, without changing surrounding products.
  Its name, agent identity, work trace and input/approval cards are specific to the story.
- Brand frames use the saved palette, typography and logos, not fixed Tredence styling. Existing `td-*` layout
  names are compatibility aliases, not a brand selection. Covers/closes are optional and business-led.
- Use local approved imagery only; no silent borrowed brand photos. No gradients, decoration or product chrome
  on frames unless approved identity guidance explicitly calls for it and validation supports it.
- Keep text readable, contrast adequate, keyboard navigation working and reduced-motion final states intact.
  Never shrink key content to squeeze around captions or chrome.

## Agent behavior and scope

Show a careful colleague: sources, checks, gaps and who acts. Money, orders, external contact and hard-to-undo
actions wait for a person, with the policy reason visible. Show where an approved action lands.
Use product names accurately; no invented SKU, price, capability or release commitment.
No APIs, logins, live data, external URLs, confidential records or unapproved customer identifiers.
The user owns the story, claims and decision to show it; never send outputs externally or claim approval.
"Change scene 3" means scene 3, not a redesign of approved scenes. Review your own outputs.

## Film loop

Read [film](./references/film.md), [narration](./references/narration.md),
[voice](./references/voice.md), [film look](./references/film-look.md) and [film QA](./references/film-qa.md).
For a video request without a prototype, run the same brand guard and build the prototype first.

- Check readiness, then initialize a local temporary film build with `new_film.py`, using the same approved
  workspace brand and prototype snapshot. A changed brand must not silently replace an edited film's identity.
- Rewrite the note-derived narration in the saved tone; show it before voicing. Trace numbers to the brief,
  say "illustrative", make the close business-led, and retain the stage directions.
- Use the saved engine/voice, lexicon and line-by-line cached voicing with exact cue boundaries.
  Report unavailable engines, unresolved pronunciations and listening checks not performed; never substitute.
- Plan from measured cues and reading/settling time. Report spoken rate (target about 166 words/minute) and
  whole-film pace (at most 160). Do not slow footage or create empty holds to game these measures.
  If readability cannot fit the requested duration, revise content or obtain approval for a longer cut.
- Render a short opening/signature preview before the full encode. Verify voice, pronunciation, brand, motion and
  readable timing. Obtain approval for a new voice/recording setup; reuse approval for unchanged settings.
- Prefer evenly spaced prototype-clock capture where supported, with explicit compatibility recording otherwise.
  Preserve driven steps and narration synchronization. Re-record only affected segments after edits.
- Generate original ambient music, mix, captions and MP4; inspect contact sheets and playback before delivery.
  Report checks, actual duration/rates, recorder mode, voice, and any pending external/user approval.

## Cleanup and later edits

Only once the user is happy, offer zip-and-tidy, delete-without-zip, or leave-as-is. Dry-run first:

```text
python <skill>/assets/cleanup.py working/<name> --build <temporary-film-build>
```

Show the exact list and run with `--yes` only after approval. Keep the packed HTML/latest MP4, and zip source
including brand snapshot, brief, narration, lexicon and film config. Never delete `.prototype-film/` or legacy
runtime state, the workspace, skill, or any unrelated folder. Restore sources for edits; reuse the saved brand.

## Skill contents

`assets/` contains setup/init, starter/frame/product outlines, kit, check/pack/readiness and cleanup.
`film/` contains scripts, templates, generic lexicon and explicitly legacy examples.
`references/` contains progressively loaded guides. `tests/` contains contract, browser and film regressions.
Legacy Tredence assets are available only through an explicit reviewed import, never generic defaults.
Install under a matching `prototype-film` folder or as a ZIP with this file at its root.
Source: [WillieAhlers1/willieahlers1-prototype-film](https://github.com/WillieAhlers1/willieahlers1-prototype-film).
