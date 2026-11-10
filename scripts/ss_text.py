"""Text route: measure the style of writing (Thai or English) and fingerprint it for the copy check.

Standard library only. A reference is split into blocks (paragraphs, headings, list blocks) and
sentences. Thai has no sentence punctuation, so a Thai sentence ends at a space between two Thai
characters, at a line break, or at ! and ?; a space next to a Latin word or a number is word spacing.
"""

import hashlib
import html
import math
import re

from ss_common import StyleError

THAI = re.compile(r"[฀-๿]")
LATIN = re.compile(r"[A-Za-z]")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")
DIGIT = re.compile(r"[0-9๐-๙]")
WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
EN_SPLIT = re.compile(r"(?<=[.!?…])[\"'”’)]*\s+")
# a space between two Thai characters ends a Thai sentence, unless the left one is the repeat mark
TH_SPLIT = re.compile(r"(?<=[฀-ๅ็-๿])[ \t]+(?=[฀-๿])|(?<=[!?])\s+")

TH_POLITE = ("ครับ", "ค่ะ", "คะ", "ค่า", "คับ", "ฮะ", "งับ", "ขอรับ")
TH_SOFT = ("นะ", "น้า", "จ้ะ", "จ้า", "จ๊ะ", "เนอะ", "นะจ๊ะ", "สิ", "เลย", "ล่ะ", "หรอก")
TH_QUESTION = ("ไหม", "มั้ย", "หรือเปล่า", "หรือยัง", "อะไร", "ทำไม", "ยังไง", "อย่างไร", "เหรอ", "หรอ",
               "ไหน", "ใคร", "เมื่อไร", "เมื่อไหร่", "กี่", "บ้าง", "มั๊ย", "ป่าว")
# Thai has no spaces between words, so each pronoun is matched with the common words that contain it ruled
# out: คุณภาพ, เท่านั้น, ข้าว, แก้, นายก and the like are not people.
TH_FIRST = re.compile(r"ผม|ดิฉัน|ฉัน|เรา(?!ะ)|หนู|กู(?!เกิล)|ข้า(?![วงมหยศ])")
TH_SECOND = re.compile(r"คุณ(?!ภาพ|ค่า|สมบัติ|ลักษณ|ธรรม|ประโยชน์|วุฒิ|งาม|หญิง|นาย)|นาย(?!ก|จ้าง|ทุน|หน้า|ทหาร|ร้อย|พล|สิบ|ตรวจ)"
                       r"|เธอ|แก(?![่้๊๋งวลสะรน])|มึง|(?<!เ)ท่าน|ตัวเอง")
EN_FIRST = {"i", "me", "my", "mine", "we", "us", "our", "ours", "i'm", "i've", "i'd", "i'll", "we're", "we've", "we'll"}
EN_SECOND = {"you", "your", "yours", "you're", "you've", "you'll", "you'd"}

CHUNK = 10  # sentences per window for rates


