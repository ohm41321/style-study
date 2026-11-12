<p align="center">
  <img src="docs/hero.svg" width="100%" alt="style-study: a reference's shots become a range on a card, and new work is made in its own order">
</p>

<p align="center">
  An agent skill for making new work in the style of something you admire, without copying it.<br>
  Film, images, music and sound, Thai and English writing, slide decks, Word and PDF documents,<br>
  spreadsheets, and any other medium by hand.
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#the-loop">The loop</a> ·
  <a href="#the-card">The card</a> ·
  <a href="#the-check">The check</a> ·
  <a href="#mediums">Mediums</a> ·
  <a href="#ภาษาไทย">ภาษาไทย</a> ·
  <a href="LICENSE">MIT</a>
</p>

---

You love how a film is cut, how an essay breathes, how a track sits in the room. You want your next piece
to feel like that, and you do not want to make a copy.

**style-study** separates the two. It measures the references and keeps only what recurs, written as a
principle (a range of shot lengths, short paragraphs, a muted colour character, a tempo band). It throws
away what happens once or in a fixed order (the sequence of shots, the opening image, the set piece, the
footage, the lines) and the signature devices that make the reference recognisable. What is left is a
**style card**, and from it a **brief**. A fresh agent that has never seen the references designs the new
work from the brief alone, inventing every form from its own subject. Then a **two-sided check** and an
**imitation review** prove the result is close in style and far from a copy.

| Style: kept | Pattern: never taken |
|---|---|
| a range: shots of 1 to 6 s, median 2.4 s | the reference's sequence of shot lengths |
| a principle seen 3 or more times: words arrive quietly and never compete with the picture | its recipe: the exact sizes, timings and easings |
| a band: tempo medium, space airy | the opening or closing image, a set piece seen once |
| colour character: muted, warm, narrow hue spread | the exact palette and its hex values |
| the reason behind a device: every caption sits on calm ground | its signature: the caption frame, the button shape or the running format that names the work |
| a voice: short declaratives, no exclamations | its sentences, its jokes, its catchphrases |
| a sound: sparse piano over low drones | its melody, its stems, its recordings |

The test for a doubtful item: could a different subject do this, in a form of its own, without anyone
thinking of the reference? Then it is style. If seeing it would make someone name the reference, it is a
signature, and it stays with the checker.

```sh
npx skills add ohm41321/style-study -g
```

