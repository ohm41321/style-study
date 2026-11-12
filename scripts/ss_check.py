"""The two-sided check: is the new work close enough in style, and far enough in pattern?"""

from ss_common import WORDED, WRITING, StyleError, summary
from ss_dims import BANDS3, accept_range, axes_of, spec
import ss_pattern as pat

LANG_DIMS = {"sentence_length", "polite_end_rate", "soft_end_rate", "latin_mix", "comma_rate", "contraction_rate",
             "word_length", "variety", "slide_text", "title_length", "page_text", "label_length"}
DOCS = ("slides", "document", "sheet")
# a card with no block for this medium is compared with its nearest written medium: prose is prose in a .md or a .docx
NEAREST = {"document": "text", "text": "document"}
STYLE_SHARE = 0.75


def compare_dim(dim, m, value):
    sp = spec(dim)
    lo, hi = m["p10"], m["p90"]
    a, b = accept_range(dim, m)
    v = max(value, 1e-9) if sp["scale"] == "log" else value
    side = "high" if v > b else "low" if v < a else ""
    ok = not side
    return {"dim": dim, "label": sp["label"], "core": sp["core"], "new": value, "p10": lo, "p90": hi,
            "unit": sp["unit"], "ok": ok, "side": side}


def style_side(card, medium, values, lang):
    source = medium
    if not card.get("measured", {}).get(medium) and card.get("measured", {}).get(NEAREST.get(medium)):
        source = NEAREST[medium]
    measured = card.get("measured", {}).get(source)
    if measured:
        card_lang = card.get("lang", {}).get(source)
        rows, skipped = [], []
        for dim, m in measured.items():
            if dim not in values:
                skipped.append(dim)
                continue
            if source in WORDED and lang != card_lang and dim in LANG_DIMS:
                skipped.append(dim)
                continue
            s = summary(values[dim])
            if s:
                rows.append(compare_dim(dim, m, s["p50"]))
        if not rows:
            raise StyleError("no measured dimension in common between the card and the new work")
        share = sum(r["ok"] for r in rows) / len(rows)
        core_off = [r for r in rows if r["core"] and not r["ok"]]
        return {"mode": "measured", "medium": medium, "source": source, "rows": rows, "skipped": skipped, "share": share,
                "ok": share >= STYLE_SHARE and not core_off}
    # translated: the card was learned from another medium; compare axis bands
    new_measured = {d: {**summary(v), "label": d} for d, v in values.items() if summary(v)}
    new_axes = axes_of(new_measured, lang)
    rows = []
    for axis, v in card.get("axes", {}).items():
        if axis not in new_axes:
            continue
        names = BANDS3[axis]
        dist = abs(names.index(v["band"]) - names.index(new_axes[axis]["band"]))
        rows.append({"axis": axis, "card": v["band"], "new": new_axes[axis]["band"], "ok": dist <= 1, "same": dist == 0})
    if not rows:
        raise StyleError(f"the card has no {medium} measurements and no axis this {medium} can be compared on")
    same = sum(r["same"] for r in rows) / len(rows)
    return {"mode": "translated", "rows": rows, "share": same, "ok": all(r["ok"] for r in rows) and same >= 0.5}


def pattern_side(card, fingerprints, medium, new_fp, new_text=None, lang=None, own_palette=False):
    from ss_text import verbatim

    findings, warnings, gaps = [], [], []
    refs = [r for r in (fingerprints or {}).get("refs", [])]
    for r in refs:
        rid, rfp = r["id"], r["fp"]
        same_medium = r["medium"] == medium
        if same_medium and "seq" in rfp and "seq" in new_fp:
            o = pat.order_test(rfp["seq"], new_fp["seq"])
            if o is None:
                warnings.append(f"{rid}: too few units on one side to test the order")
            elif o["alarm"]:
                findings.append(f"{rid}: follows the reference's order (r={o['r']:.2f}, p={o['p']:.3f}); build your own structure")
        elif r["medium"] in WRITING and medium in WRITING:
            # Markdown against Word, a PDF against a deck: compare the paragraphs the text route sees on both sides
            rs, ns = writing_seq(r["medium"], rfp), writing_seq(medium, new_fp)
            if rs is None or ns is None:
                gaps.append(f"{rid}: order not compared between {r['medium']} and {medium}; "
                            "these fingerprints come from an older style-study, run `style.py card` again")
            else:
                o = pat.order_test(rs, ns)
                if o is None:
                    warnings.append(f"{rid}: too few paragraphs on one side to test the order")
                elif o["alarm"]:
                    findings.append(f"{rid}: follows the reference's order of paragraphs (r={o['r']:.2f}, p={o['p']:.3f}); "
                                    "build your own structure")
        if medium in ("video", "image") and r["medium"] in ("video", "image"):
            d = pat.duplicate_frames(rfp.get("dhash", []), new_fp.get("dhash", []), single=medium == "image",
                                     ref_thumbs=rfp.get("thumbs"), new_thumbs=new_fp.get("thumbs"))
            if d["alarm"]:
                findings.append(f"{rid}: {d['matched']} of {d['of']} frames or images are near-duplicates of the reference's")
            palette(rid, rfp, new_fp, own_palette, findings, warnings)
        ra = rfp if r["medium"] == "audio" else rfp.get("audio")
        na = new_fp if medium == "audio" else new_fp.get("audio")
        if ra and na:
            a = pat.audio_reuse(ra, na)
            if a.get("stale"):
                gaps.append(f"{rid}: audio not compared; these fingerprints come from an older style-study, "
                            "run `style.py card` again")
            elif a["alarm"]:
                findings.append(f"{rid}: {a['run']} s of audio match the reference's audio second for second")
        if medium in DOCS or r["medium"] in DOCS:
            media_reuse(rid, r["medium"], rfp, medium, new_fp, findings, warnings, own_palette)
        if medium in WORDED and r["medium"] in WORDED and new_text is not None and rfp.get("shingles"):
            # in the reference's language, whatever the draft's: Thai pasted into English text still counts
            rl = r.get("lang") or "en"
            span, share = verbatim(new_text, rl, rfp.get("shingles", []), rfp.get("shingle_n", 15 if rl == "th" else 8))
            unit = "characters" if rl == "th" else "words"
            if span >= pat.TEXT_SPAN.get(rl, 12) or share >= pat.TEXT_SHARE:
                findings.append(f"{rid}: shares a run of {span} {unit} with the reference ({share:.0%} of the new text's shingles)")
    if new_text is not None:
        low = new_text.lower()
        for name in card.get("forbid", []):
            if name and name.lower() in low:
                findings.append(f"uses the forbidden name {name!r}")
    return {"ok": not findings and not gaps, "findings": findings, "warnings": warnings, "gaps": gaps}


