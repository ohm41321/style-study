# The two-sided check

```sh
python3 scripts/style.py check NEW... --card style.json --fingerprints fingerprints.json [-o report.json]
```

New work passes only when both sides pass: the style is close enough to the card, and the pattern is far
enough from every reference. Without `--fingerprints` the pattern side cannot run: the report says
`PATTERN NOT RUN` and the exit code is 1, because unchecked is not passed. For the same reason, when part of
the pattern side cannot run, such as audio against fingerprints written by an older style-study, the report
says `PATTERN INCOMPLETE`, names what was `NOT CHECKED`, and exits 1; run `style.py card` again to rebuild the
fingerprints. A file that is not a
fingerprints file (a card passed by mistake) exits 2. Exit code 0 means both sides ran and passed.

With several new files, each is checked against the references on its own, and a finding names the file.

## Style side

**Same medium (measured mode).** Each card dimension the new work also has is compared: the new work's
median against the card's p10 to p90, widened by a slack. Ratio dimensions (shot length, tempo, sentence
length, onsets, centroid) are compared on a log scale with slack in log10 units, so 2 s against 4 s is the
same step as 4 s against 8 s; the others get slack in their own units, at least 10% of the range. The side
passes when 75% or more of the dimensions are in range and no core dimension is off.

Core dimensions: shot length, cuts per minute, movement (video); onsets per second, spectral centroid
(audio); sentence length, sentences per paragraph (text and document); text per slide, slide area covered,
background brightness (slides); columns per sheet, share of number cells (sheet). Images have none.

English and Thai writing are compared only on the dimensions both languages share. A card with text
measurements and none for documents checks a .docx or PDF against its text block, and the reverse; the
report then says `(against the card's text measurements)`, and only the writing dimensions take part.

Reading a row: `OFF Shot length [core]: 0.9 against 1.4 to 5.8 s (too low)`. The fix is in the work, not the
card: longer holds, fewer cuts. Widening the card to make a draft pass defeats the check. Each dimension
has a small tolerance past p10 and p90 (its `tol`, or a tenth of the range); a value there passes and the
row says `(just outside, within the tolerance)`.

**Another medium (translated mode).** When the card has no measurements for the new work's medium, the
check measures the new work, derives its axis bands, and compares bands: every shared axis within one band
of the card, and at least half in the same band.

## Pattern side

Run against every reference in `fingerprints.json`.

| Test | Alarm | Why |
|---|---|---|
| order | the new work's sequence correlates with the reference's at r 0.5 or more, and fewer than 2% of 300 shuffles of the new work do as well (p 0.02 or less) | following the reference's structure, even with all-new material |
| frames and images | a frame or image whose dHash is close (12 bits) and whose 16x16 grey layout correlates at 0.9 or more with a reference frame. Video: 20% of shots and at least 2. Images: any one | reused footage, traced or recoloured images, the same composition |
| audio | 8 or more consecutive seconds whose 24-band profile (each one-second window against its own average, less the reference's average profile so the tilt all music shares does not count) matches reference windows in step, at cosine 0.92; the reference is fingerprinted every quarter second, so an excerpt cut from anywhere, off the second grid and re-encoded, still lines up; every matching window counts, not only the closest, so loops and repeated choruses keep the run going; silent seconds ignored | reused recordings, stems, excerpts and loops |
| text | a shared run of 12 English words or 40 Thai characters, or 5% of the new text's 8-word (15-character) shingles found in the reference; run in the reference's language, so Thai pasted into English text is still found. Between any two of text, documents, slides and sheets; in a sheet, only runs inside one cell count, so a shared header row (January to December) is not a copy | copied sentences, slide copy, notes in cells |
| pictures | a picture inside a deck, document or sheet that is one of the reference's own files byte for byte; or, with numpy and ffmpeg, one whose dHash and grey layout match a reference picture, frame or image as above. Without numpy a warning says pictures were compared by their bytes only | reused photos, icons and illustrations, re-saved or resized |
| names | a `forbid` name in new text | the reference's brand or characters |
| palette | every chromatic colour of the new work within delta E 6 of one of the reference's, and the reference's within 6 of the new work's on average; images and video against images and video, a deck against a deck, a document against a document. With `--own-palette` (the colours are the person's own brand) it is a warning | the reference's exact colours are its material |

