"""Build a style card from measurements, lint it against the pattern firewall, render it, write briefs."""

import datetime
import math
import os
import re

from ss_common import MEDIA, SCHEMA_CARD, SCHEMA_FP, WORDED, WRITING, StyleError, summary
from ss_dims import BANDS3, DIMS, LANG_UNIT, MEDIUM_DIMS, TARGETS, axes_of, spec, translate

MEASURED_KEYS = {"label", "unit", "p10", "p50", "p90", "n", "refs", "confidence"}
INFO_KEYS = ("units", "unit", "seconds", "lang", "fps", "width", "height", "aspect", "audio", "pages")


def confidence(n, refs, single):
    if single:
        return "high" if refs >= 3 else "medium" if refs == 2 else "low"
    if n >= 30 and refs >= 2:
        return "high"
    return "medium" if n >= 10 else "low"


def build(measure_sets, name):
    """measure_sets: list of measures.json dicts. Returns (card, fingerprints)."""
    card = {"schema": SCHEMA_CARD, "name": name, "made": datetime.date.today().isoformat(), "references": [],
            "measured": {}, "lang": {}, "axes": {}, "traits": [], "avoid": [], "forbid": [], "notes": ""}
    fps = {"schema": SCHEMA_FP, "refs": []}
    pooled = {}
    count = 0
    for ms in measure_sets:
        medium = ms["medium"]
        for ref in ms["refs"]:
            count += 1
            rid = f"r{count}"
            info = {k: ref["info"][k] for k in INFO_KEYS if k in ref["info"]}
            card["references"].append({"id": rid, "medium": medium, "file": os.path.basename(ref["file"]), **info})
            fps["refs"].append({"id": rid, "medium": medium, "lang": ref["info"].get("lang"), "fp": ref["fp"]})
            if medium in WORDED:
                card["lang"].setdefault(medium, ref["info"].get("lang"))
                if medium in WRITING and ref["info"].get("lang") != card["lang"][medium]:
                    raise StyleError(f"{medium} references mix Thai and English; make one card per language")
            for dim, vals in ref["values"].items():
                pooled.setdefault(medium, {}).setdefault(dim, []).append(vals)
    for medium, dims in pooled.items():
        order = MEDIUM_DIMS.get(medium, [])
        keys = sorted(dims, key=lambda k: (order.index(k) if k in order else len(order) + (k.startswith("audio_")), k))
        out = {}
        for dim in keys:
            per_ref = dims[dim]
            flat = [v for vals in per_ref for v in vals]
            s = summary(flat)
            if not s:
                continue
            sp = spec(dim)
            unit = sp["unit"]
            if dim in LANG_UNIT:
                unit = "characters" if card["lang"].get(medium) == "th" else "words"
            single = all(len(v) == 1 for v in per_ref)
            out[dim] = {"label": sp["label"], "unit": unit, "p10": s["p10"], "p50": s["p50"], "p90": s["p90"],
                        "n": s["n"], "refs": len(per_ref), "confidence": confidence(s["n"], len(per_ref), single)}
        card["measured"][medium] = out
    card["axes"] = all_axes(card)
    return card, fps


def all_axes(card):
    out = {}
    for medium in MEDIA:
        m = card["measured"].get(medium)
        if not m:
            continue
        for axis, v in axes_of(m, card.get("lang", {}).get(medium)).items():
            if axis not in out:
                out[axis] = {**v, "medium": medium}
    return out


# ---------------------------------------------------------------- lint (the pattern firewall)
CLOCK = re.compile(r"(?<![\d.])\d{1,2}:\d{2}(?::\d{2})?(?![\d])")
AT_TIME = re.compile(r"\b(at|from|until|around)\s+\d+(\.\d+)?\s?(s|sec|secs|seconds)\b|\b\d+(\.\d+)?\s?(s|sec|seconds)\s+(in|into|mark)\b"
                     r"|วินาทีที่\s*\d+|นาทีที่\s*\d+", re.I)
