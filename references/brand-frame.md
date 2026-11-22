# Brand frames

Frames carry the story and ask: an optional cover, chapter break, business-level shift, close and sign-off.
Product scenes show the proof. A frame is not a slide per capability or a recap of the product tour.

The workspace manifest supplies palette, typography, logo variants, imagery, tagline and sign-off.
`brand.js` loads before `kit/proto-style.js`; `brand.css` loads after it.
The generic layout classes `bf-cover`, `bf-content`, `bf-section`, `bf-divider`, `bf-ask` and `bf-closing`
do not select a brand identity. All identity values come from the approved workspace manifest.

## Layout

Use `<section class="scene frame bf-content">` and the frame outlines in `assets/frames.html`.
The kit creates generic brand chrome from approved configuration. Don't draw a second logo/footer over it.
At the 1920x1080 stage, keep content above approximately y=995 and clear of the logo, top rule and concept footer.
Text sits in separately positioned elements over simple boxes; do not hide prose under chrome.

- Cover: business shift and tension in the customer's words, with approved presenting identity.
- Content: kicker, headline, specific before/after work and illustrative measure.
- Section/divider: only when a story genuinely needs an act break.
- Ask: one small measurable next step, if the meeting needs it.
- Closing: optional configured sign-off; no borrowed hashtag or forced branded photo.

Use supplied images only; if absent, use the approved flat background and say so.
Pick logo variants appropriate to the background. Text-only identity must be explicitly approved.

## Tokens and type

Frame tokens: `--brand-accent`, `--brand-background`, `--brand-foreground`, `--brand-muted`, `--brand-font`.
These tokens carry approved values directly. Product Fluent tokens are unchanged.
Use the configured font; locally supplied font files are packed. System fonts require explicit acceptance.
Prefer headlines around 48-72px, supporting text around 24-32px and labels at least 18px on frame scenes.
Keep contrast readable, sentence case natural, and content brief enough to understand from the room's back.

Do not use a brand identity to recolor accurately represented Microsoft applications.
Decorative gradients, shadows, slogans and claims are not invented just to fill a frame.
Business numbers remain illustrative and traceable to the brief regardless of supplied brand messaging.

## Review

Check the actual selected brand, not a fixed palette/font/logo. Review every frame's logo/background pairing,
font loading, clipping, contrast, footer clearance, captions and reduced-motion appearance.
The close must explain a business change and credible next step, not a product list.