**How the order test works.** Each unit (shot, paragraph, second, image, slide, block, sheet) carries a
few features (length, light, contrast, movement, colour; or length, sentence count, questions, list,
heading, numbers; or level, tone, noise, onsets; or a slide's text, bullets, pictures, fill, background and
title; a block's length, heading, list, table, size and bold; a sheet's columns, rows, numbers, formulas,
charts and header). Both sequences are stretched onto 32 points of a 0 to 1 timeline, weighted by
duration, and their overall arc (a quadratic trend) is removed: a shared "builds to the end" shape is
style. The rest is correlated feature by feature. Then the new work's own units are shuffled 300 times;
if the true order beats almost all shuffles, the new work follows the reference. Fewer than 5 units on
either side: no verdict (a warning says so). Between two written media (Markdown against Word, a PDF
against a deck) the test compares the paragraphs the text route reads on both sides, so saving a
same-order rewrite in another format does not get it past.

## Imitation review

The check sees order and material. It cannot see a signature device drawn anew: the same button shape in
other colours, the same caption treatment on new footage, the same page structure with new content. A
reviewer can.

```sh
python3 scripts/style.py review pattern.md NEW... -o review.md
```

`review.md` is a prompt. Give it, with the new files, to a fresh agent or subagent that has not seen the
brief and is not the maker. It marks every item in `pattern.md` PRESENT (the device, or something a viewer
would take for it), BENT (a related idea in the work's own form) or ABSENT, names anything else that
recalls the reference, and ends with `REVIEW: CLEAR` or `REVIEW: IMITATION`. The work is done only when
the review is clear and both sides of the check pass. Without a Signatures section in `pattern.md` the
review has nothing to look for; lint `--pattern` refuses such a file.

## When it fails

- **Order.** Rebuild the structure from the subject: list the parts the subject needs, in the order it
  needs them, then fit the style to that. Moving two sections around is not enough if the rest still follows.
- **Frames, images or pictures.** Replace the flagged footage, image or picture with new material. A
  recolour, crop or re-encode of the reference is still the reference.
- **Audio.** Replace the matched stretch with new music or sound; a remix of the reference's stems counts
  as reuse.
- **Text.** Rewrite the flagged run in your own words; quote at most a few words, and only with credit.
- **Palette.** Build a palette from the subject (a material, a place, an object in it), with the card's
  character. `--own-palette` is for colours the person owns, such as their own brand; never for convenience.
- **Imitation.** For each item the reviewer marked present, go back to the brief's concept and design that
  part again from the subject. Recolouring, resizing or moving the device is not enough. If the person
  points at a part the list missed, add it to `pattern.md` under Signatures first.
- **Style.** Work on the `OFF` rows, starting with the core ones.

## False alarms and blind spots

- Two works can share a generic order without copying (talking head, then product, then logo). If the
  alarm fires on such a structure, check the card's references: a style learned from one reference makes
  every one of its habits look like order. Add references. Do not raise the thresholds.
- Very simple graphics (one shape on a flat field) can match a reference's layout by chance; look at the
  flagged frame before rebuilding.
- Two decks or documents that both keep a stock template's colours (a default Office or Keynote theme)
  share a palette that belongs to neither. Build a palette from the subject anyway: a stock palette is no
  one's design, the new work's included.
- The check does not see mirrored copies, hard crops, re-performances, paraphrase, or a melody played on
  another instrument. It does not judge quality. Look, listen and read as well.

Show the person both verdicts and the rows that moved, with the files. They decide when it is right.