UNITS_EN = r"(shot|scene|slide|section|paragraph|verse|chorus|bridge|bar|frame|line|chapter|image|page|beat|act|card|panel|sentence|post|clip)"
ORDINAL_EN = re.compile(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|opening|closing|final|last|"
                        r"penultimate|\d+(st|nd|rd|th))\s+" + UNITS_EN + r"s?\b|\b" + UNITS_EN + r"\s+(no\.?\s*)?\d+\b", re.I)
ORDINAL_TH = re.compile(r"(ช็อต|ช็อท|ช๊อต|ฉาก|สไลด์|ย่อหน้า|ท่อน|หน้า|ภาพ|บรรทัด|ประโยค|คัต|ซีน|พาร์ท)\s*(แรก|สุดท้าย|ที่\s*\d+)")
EDGE_EN = re.compile(r"\b(the\s+)?(film|video|clip|track|song|piece|post|essay|article|deck|page|story|trailer|ad|reel)\s+"
                     r"(opens|closes|starts|begins|ends|finishes)\b|^\s*(opens|closes|starts|begins|ends)\s+(with|on)\b", re.I)
EDGE_TH = re.compile(r"ตอนต้นเรื่อง|ตอนจบ|ตอนท้ายเรื่อง|ช่วงเปิดเรื่อง|ช่วงปิดท้าย|เปิดเรื่องด้วย|ปิดท้ายด้วย|จบด้วย")
QUOTE = re.compile(r"[\"“«「]([^\"”»」]{3,})[\"”»」]|‘([^’]{3,})’|(?:^|(?<=[\s(]))'([^']{3,})'(?=[\s.,;:!?)]|$)")


def text_fields(card):
    if card.get("name"):
        yield "name", str(card["name"])
    for i, r in enumerate(card.get("references", [])):
        if r.get("file"):
            yield f"references[{i}].file", str(r["file"])
    for i, t in enumerate(card.get("traits", [])):
        for key in ("dimension", "statement", "do"):
            if isinstance(t.get(key), str):
                yield f"traits[{i}].{key}", t[key]
    for i, a in enumerate(card.get("avoid", [])):
        if isinstance(a, str):
            yield f"avoid[{i}]", a
    if isinstance(card.get("notes"), str) and card["notes"]:
        yield "notes", card["notes"]


def validate(card, where="card"):
    """Structure check for a card written or edited by hand; raises StyleError (exit 2) instead of a traceback."""
    def bad(msg):
        raise StyleError(f"{where}: {msg} (see references/card.md)")
    if not isinstance(card, dict):
        bad("a card is a JSON object")
    if not isinstance(card.get("name", ""), str) or not str(card.get("name", "")).strip():
        bad("name must be a non-empty string")
    for key, kind in (("references", dict), ("traits", dict), ("avoid", str), ("forbid", str)):
        items = card.get(key, [])
        if not isinstance(items, list) or not all(isinstance(x, kind) for x in items):
            bad(f"{key} must be a list of {'objects' if kind is dict else 'strings'}")
    for i, t in enumerate(card.get("traits", [])):
        if not isinstance(t.get("evidence", {}), dict):
            bad(f"traits[{i}].evidence must be an object with refs and count")
    for key in ("measured", "axes", "lang"):
        if not isinstance(card.get(key, {}), dict):
            bad(f"{key} must be an object")
    for medium, dims in card.get("measured", {}).items():
        if not isinstance(dims, dict) or not all(isinstance(m, dict) for m in dims.values()):
            bad(f"measured.{medium} must map dimensions to objects")
        for dim, m in dims.items():
            if (dim[6:] if dim.startswith("audio_") else dim) not in DIMS:
                bad(f"measured.{medium}.{dim} is not a dimension style.py knows; describe it in a trait instead")
            if not all(isinstance(m.get(k), (int, float)) for k in ("p10", "p50", "p90")):
                bad(f"measured.{medium}.{dim} needs numeric p10, p50 and p90")
    for axis, v in card.get("axes", {}).items():
        if axis not in BANDS3 or not isinstance(v, dict) or v.get("band") not in BANDS3[axis]:
            bad(f"axes.{axis}: unknown axis or band; axes and bands are listed in references/translate.md")
    if not isinstance(card.get("notes", ""), str):
        bad("notes must be a string")
    card.setdefault("references", [])
    card.setdefault("measured", {})
    return card