def read_text(path):
    from ss_common import kind_of
    if kind_of(path) in ("slides", "document", "sheet"):
        import ss_docs
        return ss_docs.prose_of(path)
    low = path.lower()
    if low.endswith(".eml"):
        return email_text(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if low.endswith(".tex"):
        return tex_text(raw)
    if low.endswith(".org"):
        return re.sub(r"(?m)^(\*+)\s", lambda m: "#" * min(6, len(m.group(1))) + " ", raw)
    if low.endswith((".adoc", ".asciidoc")):
        return re.sub(r"(?m)^(=+)\s", lambda m: "#" * min(6, len(m.group(1))) + " ", raw)
    if low.endswith((".srt", ".vtt")):
        keep = []
        for line in raw.splitlines():
            s = line.strip()
            if not s:
                keep.append("")
            elif "-->" in s or s.isdigit() or s.upper().startswith("WEBVTT"):
                continue
            else:
                keep.append(re.sub(r"<[^>]+>", "", s))
        return "\n".join(keep)
    if low.endswith((".html", ".htm", ".xhtml")):
        raw = html_text(raw)
    return raw


def html_text(raw):
    """HTML as the Markdown-like text the measures read: headings, list items and paragraphs kept apart."""
    raw = re.sub(r"(?is)<(script|style|noscript|head)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)<h([1-6])[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)) + " ", raw)
    raw = re.sub(r"(?i)<li[^>]*>", "\n- ", raw)
    raw = re.sub(r"(?i)</(p|div|h[1-6]|ul|ol|section|article|blockquote|tr|table)>", "\n\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(raw)


def tex_text(raw):
    raw = re.sub(r"(?m)(?<!\\)%.*$", "", raw)
    raw = re.sub(r"(?s)\\begin\{(equation|align|figure|table|tabular|verbatim)\*?\}.*?\\end\{\1\*?\}", "\n", raw)
    raw = re.sub(r"\$\$.*?\$\$|\$[^$]*\$", " ", raw, flags=re.S)
    raw = re.sub(r"\\(chapter|section)\*?\{([^}]*)\}", r"\n\n# \2\n\n", raw)
    raw = re.sub(r"\\(subsection|subsubsection|paragraph)\*?\{([^}]*)\}", r"\n\n## \2\n\n", raw)
    raw = re.sub(r"\\item\s*", "\n- ", raw)
    raw = re.sub(r"\\(begin|end)\{[^}]*\}", "\n", raw)
    raw = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{([^{}]*)\})?", lambda m: m.group(3) or " ", raw)
    return raw.replace("{", "").replace("}", "").replace("~", " ")


def email_text(path):
    import email
    from email import policy
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    body = part.get_content()
    return html_text(body) if part.get_content_type() == "text/html" else body


def clean_markdown(text):
    text = re.sub(r"(?s)```.*?```", "\n", text)  # code is not prose
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    return text


def language(text):
    th = len(THAI.findall(text))
    la = len(LATIN.findall(text))
    return "th" if th > 0.3 * max(1, th + la) else "en"


def blocks_of(text):
    out = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l.rstrip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue
        if all(re.match(r"^\s*#{1,6}\s", l) for l in lines):
            kind = "heading"
        elif all(re.match(r"^\s*([-*+•]|\d+[.)])\s", l) for l in lines):
            kind = "list"
        elif all(l.lstrip().startswith(">") for l in lines):
            kind = "quote"
        else:
            kind = "body"
        body = "\n".join(re.sub(r"^\s*(#{1,6}|[-*+•]|\d+[.)]|>)\s*", "", l) for l in lines)
        out.append({"kind": kind, "text": body})
    return out


def sentences_of(text, lang):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = TH_SPLIT.split(line) if lang == "th" else EN_SPLIT.split(line)
        out.extend(p.strip() for p in parts if p and p.strip())
    return out


def strip_end(s):
    return re.sub(r"[\s.!?…,\"'”’)\]~]+$", "", s)


def thai_end(s, words):
    tail = strip_end(s)
    # peel softening particles so "ไปไหนนะครับ" still reads as a question
    for _ in range(3):
        hit = next((w for w in TH_POLITE + TH_SOFT if tail.endswith(w)), None)
        if not hit:
            break
        tail = tail[: -len(hit)]
    return any(tail.endswith(w) for w in words)


def sentence_features(s, lang):
    tail = strip_end(s)
    words = [w.lower() for w in WORD.findall(s)]
    f = {
        "question": 1.0 if s.rstrip().endswith(("?", "？")) or (lang == "th" and thai_end(s, TH_QUESTION)) else 0.0,
        "exclaim": 1.0 if s.rstrip().endswith(("!", "！")) else 0.0,
        "digits": 1.0 if DIGIT.search(s) else 0.0,
        "emoji": float(len(EMOJI.findall(s))),
    }
    if lang == "th":
        chars = len(re.sub(r"\s", "", s))
        f["length"] = float(chars)
        f["polite"] = 1.0 if any(tail.endswith(w) for w in TH_POLITE) else 0.0
        f["soft"] = 1.0 if any(tail.endswith(w) for w in TH_SOFT) else 0.0
        f["first"] = 1.0 if TH_FIRST.search(s) else 0.0
        f["second"] = 1.0 if TH_SECOND.search(s) else 0.0
        latin = len(LATIN.findall(s))
        f["latin"] = latin / max(1, chars)
    else:
        f["length"] = float(len(words))
        f["first"] = 1.0 if any(w in EN_FIRST for w in words) else 0.0
        f["second"] = 1.0 if any(w in EN_SECOND for w in words) else 0.0
        f["commas"] = float(s.count(","))
        f["contractions"] = float(sum(1 for w in words if "'" in w))
        f["words"] = float(len(words))
        letters = [len(w) for w in words if w.isalpha()]
        f["word_length"] = sum(letters) / len(letters) if letters else None
    return f


def tokens_for_shingles(text, lang):
    if lang == "th":
        return [c for c in text.lower() if c.isalnum() or THAI.match(c)]
    return [w.lower() for w in WORD.findall(text)]


def shingle_size(lang):
    return 15 if lang == "th" else 8


def shingle_hashes(tokens, n):
    sep = "" if n >= 15 else " "
    out = []
    for i in range(len(tokens) - n + 1):
        key = sep.join(tokens[i:i + n])
        out.append(hashlib.blake2b(key.encode("utf-8"), digest_size=6).hexdigest())
    return out


def mattr(words, window=50):
    if len(words) < window:
        return len(set(words)) / len(words) if words else None
    vals = [len(set(words[i:i + window])) / window for i in range(0, len(words) - window + 1, 5)]
    return sum(vals) / len(vals)


def text_units(s, lang):
    """Length in the unit sentences use: words in English, characters without spaces in Thai."""
    return len(re.sub(r"\s", "", s)) if lang == "th" else len(WORD.findall(s))


def measure_text(path):
    return measure_string(read_text(path), path)


def measure_string(raw, path, lang=None):
    text = clean_markdown(raw)
    lang = lang or language(text)
    blocks = blocks_of(text)
    sents, para_rows = [], []
    for b in blocks:
        ss = sentences_of(b["text"], lang) if b["kind"] != "heading" else [b["text"].strip()]
        feats = [sentence_features(s, lang) for s in ss]
        for s, f in zip(ss, feats):
            if b["kind"] != "heading":
                sents.append((s, f))
        n = max(1, len(feats))
        para_rows.append({
            "kind": b["kind"],
            "row": [
                math.log1p(len(re.sub(r"\s", "", b["text"]))),
                float(len(ss)),
                sum(f["question"] for f in feats) / n,
                1.0 if b["kind"] == "list" else 0.0,
                1.0 if b["kind"] == "heading" else 0.0,
                sum(f["digits"] for f in feats) / n,
            ],
        })
    if len(sents) < 3:
        raise StyleError(f"{path}: only {len(sents)} sentences of prose; a text reference needs more to measure")

    values = {"sentence_length": [f["length"] for _, f in sents]}
    body = [b for b in blocks if b["kind"] == "body"]
    values["paragraph_sentences"] = [float(len(sentences_of(b["text"], lang))) for b in body]

    # rates per window of CHUNK sentences, so one reference still gives a spread
    chunks = [sents[i:i + CHUNK] for i in range(0, len(sents), CHUNK)]
    if len(chunks) > 1 and len(chunks[-1]) < CHUNK // 2:
        chunks[-2].extend(chunks.pop())

    def rate(key, per=None):
        out = []
        for c in chunks:
            fs = [f for _, f in c]
            if per:
                denom = sum(f[per] for f in fs)
                out.append(100.0 * sum(f[key] for f in fs) / denom if denom else 0.0)
            else:
                out.append(sum(f[key] for f in fs) / len(fs))
        return out

    values["question_rate"] = rate("question")
    values["exclaim_rate"] = rate("exclaim")
    values["digit_rate"] = rate("digits")
    values["emoji_rate"] = rate("emoji")
    values["first_person_rate"] = rate("first")
    values["second_person_rate"] = rate("second")
    if lang == "th":
        values["polite_end_rate"] = rate("polite")
        values["soft_end_rate"] = rate("soft")
        values["latin_mix"] = rate("latin")
    else:
        values["comma_rate"] = rate("commas")
        values["contraction_rate"] = rate("contractions", per="words")
        values["word_length"] = [f["word_length"] for _, f in sents if f.get("word_length")]
        words = [w.lower() for s, _ in sents for w in WORD.findall(s)]
        values["variety"] = [v for v in (mattr(words[i:i + 300]) for i in range(0, max(1, len(words) - 150), 300)) if v]
    groups = [blocks[i:i + 8] for i in range(0, len(blocks), 8)]
    values["list_share"] = [sum(b["kind"] == "list" for b in g) / len(g) for g in groups]
    values["heading_share"] = [sum(b["kind"] == "heading" for b in g) / len(g) for g in groups]

    toks = tokens_for_shingles(" ".join(b["text"] for b in blocks), lang)
    fp = {
        "lang": lang,
        "shingle_n": shingle_size(lang),
        "shingles": sorted(set(shingle_hashes(toks, shingle_size(lang)))),
        "seq": {"features": ["log_chars", "sentences", "question_share", "is_list", "is_heading", "digit_share"],
                "rows": [p["row"] for p in para_rows]},
    }
    info = {"lang": lang, "units": len(sents), "unit": "sentences", "blocks": len(blocks)}
    return info, values, fp, text


def verbatim(new_text, lang, ref_shingles, n):
    """Longest run of the new text that also appears in a reference, and the share of shingles shared."""
    toks = tokens_for_shingles(new_text, lang)
    hs = shingle_hashes(toks, n)
    ref = set(ref_shingles)
    hit = [h in ref for h in hs]
    longest, run = 0, 0
    for x in hit:
        run = run + 1 if x else 0
        longest = max(longest, run)
    span = longest + n - 1 if longest else 0
    share = sum(hit) / len(hit) if hit else 0.0
    return span, share