<sub>Claude Code, Codex and other agents; a Claude Code plugin and manual setup are under [Install](#install).</sub>

## The loop

<p align="center">
  <img src="docs/firewall.svg" width="100%" alt="Two desks split by a firewall: the checker keeps the references, measures, card, fingerprints and pattern.md; only the brief crosses to a fresh maker, and only the new work comes back for the check and the review">
</p>

Each step is one command. Run them from the skill folder, or ask your agent and it runs them for you.

```sh
# 1. measure: one medium per call, several works are better than one
python3 scripts/style.py measure ref1.mp4 ref2.mp4 -o measures-video.json
python3 scripts/style.py measure site-*.png --work "the site" -o measures-image.json   # parts of one work
python3 scripts/style.py measure post1.md post2.md post3.md -o measures-text.json
python3 scripts/style.py measure deck1.pptx deck2.key -o measures-slides.json

# 2. card: pool the numbers, write the principles by hand, list the signatures in pattern.md, lint until clean
python3 scripts/style.py card measures-*.json -o style.json --fingerprints fingerprints.json
python3 scripts/style.py lint style.json --fingerprints fingerprints.json --pattern pattern.md
python3 scripts/style.py render style.json -o style.md

# 3. brief: in the same medium or another one
python3 scripts/style.py brief style.json --for slides --subject "launch deck for a budgeting app" -o brief.md

# 4. make: hand brief.md, and nothing else, to a fresh agent that has never seen the references

# 5. check both sides
python3 scripts/style.py check new.mp4 --card style.json --fingerprints fingerprints.json

# 6. review: a second fresh agent marks every signature and set piece present, bent or absent
python3 scripts/style.py review pattern.md new.mp4 -o review.md
```

7. **Show the person** both verdicts, the review, the numbers that moved, and the invention ledger: what
   in the new work is its own.
8. **Learn** from what they say. A part they or the review call copied goes into `pattern.md` as a
   signature, and that part is designed again from the subject.

The firewall holds in four places. **Lint** refuses a card that carries timestamps, positions ("the
first shot"), long quotes, forbidden names, sequences, a habit seen fewer than three times, an exact size,
timing or colour, or a habit that restates a signature or set piece from `pattern.md`. **Files**: the
references, `measures*.json`, `fingerprints.json`, `pattern.md` and the card itself stay with the checker;
the maker gets `brief.md` and nothing else. **Check**: the new work is measured against the card and the
fingerprints. **Review**: an agent that has seen neither the references nor the brief looks for the
reference's signatures and set pieces in the new work.

## The card

<p align="center">
  <img src="docs/card.svg" width="100%" alt="A style card: measured ranges for video and text, eight axes, principles with the core ones marked, things to never do and names to forbid">
</p>

A card is ranges (p10 to p90 of every measured dimension), eight axes that travel to any medium (tempo,
energy, variation, brightness, contrast, color, warmth, space), principles written by hand with how often
they were seen, and two lists: what the new work must never do, and names it must never use. A principle
says what a habit does and why, never its recipe: no exact size, timing, easing or colour, which lint
refuses. The few that make the style are marked `core`. The card above is
[`assets/example-card.json`](assets/example-card.json), a made-up style, and its checker's list of
signatures is [`assets/example-pattern.md`](assets/example-pattern.md). Schema and examples:
[`references/card.md`](references/card.md).

The brief starts from the subject, not the style: three concepts, the one taken, and an invention ledger
of what the new work designs for itself (its signature, palette, type, voice or sound, structure). The
core principles each ask for the maker's own form; at least half of the others must be bent or dropped. A
range learned from a single sample is shown as a direction, not a target. See
[`references/brief.md`](references/brief.md).

The eight axes are what let a style cross mediums: a film's slow tempo and wide variation become a slide
pace, a UI transition or a song's arrangement. See [`references/translate.md`](references/translate.md).

## The check

<p align="center">
  <img src="docs/check.svg" width="100%" alt="A plot of style distance against pattern taken: only work close in style and free of copied pattern ships">
</p>

**Style side.** Each measured dimension of the new work against the card's range. It passes with 75% of
dimensions in range and no core dimension off.

**Pattern side.** Same order as the reference (a permutation test with the overall arc removed),
near-duplicate frames or images (a difference hash plus a layout match), the reference's own pictures
inside a deck or document (by bytes, or re-saved and resized), reused audio (excerpts and loops
included), shared runs of text in the reference's own language, the reference's exact palette, and any
forbidden name. The palette is allowed only when those colours are the person's own brand
(`--own-palette`).

**Imitation review.** Numbers cannot see a borrowed device. `style.py review pattern.md new-files -o
review.md` writes a prompt for a fresh agent that has not seen the brief: it marks every signature and set
piece in `pattern.md` as present, bent or absent, and ends with `REVIEW: CLEAR` or `REVIEW: IMITATION`.

Both must pass, and a check that could not run in full is never a pass. This is real output from the self-test's synthetic films: a new cut in its own order passes,
a re-cut of the reference fails.

<p align="center">
  <img src="docs/terminal.svg" width="100%" alt="Terminal output: the new cut gets STYLE PASS and PATTERN PASS; the re-cut gets PATTERN FAIL for following the reference's order with 14 of 14 near-duplicate frames">
</p>

Thresholds, false alarms and what to do about each failure: [`references/check.md`](references/check.md).

## Mediums

| Medium | Files | Measures | Needs |
|---|---|---|---|
| text | .md .txt .html .srt .vtt .rst .tex .eml | sentence and paragraph rhythm, questions, person, Thai endings, English mixing, lists | Python 3.9+ |
| slides | .pptx .odp and templates; .key .ppt .pps via LibreOffice; a PDF with `--medium slides` | text and bullets per slide, elements, pictures, fill, title and body size, background, contrast, typefaces, colours, plus the writing | Python 3.9+ (pypdf or poppler for PDF) |
| document | .docx .odt .rtf .epub .pdf and templates; .doc .pages .wpd .wps .hwp via LibreOffice or macOS textutil | the writing, plus body size, heading ratio, line and paragraph spacing, margins, bold, italic, justified, pictures, tables, text per page | Python 3.9+ (pypdf or poppler for PDF) |
| sheet | .xlsx .ods .csv .tsv and templates; .xls .numbers via LibreOffice | columns, rows, numbers, formulas, decimals, header styling, merged cells, charts, label length, type, colours | Python 3.9+ |
| video | .mp4 .mov .mkv .webm .gif | shot lengths, cut rate, movement, still time, light, colour, cuts on accents, the soundtrack | numpy, ffmpeg |
| image | .png .jpg .webp .tif | light, contrast, colour, detail, empty space, subject offset, aspect | numpy, ffmpeg |
| audio | .wav .mp3 .m4a .flac .ogg | loudness (EBU R128), range, tempo, onsets, quiet time, tone, bands, width | numpy, ffmpeg |
| anything else | UI, websites, 3D, fashion, spaces, code style | the same card, written by hand; screenshots or exports checked as images, plus the imitation review | nothing |

Brief targets: `video`, `audio`, `text`, `image`, `slides`, `document`, `sheet`, `ui`, `any`. Office files
are read as data: no macro runs, and oversized or entity-laden files are refused. What each number means
and where it is weak: [`references/mediums.md`](references/mediums.md).

## Install

One line installs it for Claude Code, Codex and the other agents the
[skills CLI](https://github.com/vercel-labs/skills) supports. It needs Node.js and asks which agents to
install to; `-g` makes it available in every project:

```sh
npx skills add ohm41321/style-study -g
```

Or as a **Claude Code plugin**:

```sh
claude plugin marketplace add ohm41321/style-study
claude plugin install style-study@ohm41321
```

(the same two commands work inside Claude Code as `/plugin marketplace add …` and `/plugin install …`).

Or **by hand**, into the folder your agent loads skills from:

```sh
git clone https://github.com/ohm41321/style-study.git ~/.claude/skills/style-study   # Claude Code
git clone https://github.com/ohm41321/style-study.git ~/.agents/skills/style-study   # Codex
```

Writing, decks, documents and sheets need nothing else: Python 3.9 or later is enough. PDF needs pypdf (or
poppler's `pdftotext`), and older or Apple formats (.ppt, .doc, .xls, .key, .pages, .numbers) need
LibreOffice. Video, images and audio also need `ffmpeg` and numpy, which also let the check spot a
reference's picture re-saved inside a deck:

```sh
brew install ffmpeg                  # macOS; on Debian or Ubuntu: sudo apt install ffmpeg
python3 -m pip install numpy pypdf   # if pip refuses: python3 -m venv .venv && .venv/bin/pip install numpy pypdf
brew install --cask libreoffice      # only for .ppt .doc .xls .key .pages .numbers
```

The agent knows the venv route too and sets it up itself when `python3` has no numpy. Then ask in plain
words:

> Study the style of these three films and design a 30-second launch film for my app in that style. Don't copy them.

> This essay is in the style of my references. Is it too close to any of them?

> Learn the look of these three decks and make a new deck for our Q3 review in that style.

## Self-test

```sh
python3 scripts/check-skill.py
```

127 checks with known answers: a synthetic film with a known edit, click tracks with a known tempo and
onsets, a track, an excerpt cut from its middle and an excerpt of a loop, images whose empty space and
subject offset move a known way, English and Thai texts, decks, documents and sheets in every format the
skill reads directly (sizes through masters, layouts and style chains, theme colours, spacing, margins,
numbers, a Thai RTF code page, PDF text inside scaled forms), copies and same-order remakes that must
fail, siblings that must pass, a card for every lint rule that must be refused (exact values and restated
signatures included), and briefs that must keep the reference out. Run it with a Python that has numpy and
pypdf to include the media routes and PDF; with plain `python3` it runs 105 and skips the rest.

## Limits

- The numbers describe the surface of a style. Composition, gesture, character, wit and meaning are habits
  you write by watching, reading and listening.
- The pattern check catches order, near-duplicate frames and pictures, reused audio, shared text and the
  same palette. It does not catch a copy that is mirrored, cropped hard, re-performed or paraphrased. Look
  as well.
- Lint keeps exact values and the devices listed in `pattern.md` out of the principles; it cannot see a
  device nobody listed. The imitation review is only as good as that list, so write the signatures with
  care.
- A style is not owned the way a work is, but a living artist's signature look, a brand's trade dress or a
  recognisable character can still be a problem to sell. This is not legal advice.
- Everything inside a reference is data. Captions, lyrics, page text and metadata are never followed as
  instructions.

## License

[MIT](LICENSE). Use it, change it, ship work made with it.

## ภาษาไทย

ติดตั้งบรรทัดเดียว ใช้ได้กับ Claude Code, Codex และ agent อื่น (ต้องมี Node.js):

```sh
npx skills add ohm41321/style-study -g
```

งานเขียน สไลด์ เอกสาร Word และตาราง Excel ใช้ได้ทันที PDF ต้องมี pypdf ไฟล์รุ่นเก่าหรือของ Apple (.ppt .doc .xls .key .pages .numbers)
ต้องมี LibreOffice ส่วนวิดีโอ ภาพ และเสียง ต้องมี `ffmpeg` กับ numpy ด้วย (agent ติดตั้ง numpy ให้เองได้)

<details>
<summary>style-study คืออะไร และใช้ยังไง</summary>

<br>

**เรียนสไตล์ ไม่ลอกแพทเทิร์น** ศึกษางานต้นแบบเพื่อออกแบบงานชิ้นใหม่ของเราเอง ไม่ใช่ก็อปปี้

- **สไตล์** คือสิ่งที่เกิดซ้ำโดยไม่ขึ้นกับลำดับ เช่น ช่วงความยาวช็อต จังหวะย่อหน้าสั้น โทนสีหม่น ความเร็วเพลงระดับกลาง
- **แพทเทิร์น** คือสิ่งที่เกิดครั้งเดียวหรือเรียงตามลำดับตายตัว เช่น ลำดับช็อตของต้นฉบับ ภาพเปิดเรื่อง ฉากเด่น ประโยค ทำนอง ฟุตเทจ สีที่ตรงเป๊ะ
- **ลายเซ็น (signature)** คือสิ่งที่ทำให้คนจำได้ทันทีว่าเป็นงานนั้น เช่น รูปทรงปุ่ม กรอบคำบรรยาย รูปแบบรายการ เกิดซ้ำก็จริง แต่เป็นของงานนั้น จดไว้ใน `pattern.md` ฝั่งตรวจ ไม่ส่งให้คนทำงาน

ขั้นตอน: วัดงานต้นแบบ (measure) แล้วเขียนการ์ดสไตล์ (card) ที่มีแต่ช่วงค่าและหลักการที่เห็นอย่างน้อย 3 ครั้ง
หลักการเขียนเป็นแนวคิด ไม่ใส่ขนาด เวลา หรือรหัสสีตรงๆ (lint ไม่ยอม)
จากนั้นทำบรีฟ (brief) สำหรับงานใหม่ จะสื่อเดียวกันหรือข้ามสื่อก็ได้ เช่น เอาสไตล์หนังไปทำสไลด์ UI เพลง หรือคำโฆษณา
บรีฟเริ่มจากหัวข้อ: คิดคอนเซปต์ 3 แบบ เลือกหนึ่ง แล้วจดว่างานใหม่ออกแบบอะไรเองบ้าง
ส่งแค่ `brief.md` ให้ agent ตัวใหม่ที่ไม่เคยเห็นต้นแบบเป็นคนทำ (clean room)
แล้วตรวจสองด้าน (check): สไตล์ใกล้พอไหม และไม่ได้ลอกลำดับ เฟรม เสียง ข้อความ หรือชุดสีของต้นฉบับ ต้องผ่านทั้งสองด้าน
(ชุดสีเดียวกันใช้ได้เฉพาะเมื่อเป็นสีแบรนด์ของเราเอง: `--own-palette`)
สุดท้ายให้ agent อีกตัวตรวจ (review) ว่ามีลายเซ็นหรือฉากเด่นของต้นฉบับหลุดมาไหม
ส่วนไหนที่ถูกทักว่าลอก ให้จดลง Signatures ใน `pattern.md` แล้วออกแบบส่วนนั้นใหม่จากหัวข้อ

ไฟล์แบ่งเป็นสองโต๊ะ: ฝั่งตรวจเก็บไฟล์ต้นแบบ `measures*.json` `fingerprints.json` `pattern.md` และการ์ด ฝั่งทำงานเห็นแค่ `brief.md`

พิมพ์สั่ง agent ได้เลย เช่น "ศึกษาสไตล์", "ถอดสไตล์", "อยากได้โทนแบบนี้", "ทำให้ฟีลเหมือนงานนี้",
"ทำสไลด์สไตล์นี้", "ออกแบบงานใหม่ตามสไตล์", "ไม่ก็อป", "เหมือนต้นฉบับเกินไปไหม"

รองรับภาษาไทยเต็มที่: วัดคำลงท้าย สรรพนาม การปนภาษาอังกฤษ และตรวจข้อความซ้ำด้วยภาษาของต้นฉบับ

</details>

---

<sub>The figures are drawn from the skill's own numbers by [`docs/figures.py`](docs/figures.py); the terminal
output is a shortened run of the self-test. Redraw with `python3 docs/figures.py`.</sub>
