# Ares Empire — deity bust prompts

Image-gen prompts for new marble busts, in the exact family of the existing ones
(Aristotle / Hermes / the David head): **front-facing, pure white Carrara marble,
photographic, floating on black → cut out to a transparent PNG, head/face only.**
See `LOGO_PROMPT.md` for the Ares (empire-crown) variant that adds gold war-gear.

## Shared style (every prompt already embeds this — here for reference)

> Photorealistic studio product render. **Perfectly symmetrical, front-facing, dead-on view,
> looking directly at the camera, no tilt, no profile.** Carved from pristine **white Carrara
> marble** with subtle grey veining, realistic marble micro-detail and faint translucency.
> Soft symmetrical key light. **The entire head and any headgear is fully inside the frame with
> clear empty margin above — nothing cropped or cut off.** The bust ends cleanly at the
> shoulders/chest and **FLOATS in the center — NO pedestal, NO plinth, NO stand, NO base of any
> kind**, only empty space on a **pure solid black background** (so it cuts cleanly to
> transparent). Premium, cinematic, restrained — the gravitas of a sovereign emblem, not a game
> asset. Single subject, centered, square 1:1. No text, no logos, no watermark.

**Shared negative prompt** (paste in the negative field; Midjourney → `--no …`):

> pedestal, plinth, stand, base, column, podium, table, three-quarter view, side profile,
> looking away, tilted head, cropped head, headgear cut off, out of frame, extra figures,
> colored or textured background, gradient background, text, letters, watermark, signature,
> blurry, low detail, modern clothing, painted color, gold skin

> ⚠️ For **Janus** and **Cerberus** REMOVE `multiple heads` / `multiple faces` from the negative
> (they are meant to have several) — the rest of the negative still applies.

**Optional "empire-tier" gold:** to lift any one of these toward the Ares crown, render its
metal attribute (Athena's helmet, Zeus's laurel, Artemis's crescent) in **polished shiny gold**
instead of marble — *gold on the gear/attribute only, never the skin* (see `LOGO_PROMPT.md`).

Post-process each render with `arestoteles/scripts/make_bust.py` for the same crop/trim →
transparent, and save as `web/brand/<name>.png`.

---

## Athena — wisdom & strategic war

> **Front-facing marble bust of Athena, Greek goddess of wisdom and strategic warfare, looking
> directly at the camera, perfectly symmetrical head-on, no tilt.** A serene, intelligent, calm
> and commanding young female face carved from pristine **white Carrara marble** with subtle
> grey veining; waved hair drawn back beneath a **pushed-back Attic/Corinthian helmet (carved in
> marble) that fully reveals her face**, a tall frontal crest, a small carved owl motif at the
> helmet's brow. **The entire helmet, including the top of the crest, is fully inside the frame
> with empty margin above it — nothing cropped.** The bust ends at the shoulders and **FLOATS —
> no pedestal, plinth, stand or base** — on a **pure solid black background**. Photorealistic
> studio render, soft symmetrical key light, realistic marble micro-detail and faint
> translucency. Premium, cinematic, restrained sovereign emblem. Single subject, centered, 1:1.
> No text, no watermark.

## Artemis — the hunt & the moon

> **Front-facing marble bust of Artemis, Greek goddess of the hunt and the moon, looking
> directly at the camera, perfectly symmetrical head-on, no tilt.** A youthful, agile, serene
> yet alert female face in pristine **white Carrara marble** with subtle grey veining; hair
> drawn up and back in a hunter's knot; a slender **crescent-moon diadem carved across her
> brow**; a faint quiver strap over one shoulder. **The whole head and crescent diadem are fully
> inside the frame with empty margin above — nothing cropped.** The bust ends at the shoulders
> and **FLOATS — no pedestal, plinth, stand or base** — on a **pure solid black background**.
> Photorealistic studio render, soft symmetrical key light, realistic marble micro-detail and
> faint translucency. Premium, cinematic, restrained sovereign emblem. Single subject, centered,
> 1:1. No text, no watermark.

## Aeolus — keeper of the winds

> **Front-facing marble bust of Aeolus, Greek keeper of the winds, looking directly at the
> camera, perfectly symmetrical head-on, no tilt.** A mature male face with a short curled beard
> in pristine **white Carrara marble** with subtle grey veining; **wind-swept, back-blown hair
> and beard caught mid-gust**, every strand carved in stone; a calm, lofty, far-seeing
> expression; a plain marble circlet at the brow. **The entire windswept head is fully inside
> the frame with empty margin all around — nothing cropped.** The bust ends at the shoulders and
> **FLOATS — no pedestal, plinth, stand or base** — on a **pure solid black background**.
> Photorealistic studio render, soft symmetrical key light, realistic marble micro-detail and
> faint translucency. Premium, cinematic, restrained sovereign emblem. Single subject, centered,
> 1:1. No text, no watermark.

## Janus — beginnings, doorways, transitions  *(two faces)*

> **Front-facing marble bust of Janus, the two-faced Roman god of doorways, beginnings and
> transitions: a SINGLE head bearing TWO bearded male faces joined back-to-back**, one gazing
> left and one gazing right, **perfectly mirror-symmetric, both faces fully visible from the
> front**. Mature, dignified, identical features with classical curled hair and beard, carved
> from pristine **white Carrara marble** with subtle grey veining. **Both faces and the whole
> head are entirely inside the frame with empty margin all around — nothing cropped.** The bust
> ends at the shoulders and **FLOATS — no pedestal, plinth, stand or base** — on a **pure solid
> black background**. Photorealistic studio render, soft symmetrical key light, realistic marble
> micro-detail and faint translucency. Premium, cinematic, restrained sovereign emblem. Single
> subject, centered, 1:1. No text, no watermark.
>
> *(Negative: drop `multiple heads / multiple faces` — Janus needs two.)*

## Cerberus — three-headed hound of Hades  *(three heads)*

> **Front-facing marble sculpture of Cerberus, the three-headed hound of the underworld: THREE
> powerful dog heads rising symmetrically from one muscular neck and chest**, the central head
> facing the camera dead-on, the two flanking heads turned slightly outward, **all three heads
> fully inside the frame**. Alert, snarling guardian intensity; finely carved fur, bared teeth,
> taut musculature, all in pristine **white Carrara marble** with subtle grey veining. **Nothing
> cropped, clear empty margin around all three heads.** The sculpture ends at the chest and
> **FLOATS — no pedestal, plinth, stand or base** — on a **pure solid black background**.
> Photorealistic studio render, soft symmetrical key light, realistic marble micro-detail and
> faint translucency. Premium, cinematic, restrained sovereign emblem, not a game asset. Single
> subject, centered, 1:1. No text, no watermark.
>
> *(Negative: drop `multiple heads` — Cerberus needs three.)*

## Zeus — king of the gods

> **Front-facing marble bust of Zeus, king of the Greek gods, looking directly at the camera,
> perfectly symmetrical head-on, no tilt.** A majestic, powerful older male face with deep-set
> commanding eyes, a broad noble brow, and a **long full flowing beard and thick wavy hair in
> classical curls**, carved from pristine **white Carrara marble** with subtle grey veining;
> sovereign, thunderous calm; a **laurel wreath carved in marble** resting on his head. **The
> entire head and laurel are fully inside the frame with empty margin above — nothing cropped.**
> The bust ends at the chest and **FLOATS — no pedestal, plinth, stand or base** — on a **pure
> solid black background**. Photorealistic studio render, soft symmetrical key light, realistic
> marble micro-detail and faint translucency. Premium, cinematic, restrained sovereign emblem.
> Single subject, centered, 1:1. No text, no watermark.
