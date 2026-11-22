# Workspace brand setup

Branding is configured once per workspace after installation, or on first use if setup was skipped.
Collect files in one form, propose an identity and summary, and get approval. A valid saved manifest means reuse,
not another questionnaire. "Update branding" is an explicit approved update.

## Intake contract

Use local paths relative to the intake JSON. Supported visuals: SVG, PNG, JPEG, WebP; fonts: TTF, OTF, WOFF,
WOFF2; reference materials: those visuals plus PDF, PPTX, DOCX, TXT, Markdown and JSON.
Paths must stay inside the intake directory, without parent traversal, drive letters or remote URLs.
SVG assets must be static and self-contained: no scripts, event handlers, imports or non-embedded references.

```json
{
  "schema_version": 1,
  "approved": false,
  "asset_permissions": true,
  "name": "Northstar",
  "text_only": false,
  "palette": {
    "accent": "#663399",
    "background": "#ffffff",
    "foreground": "#202020",
    "muted": "#e0e0e0"
  },
  "typography": {"family": "Arial", "files": [], "system_font": true},
  "logos": {"primary": "logo.svg", "light": "logo-light.svg"},
  "tagline": "Work, connected",
  "signoff": "Build what comes next",
  "images": ["team.jpg"],
  "materials": [
    {"path": "guidelines.pdf", "role": "identity"},
    {"path": "product.md", "role": "content"}
  ],
  "summary": "Approved tone and messaging. Identity source: guidelines.pdf; product claims: product.md.",
  "pronunciations": {"say": {"Northstar": "North star"}, "ipa": {}}
}
```

`asset_permissions` confirms approved asset use and font embedding. A logo is required unless `text_only=true`.
An approved system font is allowed; otherwise supply local font files. For static fonts, use filenames including
Regular, Medium, SemiBold, Bold and Italic to identify their weight/style. Portable font embedding is preferable
to system fonts, whose availability can differ by machine.
Use all four explicit six-digit palette colors. Check actual rendered contrast rather than assuming a valid color
format guarantees readability. Primary/light/dark logo variants are optional except primary for non-text identity.

Classify material roles as `identity`, `content` or `visual`. Read supported documents with host-available tools;
extract approved tone, claims and provenance into `summary`. The setup script copies and validates files, not
their semantic contents. If no document-reading tool supports a material, request an exported TXT/Markdown
summary rather than inventing an extraction or claiming it was read.
Pronunciation maps are optional; future film-specific terms belong to the film lexicon.

## Commands and persistence

```text
python <skill>/assets/brand_setup.py setup --workspace <workspace> --intake <intake.json> --approve
python <skill>/assets/brand_setup.py validate --workspace <workspace>
python <skill>/assets/brand_setup.py setup --workspace <workspace> --intake <new-intake.json> --approve --update
```

Approval is a user decision; the CLI flag records it, not a substitute for it.
Setup validates before publication, copies assets into `.prototype-film/brand/assets/`, and writes
`.prototype-film/brand.json`. Runtime voice/model state lives separately in the same workspace home.
Source materials stay local/private; don't put secrets, keys or customer records in the manifest.
Packed prototypes embed the approved material assets as well as identity assets; share them only with people
authorized to receive those materials. Do not submit sensitive source documents merely to extract branding.
Unknown schema versions and broken files fail explicitly; repair before generating.

Generated prototypes and films receive portable brand snapshots. Updating workspace branding does not silently
rebrand already-approved concepts or narration. Regenerate/review explicitly when changing their identity.
Never modify the installed skill or rely on attachment paths that disappear between sessions.

No brand-specific imports or asset bundles ship with the skill. Supply an approved intake for every workspace.
If reusing existing voice models, select their directory explicitly through runtime configuration, separately
from brand setup.