def lint(card, fingerprints=None):
    from ss_text import shingle_hashes, tokens_for_shingles

    errors, warnings = [], []
    if card.get("schema") != SCHEMA_CARD:
        errors.append(f"schema must be {SCHEMA_CARD!r}")
    for r in card.get("references", []):
        f = str(r.get("file", ""))
        if "/" in f or "\\" in f:
            errors.append(f"references {r.get('id')}: file must be a bare file name, not a path ({f})")
    for medium, dims in (card.get("measured") or {}).items():
        for dim, m in dims.items():
            extra = set(m) - MEASURED_KEYS
            if extra:
                errors.append(f"measured.{medium}.{dim}: unexpected keys {sorted(extra)}; a card keeps ranges, not sequences")
            if any(isinstance(v, (list, dict)) for v in m.values()):
                errors.append(f"measured.{medium}.{dim}: holds a list; per-unit sequences are pattern and stay in fingerprints.json")
    for axis, v in (card.get("axes") or {}).items():
        if axis not in BANDS3:
            errors.append(f"axes.{axis}: unknown axis; use one of {', '.join(BANDS3)}")
        elif not isinstance(v, dict) or v.get("band") not in BANDS3[axis]:
            errors.append(f"axes.{axis}: band must be one of {', '.join(BANDS3[axis])}")
    for i, t in enumerate(card.get("traits", [])):
        where = f"traits[{i}]"
        if not str(t.get("statement", "")).strip():
            errors.append(f"{where}: statement is empty")
        if not str(t.get("dimension", "")).strip():
            errors.append(f"{where}: dimension is empty")
        ev = t.get("evidence") or {}
        cnt, refs = ev.get("count", 0), ev.get("refs", 0)
        if not isinstance(cnt, (int, float)) or cnt < 3:
            errors.append(f"{where}: evidence.count {cnt!r} under 3; something seen once or twice is a set piece (pattern): "
                          "move it to pattern.md")
        if not isinstance(refs, (int, float)) or refs < 1:
            errors.append(f"{where}: evidence.refs must be 1 or more")
        if t.get("confidence") not in ("high", "medium", "low"):
            errors.append(f"{where}: confidence must be high, medium or low")
    forbid = [f.strip() for f in card.get("forbid", []) if isinstance(f, str) and f.strip()]
    lang = (card.get("lang") or {}).get("text")
    ref_sh = {}
    for r in (fingerprints or {}).get("refs", []):
        if r["fp"].get("shingles"):  # text, and the words of slides, documents and sheets
            ref_sh.setdefault(r.get("lang") or "en", set()).update(r["fp"]["shingles"])
    for where, text in text_fields(card):
        if CLOCK.search(text) or AT_TIME.search(text):
            errors.append(f"{where}: names a time in the reference; a style is a rate or a habit, not a timestamp")
        m = ORDINAL_EN.search(text) or ORDINAL_TH.search(text)
        if m:
            errors.append(f"{where}: names a position ({m.group(0)!r}); positions are pattern")
        m = EDGE_EN.search(text) or EDGE_TH.search(text)
        if m:
            warnings.append(f"{where}: describes how the work opens or ends ({m.group(0)!r}); keep it only if every reference does it")
        for name in forbid:
            if name.lower() in text.lower():
                errors.append(f"{where}: contains the forbidden name {name!r}")
        for q in ("".join(g) for g in QUOTE.findall(text)):
            words = len(q.split())
            thai = len(re.findall(r"[฀-๿]", q))
            if words > 5 or thai > 20:
                errors.append(f"{where}: quotes {q[:40]!r}...; quote at most 5 words (20 Thai characters) of a reference")
        for lg, shingles in ref_sh.items():
            n = 15 if lg == "th" else 8
            hs = shingle_hashes(tokens_for_shingles(text, lg), n)
            if any(h in shingles for h in hs):
                errors.append(f"{where}: repeats a run of the reference's own text")
                break
    if not card.get("traits"):
        warnings.append("no traits yet: add habits seen across the references (camera, framing, type, voice, sound); see references/card.md")
    if not forbid:
        warnings.append("forbid is empty: list the reference's brand, product, title and character names")
    return errors, warnings


