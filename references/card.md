# The style card

`style.json` is the person studying's record of the style, and the checker's. The maker of the new work
never sees it: they get `brief.md`, which `style.py brief` writes from the card. `style.py card` fills the
measured part; you write the habits.

## Schema (`style-study/1`)

```json
{
  "schema": "style-study/1",
  "name": "quiet-ledger",
  "made": "2026-11-10",
  "references": [{"id": "r1", "medium": "video", "file": "ref1.mp4", "units": 41, "unit": "shots", "seconds": 92.4,
                  "work": "harbour films"}],
  "measured": {
    "video": {
      "shot_length": {"label": "Shot length", "unit": "s", "p10": 1.1, "p50": 2.4, "p90": 5.8, "n": 41, "refs": 1, "confidence": "medium"}
    }
  },
  "lang": {"text": "en"},
  "axes": {"tempo": {"band": "medium", "from": "shot_length", "value": 2.4, "medium": "video"}},
  "traits": [
    {"dimension": "camera", "statement": "The camera drifts sideways and never zooms.",
     "do": "Let movement run sideways and slowly; never push in.",
     "evidence": {"refs": 1, "count": 14}, "confidence": "high", "core": true}
  ],
  "avoid": ["Whip pans and speed ramps."],
  "forbid": ["Brand, product, title and character names of the reference"],
  "notes": ""
}
```

Keys `style.py` writes: `schema`, `name`, `made`, `references` (bare file names only, never paths; `work`
when `measure --work` said the files are parts of one work),
`measured`, `lang` (per medium that has words: text, slides, document, sheet), `axes`. Keys you write: `traits`, `avoid`, `forbid`, `notes`. Do not add other keys
under `measured`: a card keeps ranges, never per-unit lists. Lint refuses both.

### measured

Per medium, per dimension: `p10`, `p50` and `p90` of every unit pooled across references (shots, sentences,
seconds, images, slides, paragraphs, sheets), with `n` units from `refs` references. `confidence` is `high` with 30 or more units from two
or more references, `medium` with 10 or more units, otherwise `low`. For values measured once per reference
(loudness, tempo), it counts references: three or more is `high`. A `low` range is a hint, not a target.

### axes

Coarse bands (`tempo`, `energy`, `variation`, `brightness`, `contrast`, `color`, `warmth`, `space`) that carry
the style across media. `style.py` derives them; see [translate.md](translate.md). You may override a band
by hand when the numbers mislead (say why in `notes`), but never invent an axis.

## Writing traits

A trait is a habit: something the references do again and again, stated as a **principle** that a maker
can carry out in a new subject, in a form of their own. Watch, read or listen to all of the references
first, the way their audience meets them; use `style.py sheet` for video. Do not read the reference's
source (its CSS, design tokens, project files, stems, scripts): the values in them are its look, and a card
built from them rebuilds the reference.

Each trait has:

- `dimension`: what it is about. Use plain names: `camera`, `framing`, `light`, `colour`, `type`,
  `layout`, `motion`, `transitions`, `voice`, `diction`, `structure-habit`, `sound`, `mix`, `rhythm`.
- `statement`: what the references do, as a rate or a habit. "Most shots hold on one subject with empty
  space on one side", not "the shot of the bridge holds on the left".
- `do`: the principle as an instruction for new work. It says what the work does and why, and leaves the
  form open: no shape, placement, component, colour or exact value of the reference.
- `evidence.count`: how many times you saw it (3 or more; lint refuses less). `evidence.refs`: in how many
  references.
- `confidence`: `high` when every reference does it, `medium` when most do, `low` otherwise.
- `core` (optional): `true` on the few habits, at most five, without which the style is not this style.
  The brief asks the maker to carry every core habit in their own form; the others are free to keep, bend
  or drop. With none marked, the brief takes the three most certain.

### Principle, not recipe

The maker follows the card literally. A trait that names the reference's forms makes the maker rebuild
the reference, however new the subject.

| Recipe (refused or rewritten) | Principle (keep) |
|---|---|
| Labels at 13 px, line height 1.4, a scale step of 1.25 | Small type does most of the work; hierarchy comes from size steps and grey, never a second face |
| Buttons are pills with a filled circle and arrow at the right end | One kind of action control, plainly secondary, with a single mark that says "go" |
| A fixed hook line on a rounded pill in the top band of every shot | A short line that names the premise stays readable in every shot, so the joke works with the sound off |
| Hovers fade over 150 ms on a fast-out curve | Motion answers a change of state, quickly, and never runs on its own |
| Square tiles, four across, a tall gap under each for its caption | Collections read as an even grid where every item gets the same space and a quiet caption |

Lint refuses an exact value in a habit: a number with a unit (`px`, `pt`, `em`, `ms`, `s`, `%`, `x`, `Hz`,
`BPM`, `dB`, `พิกเซล`, `วินาที`), a bare decimal, a hex colour, or a CSS function such as `cubic-bezier(`.
Measured ranges belong in the measured table, where the check reads them; values for the new work are the
maker's to choose. An exact value in `avoid` is a warning.

### Habit or signature?

The test: would someone who knows the reference recognise it from this element alone, in a different
subject? Then it is a **signature**, the reference's own device, even if it appears on every screen. Write
it in `pattern.md` under Signatures, never in the card, and keep only the principle behind it as a trait.
Recurring by design is how a signature works, so counting sightings does not tell a habit from a signature.

A card from one work (one film, one site's screenshots, one book) cannot tell its style from its signature
at all; lint warns, and every trait must then be a principle. Pass `measure --work NAME` when several files
are parts of one work, so the card counts them as one.

Good traits name a mechanism: "Type enters by fading up; nothing slides." "Paragraphs end on a concrete
noun, not on a moral." "Hits come after a beat of silence." "ประโยคจบด้วย ครับ เกือบทุกประโยค และไม่ใช้ นะ
เลย". Weak traits name an adjective only ("clean", "cinematic", "friendly"): add what makes it so.

Write 4 to 8 traits. A card that covers every part of the work (type, scale, grid, tiles, metadata, detail
page, surfaces, colour, motion, spacing, theme) describes one work, not a style, and leaves the maker
nothing to design; lint warns past eight. Cover the parts of the style the numbers cannot see:
composition, gesture, texture, voice, the kind of joke, how sound and picture relate.

## avoid and forbid

`avoid` lists what the style never does, as habits ("No lens flares.", "Never two questions in a row.").
They become the "Never" section of every brief.

`forbid` lists names that must not appear in new work: the reference's brand, product, title, characters,
people, catchphrases, domain. The check flags any of them found in new text, and lint refuses them inside the
card's own wording. Do not leave it empty for a branded reference.

## What never goes in the card

Timestamps, positions ("the first shot", "slide 3", "ย่อหน้าแรก"), descriptions of its opening or ending,
quotes over five words (20 Thai characters), runs of the reference's text, exact values (sizes, timings,
hex colours, curves), its signature devices, frame hashes, per-unit sequences, file paths.
[firewall.md](firewall.md) lists each rule and why.

An example card for a made-up style: [../assets/example-card.json](../assets/example-card.json), and the
checker's `pattern.md` beside it: [../assets/example-pattern.md](../assets/example-pattern.md).
