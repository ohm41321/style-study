# Axes and translation across media

Measured dimensions belong to one medium. Axes are the coarse, shared vocabulary that lets a style learned
from a film steer a deck, a song, a page or an interface. Each axis has three bands.

| Axis | Bands | Read from (first one the card has) |
|---|---|---|
| tempo | slow, medium, fast | shot length (fast under 1.5 s, slow over 3.5 s); sentence length (English: fast under 10 words, slow over 18; Thai: under 35, over 70 characters); tempo (slow under 90, fast over 120 BPM); soundtrack tempo |
| energy | calm, lively, busy | movement (2 and 6 grey levels); onsets (1.5 and 4 per s); detail (0.04 and 0.09); exclamations (2% and 10%) |
| variation | even, moderate, wide | p90 over p10 of shot length or sentence length (2.5 and 4); level swing (4 and 9 dB); p90 over p10 of brightness (1.4 and 2.2) |
| brightness | dark, mid, bright | brightness (0.35 and 0.60); spectral centroid (1.2 and 2.6 kHz) |
| contrast | soft, medium, hard | contrast (0.15 and 0.25); peak to loudness (9 and 14 dB) |
| color | muted, moderate, vivid | saturation (0.20 and 0.40) |
| warmth | cool, neutral, warm | warm share (0.35 and 0.60) |
| space | dense, balanced, airy | empty space (0.30 and 0.55); still time (0.15 and 0.40); quiet time (0.05 and 0.20); sentences per paragraph (airy under 2.5, dense over 5) |

Where a card has several sources for an axis, the order is video, image, audio, text, and within a medium
the order in the table. The rendered card says which dimension each band came from.

## Starting points per target

`style.py brief` prints, for each axis, a starting point in the target medium. A few rows:

| Axis band | video | audio | text | slides | ui |
|---|---|---|---|---|---|
| tempo slow | shots of 3.5-8 s, few cuts | under 90 BPM, long notes | long sentences | one idea per slide held 20 s or more | long sections, transitions 400-700 ms |
| tempo fast | shots of 0.6-1.5 s, cut on accents | 120-150 BPM, short notes | short sentences, fragments allowed | a slide every 3-8 s | one idea per screen, transitions 120-250 ms |
| energy calm | slow drifts, little in-shot movement | under 1.5 onsets per s | no exclamations, plain verbs | one element per slide | almost no motion |
| space airy | frequent still holds | regular drops and silences | short paragraphs | mostly empty slides | large whitespace, few elements per screen |

The full table is `TRANSLATE` in `scripts/ss_dims.py`. Axes without a row for a target fall back to a
general phrase (`any`). `color` and `warmth` always say to build your own palette.

## How the numbers were chosen, and how to change them

The band edges are judgement calls near common practice, not research findings: 1.5 to 3.5 s brackets
the median shot of much edited video (trailers and ads run faster, slow cinema far slower); 90 to 120 BPM
brackets mid-tempo music; 10 to 18 words brackets plain English prose. The starting points are rules of
thumb from editing, music and interface practice. None of them is a measurement of the reference; they
are where to begin before you tune by eye and ear.

To override for one project, edit the card's `axes` by hand (change `band`, and say why in `notes`); the
brief and the translated check follow the card. To change them for everyone, edit `AXIS_SOURCES` or
`TRANSLATE` in `scripts/ss_dims.py` and run `scripts/check-skill.py` again.