# ---------------------------------------------------------------- rendering
def fmt(v):
    if v is None:
        return "-"
    a = abs(v)
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.1f}"
    if a >= 1:
        return f"{v:.2f}"
    return f"{v:.3f}"


def render(card):
    out = [f"# Style card: {card['name']}", "",
           "Hand this card to whoever makes the new work. It holds the reference's style as ranges and habits.",
           "It holds no order, no timestamps and no material from the reference, and it must not gain any.", ""]
    refs = card.get("references", [])
    kinds = sorted({r["medium"] for r in refs})
    out += [f"Learned from {len(refs)} reference(s): {', '.join(kinds)}. Made {card.get('made', '')}.", ""]
    if card.get("axes"):
        out += ["## Axes", "", "Coarse bands that carry the style into any medium.", ""]
        for axis, v in card["axes"].items():
            src = f"from {v.get('medium', '?')} {v['from']} = {fmt(v.get('value'))}" if v.get("from") else "judged by hand"
            out.append(f"- **{axis}**: {v['band']} ({src})")
        out.append("")
    for medium, dims in card.get("measured", {}).items():
        out += [f"## Measured: {medium}", "", "| Dimension | Typical range (p10-p90) | Median | Unit | Confidence |", "|---|---|---|---|---|"]
        for dim, m in dims.items():
            out.append(f"| {m.get('label', dim)} | {fmt(m['p10'])} - {fmt(m['p90'])} | {fmt(m['p50'])} | {m.get('unit', '')} | "
                       f"{m.get('confidence', '?')} (n={m.get('n', '?')}) |")
        out.append("")
    out += ["## Habits", ""]
    if card.get("traits"):
        for t in card["traits"]:
            line = f"- **{t.get('dimension', '?')}**: {t.get('statement', '')}"
            if t.get("do"):
                line += f" Do: {t['do']}"
            line += f" ({t.get('confidence', '?')}, seen {t.get('evidence', {}).get('count', '?')}x)"
            out.append(line)
    else:
        out.append("- (none written yet)")
    out.append("")
    if card.get("avoid"):
        out += ["## Never in this style", ""] + [f"- {a}" for a in card["avoid"]] + [""]
    if card.get("forbid"):
        out += ["## Names that must not appear", ""] + [f"- {f}" for f in card["forbid"]] + [""]
    out += ["## Firewall", "",
            "Never take the reference's order of shots, sections or ideas, its opening or closing images, its set pieces,",
            "its copy, its music, its footage or its exact colours. Build those from your own subject.", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- briefs
def freedoms(card, medium):
    """The two dimensions with the widest relative ranges: where the new work has the most room."""
    dims = card.get("measured", {}).get(medium, {})
    scored = []
    for dim, m in dims.items():
        lo, hi = m["p10"], m["p90"]
        if spec(dim)["scale"] == "log" and lo > 0:
            w = math.log10(hi / lo)
        else:
            w = (hi - lo) / (abs(m["p50"]) + 1e-6)
        scored.append((w, dim))
    return [d for _, d in sorted(scored, reverse=True)[:2]]


NOUNS = {"video": "video", "audio": "piece of audio", "text": "piece of writing", "image": "image or image set",
         "slides": "slide deck", "document": "document", "sheet": "spreadsheet", "ui": "interface", "any": "work"}


def article(noun):
    return "an" if noun[0] in "aeiou" else "a"


def brief(card, target, subject=None):
    if target not in TARGETS:
        raise StyleError(f"--for must be one of {', '.join(TARGETS)}")
    same = target in card.get("measured", {})
    noun = NOUNS[target]
    out = [f"# Design brief: a new {noun} in the style '{card['name']}'", "",
           "This brief is for making new, original work. The style card says how the reference behaves; the",
           "content, structure and every concrete choice come from the subject below.", "",
           "## 1. Subject", "", subject or "(write the subject: what is being made, for whom, and the one thing it must say or do)", "",
           "## 2. Concept (write this before anything else)", "",
           "- The one idea, in a sentence, taken from the subject, not from the reference.",
           "- Your own structure: list the parts in the order this subject needs. Do not look at the reference's order.",
           "- One element the reference never had (a material, a motif, a viewpoint). This is what makes it a sibling, not a copy.", "",
           "## 3. Style targets", ""]
    if same:
        out += [f"Measured on the reference ({target}). Aim inside these ranges:", ""]
        for dim, m in card["measured"][target].items():
            out.append(f"- {m.get('label', dim)}: {fmt(m['p10'])} - {fmt(m['p90'])} {m.get('unit', '')} (median {fmt(m['p50'])})")
        out.append("")
    if card.get("axes"):
        if same:
            verb = "Also carry these axes"
        elif target == "any":
            verb = "Carry the reference's axes into whatever medium this is"
        else:
            verb = f"The reference was not {article(noun)} {noun}; carry its axes over"
        out += [f"{verb}. The numbers are starting points (rules of thumb, not measurements):", ""]
        for axis, v in card["axes"].items():
            hint = translate(axis, v["band"], target)
            if hint:
                out.append(f"- **{axis}: {v['band']}**: {hint}")
        out.append("")
    out += ["## 4. Habits to keep", ""]
    seen_in = sorted({r["medium"] for r in card.get("references", [])})
    if card.get("traits") and seen_in and target not in seen_in:
        out += [f"These were seen in {' and '.join(seen_in)}. Carry each one over by what it does, not by its literal",
                "form (a slow sideways camera becomes slow sideways movement of elements), and drop any that has no",
                f"counterpart in {article(noun)} {noun}.", ""]
    if card.get("traits"):
        for t in card["traits"]:
            out.append(f"- {t.get('do') or t.get('statement', '')}")
    else:
        out.append("- (the card has no habits yet; add traits to the card first, then rewrite this brief)")
    out += ["", "## 5. Never", ""]
    for a in card.get("avoid", []):
        out.append(f"- {a}")
    for f in card.get("forbid", []):
        out.append(f"- Do not use the name, logo or look of: {f}")
    out += ["- Do not rebuild the reference's order, opening, ending, set pieces or copy.",
            "- Do not reuse its footage, images, music, text or exact colours; build your own palette with the card's character.", "",
            "## 6. Make it yours", ""]
    if same:
        fr = freedoms(card, target)
        if fr:
            labels = [card["measured"][target][d].get("label", d).lower() for d in fr]
            out.append(f"- The style has the most room in {' and '.join(labels)}: push one of them to an edge of its range on purpose.")
    out += ["- Keep the habits; vary everything the habits do not mention.", "",
            "## 7. Check before handing it over", ""]
    if target in MEDIA:
        extra = " --medium slides" if target == "slides" else ""
        out += ["```sh", f"python3 scripts/style.py check NEW_WORK --card style.json --fingerprints fingerprints.json{extra}", "```", ""]
        if target == "slides":
            out += ["`--medium slides` matters only for a deck exported to PDF, which is otherwise read as a document.", ""]
        out += ["The check passes only when the style is close enough and the pattern is far enough. Show the result to the person;",
                "the measurements do not replace their eyes and ears."]
    else:
        out += [f"There is no measuring route for {target}: review the work against sections 3-5 by eye, and confirm with the",
                "person that no part follows the reference's order or reuses its material. If the work exports to video,",
                "images, audio or text (a screen recording, slide images, its copy), run `style.py check` on the export too."]
    out.append("")
    return "\n".join(out)
