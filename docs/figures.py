#!/usr/bin/env python3
"""Draw the README figures (docs/*.svg) from the skill's own numbers.

  hero.svg       a reference's shot lengths, the card's range, a new work in its own order
  firewall.svg   the two desks: what the checker keeps and what the maker sees
  card.svg       assets/example-card.json drawn as a card
  check.svg      the two-sided check, with verdicts from scripts/check-skill.py
  terminal.svg   real `style.py check` output on the synthetic films of check-skill.py (an excerpt)

Only the standard library. Run from anywhere: python3 docs/figures.py
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.dont_write_bytecode = True
from ss_common import quantile  # noqa: E402

PAPER, PAPER2, TILE, EDGE = "#F4F0E8", "#ECE6DA", "#FBF8F2", "#DDD5C6"
INK, MUTED, FAINT, RULE = "#1F1D1A", "#6E675D", "#B9B0A2", "#E4DDD0"
RED, GREEN, SLATE = "#D9482B", "#2F6B4F", "#5B6B7A"
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=16, fill=INK, family=SANS, weight=None, italic=False, anchor=None, extra=""):
    a = f' font-family="{family}" font-size="{size}" fill="{fill}"'
    if weight:
        a += f' font-weight="{weight}"'
    if italic:
        a += ' font-style="italic"'
    if anchor:
        a += f' text-anchor="{anchor}"'
    return f'<text x="{x:.1f}" y="{y:.1f}"{a}{extra}>{esc(s)}</text>'


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{esc(title)}">\n<title>{esc(title)}</title>\n'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="22" fill="{PAPER}" stroke="{EDGE}" stroke-width="2"/>\n'
            + "\n".join(body) + "\n</svg>\n")


def save(name, content):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote docs/{name}")


# ---------------------------------------------------------------- hero
REF = [1.0, 2.0, 0.5, 1.5, 3.0, 1.0, 2.5, 0.8, 1.2, 2.0]
NEW = [1.4, 0.7, 2.2, 1.1, 2.6, 0.9, 1.6, 1.0, 2.0, 1.3]
REF_COL = ["#C8553D", "#E0A458", "#8AA29E", "#3D5A80", "#B56576", "#6D597A", "#E07A5F", "#81B29A", "#D9B26F", "#5C677D"]
NEW_COL = ["#2F6B4F", "#9BB27D", "#D2BC84", "#4F7C8A", "#B98F57", "#7A9E7E", "#CDBE9C", "#386150", "#A2BE9B", "#9C7443"]


def bars(values, colors, x0, y, k=58, gap=8, h=44):
    out, xs, x = [], [], x0
    for v, c in zip(values, colors):
        w = v * k
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="6" fill="{c}"/>')
        xs.append(x + w / 2)
        x += w + gap
    return out, xs


def hero():
    b = [text(64, 136, "style-study", 92, INK, SERIF, extra=' letter-spacing="-1.5"'),
         f'<text x="68" y="192" font-family="{SERIF}" font-size="34" font-style="italic" fill="{INK}">Learn the style. '
         f'<tspan fill="{RED}">Never the pattern.</tspan></text>',
         text(68, 236, "Measure reference works, keep only what recurs, design something new, then prove it is not a copy.", 19, MUTED),
         text(68, 266, "Video  ·  images  ·  music and sound  ·  Thai and English writing  ·  any other medium, by hand", 15, MUTED)]
    xa, xb, xc = 260, 1216, 1060
    b.append(f'<line x1="236" y1="316" x2="236" y2="596" stroke="{RULE}" stroke-width="2"/>')
    # row labels and the steps between rows
    for y, label, sub in ((350, "the reference", "its order, its material"), (458, "the card", "ranges only"),
                          (562, "your new work", "own order, own material")):
        b.append(text(64, y, label, 21, INK, SERIF, italic=True))
        b.append(text(64, y + 22, sub, 13, MUTED))
    b.append(text(64, 408, "↓ measure, drop the order", 13, GREEN))
    b.append(text(64, 512, "↓ brief, then make", 13, GREEN))
    # row 1: the reference
    r1, xs1 = bars(REF, REF_COL, xa, 322)
    b += r1
    # row 2: the card's range
    lo, hi = 0.3, 3.2
    X = lambda v: xa + (v - lo) / (hi - lo) * (xc - xa)  # noqa: E731
    p10, p50, p90 = (quantile(REF, q) for q in (0.1, 0.5, 0.9))
    yb = 452
    b.append(f'<line x1="{xa}" y1="{yb + 26}" x2="{xc}" y2="{yb + 26}" stroke="{FAINT}" stroke-width="1.5"/>')
    for t in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        b.append(f'<line x1="{X(t):.1f}" y1="{yb + 22}" x2="{X(t):.1f}" y2="{yb + 30}" stroke="{FAINT}" stroke-width="1.5"/>')
        b.append(text(X(t), yb + 46, f"{t:g} s", 12, FAINT, MONO, anchor="middle"))
    b.append(f'<rect x="{X(p10):.1f}" y="{yb - 13}" width="{X(p90) - X(p10):.1f}" height="26" rx="13" fill="{GREEN}" '
             f'fill-opacity="0.13" stroke="{GREEN}" stroke-width="2"/>')
    seen = {}
    for v, x1, c in zip(REF, xs1, REF_COL):
        n = seen.get(v, 0)
        seen[v] = n + 1
        x2 = X(v) + (n * 12 - 6 if REF.count(v) > 1 else 0)
        b.append(f'<path d="M{x1:.1f} 368 C{x1:.1f} 410 {x2:.1f} 402 {x2:.1f} {yb - 6}" fill="none" stroke="{c}" '
                 f'stroke-opacity="0.55" stroke-width="1.8"/>')
        b.append(f'<circle cx="{x2:.1f}" cy="{yb}" r="5.5" fill="{FAINT}" stroke="{PAPER}" stroke-width="1.5"/>')
    b.append(f'<line x1="{X(p50):.1f}" y1="{yb - 19}" x2="{X(p50):.1f}" y2="{yb + 19}" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')
    b.append(text(xc + 22, yb - 2, f"{p10:.1f} to {p90:.1f} s", 16, GREEN, MONO))
    b.append(text(xc + 22, yb + 19, f"median {p50:.1f} s", 13, MUTED, MONO))
    # row 3: new work
    r3, _ = bars(NEW, NEW_COL, xa, 534)
    b += r3
    return svg(1280, 640, b, "style-study: learn the style, never the pattern")


# ---------------------------------------------------------------- firewall
def tile(x, y, w, h, title, sub, num=None, title_fill=INK):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{TILE}" stroke="{EDGE}" stroke-width="1.5"/>',
           text(x + 22, y + 34, title, 19, title_fill, MONO)]
    for i, line in enumerate(sub if isinstance(sub, list) else [sub]):
        out.append(text(x + 22, y + 60 + 21 * i, line, 15, MUTED))
    if num is not None:
        out.append(badge(x + w - 26, y + 26, num))
    return out


def badge(cx, cy, n, fill=INK):
    return (f'<circle cx="{cx}" cy="{cy}" r="14" fill="{fill}"/>'
            + text(cx, cy + 5, str(n), 14, PAPER, SANS, weight="700", anchor="middle"))


def arrow(x1, y1, x2, y2, color=INK, dash=False, curve=None):
    d = f"M{x1} {y1} " + (f"C{curve} {x2} {y2}" if curve else f"L{x2} {y2}")
    ang = math.atan2(y2 - (float(curve.split()[-1]) if curve else y1), x2 - (float(curve.split()[-2]) if curve else x1))
    hx = [x2 - 12 * math.cos(ang - 0.45), x2 - 12 * math.cos(ang + 0.45)]
    hy = [y2 - 12 * math.sin(ang - 0.45), y2 - 12 * math.sin(ang + 0.45)]
    dash_a = ' stroke-dasharray="6 6"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5"{dash_a}/>'
            f'<path d="M{hx[0]:.1f} {hy[0]:.1f} L{x2} {y2} L{hx[1]:.1f} {hy[1]:.1f}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')


def pill(cx, cy, label, fill=INK, color=PAPER, w=None):
    w = w or 16 + 9.6 * len(label)
    return (f'<rect x="{cx - w / 2:.1f}" y="{cy - 15}" width="{w:.1f}" height="30" rx="15" fill="{fill}"/>'
            + text(cx, cy + 5, label, 15, color, MONO, anchor="middle"))


def firewall():
    b = [text(64, 92, "The firewall", 44, INK, SERIF),
         text(66, 130, "Two desks. Only the card and the brief reach the maker. Only the new work comes back.", 19, MUTED)]
    L, R, top, bot = (64, 584), (696, 1216), 170, 748
    for (x0, x1), label, note in ((L, "the checker's desk", "Never handed to the maker."),
                                  (R, "the maker's desk", "Never sees the references.")):
        b.append(f'<rect x="{x0}" y="{top}" width="{x1 - x0}" height="{bot - top}" rx="18" fill="{PAPER2}"/>')
        b.append(text(x0 + 24, top + 38, label, 22, INK, SERIF, italic=True))
        b.append(text(x0 + 24, bot - 22, note, 14, MUTED, italic=True))
    # the wall, with two gates
    b.append('<defs><pattern id="hatch" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             f'<line x1="0" y1="0" x2="0" y2="12" stroke="{INK}" stroke-opacity="0.28" stroke-width="3"/></pattern></defs>')
    gates = [(262, 318), (594, 650)]
    segs = [(top - 10, gates[0][0]), (gates[0][1], gates[1][0]), (gates[1][1], bot + 10)]
    for y0, y1 in segs:
        b.append(f'<rect x="604" y="{y0}" width="72" height="{y1 - y0}" rx="6" fill="url(#hatch)" stroke="{INK}" '
                 f'stroke-opacity="0.35" stroke-width="1.5"/>')
    b.append(f'<text x="640" y="460" font-family="{SERIF}" font-size="18" font-style="italic" fill="{INK}" '
             f'text-anchor="middle" transform="rotate(-90 640 460)">firewall</text>')
    # checker's desk
    b += tile(88, 230, 472, 74, "reference files", "a film, an essay, a track, a set of images")
    b += tile(88, 326, 472, 74, "measures.json", "every unit, in order", num=1)
    b += tile(88, 422, 472, 96, "fingerprints.json", ["sequences, frame hashes, layouts,", "audio and text fingerprints, palette"])
    b += tile(88, 540, 472, 74, "pattern.md", "set pieces seen once: things not to do")
    b.append(arrow(140, 304, 140, 324))
    b.append(arrow(140, 400, 140, 420))
    # maker's desk
    b += tile(720, 228, 472, 96, "style.json  ·  style.md", ["ranges, axes, habits, avoid, forbid; lint refuses",
                                                            "times, positions, quotes, names, sequences"], num=2)
    b += tile(720, 368, 472, 96, "brief.md", ["subject first, your own structure,", "one element the reference never had"], num=3)
    b += tile(720, 508, 472, 74, "the new work", "made from the brief and the card alone", num=4)
    b.append(arrow(780, 324, 780, 366))
    b.append(arrow(780, 464, 780, 506))
    # crossings
    b.append(arrow(560, 363, 718, 276, GREEN, curve="610 363 660 276"))
    b.append(pill(640, 290, "lint", GREEN))
    b.append(arrow(718, 560, 560, 662, RED, curve="660 560 610 662"))
    b.append(pill(640, 622, "check", RED))
    # verdict
    b += [f'<rect x="88" y="634" width="472" height="56" rx="12" fill="{INK}"/>',
          text(112, 669, "STYLE PASS", 17, "#9FD3AE", MONO, weight="700"),
          text(250, 669, "PATTERN PASS", 17, "#9FD3AE", MONO, weight="700"),
          text(420, 669, "show it", 16, "#CFC7B8", SERIF, italic=True),
          badge(534, 662, 6, "#3A3631")]
    b.append(badge(640, 588, 5, RED))
    return svg(1280, 790, b, "The firewall between the checker and the maker")


# ---------------------------------------------------------------- card
def range_row(y, label, m, lo, hi, scale, unit, fmt="{:.2g}"):
    unit = f" {unit}" if unit else ""
    x0, x1 = 330, 620
    if scale == "log":
        X = lambda v: x0 + (math.log10(max(v, lo)) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * (x1 - x0)  # noqa: E731
    else:
        X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)  # noqa: E731
    f = lambda v: fmt.format(v)  # noqa: E731
    return [text(64, y, label, 16, INK),
            text(64, y + 21, f"{f(m['p10'])} to {f(m['p90'])}{unit}, median {f(m['p50'])}", 13, MUTED, MONO),
            f'<line x1="{x0}" y1="{y - 4}" x2="{x1}" y2="{y - 4}" stroke="{RULE}" stroke-width="6" stroke-linecap="round"/>',
            f'<line x1="{X(m["p10"]):.1f}" y1="{y - 4}" x2="{X(m["p90"]):.1f}" y2="{y - 4}" stroke="{GREEN}" stroke-width="10" '
            f'stroke-linecap="round"/>',
            f'<circle cx="{X(m["p50"]):.1f}" cy="{y - 4}" r="7" fill="{PAPER}" stroke="{INK}" stroke-width="3"/>']


def wrap(s, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


def card():
    c = json.load(open(os.path.join(ROOT, "assets", "example-card.json"), encoding="utf-8"))
    v, t = c["measured"]["video"], c["measured"]["text"]
    kinds = {}
    for r in c["references"]:
        kinds[r["medium"]] = kinds.get(r["medium"], 0) + 1
    b = [text(64, 74, "Style card", 18, MUTED, SERIF, italic=True),
         text(64, 124, c["name"], 48, INK, SERIF),
         text(66, 156, f"learned from {len(c['references'])} references ({kinds.get('video', 0)} films, {kinds.get('text', 0)} essay)  ·  "
              "a made-up style, from assets/example-card.json", 15, MUTED),
         f'<line x1="64" y1="184" x2="1216" y2="184" stroke="{RULE}" stroke-width="2"/>']
    b.append(text(64, 226, "Measured: video", 22, INK, SERIF, italic=True))
    y = 270
    for dim, lo, hi, scale, unit, fmt in (("shot_length", 0.5, 12, "log", "s", "{:.1f}"),
                                         ("motion", 0.3, 10, "log", "frame change", "{:.1f}"),
                                         ("luma", 0, 1, "lin", "", "{:.2f}"),
                                         ("saturation", 0, 1, "lin", "", "{:.2f}"),
                                         ("warmth", 0, 1, "lin", "", "{:.2f}")):
        b += range_row(y, v[dim]["label"], v[dim], lo, hi, scale, unit, fmt)
        y += 58
    b.append(text(64, y + 10, "Measured: text", 22, INK, SERIF, italic=True))
    y += 54
    for dim, lo, hi, scale, unit, fmt in (("sentence_length", 2, 40, "log", "words", "{:.0f}"),
                                         ("paragraph_sentences", 0, 6, "lin", "", "{:.0f}"),
                                         ("question_rate", 0, 0.5, "lin", "of sentences", "{:.0%}")):
        b += range_row(y, t[dim]["label"], t[dim], lo, hi, scale, unit, fmt)
        y += 58
    left_end = y
    # axes
    ax0 = 700
    b.append(text(ax0, 226, "Axes: these travel to any medium", 22, INK, SERIF, italic=True))
    from ss_dims import BANDS3
    y = 266
    for axis, names in BANDS3.items():
        band = c["axes"].get(axis, {}).get("band")
        b.append(text(ax0, y + 5, axis, 15, INK))
        for i, n in enumerate(names):
            x = 820 + i * 132
            on = n == band
            b.append(f'<rect x="{x}" y="{y - 14}" width="124" height="28" rx="14" fill="{INK if on else "none"}" '
                     f'stroke="{INK if on else EDGE}" stroke-width="1.5"/>')
            b.append(text(x + 62, y + 5, n, 14, PAPER if on else MUTED, anchor="middle"))
        y += 38
    # habits
    y += 26
    b.append(text(ax0, y, "Habits, each seen 3 times or more", 22, INK, SERIF, italic=True))
    y += 36
    for tr in [c["traits"][i] for i in (0, 1, 3, 4)]:
        b.append(text(ax0, y, tr["dimension"], 14, GREEN, MONO))
        for j, line in enumerate(wrap(tr["statement"], 52)):
            b.append(text(ax0 + 110, y + 22 * j, line, 15, INK))
        y += 22 * len(wrap(tr["statement"], 52)) + 14
    habits_end = y
    # never and forbid, under the measured rows
    y = left_end + 22
    b.append(text(64, y, "Never", 22, RED, SERIF, italic=True))
    y += 30
    for line in (c["avoid"][0], c["avoid"][2]):
        b.append(text(64, y, line, 15, INK))
        y += 22
    y += 18
    b.append(text(64, y, "Forbid", 22, RED, SERIF, italic=True))
    b.append(text(150, y, "names that must not appear", 14, MUTED, italic=True))
    y += 30
    x = 64
    for name in c["forbid"]:
        w = 24 + 8.6 * len(name)
        b.append(f'<rect x="{x}" y="{y - 19}" width="{w:.1f}" height="28" rx="14" fill="none" stroke="{RED}" stroke-width="1.5"/>')
        b.append(text(x + w / 2, y, name, 14, RED, anchor="middle"))
        x += w + 10
    y = max(y + 24, habits_end) + 10
    b.append(f'<line x1="64" y1="{y}" x2="1216" y2="{y}" stroke="{RULE}" stroke-width="2"/>')
    b.append(text(640, y + 40, "No order, no timestamps, no quotes, no colour values: a card cannot carry a copy.", 16, MUTED,
                  SERIF, italic=True, anchor="middle"))
    return svg(1280, y + 74, b, "A style card drawn from assets/example-card.json")


# ---------------------------------------------------------------- check
def check():
    b = [text(64, 92, "The two-sided check", 44, INK, SERIF),
         text(66, 130, "New work ships only when it sits close to the card and far from the reference.", 19, MUTED)]
    x0, x1, y0, y1 = 170, 840, 176, 640
    tx, ty = 620, 440  # thresholds
    b.append(f'<rect x="{x0}" y="{ty}" width="{tx - x0}" height="{y1 - ty}" fill="{GREEN}" fill-opacity="0.10"/>')
    b.append(f'<line x1="{tx}" y1="{y0}" x2="{tx}" y2="{y1}" stroke="{GREEN}" stroke-width="2" stroke-dasharray="7 7"/>')
    b.append(f'<line x1="{x0}" y1="{ty}" x2="{x1}" y2="{ty}" stroke="{RED}" stroke-width="2" stroke-dasharray="7 7"/>')
    b.append(text(x0 + 18, y1 - 22, "ships", 24, GREEN, SERIF, italic=True))
    b.append(text(tx + 12, y0 + 18, "75% of dimensions in range", 13, GREEN, MONO))
    b.append(text(tx + 12, y0 + 36, "and no core one off", 13, GREEN, MONO))
    b.append(text(x1 - 6, ty - 10, "a copy alarm fires", 13, RED, MONO, anchor="end"))
    b.append(f'<path d="M{x0} {y0 - 10} L{x0} {y1} L{x1 + 10} {y1}" fill="none" stroke="{INK}" stroke-width="2.5"/>')
    b.append(text((x0 + x1) / 2, y1 + 44, "style: distance from the card's ranges", 16, INK, anchor="middle"))
    b.append(text(x0, y1 + 24, "in range", 13, MUTED, MONO))
    b.append(text(x1, y1 + 24, "off", 13, MUTED, MONO, anchor="end"))
    b.append(f'<text x="112" y="{(y0 + y1) / 2}" font-family="{SANS}" font-size="16" fill="{INK}" text-anchor="middle" '
             f'transform="rotate(-90 112 {(y0 + y1) / 2})">pattern: how much of the reference it takes</text>')
    b.append(text(x0 - 12, y1, "none", 13, MUTED, MONO, anchor="end"))
    b.append(text(x0 - 12, y0 + 8, "copied", 13, MUTED, MONO, anchor="end"))
    pts = [(x0 + 60, 222, RED, True, "a re-cut of the reference", "order r = 1.00, 14/14 frames near-duplicate"),
           (x0 + 96, 336, RED, False, "same order, new footage", "order r = 0.91, p = 0.003"),
           (x0 + 120, 548, GREEN, True, "its own order, new footage", "style 100% in range, pattern pass"),
           (x0 + 570, 584, SLATE, True, "a slow, bright film", "style 50% in range")]
    for x, y, col, filled, a, sub in pts:
        b.append(f'<circle cx="{x}" cy="{y}" r="10" fill="{col if filled else PAPER}" stroke="{col}" stroke-width="3.5"/>')
        if x > tx:
            b.append(text(x, y - 46, a, 16, INK, anchor="middle"))
            b.append(text(x, y - 24, sub, 13, col, MONO, anchor="middle"))
        else:
            b.append(text(x + 22, y - 2, a, 16, INK))
            b.append(text(x + 22, y + 20, sub, 13, col, MONO))
    px = 880
    b.append(text(px, 214, "Style side", 22, GREEN, SERIF, italic=True))
    for i, line in enumerate(["Each measured dimension: the new", "work's median against the card's",
                              "p10 to p90. Passes with 75% in range", "and no core dimension off."]):
        b.append(text(px, 246 + 23 * i, line, 15, INK))
    b.append(text(px, 374, "Pattern side", 22, RED, SERIF, italic=True))
    for i, line in enumerate(["Same order (a permutation test),", "near-duplicate frames or images,",
                              "reused audio, shared text, names", "the card forbids."]):
        b.append(text(px, 406 + 23 * i, line, 15, INK))
    b.append(text(px, 548, "Both must pass.", 26, INK, SERIF, italic=True))
    b.append(text(px, 580, "Positions are a sketch. The verdicts", 13, MUTED))
    b.append(text(px, 598, "are real results of check-skill.py", 13, MUTED))
    b.append(text(px, 616, "on synthetic films.", 13, MUTED))
    return svg(1280, 720, b, "The two-sided check: close in style, far in pattern")


# ---------------------------------------------------------------- terminal
TERM = [
    ("$ ", "python3 scripts/style.py check new-cut.mp4 --card style.json --fingerprints fingerprints.json", "cmd"),
    ("", "STYLE PASS: 100% of dimensions in range", "pass"),
    ("", "  ok  Shot length [core]: 1.3 against 0.6 to 2.8 s", "ok"),
    ("", "  ok  Movement inside a shot [core]: 0.824 against 0.01 to 3.35 frame change", "ok"),
    ("", "  ok  Brightness: 0.445 against 0.3 to 0.623 0-1", "ok"),
    ("", "  ...  7 more dimensions in range", "dim"),
    ("", "PATTERN PASS: nothing taken from the reference's order or material", "pass"),
    ("", "check: PASS", "pass"),
    ("", "", "dim"),
    ("$ ", "python3 scripts/style.py check recut.mp4 --card style.json --fingerprints fingerprints.json", "cmd"),
    ("", "STYLE PASS: 100% of dimensions in range", "pass"),
    ("", "  ...  10 dimensions in range", "dim"),
    ("", "PATTERN FAIL: copied pattern found", "fail"),
    ("", "  COPY r1: follows the reference's order (r=1.00, p=0.003); build your own structure", "fail"),
    ("", "  COPY r1: 14 of 14 frames or images are near-duplicates of the reference's", "fail"),
    ("", "check: FAIL", "fail"),
]


def terminal():
    colors = {"cmd": "#ECE6DA", "pass": "#8FCB9C", "fail": "#F08A70", "ok": "#A79F92", "dim": "#6E675D"}
    h = 92 + 27 * len(TERM) + 30
    b = [f'<rect x="1" y="1" width="1278" height="{h - 2}" rx="22" fill="#1C1B19" stroke="#2E2B27" stroke-width="2"/>',
         f'<line x1="2" y1="52" x2="1278" y2="52" stroke="#2E2B27" stroke-width="2"/>']
    for i in range(3):
        b.append(f'<circle cx="{34 + 22 * i}" cy="27" r="7" fill="#4A4640"/>')
    b.append(text(640, 32, "films  ·  zsh", 14, "#8D867B", MONO, anchor="middle"))
    y = 96
    for prompt, line, kind in TERM:
        if prompt:
            b.append(f'<text x="40" y="{y}" font-family="{MONO}" font-size="16.5" xml:space="preserve">'
                     f'<tspan fill="#8D867B">{esc(prompt)}</tspan><tspan fill="{colors[kind]}">{esc(line)}</tspan></text>')
        elif line:
            b.append(f'<text x="40" y="{y}" font-family="{MONO}" font-size="16.5" fill="{colors[kind]}" '
                     f'xml:space="preserve">{esc(line)}</text>')
        y += 27
    out = svg(1280, h, b, "style.py check output: a sibling passes, a re-cut fails")
    return out.replace(f'fill="{PAPER}" stroke="{EDGE}"', 'fill="#1C1B19" stroke="#2E2B27"', 1)


if __name__ == "__main__":
    save("hero.svg", hero())
    save("firewall.svg", firewall())
    save("card.svg", card())
    save("check.svg", check())
    save("terminal.svg", terminal())
