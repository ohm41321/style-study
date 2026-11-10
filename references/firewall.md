# The pattern firewall

The skill exists to make new work that belongs to a style without copying any one work. The firewall is
the line between the two, and it holds in three places: what the card may say (lint), what the maker may
see (files), and what the new work may share with the reference (check).

## Style or pattern?

| Style (keep) | Pattern (never take) |
|---|---|
| a range: shots of 1-6 s, median 2.4 s | the reference's sequence of shot lengths |
| a rate: a question in one sentence of five | the reference's questions, or where they fall |
| a habit seen 3+ times: type fades up, never slides | a set piece seen once: the logo assembling from dust |
| a band: tempo medium, space airy | the reference's opening or closing image |
| colour character: muted, warm, narrow hue spread | the reference's exact palette, its hex values |
| an arc shape every reference shares: builds to the end | its particular beats, in its particular order |
| a voice: short declaratives, no exclamations | its sentences, its jokes, its catchphrases |
| a sound: sparse piano over low drones | its melody, its stems, its recordings |

The test for a doubtful item: could a different subject do this without anyone thinking of one specific
moment in the reference? Yes: style. No: pattern.

An arc is style only when it is generic and shared. "Starts quiet, ends loud" is a style; "a quiet open on
a city at night, a drop at the halfway mark, a logo on a white flash" is that work's pattern. The order
check removes the overall arc (a quadratic trend) before it compares sequences, for the same reason.

## Lint rules

`style.py lint style.json --fingerprints fingerprints.json` reads the card's `name`, reference file names,
every trait's `dimension`, `statement` and `do`, every `avoid` line, `notes`, and the card's structure. Errors fail the lint; warnings ask you to look again.

| Rule | Catches | Level |
|---|---|---|
| time | `0:12`, `1:02:30`, `at 14 seconds`, `14 s into`, `วินาทีที่ 5` | error |
| position | `first shot`, `last slide`, `opening scene`, `3rd paragraph`, `scene 3`, `slide no. 4`, `ช็อตแรก`, `ฉากสุดท้าย`, `ย่อหน้าที่ 2` | error |
| edge | `the film opens with`, `the post ends on`, `starts with`, `ตอนจบ`, `เปิดเรื่องด้วย` | warning |
| forbidden name | any `forbid` entry inside the card's own wording | error |
| quote | a run in double, curly, single, `«»` or `「」` quotes longer than 5 words or 20 Thai characters (apostrophes are not quotes) | error |
| verbatim | any 8-word (English) or 15-character (Thai) run of a reference's own text | error, needs `--fingerprints` |
| thin evidence | a trait with `evidence.count` under 3 | error |
| sequence | a list, a dict or an unknown key under `measured` | error |
| path | a reference `file` that holds a directory path | error |
| axes | an axis or band name the skill does not know (see [translate.md](translate.md)) | error (exit 2: the card cannot be read) |
| empty | no traits, or an empty `forbid` | warning |

An edge warning is right to keep when every reference opens or ends the same way and the habit is generic
("every piece ends on the product name over black"): then it is style. Write the habit, not the image.

## Files and who sees them

The maker (you in a later step, another skill, another agent, a person) gets `style.md` or `style.json`
and `brief.md`. The checker keeps `fingerprints.json`, `measures*.json`, `pattern.md` and the references.
A maker who can see the reference's sequence will drift toward it, even without meaning to. When the same
agent does both, close the reference files before making, and work from the brief.

## The check

`style.py check` measures the new work and asks whether it follows the reference's order, reuses its
frames, images, audio or text, uses a forbidden name, or wears the same chromatic palette (a warning: a
palette can be a look or a brand). What each test does and its thresholds: [check.md](check.md).

## When the person asks for a copy

If the person wants the reference itself remade, reshot, re-recorded or traced, that is not this skill.
Say so, and offer the style route: same feel, new subject, new structure.
