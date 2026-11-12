#!/usr/bin/env python3
"""style-study: learn a reference's style, never its pattern, and design new work from it.

  measure FILE...            measure references (one medium per call: video, image, audio, text, slides,
                             document or sheet)
  card MEASURES...           pool measurements into style.json (ranges, axes) + fingerprints.json (copy check data)
  lint CARD                  the pattern firewall: timestamps, positions, quotes, names, thin evidence, exact
                             values, habits that restate a device from pattern.md (--pattern)
  render CARD                write the card as Markdown for the person studying and the checker
  brief CARD --for TARGET    a design brief for a new, original work in any target medium (the maker's only file)
  check NEW... --card CARD   two-sided: style close enough, pattern far enough
  review PATTERN NEW...      the prompt for an independent imitation review of new work against pattern.md
  sheet VIDEO                contact sheet (one frame per shot) to read habits from

The text, slides, document and sheet routes need only Python 3.9+ (PDF also needs pypdf or poppler; older
and Apple formats need LibreOffice). Video, image and audio need numpy and ffmpeg.
Exit codes: 0 ok, 1 check or lint failed (or the pattern side could not run), 2 usage or input problem.
"""

import argparse
import os
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ss_common import MEDIA, SCHEMA_FP, StyleError, kind_of, load_json, media_in, run, save_json  # noqa: E402


def group(files, medium=None):
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise StyleError(f"not found: {', '.join(missing)}")
    kinds = {f: (medium or kind_of(f)) for f in files}
    unknown = [f for f, k in kinds.items() if k is None]
    if unknown:
        raise StyleError(f"unknown file type: {', '.join(unknown)} (pass --medium {'|'.join(MEDIA)})")
    found = set(kinds.values())
    if len(found) > 1:
        raise StyleError(f"one medium per call, got {sorted(found)}; measure each medium separately and pass all "
                         "measures files to `card`")
    return found.pop()


def measure_files(files, medium, max_seconds):
    refs = []
    if medium == "text":
        import ss_text
        for f in files:
            info, values, fp, _ = ss_text.measure_text(f)
            refs.append({"file": os.path.basename(f), "info": info, "values": values, "fp": fp})
    elif medium in ("slides", "document", "sheet"):
        import ss_docs
        for f in files:
            info, values, fp, text = ss_docs.measure(f, medium)
            refs.append({"file": os.path.basename(f), "info": info, "values": values, "fp": fp, "_text": text})
    elif medium == "image":
        import ss_media
        info, values, fp = ss_media.measure_images(files)
        name = os.path.basename(files[0]) + (f" (+{len(files) - 1} more)" if len(files) > 1 else "")
        refs.append({"file": name, "info": info, "values": values, "fp": fp})
    else:
        import ss_media
        fn = ss_media.measure_video if medium == "video" else ss_media.measure_audio
        for f in files:
            info, values, fp = fn(f, max_seconds)
            refs.append({"file": os.path.basename(f), "info": info, "values": values, "fp": fp})
    return {"schema": "style-study/measures-1", "medium": medium, "refs": refs}


def cmd_measure(a):
    medium = group(a.files, a.medium)
    ms = measure_files(a.files, medium, a.max_seconds)
    if a.work:
        for r in ms["refs"]:
            r["info"]["work"] = a.work
    for r in ms["refs"]:
        r.pop("_text", None)  # the words stay out of measures.json; only their hashes are kept
    save_json(ms, a.out)
    if a.out not in (None, "-"):
        for r in ms["refs"]:
            i = r["info"]
            print(f"measured {r['file']}: {i.get('units')} {i.get('unit')}" + (f", {i['seconds']:.1f} s" if i.get("seconds") else "")
                  + (f", language {i['lang']}" if i.get("lang") else ""))
        print(f"wrote {a.out}")
    return 0


