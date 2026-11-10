"""The two-sided check: is the new work close enough in style, and far enough in pattern?"""

import math

from ss_common import StyleError, summary
from ss_dims import BANDS3, axes_of, spec
import ss_pattern as pat

LANG_DIMS = {"sentence_length", "polite_end_rate", "soft_end_rate", "latin_mix", "comma_rate", "contraction_rate",
             "word_length", "variety"}
STYLE_SHARE = 0.75


def compare_dim(dim, m, value):
    sp = spec(dim)
    lo, hi, tol = m["p10"], m["p90"], sp["tol"]
    if sp["scale"] == "log":
        v, a, b = (math.log10(max(x, 1e-9)) for x in (value, lo, hi))
        a, b = a - tol, b + tol
        off = (v - b) if v > b else (a - v) if v < a else 0.0
        ok = off == 0.0
        side = "high" if v > b else "low" if v < a else ""
    else:
        slack = max(tol, 0.1 * (hi - lo))
        ok = lo - slack <= value <= hi + slack
        side = "high" if value > hi + slack else "low" if value < lo - slack else ""
    return {"dim": dim, "label": sp["label"], "core": sp["core"], "new": value, "p10": lo, "p90": hi,
            "unit": sp["unit"], "ok": ok, "side": side}


def style_side(card, medium, values, lang):
    measured = card.get("measured", {}).get(medium)
    if measured:
        card_lang = card.get("lang", {}).get("text")
        rows, skipped = [], []
        for dim, m in measured.items():
            if dim not in values:
                skipped.append(dim)
                continue
            if medium == "text" and lang != card_lang and dim in LANG_DIMS:
                skipped.append(dim)
                continue
            s = summary(values[dim])
            if s:
                rows.append(compare_dim(dim, m, s["p50"]))
        if not rows:
            raise StyleError("no measured dimension in common between the card and the new work")
        share = sum(r["ok"] for r in rows) / len(rows)
        core_off = [r for r in rows if r["core"] and not r["ok"]]
        return {"mode": "measured", "rows": rows, "skipped": skipped, "share": share,
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


def pattern_side(card, fingerprints, medium, new_fp, new_text=None, lang=None):
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
        if medium in ("video", "image") and r["medium"] in ("video", "image"):
            d = pat.duplicate_frames(rfp.get("dhash", []), new_fp.get("dhash", []), single=medium == "image",
                                     ref_thumbs=rfp.get("thumbs"), new_thumbs=new_fp.get("thumbs"))
            if d["alarm"]:
                findings.append(f"{rid}: {d['matched']} of {d['of']} frames or images are near-duplicates of the reference's")
            if rfp.get("palette") and new_fp.get("palette"):
                pm = pat.palette_match(rfp["palette"], new_fp["palette"])
                if pm["warn"]:
                    warnings.append(f"{rid}: uses the reference's chromatic colour set (worst delta E {pm['worst_delta_e']:.1f}); "
                                    "fine for a look, not for a brand")
        ra = rfp if r["medium"] == "audio" else rfp.get("audio")
        na = new_fp if medium == "audio" else new_fp.get("audio")
        if ra and na:
            a = pat.audio_reuse(ra, na)
            if a.get("stale"):
                gaps.append(f"{rid}: audio not compared; these fingerprints come from an older style-study, "
                            "run `style.py card` again")
            elif a["alarm"]:
                findings.append(f"{rid}: {a['run']} s of audio match the reference's audio second for second")
        if medium == "text" and r["medium"] == "text" and new_text is not None:
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
                      + ("" if style["ok"] else "; a core dimension is off or under 75% are in range"))
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
