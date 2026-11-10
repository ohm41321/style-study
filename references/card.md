# The style card

`style.json` is the only thing about the reference that the maker of the new work sees (with `style.md`,
its rendering, and `brief.md`). `style.py card` fills the measured part; you write the habits.

## Schema (`style-study/1`)

```json
{
  "schema": "style-study/1",
  "name": "quiet-ledger",
  "made": "2026-11-10",
  "references": [{"id": "r1", "medium": "video", "file": "ref1.mp4", "units": 41, "unit": "shots", "seconds": 92.4}],
  "measured": {
    "video": {
      "shot_length": {"label": "Shot length", "unit": "s", "p10": 1.1, "p50": 2.4, "p90": 5.8, "n": 41, "refs": 1, "confidence": "medium"}
    }
  },
  "lang": {"text": "en"},
  "axes": {"tempo": {"band": "medium", "from": "shot_length", "value": 2.4, "medium": "video"}},
  "traits": [
    {"dimension": "camera", "statement": "The camera drifts sideways and never zooms.",
     "do": "Move the camera on a slow lateral slide; keep focal length fixed.",
     "evidence": {"refs": 1, "count": 14}, "confidence": "high"}
  ],
  "avoid": ["Whip pans and speed ramps."],
  "forbid": ["Brand, product, title and character names of the reference"],
  "notes": ""
}
```

Keys `style.py` writes: `schema`, `name`, `made`, `references` (bare file names only, never paths),
`measured`, `lang`, `axes`. Keys you write: `traits`, `avoid`, `forbid`, `notes`. Do not add other keys
under `measured`: a card keeps ranges, never per-unit lists. Lint refuses both.

### measured

Per medium, per dimension: `p10`, `p50` and `p90` of every unit pooled across references (shots, sentences,
seconds, images), with `n` units from `refs` references. `confidence` is `high` with 30 or more units from two
or more references, `medium` with 10 or more units, otherwise `low`. For values measured once per reference
(loudness, tempo), it counts references: three or more is `high`. A `low` range is a hint, not a target.

### axes

Coarse bands (`tempo`, `energy`, `variation`, `brightness`, `contrast`, `color`, `warmth`, `space`) that carry
the style across media. `style.py` derives them; see [translate.md](translate.md). You may override a band
by hand when the numbers mislead (say why in `notes`), but never invent an axis.

## Writing traits

A trait is a habit: something the references do again and again, stated so that a maker can do it in a
new subject. Watch, read or listen to all of the references first; use `style.py sheet` for video.

Each trait has:

- `dimension`: what it is about. Use plain names: `camera`, `framing`, `light`, `colour`, `type`,
  `layout`, `motion`, `transitions`, `voice`, `diction`, `structure-habit`, `sound`, `mix`, `rhythm`.
- `statement`: what the references do, as a rate or a habit. "Most shots hold on one subject with empty
  space on one side", not "the shot of the bridge holds on the left".
- `do`: the instruction for new work. Write it so it works for a different subject.
- `evidence.count`: how many times you saw it (3 or more; lint refuses less). `evidence.refs`: in how many
  references.
- `confidence`: `high` when every reference does it, `medium` when most do, `low` otherwise.

Good traits name a mechanism: "Type enters by fading up over 6-10 frames; nothing slides." "Paragraphs end
on a concrete noun, not on a moral." "Hits come after a beat of silence." "ประโยคจบด้วย ครับ เกือบทุกประโยค
และไม่ใช้ นะ เลย". Weak traits name an adjective only ("clean", "cinematic", "friendly"): add what makes it so.

Write 5 to 12 traits. Cover the parts of the style the numbers cannot see: composition, typography,
gesture, texture, voice, the kind of joke, how sound and picture relate.

## avoid and forbid

`avoid` lists what the style never does, as habits ("No lens flares.", "Never two questions in a row.").
They become the "Never" section of every brief.

`forbid` lists names that must not appear in new work: the reference's brand, product, title, characters,
people, catchphrases, domain. The check flags any of them found in new text, and lint refuses them inside the
card's own wording. Do not leave it empty for a branded reference.

## What never goes in the card

Timestamps, positions ("the first shot", "slide 3", "ย่อหน้าแรก"), descriptions of its opening or ending,
quotes over five words (20 Thai characters), runs of the reference's text, palette hex values, frame hashes,
per-unit sequences, file paths. [firewall.md](firewall.md) lists each rule and why.

An example card for a made-up style: [../assets/example-card.json](../assets/example-card.json).