def writing_seq(medium, fp):
    """The paragraph sequence of a written medium: a text fingerprint's own, or the one a document or deck keeps."""
    return fp.get("seq") if medium == "text" else fp.get("text_seq")


def _pictures(medium, fp):
    """(dHashes, layouts) of a fingerprint's pictures: frames and images, or the pictures inside a document."""
    if medium in ("video", "image"):
        return fp.get("dhash"), fp.get("thumbs")
    return fp.get("media_dhash"), fp.get("media_thumbs")


def palette(rid, rfp, new_fp, own_palette, findings, warnings):
    """The reference's exact colour set is its material, like its footage: a copy, unless the colours are the person's own."""
    if not (rfp.get("palette") and new_fp.get("palette")):
        return
    pm = pat.palette_match(rfp["palette"], new_fp["palette"])
    if not pm["warn"]:
        return
    if own_palette:
        warnings.append(f"{rid}: uses the reference's chromatic colour set (worst delta E {pm['worst_delta_e']:.1f}); "
                        "allowed by --own-palette because the colours are the person's own")
    else:
        findings.append(f"{rid}: uses the reference's chromatic colour set (worst delta E {pm['worst_delta_e']:.1f}); "
                        "build a palette from the subject (pass --own-palette only when these colours are the person's own brand)")


def media_reuse(rid, ref_medium, rfp, medium, new_fp, findings, warnings, own_palette=False):
    """Pictures a document, deck or sheet shares with a reference: the same bytes, or the same picture re-saved."""
    same = sorted(set(rfp.get("media") or []) & set(new_fp.get("media") or []))
    if same:
        findings.append(f"{rid}: {len(same)} picture(s) are the reference's own files, byte for byte")
    rh, rt = _pictures(ref_medium, rfp)
    nh, nt = _pictures(medium, new_fp)
    if rh and nh:
        d = pat.duplicate_frames(rh, nh, single=True, ref_thumbs=rt, new_thumbs=nt)
        if d["alarm"] and not same:
            findings.append(f"{rid}: {d['matched']} of {d['of']} pictures look like the reference's pictures")
    elif (rh is None and rfp.get("media")) or (nh is None and new_fp.get("media")):
        warnings.append(f"{rid}: pictures compared by their bytes only; with numpy and ffmpeg installed, a re-saved or "
                        "resized copy is caught too")
    if ref_medium == medium:
        palette(rid, rfp, new_fp, own_palette, findings, warnings)


def _shown(x):
    """The value as the report prints it (3 significant digits), so a note never contradicts the numbers."""
    return float(f"{x:.3g}")


def report_lines(style, pattern):
    out = []
    if style["mode"] == "measured":
        for r in style["rows"]:
            mark = "ok " if r["ok"] else "OFF"
            if r["side"]:
                note = f" (too {r['side']})"
            elif not _shown(r["p10"]) <= _shown(r["new"]) <= _shown(r["p90"]):
                note = " (just outside, within the tolerance)"
            else:
                note = ""
            core = " [core]" if r["core"] else ""
            out.append(f"  {mark} {r['label']}{core}: {r['new']:.3g} against {r['p10']:.3g} to {r['p90']:.3g} "
                       f"{r['unit']}{note}")
        if style.get("skipped"):
            out.append(f"  (not compared: {', '.join(style['skipped'])})")
        out.insert(0, f"STYLE {'PASS' if style['ok'] else 'FAIL'}: {style['share']:.0%} of dimensions in range"
                      + ("" if style["ok"] else "; a core dimension is off or under 75% are in range")
                      + (f" (against the card's {style['source']} measurements)" if style.get("source") not in (None, style.get("medium")) else ""))
    else:
        out.append(f"STYLE {'PASS' if style['ok'] else 'FAIL'} (translated across media): {style['share']:.0%} of axes in the same band")
        for r in style["rows"]:
            out.append(f"  {'ok ' if r['ok'] else 'OFF'} {r['axis']}: card {r['card']}, new {r['new']}")
    if not pattern.get("ran", True):
        out.append("PATTERN NOT RUN: pass --fingerprints fingerprints.json; until then this work is not checked for copying")
    elif pattern["ok"]:
        out.append("PATTERN PASS: nothing taken from the reference's order or material")
    elif pattern["findings"]:
        out.append("PATTERN FAIL: copied pattern found")
    else:
        out.append("PATTERN INCOMPLETE: part of the copy check could not run, so this work is not cleared")
    out += [f"  COPY {f}" for f in pattern["findings"]]
    out += [f"  NOT CHECKED {g}" for g in pattern.get("gaps", [])]
    out += [f"  warn {w}" for w in pattern["warnings"]]
    return out
