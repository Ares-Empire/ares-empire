# Ares Empire — logo brief (Claude Design handoff)

The empire's crown mark is a **marble bust of Ares**, the war-god figure behind the owner's
handle. It must sit in the same family as the Arestoteles **Aristotle** bust (white marble,
black wall, premium, photographic) while clearly out-ranking it — this is the *empire*, the
sub-products are its members. The differentiator is martial gravitas: a **helmet, a beard,
a hint of armor**.

## Resolved style choices

Among the open options (armor vs none · beard vs clean · color vs white), the picks are:

| Axis | Choice | Why |
|---|---|---|
| Material — face/head | **White Carrara marble**, faintly veined | Keeps the bust in the empire's marble family; the face stays unmistakably a sculpted figure. |
| Material — war-gear | **Polished shiny gold** (helmet + armor) | The empire crown's signature: marble + gold + black is a regal, luxury palette that elevates this above the pure-white philosopher busts (the sub-products) without leaving the family. Gold is on metal only — never the skin. |
| Headgear | **Gilded Corinthian helmet, pushed back** off the face (crest visible) | Instantly "Ares / war" without hiding the face; the pushed-back wear reads noble, not aggressive. |
| Facial hair | **Bearded**, classical curls (white marble) | Mature, sovereign — distinguishes him from a youthful/clean look and from beardless Aristotle. |
| Armor | **Gold cuirass / pauldrons** at the shoulders | Martial signal + the gold accent; keeps the silhouette a bust (gear only at the base/shoulders). |
| Expression | Calm, commanding, **eyes to camera, head-on** | Authority over aggression. |
| Pose | **Front-facing, dead-on, symmetrical** — no three-quarter turn, no profile, no tilt | Kills most of the variation; a frontal symmetric crest reads as an emblem. |
| Framing | The **entire helmet, including the top of the crest, fully inside the frame** with empty margin above it; bust ends at the chest | Stop the helmet getting cropped. |
| Base | **None** — the bust floats, no pedestal / plinth / stand / column | The "floating" look requested. |
| Background | **Pure solid black** | The marble white and metallic gold both pop hard against it — the core of the look. |

## Copy-paste prompt

> **Front-facing marble bust of Ares, the Greek god of war, looking directly at the camera,
> perfectly symmetrical head-on view, no tilt.** The face, head and full curled beard are
> carved from pristine **white Carrara marble** with subtle grey veining — mature, powerful
> male features, calm and commanding, eyes forward. He wears **polished shiny gold war-gear**:
> a **gilded Corinthian helmet pushed back** to fully reveal the face, with a tall frontal
> crest. **The ENTIRE helmet, including the very top of the crest, is fully visible inside the
> frame with clear empty space (margin) above it — nothing is cropped or cut off.** An ornate
> **golden cuirass with shoulder pauldrons** forms the base of the bust. Luminous white marble
> skin contrasted against gleaming reflective metallic gold. **The bust ends cleanly at the
> chest and FLOATS in the center of the image — there is NO pedestal, NO plinth, NO stand, NO
> base of any kind**, only empty space around it on a **pure solid black background**.
> Photorealistic studio product render, soft symmetrical key light, realistic marble
> micro-detail and faint translucency, true metallic gold reflections and specular highlights
> on the armor. Premium, cinematic, restrained — the gravitas of a sovereign emblem, not a
> game asset. Single subject, centered, square 1:1. Gold appears on the metal gear ONLY; the
> skin and beard stay white marble. No text, no logos, no watermark.

**Negative prompt** (paste into Flux / Stable Diffusion / Ideogram negative field; for
Midjourney use `--no …`; for ChatGPT just say "avoid these"):

> pedestal, plinth, stand, base, column, podium, table, three-quarter view, side profile,
> looking away, tilted head, cropped helmet, helmet cut off, crest cut off, out of frame,
> multiple heads, multiple busts, extra figures, colored or textured background, gradient
> background, text, letters, watermark, signature, blurry, low detail, modern clothing, gold skin

### Per-generator settings (to cut variation)

- **ChatGPT (GPT-4o image):** paste the prompt; if it drifts, reply "front-facing and
  symmetrical, show the whole helmet with space above it, remove the pedestal — it should float
  on black." It edits the same image coherently, so you converge instead of re-rolling.
- **Midjourney:** append `--ar 1:1 --style raw --stylize 150 --no pedestal, base, stand, crop`.
  Note the **`--seed <number>`** of a result you like and reuse it to keep iterating from the
  same composition rather than getting fresh variations each time.
- **Flux / SDXL / Ideogram:** put the paragraph in the positive field and the negative prompt
  above in the negative field; 1:1; raise guidance/CFG a little for stricter adherence.

## Output / placement

- Render on a **black or transparent** background to match the dark wall; export PNG.
- Save here as `brand/ares-bust.png`.
- Mirror whatever post-processing the Arestoteles bust used (`arestoteles/scripts/make_bust.py`)
  for a consistent crop, vignette and trim.

## Then: wire the Arestoteles button

Once `ares-bust.png` exists, update the Arestoteles header hub-link
(`web/app/app.jsx`, `TopBar`) from the plain "Ares Empire" wordmark to **the bust mark +
"Ares Empire"** — small (~22px) mark on the left of the existing label, same glass pill.

## The coin mark (2026-11-27)

A flat companion to the bust for small round places such as profile pictures: `brand/ares-coin.svg` (vector) and
`brand/ares-coin.png` (1024 × 1024 px), black `#0b0b0c` on off-white `#f4f1e9`. At 16 px it reads only as a dark
shape, so the favicon stays the bust.

Made in two steps: Codex image generation drew a black-on-white reference from the prompt below, then the reference
was traced into vector shapes (potrace) and fitted into a 512-unit circle. Other colours are the same shapes with
the two fills swapped or replaced (off-white on black, gold `#e4c264` on black).

> Short, compact crest. The bust starts at the upper shoulder: a muscled cuirass edge and one shoulder plate with a
> small lion head on it. Only a few bold white engraved lines (eye, brow, helmet edge, a few beard locks), thick
> enough to survive at small sizes. Profile facing right of the Greek god Ares as on a classical Greek coin of the
> 5th century BC (style of the Zeus staters of Elis): a mature, majestic bearded god, calm and stern, idealised
> classical features. Strong straight Greek nose continuing the line of the brow, deep-set eye under a defined brow,
> high cheekbone, firm closed mouth, long beard in clear structured curly locks. Attic helmet with a pointed brow band
> over the forehead and a box-shaped crest holder. Flat solid black on a plain white background, centred, generous
> margin, square, composed to sit inside a circle. No text, no coin rim, no shading, no gradients, no grey.
