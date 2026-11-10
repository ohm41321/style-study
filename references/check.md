# The two-sided check

```sh
python3 scripts/style.py check NEW... --card style.json --fingerprints fingerprints.json [-o report.json]
```

New work passes only when both sides pass: the style is close enough to the card, and the pattern is far
enough from every reference. Without `--fingerprints` the pattern side cannot run: the report says
`PATTERN NOT RUN` and the exit code is 1, because unchecked is not passed. A file that is not a
fingerprints file (a card passed by mistake) exits 2. Exit code 0 means both sides ran and passed.

With several new files, each is checked against the references on its own, and a finding names the file.

## Style side

**Same medium (measured mode).** Each card dimension the new work also has is compared: the new work's
median against the card's p10 to p90, widened by a slack. Ratio dimensions (shot length, tempo, sentence
length, onsets, centroid) are compared on a log scale with slack in log10 units, so 2 s against 4 s is the
same step as 4 s against 8 s; the others get slack in their own units, at least 10% of the range. The side
passes when 75% or more of the dimensions are in range and no core dimension is off.

Core dimensions: shot length, cuts per minute, movement (video); onsets per second, spectral centroid
(audio); sentence length, sentences per paragraph (text). Images have none.

English and Thai text are compared only on the dimensions both languages share.

Reading a row: `OFF Shot length [core]: 0.9 against 1.4-5.8 s (too low)`. The fix is in the work, not the
card: longer holds, fewer cuts. Widening the card to make a draft pass defeats the check.

**Another medium (translated mode).** When the card has no measurements for the new work's medium, the
check measures the new work, derives its axis bands, and compares bands: every shared axis within one band
of the card, and at least half in the same band.

## Pattern side

Run against every reference in `fingerprints.json`.

| Test | Alarm | Why |
|---|---|---|
| order | the new work's sequence correlates with the reference's at r 0.5 or more, and fewer than 2% of 300 shuffles of the new work do as well (p 0.02 or less) | following the reference's structure, even with all-new material |
| frames and images | a frame or image whose dHash is close (12 bits) and whose 16x16 grey layout correlates at 0.9 or more with a reference frame. Video: 20% of shots and at least 2. Images: any one | reused footage, traced or recoloured images, the same composition |
| audio | 8 or more consecutive seconds whose 24-band profile (against the file's own average) matches consecutive reference seconds at cosine 0.97, at any offset; silent seconds ignored | reused recordings or stems |
| text | a shared run of 12 English words or 40 Thai characters, or 5% of the new text's 8-word (15-character) shingles found in the reference; run in the reference's language, so Thai pasted into English text is still found | copied sentences |
| names | a `forbid` name in new text | the reference's brand or characters |
| palette (warning) | every chromatic colour of the new work within delta E 6 of one of the reference's, and the reference's within 6 of the new work's on average | same colour set: fine for a look, not for a brand |

**How the order test works.** Each unit (shot, paragraph, second, image) carries a few features (length,
light, contrast, movement, colour; or length, sentence count, questions, list, heading, numbers; or level,
tone, noise, onsets). Both sequences are stretched onto 32 points of a 0 to 1 timeline, weighted by
duration, and their overall arc (a quadratic trend) is removed: a shared "builds to the end" shape is
style. The rest is correlated feature by feature. Then the new work's own units are shuffled 300 times;
if the true order beats almost all shuffles, the new work follows the reference. Fewer than 5 units on
either side: no verdict (a warning says so).

## When it fails

- **Order.** Rebuild the structure from the subject: list the parts the subject needs, in the order it
  needs them, then fit the style to that. Moving two sections around is not enough if the rest still follows.
- **Frames or images.** Replace the flagged footage or image with new material. A recolour, crop or
  re-encode of the reference is still the reference.
- **Audio.** Replace the matched stretch with new music or sound; a remix of the reference's stems counts
  as reuse.
- **Text.** Rewrite the flagged run in your own words; quote at most a few words, and only with credit.
- **Style.** Work on the `OFF` rows, starting with the core ones.

## False alarms and blind spots

- Two works can share a generic order without copying (talking head, then product, then logo). If the
  alarm fires on such a structure, check the card's references: a style learned from one reference makes
  every one of its habits look like order. Add references. Do not raise the thresholds.
- Very simple graphics (one shape on a flat field) can match a reference's layout by chance; look at the
  flagged frame before rebuilding.
- The check does not see mirrored copies, hard crops, re-performances, paraphrase, or a melody played on
  another instrument. It does not judge quality. Look, listen and read as well.

Show the person both verdicts and the rows that moved, with the files. They decide when it is right.
