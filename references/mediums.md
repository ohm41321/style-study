# Mediums: what is measured, and where it is weak

Every number is a distribution over units (shots, sentences, seconds, images, slides, paragraphs, sheets), pooled across references
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

Loudness, loudness range, peak to loudness and tempo are one number per file. Two references from one
project (often mastered to the same level, at the same tempo) give the card a range of almost nothing on
those, so the tolerance decides, and a cheerful pop track can pass while another score fails. Study three
to five pieces that differ, and judge mood and instrumentation by ear.

## Documents: how files are read

Slides, documents and sheets need Python only. The files are read as data: OOXML (.pptx, .docx, .xlsx and
their macro and template forms), OpenDocument (zipped or flat XML), EPUB, RTF and CSV are parsed directly;
no macro runs. A zip part over 64 MB, a file over 512 MB unpacked (each part counted once), or XML with a DTD or
entities in any encoding is refused, so a crafted file cannot exhaust memory. A sheet is read up to 200,000 cells.

| Format | How |
|---|---|
| .pptx .docx .xlsx and kin | the XML, with styles resolved: slide master, layout, placeholder and theme for decks; the style chain and document defaults for Word |
| .odp .odt .ods and flat .fodp .fodt .fods | the XML, with named and automatic styles |
| .epub | the XHTML chapters in spine order, as prose; tables are left out of the prose |
| .rtf | a small RTF reader: paragraphs, sizes, bold, italic, tables, pictures, margins, Thai and other code pages |
| .csv .tsv | cells and numbers only, no formatting |
| .pdf | pypdf for text, sizes, typefaces and pictures; poppler's `pdftotext` for text alone when pypdf is missing |
| .ppt .pps .pot .key .sxi, .doc .dot .pages .wpd .wps .abw .hwp .sxw, .xls .xlt .numbers .sxc | converted first by LibreOffice (`soffice --headless`, with a throwaway profile); `.doc`, `.dot`, `.wordml` and `.webarchive` fall back to macOS `textutil` |

Pictures inside a file are fingerprinted for the check: the bytes (a hash), and, with numpy and ffmpeg, how
they look, so a picture re-saved or re-compressed is still found. SVG, EMF and WMF are compared by bytes
only.

## slides

One unit is one slide. Hidden slides, speaker notes and the date, footer and slide-number placeholders
are not measured; the words and pictures of hidden slides still go to the copy check, so hiding a copied
slide does not hide it. The writing on the slides is
also measured with the text dimensions, in the deck's language.

| Dimension | How |
|---|---|
| Text per slide | words (English) or characters without spaces (Thai), titles included |
| Bullets, elements, pictures per slide | bullet paragraphs outside the title; shapes with text or a fill, pictures, tables and charts; pictures alone |
| Slide area covered | share of a 40x40 grid under any element's box. A filled shape without text over 90% of the slide counts as the background, not as an element |
| Title size, body size, title to body | in points, after PowerPoint's shrink-on-overflow scale; body is the commonest size outside the title |
| Background brightness, text contrast | the slide, layout or master fill (a picture fill leaves it unmeasured); median WCAG contrast of text colour against it |
| Typefaces, colours, saturation | faces used across the deck (theme fonts resolved); chromatic colours in text, fills and lines, clustered |
| Aspect | slide width over height |

A PDF deck (`--medium slides`) gives text, bullets, sizes and pictures per page; it has no boxes, so no
fill, elements or background. Weak spots: autofit is applied as PowerPoint last saved it, so a deck that
was never opened in PowerPoint after editing can read larger type than it shows; text drawn in pictures is
invisible; animations, transitions and speaker notes are not measured. Layout grids, alignment, icon style
and how a deck builds an argument are traits: look at the slides.

## document

One unit is one sentence for the writing dimensions (as in text) and one paragraph or page for the layout
dimensions. Headings, lists and tables are told apart from body paragraphs.

| Dimension | How |
|---|---|
| Every text dimension | the prose of the document: headings, body and lists, without tables |
| Body size, heading to body | points; the commonest body size, and each heading against it |
| Line spacing, space after a paragraph | in lines and points, per body paragraph, inherited through the styles |
| Side margins | left plus right margin over page width |
| Bold, italic, justified | share of characters, per 10 blocks; share of justified body paragraphs |
| Pictures, tables | per 10 paragraphs |
| Text per page | words or Thai characters per page: PDF only, since Word and OpenDocument files store no page breaks |
| Typefaces, colours, saturation, aspect | as for slides; aspect is the page |

PDF is read without layout: lines are joined into paragraphs by their length and ending, headings found by
size, so line spacing, margins, bold and justification are not measured from a PDF, and a two-column PDF
can join lines across columns. PDF type sizes include the page and form scales (exports from Canva and
similar tools draw every page inside a scaled form). macOS `textutil` keeps text and sizes but drops heading
styles and tables. Layout of figures, captions, page furniture and voice are traits.

## sheet

One unit is one sheet (a CSV is one sheet). Empty and hidden sheets are not measured; a hidden sheet's
words and pictures still go to the copy check.

| Dimension | How |
|---|---|
| Columns, rows | columns and rows that hold a value, per sheet |
| Numbers, formulas | share of cells holding a number; share holding a formula |
| Decimal places | per number cell, from its number format, or from the value in a CSV |
| Styled header | share of sheets whose first used row is mostly bold or filled |
| Merged ranges, charts | per sheet |
| Label length | characters per text cell |
| Type size, typefaces, colours | from the cell styles |

A CSV has no formatting: only columns, rows, numbers, decimals and labels. The sheet's own numbers, names and
labels are its material and never go on the card. The copy check looks for shared runs of words inside a
cell (a note, a description), not across cells, so two sheets that both have a January to December header
do not match.
Chart types, conditional formats, number formats as a habit (currency, percent) and dashboard layout are
traits.

## The generic route (any other medium)

UI, websites, 3D scenes, fashion, interiors, product photography sets, code style, packaging: there
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
   work exports to a measured medium (a UI recording to video, screens to images, a page to PDF, copy to
   text), measure that export and run `style.py check` on it too.