def cmd_card(a):
    import ss_card
    sets = [load_json(p) for p in a.measures]
    for p, s in zip(a.measures, sets):
        if s.get("schema") != "style-study/measures-1":
            raise StyleError(f"{p}: not a measures file from `style.py measure`")
    card, fps = ss_card.build(sets, a.name or os.path.splitext(os.path.basename(a.out))[0])
    save_json(card, a.out)
    save_json(fps, a.fingerprints)
    axes = ", ".join(k + " " + v["band"] for k, v in card["axes"].items()) or "none"
    dims = sum(len(d) for d in card["measured"].values())
    print(f"wrote {a.out} ({dims} measured dimensions, axes: {axes})")
    print(f"wrote {a.fingerprints} (copy-check data: keep it away from whoever makes the new work)")
    print("next: add traits, avoid and forbid by hand (references/card.md), then run `style.py lint`")
    return 0


def cmd_lint(a):
    import ss_card
    card = ss_card.validate(load_json(a.card), a.card)
    fps = load_json(a.fingerprints) if a.fingerprints else None
    items = None
    if a.pattern:
        if not os.path.isfile(a.pattern):
            raise StyleError(f"not found: {a.pattern}")
        with open(a.pattern, encoding="utf-8-sig") as f:
            text = f.read()
        items = ss_card.pattern_items(text)
    errors, warnings = ss_card.lint(card, fps, items)
    if items is not None and not ss_card.pattern_signatures(text):
        errors.append(f"{a.pattern} has no Signatures section: under a heading named Signatures, list the devices that make "
                      "the reference recognisable (a component, a placement, a treatment, a format, a motif), one bullet each")
    if items is None:
        warnings.append("no --pattern: the habits were not checked against the reference's devices in pattern.md")
    for e in errors:
        print(f"FAIL {e}")
    for w in warnings:
        print(f"warn {w}")
    print(f"lint: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def cmd_render(a):
    import ss_card
    text = ss_card.render(ss_card.validate(load_json(a.card), a.card))
    return write_text(text, a.out)


def cmd_brief(a):
    import ss_card
    text = ss_card.brief(ss_card.validate(load_json(a.card), a.card), a.target, a.subject)
    return write_text(text, a.out)


def write_text(text, out):
    if out in (None, "-"):
        sys.stdout.write(text)
    else:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {out}")
    return 0


def cmd_check(a):
    import ss_card
    import ss_check
    card = ss_card.validate(load_json(a.card), a.card)
    fps = None
    if a.fingerprints:
        fps = load_json(a.fingerprints)
        if not isinstance(fps, dict) or fps.get("schema") != SCHEMA_FP or not isinstance(fps.get("refs"), list):
            raise StyleError(f"{a.fingerprints}: not a fingerprints file from `style.py card` (schema {SCHEMA_FP})")
    medium = group(a.files, a.medium)
    ms = measure_files(a.files, medium, a.max_seconds)
    pooled = {}
    for r in ms["refs"]:
        for k, v in r["values"].items():
            pooled.setdefault(k, []).extend(v)
    lang = ms["refs"][0]["info"].get("lang")
    style = ss_check.style_side(card, medium, pooled, lang)
    # one measured ref per file for text, video and audio; one for the whole set of images
    names = a.files if medium != "image" else [ms["refs"][0]["file"]]
    texts = [None] * len(names)
    if medium == "text":
        import ss_text
        texts = [ss_text.clean_markdown(ss_text.read_text(f)) for f in a.files]
    elif medium in ("slides", "document", "sheet"):
        texts = [r["_text"] for r in ms["refs"]]
    findings, warnings, gaps = [], [], []
    for name, r, text in zip(names, ms["refs"], texts):
        p = ss_check.pattern_side(card, fps, medium, r["fp"], text, r["info"].get("lang"), a.own_palette)
        tag = f"{name}: " if len(names) > 1 else ""
        findings += [tag + x for x in p["findings"]]
        warnings += [tag + x for x in p["warnings"]]
        gaps += [tag + x for x in p["gaps"]]
    ran = bool(fps and fps["refs"])
    pattern = {"ok": ran and not findings and not gaps, "ran": ran, "findings": findings,
               "warnings": sorted(set(warnings)), "gaps": sorted(set(gaps))}
    for line in ss_check.report_lines(style, pattern):
        print(line)
    ok = style["ok"] and pattern["ok"]
    print(f"check: {'PASS' if ok else 'FAIL'}")
    if a.out:
        save_json({"ok": ok, "style": style, "pattern": pattern}, a.out)
    return 0 if ok else 1


def cmd_review(a):
    import ss_card
    if not os.path.isfile(a.pattern):
        raise StyleError(f"not found: {a.pattern}")
    with open(a.pattern, encoding="utf-8-sig") as f:
        items = ss_card.pattern_items(f.read())
    if not items:
        raise StyleError(f"{a.pattern}: lists no signatures or set pieces; write them as bullets (references/firewall.md)")
    missing = [f for f in a.files if not os.path.exists(f)]
    if missing:
        raise StyleError(f"not found: {', '.join(missing)}")
    return write_text(ss_card.review_prompt(items, a.files), a.out)


def cmd_sheet(a):
    import ss_media
    info, _, _ = ss_media.measure_video(a.video, a.max_seconds)
    mids = info["shot_mids"]
    if len(mids) > a.max_tiles:
        step = len(mids) / a.max_tiles
        mids = [mids[int(i * step)] for i in range(a.max_tiles)]
    fps = info["fps"] if 0 < info["fps"] <= 30.5 else 30.0
    pre = "" if 0 < info["fps"] <= 30.5 else "fps=30,"
    frames = sorted({int(round(t * fps)) for t in mids})
    rows = (len(frames) + a.cols - 1) // a.cols
    expr = "+".join(f"eq(n\\,{n})" for n in frames)
    run(["ffmpeg", "-v", "error", "-y", *media_in(a.video), "-an", "-vf",
         f"{pre}select='{expr}',scale=320:-2,tile={a.cols}x{rows}:padding=4:color=black", "-fps_mode", "vfr",
         "-frames:v", "1", a.out])
    print(f"wrote {a.out}: {len(frames)} shots, one frame from the middle of each")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="style.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("measure", help="measure references")
    p.add_argument("files", nargs="+")
    p.add_argument("-o", "--out", default="measures.json")
    p.add_argument("--medium", choices=MEDIA)
    p.add_argument("--max-seconds", type=float, default=600.0)
    p.add_argument("--work", help="these files are parts of one work (screenshots of one site, chapters of one book)")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("card", help="build style.json and fingerprints.json")
    p.add_argument("measures", nargs="+")
    p.add_argument("-o", "--out", default="style.json")
    p.add_argument("--fingerprints", default="fingerprints.json")
    p.add_argument("--name")
    p.set_defaults(fn=cmd_card)

    p = sub.add_parser("lint", help="run the pattern firewall on a card")
    p.add_argument("card")
    p.add_argument("--fingerprints")
    p.add_argument("--pattern", help="the checker's pattern.md: refuse habits that restate a device listed there")
    p.set_defaults(fn=cmd_lint)

    p = sub.add_parser("render", help="write the card as Markdown")
    p.add_argument("card")
    p.add_argument("-o", "--out", default="style.md")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("brief", help="write a design brief for new work")
    p.add_argument("card")
    p.add_argument("--for", dest="target", required=True, help="video, audio, text, image, slides, document, sheet, ui or any")
    p.add_argument("--subject", help="what the new work is about")
    p.add_argument("-o", "--out", default="brief.md")
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("check", help="two-sided check of new work")
    p.add_argument("files", nargs="+")
    p.add_argument("--card", required=True)
    p.add_argument("--fingerprints", help="fingerprints.json from `card`; without it the pattern side does not run")
    p.add_argument("--medium", choices=MEDIA)
    p.add_argument("--max-seconds", type=float, default=600.0)
    p.add_argument("-o", "--out", help="also write the report as JSON")
    p.add_argument("--own-palette", action="store_true",
                   help="the reference's colours are the person's own (their brand): report a shared palette as a warning")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("review", help="prompt for an independent imitation review against pattern.md")
    p.add_argument("pattern", help="the checker's pattern.md")
    p.add_argument("files", nargs="+", help="the new work: renders, screenshots, pages, text")
    p.add_argument("-o", "--out", default="review.md")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("sheet", help="contact sheet of a video, one frame per shot")
    p.add_argument("video")
    p.add_argument("-o", "--out", default="sheet.png")
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--max-tiles", type=int, default=48)
    p.add_argument("--max-seconds", type=float, default=600.0)
    p.set_defaults(fn=cmd_sheet)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except StyleError as e:
        print(f"style.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
