# Mediums: what is measured, and where it is weak

Every number is a distribution over units (shots, sentences, seconds, images), pooled across references
into p10, p50 and p90. More references and longer references give tighter, more honest ranges: one 30 s
clip is a hint; three pieces of a few minutes each is a style.

`measure` keeps the per-unit lists in `measures*.json`; `card` keeps only the ranges and moves the
sequences into `fingerprints.json`.

## text

Any Python 3.9+, no packages. Markdown, plain text, HTML, SRT and VTT are cleaned to prose first (code
blocks, images, link targets, emphasis marks, tags, scripts and subtitle timings removed; link text kept). The language is Thai when Thai letters are over 30% of
the letters, otherwise English. Make one card per language: lint refuses a mix.

| Dimension | How |
|---|---|
| Sentence length | words (English), characters without spaces (Thai). Thai sentences end at a space between Thai letters, at `?` or `!` |
| Sentences per paragraph | body paragraphs only, not lists or headings |
| Questions, exclamations, numbers, emoji | share of sentences, in windows of 10 sentences. A Thai question also ends in ไหม, มั้ย, หรือเปล่า, ยังไง and similar |
| First and second person | share of sentences with I, we / ผม, ฉัน, เรา, or you / คุณ, ท่าน. Thai words that only contain a pronoun (คุณภาพ, เท่านั้น, ข้าว) do not count |
| Polite and soft endings (Thai) | sentences ending in ครับ, ค่ะ, คะ and similar; นะ, จ้า, เลย, สิ and similar |
| English in Thai | share of characters that are Latin letters |
| Commas, contractions, word length, variety (English) | per sentence; per 100 words; letters per word; moving-average type-token ratio over 50 words |
| Lists, headings | share of blocks, in groups of 8 blocks |

Weak spots: Thai sentence breaks follow spaces, so Thai written without spaces between sentences reads as
long sentences, and Thai written with a space after every phrase reads as short ones. Look at
`measures-text.json` once: if the units look wrong, say so on the card (`notes`) and lean on the traits.
Tone, humour, argument shape and word choice are habits for `traits`, not numbers.

## video

numpy and ffmpeg. The picture is read at up to 30 fps on a 128x72 grey copy (cuts, movement) and at 4 fps
on a 64x36 colour copy (colour), so a ten-minute film fits in memory. `--max-seconds` (default 600) caps
the length read.

| Dimension | How |
|---|---|
| Shot length, cuts per minute | a hard cut is a lone spike in frame change: over 6 times the median change (at least 12 grey levels) and over twice both neighbours. Tested to within one frame |
| Movement inside a shot | median frame change inside the shot, in grey levels |
| Time in still shots | share of time in shots whose movement is under 0.5 grey levels, per 30 s window |
| Brightness, contrast, saturation, colourfulness, warmth, hue spread | per shot, from the colour copy |
| Cuts on an audio accent | share of cuts within 60 ms of an audio onset (only with a soundtrack) |
| Soundtrack | every audio dimension below, with a `Soundtrack:` label and an `audio_` key |

Dissolves, wipes and slow fades are not counted as cuts: a piece built on them measures as long shots,
which is honest about its pace but not about its cutting. Say so in a trait. Camera language, framing,
type, graphics and how motion eases are traits: run `style.py sheet` and watch the references.

## image

numpy and ffmpeg. Pass a set of images in one `measure` call; each image is one unit. Images are read at up
to 256 px on the long side.

| Dimension | How |
|---|---|
| Brightness, contrast | mean and spread of luma |
| Saturation, colourfulness, warmth, hue spread | from the pixels |
| Detail | mean edge energy |
| Empty space | share of an 8x8 grid whose edge energy is under 15% of the busiest cells |
| Subject distance from centre | distance of the edge-energy centroid from the centre, 0 centred to 1 in a corner |
| Aspect ratio | width over height |

An image set has no natural order, so the order check on images matters only for a sequence (a carousel,
a comic, a storyboard). Typography, illustration style, line quality and composition rules are traits.

## audio

numpy and ffmpeg. Read at 22.05 kHz stereo. Loudness numbers come only from ffmpeg's EBU R128 meter
(`ebur128`); the per-second levels used elsewhere are plain RMS dBFS and are never called LUFS.

| Dimension | How |
|---|---|
| Integrated loudness, loudness range, peak to loudness | ffmpeg `ebur128` with true peak, once per file |
| Tempo | autocorrelation of the onset envelope between 55 and 200 BPM, leaning toward 115 BPM; only when there are enough onsets. Tested within 1.5 BPM on click tracks |
| Onsets per second | log-band spectral flux peaks, placed on the steepest energy rise inside the frame. Tested within 12 ms |
| Level swing, quiet time | per 10 s window: p90 minus p10 of per-second level; share of seconds 12 dB under the median |
| Tone | spectral centroid and flatness, per second |
| Bands | share of energy under 250 Hz, 250 Hz to 2 kHz and over 2 kHz, per 5 s |
| Width | side energy under mid energy, in dB |

Tempo can land on half or double time for music with a weak pulse; trust it only when it matches what you
hear. Instrumentation, harmony, melody shape and production habits (reverb, saturation, how hits are built)
are traits. Never transcribe the reference's melody or harmony into the card: that is the pattern.

## The generic route (any other medium)

UI, slides, websites, 3D scenes, fashion, interiors, product photography sets, code style, packaging: there
is no measuring route, and the card still works.

1. Study at least three references, or three distinct parts of one large reference (three screens of an
   app, three rooms, three pieces of a collection).
2. Write the card by hand: `schema`, `name`, `references` (bare names), `traits`, `avoid`, `forbid`, and
   `axes` with bands you judge yourself (`tempo`, `energy`, `variation`, `brightness`, `contrast`,
   `color`, `warmth`, `space`; band names in [translate.md](translate.md)). Leave `measured` as `{}`.
   Write each trait with a number where the medium has one: spacing in px, type sizes in a ratio, corner
   radius, transition length in ms, line height.
3. Lint it (`style.py lint style.json`). The firewall applies unchanged: no positions ("the second
   screen"), no copied copy, no names, no exact palette.
4. Brief it (`style.py brief style.json --for ui`) and make the work.
5. Check by review: put the new work and the brief side by side and go through sections 3 to 5 of the
   brief. Then the pattern questions by eye: does any screen, slide or piece follow the reference's order?
   Reuse its layout grid exactly, its illustrations, its copy, its icons, its colour values? If the new
   work exports to a measured medium (a UI recording to video, a deck to images, copy to text), measure
   that export and run `style.py check` on it too.
