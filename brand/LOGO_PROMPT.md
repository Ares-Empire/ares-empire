# Ares Empire — logo brief (Claude Design handoff)

The empire's crown mark is a **marble bust of Ares**, the war-god figure behind Patrik's
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
| Expression | Calm, commanding, eyes forward | Authority over aggression. |
| Background | **Pure black** | The marble white and metallic gold both pop hard against it — the core of the look. |

## Copy-paste prompt

> A museum-quality bust sculpture of **Ares, the Greek god of war**. The face, head and
> beard are carved from pristine **white Carrara marble** with subtle natural grey veining —
> mature, powerful male features, full classical curled beard, calm commanding forward gaze.
> He wears **polished shiny gold war-gear**: a **gilded Corinthian helmet pushed back** on the
> head so the face is fully visible, its crest rising behind, and an ornate **golden cuirass /
> shoulder pauldrons** at the base of the bust. The contrast is the point — luminous white
> marble skin against gleaming reflective gold metal. Photorealistic studio render, soft
> directional key light from upper left, deep shadow, realistic marble micro-detail and faint
> translucency, true metallic gold reflections and specular highlights on the armor.
> **Isolated on a pure black background**, centered, head-and-shoulders bust, slight
> three-quarter turn. Premium, cinematic, restrained — the gravitas of a sovereign emblem, not
> a game asset. Gold appears on the metal gear ONLY; the skin and beard stay white marble. No
> text, no logos.

## Output / placement

- Render on a **black or transparent** background to match the dark wall; export PNG.
- Save here as `brand/ares-bust.png`.
- Mirror whatever post-processing the Arestoteles bust used (`arestoteles/scripts/make_bust.py`)
  for a consistent crop, vignette and trim.

## Then: wire the Arestoteles button

Once `ares-bust.png` exists, update the Arestoteles header hub-link
(`web/app/app.jsx`, `TopBar`) from the plain "Ares Empire" wordmark to **the bust mark +
"Ares Empire"** — small (~22px) mark on the left of the existing label, same glass pill.
