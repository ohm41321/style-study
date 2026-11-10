#!/usr/bin/env python3
"""Validate the style-study skill itself on synthetic fixtures with known answers.

  package     SKILL.md frontmatter (name = folder, description <= 1024 chars), links resolve, scripts compile
              and answer --help, no stray files, the example card lints clean
  text        English and Thai fixtures: sentence and paragraph counts, questions, polite endings
  lint        each firewall rule fires on a card that breaks it; a clean card passes
  card        style.json holds no per-unit sequence, palette hex or frame hash
  brief       a brief for every target has all seven sections and no fingerprint data
  text check  copy and same-order rewrite fail the pattern side; a reshuffled sibling passes both sides;
              unrelated writing fails the style side
  video       cut times within one frame on a known edit; copy and same-order remake fail; sibling passes;
              a slow bright film fails the style side       (needs numpy and ffmpeg)
  audio       tempo within 1.5 BPM and onsets within 12 ms on click tracks (with and without a noise
              floor); a copied track, a re-encoded excerpt cut from mid-track and an excerpt of a
              looped track fail; a reshuffled sibling passes; fingerprints from before the excerpt fix
              leave the check incomplete, never passed  (needs numpy and ffmpeg)
  image       negative space and subject offset move the right way; copied images fail; a sibling set
              passes                                        (needs numpy and ffmpeg)
  documents   known answers from .pptx, .docx, .xlsx, .odt, .odp, .fods, .epub, .rtf (Thai code page) and
              .csv written here: sizes through master, layout and style inheritance, theme colours,
              spacing, margins, numbers, decimals, charts; oversized parts and DTDs refused; macOS textutil
              round trips; PDF as a document and as a deck, including text inside scaled form XObjects
              (needs pypdf or pdftotext). Copy, same-order rewrite and reshuffled sibling for slides,
              documents and sheets; a same-order rewrite saved in another written format; hidden slides and
              sheets still checked; a shared month header is not a copy; parts counted once toward the size
              limit; a UTF-16 DTD refused; a reference picture re-saved inside a new deck is caught by its
              look with numpy and ffmpeg, by its bytes without them

Run with a Python that has numpy and pypdf for the media and PDF checks; without them they print SKIP. Exit 1
on any failure.
Usage: check-skill.py [--keep DIR]
"""

import argparse
import json
import os
import py_compile
import random
import re
import shutil
import subprocess
import sys
import struct
import tempfile
import wave
import zipfile
import zlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
STYLE = os.path.join(HERE, "style.py")

results = []


def check(name, ok, detail=""):
    results.append(("PASS" if ok else "FAIL", name, detail))


def skip(name, detail):
    results.append(("SKIP", name, detail))


def cli(*args, ok_codes=(0, 1)):
    p = subprocess.run([sys.executable, STYLE, *args], capture_output=True, text=True)
    if p.returncode not in ok_codes:
        raise RuntimeError(f"style.py {' '.join(args)} exited {p.returncode}: {p.stderr.strip()[-400:]}")
    return p


# ---------------------------------------------------------------- package
def check_package():
    text = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    name = re.search(r"^name:\s*(\S+)", fm.group(1), re.M).group(1) if fm else None
    desc = re.search(r"^description:\s*(>-?|\|)?\s*\n?(.*?)(?=^\w|\Z)", fm.group(1), re.M | re.S) if fm else None
    desc_text = " ".join(desc.group(2).split()) if desc else ""
    folder = os.path.basename(SKILL)
    if re.fullmatch(r"\d+(\.\d+)*", folder):  # a Claude Code plugin is installed as <name>/<version>/
        folder = os.path.basename(os.path.dirname(SKILL))
    check("frontmatter", bool(fm) and name == folder and 0 < len(desc_text) <= 1024,
          f"name={name}, folder {folder}, description {len(desc_text)} chars")
    broken = []
    for root, _, files in os.walk(SKILL):
        for f in files:
            if f.endswith(".md"):
                path = os.path.join(root, f)
                for link in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", open(path, encoding="utf-8").read()):
                    if "://" in link:
                        continue
                    if not os.path.exists(os.path.normpath(os.path.join(root, link))):
                        broken.append(f"{os.path.relpath(path, SKILL)} -> {link}")
    check("links", not broken, "; ".join(broken) or "all relative links resolve")
    bad = []
    for f in sorted(os.listdir(HERE)):
        if f.endswith(".py"):
            try:
                py_compile.compile(os.path.join(HERE, f), doraise=True, cfile=os.path.join(tempfile.gettempdir(), "ss-compile.pyc"))
            except py_compile.PyCompileError as e:
                bad.append(f"{f}: {e.msg}")
    p = subprocess.run([sys.executable, STYLE, "--help"], capture_output=True, text=True)
    if p.returncode != 0 or "measure" not in p.stdout:
        bad.append("style.py --help")
    for exe in ("style.py", "check-skill.py"):
        if not os.access(os.path.join(HERE, exe), os.X_OK):
            bad.append(f"{exe} is not executable")
    check("scripts", not bad, "; ".join(bad) or "compile, --help, executable bits")
    stray = []
    for root, dirs, files in os.walk(SKILL):
        for d in dirs:
            if d in ("__pycache__", ".venv", "node_modules"):
                stray.append(os.path.relpath(os.path.join(root, d), SKILL))
        for f in files:
            if f == ".DS_Store" or f.endswith((".pyc", ".mp4", ".wav", ".png")):
                stray.append(os.path.relpath(os.path.join(root, f), SKILL))
    check("stray files", not stray, ", ".join(stray) or "none")
    ex = os.path.join(SKILL, "assets", "example-card.json")
    p = cli("lint", ex)
    check("example card lints clean", p.returncode == 0, p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr)


# ---------------------------------------------------------------- text fixtures
WORDS = ("river stone lamp quiet market morning signal paper window garden engine harbor letter"
         " orange table winter field bridge cotton silver mirror ladder pocket candle station"
         " meadow thunder violet copper island forest velvet compass shadow ribbon granite").split()
WORDS2 = ("cloud anchor basket cedar dune ember feather glacier hollow ivory jasmine kettle lantern"
          " marble nectar orchard pebble quartz raven saddle tulip umbrella valley walnut yarrow"
          " zephyr acorn blossom canyon dahlia falcon grove heron juniper").split()


def sentence(rng, bank, n, question=False):
    ws = [rng.choice(bank) for _ in range(n)]
    ws[0] = ws[0].capitalize()
    return " ".join(ws) + ("?" if question else ".")


def make_text(plan, bank, seed):
    """plan: list of paragraphs, each a list of (length, question) or ('list', items)."""
    rng = random.Random(seed)
    out = []
    for para in plan:
        if para and para[0] == "list":
            out.append("\n".join("- " + sentence(rng, bank, 4)[:-1] for _ in range(para[1])))
        else:
            out.append(" ".join(sentence(rng, bank, n, q) for n, q in para))
    return "\n\n".join(out) + "\n"


def text_plan(seed):
    rng = random.Random(seed)
    plan = []
    for i in range(22):
        if i % 6 == 4:
            plan.append(("list", 3 + i % 3))
            continue
        k = 1 + (i * 7 % 4)
        plan.append([(4 + (i * 5 + j * 3) % 14, (i + j) % 5 == 0) for j in range(k)])
    return plan


def check_text(tmp):
    import ss_text
    # exact counts on a small English fixture
    en = os.path.join(tmp, "count-en.txt")
    with open(en, "w", encoding="utf-8") as f:
        f.write("One two three four. Five six seven eight nine ten?\n\nEleven twelve. Thirteen fourteen fifteen!\n")
    info, values, _, _ = ss_text.measure_text(en)
    ok = (info["units"] == 4 and values["sentence_length"] == [4, 6, 2, 3] and values["paragraph_sentences"] == [2, 2]
          and abs(values["question_rate"][0] - 0.25) < 1e-9 and abs(values["exclaim_rate"][0] - 0.25) < 1e-9)
    check("text: English counts", ok, f"sentences {values['sentence_length']}, paragraphs {values['paragraph_sentences']}")
    th = os.path.join(tmp, "count-th.txt")
    with open(th, "w", encoding="utf-8") as f:
        f.write("วันนี้อากาศดีมากครับ ไปเดินเล่นกันไหมครับ ผมชอบใช้ Claude Code ทำงาน ดีๆ แบบนี้ต้องลองนะ\n\n"
                "เรื่องนี้สำคัญค่ะ คุณคิดว่ายังไงคะ\n")
    info, values, _, _ = ss_text.measure_text(th)
    ok = (info["lang"] == "th" and info["units"] == 6 and values["paragraph_sentences"] == [4, 2]
          and abs(values["question_rate"][0] - 2 / 6) < 1e-9 and abs(values["polite_end_rate"][0] - 4 / 6) < 1e-9
          and abs(values["soft_end_rate"][0] - 1 / 6) < 1e-9 and values["latin_mix"][0] > 0)
    check("text: Thai sentences and endings", ok,
          f"lang {info['lang']}, {info['units']} sentences, paragraphs {values['paragraph_sentences']}, "
          f"questions {values['question_rate'][0]:.2f}, polite {values['polite_end_rate'][0]:.2f}")

    wrong = []
    for s, first, second in (("คุณภาพดีเท่านั้น", 0, 0), ("ข้าวมันไก่อร่อย", 0, 0), ("แก้ปัญหาได้เลย", 0, 0),
                             ("นายกฯ แถลง", 0, 0), ("คุณลองดูนะ", 0, 1), ("ท่านเลือกได้", 0, 1), ("เพราะเราไปด้วยกัน", 1, 0)):
        f = ss_text.sentence_features(s, "th")
        if (f["first"], f["second"]) != (first, second):
            wrong.append(f"{s}: first {f['first']:.0f} second {f['second']:.0f}")
    check("text: Thai pronouns inside other words do not count", not wrong, "; ".join(wrong) or "7 sentences")

    plan = text_plan(1)
    ref = os.path.join(tmp, "ref.md")
    open(ref, "w", encoding="utf-8").write(make_text(plan, WORDS, 1))
    copy = os.path.join(tmp, "copy.md")
    shutil.copy(ref, copy)
    remake = os.path.join(tmp, "remake.md")
    open(remake, "w", encoding="utf-8").write(make_text(plan, WORDS2, 2))
    shuffled = plan[:]
    random.Random(5).shuffle(shuffled)
    sib = os.path.join(tmp, "sibling.md")
    open(sib, "w", encoding="utf-8").write(make_text(shuffled, WORDS2, 3))
    far = os.path.join(tmp, "far.md")
    rng = random.Random(9)
    open(far, "w", encoding="utf-8").write(" ".join(sentence(rng, WORDS2, 40) for _ in range(30)) + "\n")
    cli("measure", ref, "-o", os.path.join(tmp, "m-text.json"))
    cli("card", os.path.join(tmp, "m-text.json"), "-o", os.path.join(tmp, "text.json"),
        "--fingerprints", os.path.join(tmp, "text-fp.json"))
    run_pair(tmp, "text", copy, remake, sib, far)
    return os.path.join(tmp, "text.json"), os.path.join(tmp, "text-fp.json")


def run_pair(tmp, label, copy, remake, sib, far):
    card, fp = os.path.join(tmp, f"{label}.json"), os.path.join(tmp, f"{label}-fp.json")

    def verdict(path):
        p = cli("check", path, "--card", card, "--fingerprints", fp)
        out = p.stdout
        return ("STYLE PASS" in out, "PATTERN PASS" in out, out)

    s, pt, out = verdict(copy)
    check(f"{label} check: exact copy fails the pattern side", not pt, last_copy_line(out))
    if remake:
        s, pt, out = verdict(remake)
        check(f"{label} check: same order, new material fails the pattern side", not pt and "order" in out, last_copy_line(out))
    s, pt, out = verdict(sib)
    check(f"{label} check: reshuffled sibling passes both sides", s and pt, summary_line(out))
    if far:
        s, pt, out = verdict(far)
        check(f"{label} check: unrelated work fails the style side", not s, summary_line(out))


def last_copy_line(out):
    lines = [l.strip() for l in out.splitlines() if l.strip().startswith("COPY")]
    return lines[0] if lines else out.strip().splitlines()[-1]


def summary_line(out):
    lines = [l for l in out.splitlines() if l.startswith(("STYLE", "PATTERN"))]
    return " | ".join(lines)


# ---------------------------------------------------------------- lint
def check_lint(tmp, card_path, fp_path):
    import ss_card
    base = json.load(open(card_path, encoding="utf-8"))
    fps = json.load(open(fp_path, encoding="utf-8"))
    good = dict(base, traits=[{"dimension": "rhythm", "statement": "Short sentences sit between long ones, about one in four.",
                               "do": "Follow every long sentence with a short one.", "evidence": {"refs": 1, "count": 9},
                               "confidence": "medium"}],
                avoid=["Never stack three questions."], forbid=["Northwind Parcel"])
    errors, _ = ss_card.lint(good, fps)
    check("lint: clean card passes", not errors, "; ".join(errors) or "0 errors")
    ref_words = open(os.path.join(tmp, "ref.md"), encoding="utf-8").read().split()[:12]
    cases = {
        "timestamp": "At 0:12 the narrator slows down.",
        "time mark": "The pace drops at 14 seconds into the piece.",
        "ordinal": "The first paragraph is a single question.",
        "Thai ordinal": "ช็อตแรกเป็นภาพมุมกว้าง",
        "numbered unit": "Scene 3 holds for a long time.",
        "forbidden name": "Feels like a Northwind Parcel ad.",
        "long quote": 'Uses lines like "we ship quiet things to loud places every day".',
        "verbatim text": " ".join(ref_words),
    }
    for label, statement in cases.items():
        bad = json.loads(json.dumps(good))
        bad["traits"][0]["statement"] = statement
        errors, _ = ss_card.lint(bad, fps)
        check(f"lint: {label} is refused", bool(errors), errors[0] if errors else "no error raised")
    for label, mutate in (
            ("a time in a trait's dimension", lambda c: c["traits"][0].__setitem__("dimension", "pace at 0:12")),
            ("a forbidden name in a reference file name", lambda c: c["references"][0].__setitem__("file", "Northwind Parcel ad.mp4")),
            ("a long quote in single curly quotes", lambda c: c["avoid"].append("‘we ship quiet things to loud places every day’"))):
        bad = json.loads(json.dumps(good))
        mutate(bad)
        errors, _ = ss_card.lint(bad, fps)
        check(f"lint: {label} is refused", bool(errors), errors[0] if errors else "no error raised")
    ok_card = json.loads(json.dumps(good))
    ok_card["avoid"].append("Don't stack questions; it's dull and it doesn't help the reader follow anything at all.")
    errors, _ = ss_card.lint(ok_card, fps)
    check("lint: apostrophes are not quotes", not errors, "; ".join(errors) or "0 errors")
    bad = json.loads(json.dumps(good))
    bad["traits"][0]["evidence"]["count"] = 2
    errors, _ = ss_card.lint(bad, fps)
    check("lint: a trait seen twice is refused", bool(errors), errors[0] if errors else "no error raised")
    bad = json.loads(json.dumps(good))
    dim = next(iter(bad["measured"]["text"]))
    bad["measured"]["text"][dim]["values"] = [1, 2, 3]
    errors, _ = ss_card.lint(bad, fps)
    check("lint: a per-unit sequence in measured is refused", bool(errors), errors[0] if errors else "no error raised")
    bad = json.loads(json.dumps(good))
    bad["axes"] = {"tempo": {"band": "brisk"}, "mood": {"band": "calm"}}
    errors, _ = ss_card.lint(bad, fps)
    check("lint: an unknown axis or band is refused", len(errors) == 2, "; ".join(errors) or "no error raised")
    bad = json.loads(json.dumps(good))
    bad["traits"][0]["statement"] = "The film opens with a black frame."
    _, warnings = ss_card.lint(bad, fps)
    check("lint: an opening described is warned", bool(warnings), warnings[0] if warnings else "no warning")


def check_card_and_brief(card_paths):
    import ss_card
    from ss_dims import TARGETS
    leaks = []
    for p in card_paths:
        txt = open(p, encoding="utf-8").read()
        if re.search(r"#[0-9a-f]{6}\b", txt) or re.search(r"\b[0-9a-f]{16}\b", txt):
            leaks.append(os.path.basename(p) + ": hex palette or frame hash")
        card = json.loads(txt)
        for medium, dims in card["measured"].items():
            for d, m in dims.items():
                if any(isinstance(v, list) for v in m.values()):
                    leaks.append(f"{os.path.basename(p)}: {medium}.{d} holds a list")
    check("card: no sequences, palettes or hashes", not leaks, "; ".join(leaks) or f"{len(card_paths)} card(s) clean")
    missing = []
    for p in card_paths:
        card = json.load(open(p, encoding="utf-8"))
        for t in TARGETS:
            b = ss_card.brief(card, t, "a test subject")
            for i in range(1, 8):
                if f"## {i}." not in b:
                    missing.append(f"{os.path.basename(p)} -> {t}: section {i}")
            if re.search(r"#[0-9a-f]{6}\b", b):
                missing.append(f"{os.path.basename(p)} -> {t}: palette hex")
            if t not in card["measured"] and card.get("axes") and "**" not in b:
                missing.append(f"{os.path.basename(p)} -> {t}: no translated axes")
    check("brief: every target, seven sections, translated axes", not missing,
          "; ".join(missing[:5]) or f"{len(TARGETS)} targets x {len(card_paths)} card(s)")


# ---------------------------------------------------------------- command contracts
TH_WORDS = ("แม่น้ำ ตลาด ตะเกียง หน้าต่าง สวน กระดาษ สะพาน ทุ่งนา ภูเขา ลมหนาว ดอกไม้ เรือ ถนน ร้านกาแฟ"
            " หมู่บ้าน ท้องฟ้า เมฆ ฝน แสงแดด ทะเล").split()


def thai_text(seed, n_par=12):
    rng = random.Random(seed)
    paras = []
    for i in range(n_par):
        sents = ["".join(rng.choice(TH_WORDS) for _ in range(3 + (i + j) % 5)) + ("ครับ" if j % 2 else "")
                 for j in range(1 + i % 3)]
        paras.append(" ".join(sents))
    return "\n\n".join(paras) + "\n"


def check_contracts(tmp):
    card, fp = os.path.join(tmp, "text.json"), os.path.join(tmp, "text-fp.json")
    copy = os.path.join(tmp, "copy.md")
    p = subprocess.run([sys.executable, STYLE, "check", copy, "--card", card], capture_output=True, text=True)
    check("check: no fingerprints means not run, and exit 1", p.returncode == 1 and "PATTERN NOT RUN" in p.stdout,
          f"exit {p.returncode}; " + summary_line(p.stdout))
    p = subprocess.run([sys.executable, STYLE, "check", copy, "--card", card, "--fingerprints", card],
                       capture_output=True, text=True)
    check("check: a card passed as fingerprints is refused with exit 2", p.returncode == 2,
          f"exit {p.returncode}; {p.stderr.strip()[-120:]}")

    # a report row must not look like a contradiction: a pass outside p10-p90 says it is inside the tolerance,
    # and a negative range reads "-13.8 to -13.7", not "-13.8--13.7"
    import ss_check
    row = ss_check.compare_dim("loudness", {"p10": -13.8, "p50": -13.75, "p90": -13.7}, -14.2)
    lines = ss_check.report_lines({"mode": "measured", "rows": [row], "share": 1.0, "ok": True},
                                  {"ok": True, "findings": [], "warnings": []})
    got = lines[1] if len(lines) > 1 else ""
    edge = ss_check.compare_dim("loudness", {"p10": -13.8, "p50": -13.75, "p90": -13.7}, -13.80004)
    same = ss_check.report_lines({"mode": "measured", "rows": [edge], "share": 1.0, "ok": True},
                                 {"ok": True, "findings": [], "warnings": []})[1]
    check("check: a row passed by the tolerance says so", row["ok"] and "within the tolerance" in got
          and "-13.8 to -13.7" in got and "tolerance" not in same, got.strip() + " | " + same.strip())

    # two drafts with one file name: the copy (its paragraphs reshuffled, so only the text test can see it)
    # must not hide behind the clean one
    paras = open(copy, encoding="utf-8").read().split("\n\n")
    random.Random(5).shuffle(paras)
    for d in ("a", "b"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    open(os.path.join(tmp, "a", "draft.md"), "w", encoding="utf-8").write("\n\n".join(paras))
    shutil.copy(os.path.join(tmp, "sibling.md"), os.path.join(tmp, "b", "draft.md"))
    p = cli("check", os.path.join(tmp, "a", "draft.md"), os.path.join(tmp, "b", "draft.md"), "--card", card, "--fingerprints", fp)
    check("check: same-named drafts are each checked", "PATTERN FAIL" in p.stdout, last_copy_line(p.stdout))

    # Thai copied into English: the copy check runs in the reference's language, not the draft's
    th_ref = os.path.join(tmp, "th-ref.md")
    open(th_ref, "w", encoding="utf-8").write(thai_text(1))
    cli("measure", th_ref, "-o", os.path.join(tmp, "m-th.json"))
    cli("card", os.path.join(tmp, "m-th.json"), "-o", os.path.join(tmp, "th.json"), "--fingerprints", os.path.join(tmp, "th-fp.json"))
    stolen = open(th_ref, encoding="utf-8").read().split("\n\n")[4]
    mixed = os.path.join(tmp, "mixed.md")
    rng = random.Random(4)
    open(mixed, "w", encoding="utf-8").write("\n\n".join(
        [" ".join(sentence(rng, WORDS2, 9) for _ in range(3)) for _ in range(6)] + [stolen] +
        [" ".join(sentence(rng, WORDS2, 9) for _ in range(3)) for _ in range(6)]) + "\n")
    p = cli("check", mixed, "--card", os.path.join(tmp, "th.json"), "--fingerprints", os.path.join(tmp, "th-fp.json"))
    check("check: Thai copied into an English draft is found", "shares a run" in p.stdout, last_copy_line(p.stdout))

    # the generic route: a card written by hand, no measurements, axes judged by eye
    generic = {"schema": "style-study/1", "name": "hand-card", "references": [{"id": "r1", "medium": "ui", "file": "app-screens"}],
               "measured": {}, "axes": {"tempo": {"band": "slow"}, "space": {"band": "airy"}},
               "traits": [{"dimension": "layout", "statement": "Screens hold one task each with wide margins.",
                           "do": "Give each screen one task and margins of 48 px or more.", "evidence": {"refs": 1, "count": 6},
                           "confidence": "high"}], "avoid": ["No carousels."], "forbid": ["Northwind Parcel"]}
    gpath = os.path.join(tmp, "generic.json")
    json.dump(generic, open(gpath, "w"))
    lint_p = cli("lint", gpath)
    brief_p = cli("brief", gpath, "--for", "ui", "-o", "-")
    render_p = cli("render", gpath, "-o", "-")
    chk = cli("check", os.path.join(tmp, "sibling.md"), "--card", gpath)
    ok = (lint_p.returncode == 0 and "large whitespace" in brief_p.stdout and "judged by hand" in render_p.stdout
          and "translated across media" in chk.stdout and chk.returncode == 1)
    check("generic route: hand card lints, renders, briefs and checks by axes", ok,
          f"lint exit {lint_p.returncode}; " + summary_line(chk.stdout))

    # malformed cards are input problems (exit 2), not lint failures
    bad = os.path.join(tmp, "bad-card.json")
    json.dump({"schema": "style-study/1", "name": "x", "traits": ["camera drifts"], "measured": {}}, open(bad, "w"))
    p = subprocess.run([sys.executable, STYLE, "lint", bad], capture_output=True, text=True)
    check("lint: a malformed card exits 2 with a message", p.returncode == 2 and "Traceback" not in p.stderr,
          f"exit {p.returncode}; {p.stderr.strip()[-120:]}")


# ---------------------------------------------------------------- media fixtures
def write_video(np, path, shots, fps=30, w=320, h=180, audio=None):
    """shots: dicts with dur, hue, sat, val, speed, seed, amp."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
                          "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "veryfast", path],
                         stdin=subprocess.PIPE)
    for s in shots:
        rng = np.random.default_rng(s["seed"])
        waves = [(rng.uniform(0.02, 0.09), rng.uniform(0.02, 0.09), rng.uniform(0, 6.28)) for _ in range(3)]
        base = hsv(s["hue"], s["sat"], s["val"])
        for k in range(int(round(s["dur"] * fps))):
            off = k * s["speed"]
            tex = sum(np.sin(fx * (xx + off) + fy * yy + ph) for fx, fy, ph in waves) / 3
            img = np.clip(np.array(base, np.float32)[None, None, :] * (1 + s.get("amp", 0.45) * tex[..., None]), 0, 1)
            p.stdin.write((img * 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()


def hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p_, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return [(v, t, p_), (q, v, p_), (p_, v, t), (p_, q, v), (t, p_, v), (v, p_, q)][i]


def shot_params(seed, n=14):
    rng = random.Random(seed)
    return [{"dur": rng.choice([0.6, 0.8, 1.0, 1.3, 1.7, 2.2, 2.8]), "hue": rng.random(), "sat": rng.uniform(0.3, 0.7),
             "val": rng.uniform(0.35, 0.85), "speed": rng.choice([0.0, 1.0, 2.0, 3.5]), "seed": rng.randrange(10 ** 6)}
            for _ in range(n)]


def check_video(np, tmp):
    durs = [1.0, 2.0, 0.5, 1.5, 3.0, 1.0, 2.5, 0.8, 1.2, 2.0]
    plan = [{"dur": d, "hue": (i * 0.37) % 1, "sat": 0.6, "val": 0.4 + 0.4 * (i % 2), "speed": 2.0, "seed": i}
            for i, d in enumerate(durs)]
    edit = os.path.join(tmp, "edit.mp4")
    write_video(np, edit, plan)
    import ss_media
    info, values, _ = ss_media.measure_video(edit)
    got = values["shot_length"]
    ok = len(got) == len(durs) and all(abs(a - b) <= 1 / 30 + 1e-6 for a, b in zip(got, durs))
    check("video: cuts within one frame on a known edit", ok, f"{info['cuts']} cuts; shots {[round(x, 2) for x in got]}")

    shots = shot_params(11)
    ref, copy, remake, sib, far = (os.path.join(tmp, f"{n}.mp4") for n in ("vref", "vcopy", "vremake", "vsib", "vfar"))
    write_video(np, ref, shots)
    shutil.copy(ref, copy)
    write_video(np, remake, [dict(s, seed=s["seed"] + 7) for s in shots])
    order = list(range(len(shots)))
    random.Random(3).shuffle(order)
    write_video(np, sib, [dict(shots[i], seed=shots[i]["seed"] + 13) for i in order])
    write_video(np, far, [{"dur": 7.0, "hue": 0.08, "sat": 0.9, "val": 0.95, "speed": 0.0, "seed": 5 + i, "amp": 0.1}
                          for i in range(3)])
    cli("measure", ref, "-o", os.path.join(tmp, "m-video.json"))
    cli("card", os.path.join(tmp, "m-video.json"), "-o", os.path.join(tmp, "video.json"),
        "--fingerprints", os.path.join(tmp, "video-fp.json"))
    run_pair(tmp, "video", copy, remake, sib, far)
    return os.path.join(tmp, "video.json")


def write_wav(np, path, x, sr=22050):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], 1) if x.ndim == 1 else x
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((st * 32767).astype("<i2").tobytes())


def click_track(np, bpm, secs, sr=22050, start=0.25, floor=0.0):
    x = (floor * np.random.default_rng(2).standard_normal(int(secs * sr))).astype(np.float32)
    t = start
    times = []
    rng = np.random.default_rng(1)
    while t < secs - 0.1:
        i = int(round(t * sr))
        n = int(0.012 * sr)
        x[i:i + n] += 0.6 * rng.standard_normal(n).astype(np.float32) * np.exp(-np.arange(n) / (0.003 * sr))
        times.append(t)
        t += 60 / bpm
    return x, times


def sections_audio(np, plan, seed, sr=22050):
    rng = np.random.default_rng(seed)
    out = []
    for kind, secs, f0 in plan:
        n = int(secs * sr)
        t = np.arange(n) / sr
        if kind == "tone":
            y = 0.3 * np.sin(2 * np.pi * f0 * t) + 0.1 * np.sin(2 * np.pi * 2 * f0 * t)
        elif kind == "noise":
            y = 0.15 * rng.standard_normal(n)
            if f0:
                y = np.convolve(y, np.ones(int(f0)) / int(f0), mode="same")
                y *= 3
        else:  # pulses
            y = np.zeros(n)
            step = int(sr * 60 / f0)
            for i in range(0, n - 400, step):
                y[i:i + 400] += 0.5 * rng.standard_normal(400) * np.exp(-np.arange(400) / 60)
        fade = np.minimum(1, np.minimum(np.arange(n), np.arange(n)[::-1]) / (0.01 * sr))
        out.append((y * fade).astype(np.float32))
    return np.concatenate(out)


def check_audio(np, tmp):
    import ss_media
    worst_bpm, errs = 0.0, []
    for bpm, floor in ((96.0, 0.0), (128.0, 0.0), (110.0, 0.01)):  # silence between clicks, then a noise floor
        x, times = click_track(np, bpm, 24.0, floor=floor)
        path = os.path.join(tmp, f"click{int(bpm)}.wav")
        write_wav(np, path, x)
        info, values, fp, onsets = ss_media.measure_audio(path, want_onsets=True)
        got = values.get("tempo", [0])[0]
        worst_bpm = max(worst_bpm, abs(got - bpm))
        for t in times:
            near = min(onsets, key=lambda o: abs(o - t)) if onsets else 99
            errs.append(near - t)
    errs.sort()
    med = errs[len(errs) // 2]
    worst = max(abs(e) for e in errs)
    check("audio: tempo within 1.5 BPM on click tracks", worst_bpm <= 1.5, f"worst error {worst_bpm:.2f} BPM")
    check("audio: onsets within 12 ms of the clicks", worst <= 0.012, f"median {med * 1000:+.1f} ms, worst {worst * 1000:.1f} ms")

    plan = [("tone", 4, 220), ("noise", 3, 0), ("pulses", 5, 150), ("tone", 4, 660), ("noise", 3, 12), ("pulses", 4, 95),
            ("tone", 3, 330), ("noise", 4, 4), ("pulses", 3, 200), ("tone", 4, 440)]
    ref, copy, sib, far = (os.path.join(tmp, f"{n}.wav") for n in ("aref", "acopy", "asib", "afar"))
    write_wav(np, ref, sections_audio(np, plan, 1))
    shutil.copy(ref, copy)
    order = list(range(len(plan)))
    random.Random(4).shuffle(order)
    write_wav(np, sib, sections_audio(np, [(k, s, f * 1.06 if k == "tone" else f) for k, s, f in (plan[i] for i in order)], 2))
    write_wav(np, far, sections_audio(np, [("tone", 12, 70), ("tone", 12, 82)], 3))
    cli("measure", ref, "-o", os.path.join(tmp, "m-audio.json"))
    cli("card", os.path.join(tmp, "m-audio.json"), "-o", os.path.join(tmp, "audio.json"),
        "--fingerprints", os.path.join(tmp, "audio-fp.json"))
    run_pair(tmp, "audio", copy, None, sib, far)
    # a piece cut from mid-track, off the one-second grid, and re-encoded: the usual way music is lifted
    excerpt = os.path.join(tmp, "aexcerpt.m4a")
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "7.4", "-t", "20", "-i", ref, "-c:a", "aac", "-b:a", "128k",
                        excerpt], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg could not cut the excerpt: {p.stderr.strip()[-300:]}")
    p = cli("check", excerpt, "--card", os.path.join(tmp, "audio.json"), "--fingerprints", os.path.join(tmp, "audio-fp.json"))
    check("audio check: a re-encoded 20 s excerpt from mid-track fails the pattern side", "PATTERN FAIL" in p.stdout,
          last_copy_line(p.stdout))
    # a loop: every bar repeats, so each second of an excerpt matches several places in the reference
    bar = sections_audio(np, [("tone", 1, 220), ("pulses", 1, 150), ("tone", 1, 330), ("noise", 1, 8)], 7)
    intro = sections_audio(np, [("noise", 4, 0)], 8)
    loop, loopx = os.path.join(tmp, "aloop.wav"), os.path.join(tmp, "aloopx.m4a")
    write_wav(np, loop, np.concatenate([intro] + [bar] * 8))
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "9.13", "-t", "20", "-i", loop, "-c:a", "aac", "-b:a", "128k",
                        loopx], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg could not cut the loop excerpt: {p.stderr.strip()[-300:]}")
    cli("measure", loop, "-o", os.path.join(tmp, "m-loop.json"))
    cli("card", os.path.join(tmp, "m-loop.json"), "-o", os.path.join(tmp, "loop.json"),
        "--fingerprints", os.path.join(tmp, "loop-fp.json"))
    p = cli("check", loopx, "--card", os.path.join(tmp, "loop.json"), "--fingerprints", os.path.join(tmp, "loop-fp.json"))
    check("audio check: an excerpt of a looped track is caught as reused audio", "of audio match" in p.stdout,
          last_copy_line(p.stdout))
    # fingerprints written before the quarter-second frames cannot be compared: the check must not pass
    fps = json.load(open(os.path.join(tmp, "audio-fp.json"), encoding="utf-8"))
    for r in fps["refs"]:
        r["fp"].pop("hop", None)
    stale = os.path.join(tmp, "audio-fp-old.json")
    json.dump(fps, open(stale, "w", encoding="utf-8"))
    p = cli("check", sib, "--card", os.path.join(tmp, "audio.json"), "--fingerprints", stale)
    check("audio check: old fingerprints fail the check and say reused audio was not checked",
          p.returncode == 1 and "older style-study" in p.stdout and "PATTERN PASS" not in p.stdout,
          next((l.strip() for l in p.stdout.splitlines() if l.startswith("PATTERN")), p.stdout.strip().splitlines()[-1]))
    return os.path.join(tmp, "audio.json")


def write_png(np, path, img):
    h, w, _ = img.shape
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-i", "-",
                        "-frames:v", "1", path], input=(np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
    if p.returncode:
        raise RuntimeError(f"ffmpeg could not write {path}")


def poster(np, seed, cx, cy, r, hue, w=240, h=160):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    bg = np.array(hsv(hue, 0.25, 0.9), np.float32)
    fg = np.array(hsv((hue + 0.5) % 1, 0.7, 0.35), np.float32)
    img = np.ones((h, w, 3), np.float32) * bg
    d = np.hypot(xx - cx * w, yy - cy * h)
    tex = 0.5 + 0.5 * np.sin(xx * rng.uniform(0.2, 0.5) + yy * rng.uniform(0.2, 0.5))
    mask = d < r * h
    img[mask] = fg * (0.6 + 0.4 * tex[mask][:, None])
    return img


def check_image(np, tmp):
    import ss_media
    a, b = os.path.join(tmp, "centred.png"), os.path.join(tmp, "corner.png")
    write_png(np, a, poster(np, 1, 0.5, 0.5, 0.42, 0.6))
    write_png(np, b, poster(np, 1, 0.12, 0.15, 0.12, 0.6))
    _, va, _ = ss_media.measure_images([a])
    _, vb, _ = ss_media.measure_images([b])
    ok = vb["negative_space"][0] > va["negative_space"][0] + 0.3 and vb["subject_offset"][0] > 0.5 > va["subject_offset"][0] + 0.3
    check("image: empty space and subject offset", ok,
          f"centred {va['negative_space'][0]:.2f}/{va['subject_offset'][0]:.2f}, corner {vb['negative_space'][0]:.2f}/{vb['subject_offset'][0]:.2f}")
    refs, sibs = [], []
    for i in range(5):
        p = os.path.join(tmp, f"iref{i}.png")
        write_png(np, p, poster(np, 10 + i, 0.3 + 0.1 * i, 0.4 + 0.05 * i, 0.22, (0.1 + 0.15 * i) % 1))
        refs.append(p)
        q = os.path.join(tmp, f"isib{i}.png")
        # new layouts: a mirrored copy of the reference's circle positions would be a recolour, and dHash says so
        write_png(np, q, poster(np, 50 + i, 0.25 + 0.125 * i, 0.3 if i % 2 else 0.7, 0.22, (0.55 + 0.15 * i) % 1))
        sibs.append(q)
    cli("measure", *refs, "-o", os.path.join(tmp, "m-image.json"))
    cli("card", os.path.join(tmp, "m-image.json"), "-o", os.path.join(tmp, "image.json"),
        "--fingerprints", os.path.join(tmp, "image-fp.json"))
    p = cli("check", refs[2], "--card", os.path.join(tmp, "image.json"), "--fingerprints", os.path.join(tmp, "image-fp.json"))
    check("image check: a copied image fails the pattern side", "PATTERN FAIL" in p.stdout, last_copy_line(p.stdout))
    jpg = os.path.join(tmp, "icopy-small.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", refs[1], "-vf", "scale=180:-2", "-q:v", "8", jpg], check=True)
    p = cli("check", jpg, "--card", os.path.join(tmp, "image.json"), "--fingerprints", os.path.join(tmp, "image-fp.json"))
    check("image check: a resized JPEG copy fails the pattern side", "PATTERN FAIL" in p.stdout, last_copy_line(p.stdout))
    odd = "subfile:-odd name.png"  # read as a protocol or an option unless passed to ffmpeg as file:
    shutil.copy(refs[0], os.path.join(tmp, odd))
    p = subprocess.run([sys.executable, STYLE, "measure", odd, "-o", "m-odd.json"], cwd=tmp, capture_output=True, text=True)
    check("image: a file name with a colon and a dash is read as a file", p.returncode == 0,
          p.stdout.strip().splitlines()[0] if p.returncode == 0 else p.stderr.strip()[-160:])
    p = cli("check", *sibs, "--card", os.path.join(tmp, "image.json"), "--fingerprints", os.path.join(tmp, "image-fp.json"))
    check("image check: a sibling set passes both sides", "STYLE PASS" in p.stdout and "PATTERN PASS" in p.stdout,
          summary_line(p.stdout))
    return os.path.join(tmp, "image.json")


# ---------------------------------------------------------------- documents: fixture writers
XA = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
XP = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
XR = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
XW = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
XS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def png(seed, w=48, h=36, level=6):
    """A small PNG of coloured rectangles, written without numpy; `level` changes the bytes, not the picture."""
    rng = random.Random(seed)
    base = [rng.randrange(256) for _ in range(3)]
    rects = [(rng.randrange(w), rng.randrange(h), rng.randrange(6, 24), rng.randrange(5, 18),
              [rng.randrange(256) for _ in range(3)]) for _ in range(6)]
    rows = []
    for y in range(h):
        row = bytearray(b"\x00")
        for x in range(w):
            c = base
            for rx, ry, rw, rh, col in rects:
                if rx <= x < rx + rw and ry <= y < ry + rh:
                    c = col
            row += bytes(c)
        rows.append(bytes(row))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), level)) + chunk(b"IEND", b""))


def rels_xml(items):
    return (HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="{i}" Type="{RT}{t}" Target="{g}"/>' for i, t, g in items) + "</Relationships>")


def write_zip(path, parts, mimetype=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if mimetype:
            z.writestr(zipfile.ZipInfo("mimetype"), mimetype)  # stored, first: ODF and EPUB want it so
        for name, data in parts.items():
            z.writestr(name, data)


def types_xml(main):
    return (HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
            f'<Override PartName="/{main[0]}" ContentType="{main[1]}"/></Types>')


def theme_xml(major, minor, accents):
    acc = "".join(f'<a:accent{i + 1}><a:srgbClr val="{c}"/></a:accent{i + 1}>' for i, c in enumerate(accents))
    return (HEAD + f'<a:theme {XA} name="T"><a:themeElements><a:clrScheme name="C">'
            '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
            '<a:dk2><a:srgbClr val="1F2A44"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>' + acc +
            '<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>'
            f'<a:fontScheme name="F"><a:majorFont><a:latin typeface="{major}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
            f'<a:minorFont><a:latin typeface="{minor}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
            '<a:fmtScheme name="M"/></a:themeElements></a:theme>')


GRP = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'


def xfrm(x, y, w, h):
    return f'<a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm>'


def ph_sp(i, ph, paras, box=None, body_pr=""):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Shape {i}"/><p:cNvSpPr/><p:nvPr>{ph}</p:nvPr></p:nvSpPr>'
            f'<p:spPr>{xfrm(*box) if box else ""}</p:spPr><p:txBody><a:bodyPr>{body_pr}</a:bodyPr><a:lstStyle/>{paras}</p:txBody></p:sp>')


def para_xml(text, rpr="", ppr=""):
    return f'<a:p>{ppr}<a:r><a:rPr lang="en-US"{rpr}<a:t>{esc(text)}</a:t></a:r></a:p>'


def write_pptx(path, slides, size=(12192000, 6858000), sizes=(4400, 2800), fonts=("Aptos Display", "Aptos"),
               accents=("2E7D32", "F57C00", "1565C0", "AD1457", "6A1B9A", "00838F")):
    """slides: dicts with title, bullets, title_sz, body_rpr, body_pr, bg (hex), full_rect (scheme colour),
    pictures (bytes), body_box (x, y, w, h fractions), hidden, plain (paragraphs with buNone)."""
    W, H = size
    tbox = (0.07 * W, 0.05 * H, 0.86 * W, 0.19 * H)
    bbox = (0.07 * W, 0.27 * H, 0.86 * W, 0.63 * H)
    master = (HEAD + f'<p:sldMaster {XA} {XP} {XR}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>'
              f'<p:spTree>{GRP}' + ph_sp(2, '<p:ph type="title"/>', para_xml("Master title", "/>"), tbox)
              + ph_sp(3, '<p:ph type="body" idx="1"/>', para_xml("Master text", "/>"), bbox) + '</p:spTree></p:cSld>'
              '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
              'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
              '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles>'
              f'<p:titleStyle><a:lvl1pPr><a:defRPr sz="{sizes[0]}"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
              '<a:latin typeface="+mj-lt"/></a:defRPr></a:lvl1pPr></p:titleStyle>'
              f'<p:bodyStyle><a:lvl1pPr marL="228600" indent="-228600"><a:buChar char="&#8226;"/><a:defRPr sz="{sizes[1]}">'
              '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr>'
              '</p:bodyStyle><p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle></p:txStyles></p:sldMaster>')
    layout = (HEAD + f'<p:sldLayout {XA} {XP} {XR}><p:cSld name="Title and Content"><p:spTree>{GRP}'
              + ph_sp(2, '<p:ph type="title"/>', "<a:p/>") + ph_sp(3, '<p:ph idx="1"/>', "<a:p/>")
              + '</p:spTree></p:cSld></p:sldLayout>')
    parts = {"[Content_Types].xml": types_xml(("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument."
                                                "presentationml.presentation.main+xml")),
             "_rels/.rels": rels_xml([("rId1", "officeDocument", "ppt/presentation.xml")]),
             "ppt/slideMasters/slideMaster1.xml": master,
             "ppt/slideMasters/_rels/slideMaster1.xml.rels": rels_xml([("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
                                                                       ("rId2", "theme", "../theme/theme1.xml")]),
             "ppt/slideLayouts/slideLayout1.xml": layout,
             "ppt/slideLayouts/_rels/slideLayout1.xml.rels": rels_xml([("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]),
             "ppt/theme/theme1.xml": theme_xml(fonts[0], fonts[1], accents)}
    pres_rels = [("rIdM", "slideMaster", "slideMasters/slideMaster1.xml")]
    ids = []
    pic_n = 0
    for k, s in enumerate(slides, 1):
        shapes, rels = [], [("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")]
        if s.get("full_rect"):
            shapes.append(f'<p:sp><p:nvSpPr><p:cNvPr id="9" name="Back"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>{xfrm(0, 0, W, H)}'
                          f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:schemeClr val="{s["full_rect"]}"/>'
                          '</a:solidFill></p:spPr></p:sp>')
        if s.get("title"):
            sz = f' sz="{s["title_sz"]}"' if s.get("title_sz") else ""
            shapes.append(ph_sp(2, '<p:ph type="title"/>', para_xml(s["title"], sz + "/>")))
        paras = "".join(para_xml(b, s.get("body_rpr", "/>")) for b in s.get("bullets", []))
        paras += "".join(para_xml(b, s.get("body_rpr", "/>"), '<a:pPr><a:buNone/></a:pPr>') for b in s.get("plain", []))
        if paras:
            box = tuple(f * d for f, d in zip(s["body_box"], (W, H, W, H))) if s.get("body_box") else None
            shapes.append(ph_sp(3, '<p:ph idx="1"/>', paras, box, s.get("body_pr", "")))
        for j, data in enumerate(s.get("pictures", [])):
            pic_n += 1
            name = f"image{pic_n}.png"
            parts[f"ppt/media/{name}"] = data
            rels.append((f"rIdP{j}", "image", f"../media/{name}"))
            shapes.append(f'<p:pic><p:nvPicPr><p:cNvPr id="{20 + j}" name="Picture {j}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
                          f'<p:blipFill><a:blip r:embed="rIdP{j}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
                          f'<p:spPr>{xfrm(0.62 * W, 0.3 * H + j * 0.1 * H, 0.3 * W, 0.4 * H)}<a:prstGeom prst="rect"><a:avLst/>'
                          '</a:prstGeom></p:spPr></p:pic>')
        bg = (f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{s["bg"]}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
              if s.get("bg") else "")
        show = ' show="0"' if s.get("hidden") else ""
        parts[f"ppt/slides/slide{k}.xml"] = (HEAD + f'<p:sld {XA} {XP} {XR}{show}><p:cSld>{bg}<p:spTree>{GRP}{"".join(shapes)}'
                                             '</p:spTree></p:cSld></p:sld>')
        parts[f"ppt/slides/_rels/slide{k}.xml.rels"] = rels_xml(rels)
        pres_rels.append((f"rId{k}", "slide", f"slides/slide{k}.xml"))
        ids.append(f'<p:sldId id="{255 + k}" r:id="rId{k}"/>')
    parts["ppt/presentation.xml"] = (HEAD + f'<p:presentation {XA} {XP} {XR}><p:sldMasterIdLst><p:sldMasterId id="2147483648" '
                                     f'r:id="rIdM"/></p:sldMasterIdLst><p:sldIdLst>{"".join(ids)}</p:sldIdLst>'
                                     f'<p:sldSz cx="{W}" cy="{H}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
    parts["ppt/_rels/presentation.xml.rels"] = rels_xml(pres_rels)
    write_zip(path, parts)


def write_docx(path, blocks, body_half=22, heading_half=36, line=276, after=160, margin=1440, font="Georgia", pictures=()):
    """blocks: ("h", text), ("p", [(text, bold)], {jc, after}), ("li", text), ("table", [[cell]]), ("pic", index)."""
    body, rels = [], [("rIdS", "styles", "styles.xml")]
    parts = {}
    for b in blocks:
        if b[0] == "h":
            body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{esc(b[1])}</w:t></w:r></w:p>')
        elif b[0] == "p":
            opts = b[2] if len(b) > 2 else {}
            ppr = (f'<w:jc w:val="{opts["jc"]}"/>' if opts.get("jc") else "") + (
                f'<w:spacing w:after="{opts["after"]}"/>' if "after" in opts else "")
            runs = "".join(f'<w:r>{"<w:rPr><w:b/></w:rPr>" if bold else ""}<w:t xml:space="preserve">{esc(t)}</w:t></w:r>'
                           for t, bold in b[1])
            body.append(f'<w:p>{"<w:pPr>" + ppr + "</w:pPr>" if ppr else ""}{runs}</w:p>')
        elif b[0] == "li":
            body.append('<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/>'
                        f'</w:numPr></w:pPr><w:r><w:t>{esc(b[1])}</w:t></w:r></w:p>')
        elif b[0] == "table":
            rows = "".join("<w:tr>" + "".join(f'<w:tc><w:p><w:r><w:t>{esc(c)}</w:t></w:r></w:p></w:tc>' for c in row) + "</w:tr>"
                           for row in b[1])
            body.append(f"<w:tbl>{rows}</w:tbl>")
        elif b[0] == "pic":
            rid = f"rIdP{b[1]}"
            parts[f"word/media/image{b[1]}.png"] = pictures[b[1]]
            rels.append((rid, "image", f"media/image{b[1]}.png"))
            body.append('<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/'
                        'wordprocessingDrawing"><wp:extent cx="1828800" cy="1371600"/><wp:docPr id="1" name="Picture"/>'
                        f'<a:graphic {XA}><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr>'
                        '<pic:cNvPr id="1" name="p.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
                        f'<a:blip r:embed="{rid}"/></pic:blipFill><pic:spPr/></pic:pic></a:graphicData></a:graphic>'
                        '</wp:inline></w:drawing></w:r></w:p>')
    body.append(f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="{margin}" w:bottom="1440" '
                f'w:left="{margin}"/></w:sectPr>')
    styles = (HEAD + f'<w:styles {XW}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>'
              f'<w:sz w:val="{body_half}"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="{after}" '
              f'w:line="{line}" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
              f'<w:pPr><w:spacing w:after="240"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="{heading_half}"/>'
              '</w:rPr></w:style><w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
              '<w:basedOn w:val="Normal"/></w:style></w:styles>')
    parts.update({"[Content_Types].xml": types_xml(("word/document.xml", "application/vnd.openxmlformats-officedocument."
                                                     "wordprocessingml.document.main+xml")),
                  "_rels/.rels": rels_xml([("rId1", "officeDocument", "word/document.xml")]),
                  "word/document.xml": HEAD + f'<w:document {XW} {XR}><w:body>{"".join(body)}</w:body></w:document>',
                  "word/styles.xml": styles, "word/_rels/document.xml.rels": rels_xml(rels)})
    write_zip(path, parts)


def col_name(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheets, bold_header=True, font="Calibri"):
    """sheets: dicts with name, rows (cells: str, number, ("=", formula, value) or ("3dp", number)), merged, hidden, chart."""
    strings, index = [], {}
    parts = {}
    wb_rels, entries = [("rIdS", "styles", "styles.xml"), ("rIdT", "sharedStrings", "sharedStrings.xml")], []
    for k, sh in enumerate(sheets, 1):
        rows_xml = []
        for r, row in enumerate(sh["rows"], 1):
            cells = []
            for c, v in enumerate(row, 1):
                ref = f"{col_name(c)}{r}"
                if v is None:
                    continue
                if isinstance(v, str):
                    if v not in index:
                        index[v] = len(strings)
                        strings.append(v)
                    style = ' s="1"' if r == 1 and bold_header else ""
                    cells.append(f'<c r="{ref}" t="s"{style}><v>{index[v]}</v></c>')
                elif isinstance(v, tuple) and v[0] == "=":
                    cells.append(f'<c r="{ref}" s="3"><f>{esc(v[1])}</f><v>{v[2]}</v></c>')
                elif isinstance(v, tuple) and v[0] == "3dp":
                    cells.append(f'<c r="{ref}" s="3"><v>{v[1]}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" s="2"><v>{v}</v></c>')
            rows_xml.append(f'<row r="{r}">{"".join(cells)}</row>')
        merged = sh.get("merged", [])
        merge_xml = (f'<mergeCells count="{len(merged)}">' + "".join(f'<mergeCell ref="{m}"/>' for m in merged) + "</mergeCells>"
                     if merged else "")
        drawing = ""
        if sh.get("chart"):
            drawing = '<drawing r:id="rIdD"/>'
            parts[f"xl/worksheets/_rels/sheet{k}.xml.rels"] = rels_xml([("rIdD", "drawing", f"../drawings/drawing{k}.xml")])
            parts[f"xl/drawings/drawing{k}.xml"] = (
                HEAD + '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
                f'{XA} {XR}><xdr:twoCellAnchor><xdr:graphicFrame><a:graphic><a:graphicData '
                'uri="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart '
                'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" r:id="rIdC"/></a:graphicData></a:graphic>'
                '</xdr:graphicFrame></xdr:twoCellAnchor></xdr:wsDr>')
        parts[f"xl/worksheets/sheet{k}.xml"] = (HEAD + f'<worksheet {XS} {XR}><sheetData>{"".join(rows_xml)}</sheetData>'
                                                f'{merge_xml}{drawing}</worksheet>')
        wb_rels.append((f"rId{k}", "worksheet", f"worksheets/sheet{k}.xml"))
        state = ' state="hidden"' if sh.get("hidden") else ""
        entries.append(f'<sheet name="{esc(sh["name"])}" sheetId="{k}"{state} r:id="rId{k}"/>')
    parts.update({
        "[Content_Types].xml": types_xml(("xl/workbook.xml", "application/vnd.openxmlformats-officedocument."
                                          "spreadsheetml.sheet.main+xml")),
        "_rels/.rels": rels_xml([("rId1", "officeDocument", "xl/workbook.xml")]),
        "xl/workbook.xml": HEAD + f'<workbook {XS} {XR}><sheets>{"".join(entries)}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": rels_xml(wb_rels),
        "xl/sharedStrings.xml": HEAD + f'<sst {XS} count="{len(strings)}" uniqueCount="{len(strings)}">'
                                + "".join(f"<si><t>{esc(t)}</t></si>" for t in strings) + "</sst>",
        "xl/styles.xml": (HEAD + f'<styleSheet {XS}><numFmts count="1"><numFmt numFmtId="164" formatCode="0.000"/></numFmts>'
                          f'<fonts count="2"><font><sz val="11"/><name val="{font}"/></font><font><b/><sz val="11"/>'
                          f'<name val="{font}"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill>'
                          '<fill><patternFill patternType="gray125"/></fill></fills><cellXfs count="4">'
                          '<xf numFmtId="0" fontId="0" fillId="0"/><xf numFmtId="0" fontId="1" fillId="0"/>'
                          '<xf numFmtId="2" fontId="0" fillId="0"/><xf numFmtId="164" fontId="0" fillId="0"/></cellXfs></styleSheet>')})
    write_zip(path, parts)


ODF_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
          'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
          'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
          'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
          'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
          'xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0" '
          'xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0" '
          'xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.3"')
ODF_MIME = {"text": "application/vnd.oasis.opendocument.text", "presentation": "application/vnd.oasis.opendocument.presentation",
            "spreadsheet": "application/vnd.oasis.opendocument.spreadsheet"}


def write_odf(path, kind, styles, automatic, body, pictures=None, flat=False):
    """An OpenDocument file: zipped (content.xml + styles.xml) or flat (one office:document)."""
    if flat:
        doc = (HEAD + f'<office:document {ODF_NS} office:mimetype="{ODF_MIME[kind]}"><office:styles>{styles}</office:styles>'
               f'<office:automatic-styles>{automatic}</office:automatic-styles><office:body><office:{kind}>{body}'
               f'</office:{kind}></office:body></office:document>')
        open(path, "w", encoding="utf-8").write(doc)
        return
    parts = {"META-INF/manifest.xml": HEAD + '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
             'manifest:version="1.3"><manifest:file-entry manifest:full-path="/" manifest:media-type="' + ODF_MIME[kind]
             + '"/></manifest:manifest>',
             "styles.xml": HEAD + f'<office:document-styles {ODF_NS}><office:styles>{styles}</office:styles>'
             f'<office:automatic-styles>{automatic}</office:automatic-styles></office:document-styles>',
             "content.xml": HEAD + f'<office:document-content {ODF_NS}><office:automatic-styles>{automatic}'
             f'</office:automatic-styles><office:body><office:{kind}>{body}</office:{kind}></office:body></office:document-content>'}
    for name, data in (pictures or {}).items():
        parts[name] = data
    write_zip(path, parts, ODF_MIME[kind])


def write_pdf(path, pages, size=(595, 842), nested=False):
    """A PDF with Helvetica text: pages are lists of (font size, y from the top, text).

    nested=True draws each page the way Canva exports do: the page scales by 0.24 and flips y, then calls a
    form XObject that scales by 3.125 and holds the text at size / 0.75, plus a second form with one picture.
    The sizes a reader should report are the same as the flat file's."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []

    def stream_obj(body, head=""):
        objs.append(f"<< {head} /Length {len(body)} >>\nstream\n".encode("latin-1") + body + b"endstream")
        return len(objs)
    for lines in pages:
        if not nested:
            stream = "".join(f"BT /F1 {sz} Tf 72 {size[1] - y} Td ({t}) Tj ET\n" for sz, y, t in lines).encode("latin-1")
            content = stream_obj(stream)
            resources = "<< /Font << /F1 3 0 R >> >>"
        else:
            pixels = stream_obj(bytes([200, 30, 30, 30, 200, 30, 30, 30, 200, 220, 220, 220]),
                                "/Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8")
            pic = stream_obj(b"q 100 0 0 100 0 0 cm /Im1 Do Q\n",
                             f"/Type /XObject /Subtype /Form /BBox [0 0 2480 3508] /Resources << /XObject << /Im1 {pixels} 0 R >> >>")
            text = "".join(f"BT /F1 {sz / 0.75:.4f} Tf 1 0 0 -1 96 {y / 0.75:.4f} Tm ({t}) Tj ET\n" for sz, y, t in lines)
            body = stream_obj(f"q 3.125 0 0 3.125 0 0 cm {text}Q /Pic Do\n".encode("latin-1"),
                              f"/Type /XObject /Subtype /Form /BBox [0 0 2480 3508] "
                              f"/Resources << /Font << /F1 3 0 R >> /XObject << /Pic {pic} 0 R >> >>")
            content = stream_obj(f"q .24 0 0 -.24 0 {size[1]} cm /X1 Do Q\n".encode("latin-1"))
            resources = f"<< /XObject << /X1 {body} 0 R >> >>"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {size[0]} {size[1]}] "
                    f"/Resources {resources} /Contents {content} 0 R >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + (o if isinstance(o, bytes) else o.encode("latin-1")) + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    open(path, "wb").write(bytes(out))



def md_to_docx(md_path, docx_path):
    """The same paragraphs and lists, saved as Word."""
    blocks = []
    for para in open(md_path, encoding="utf-8").read().strip().split("\n\n"):
        lines = para.splitlines()
        if all(l.startswith("- ") for l in lines):
            blocks += [("li", l[2:]) for l in lines]
        else:
            blocks.append(("p", [(" ".join(lines), False)]))
    write_docx(docx_path, blocks)


def check_review_cases(tmp, d):
    import ss_docs
    from ss_common import StyleError
    # a same-order rewrite saved as .docx is checked against a card learned from Markdown, and the reverse
    text_card, text_fp = os.path.join(tmp, "text.json"), os.path.join(tmp, "text-fp.json")
    remake_docx, sib_docx = os.path.join(d, "remake.docx"), os.path.join(d, "sibling.docx")
    md_to_docx(os.path.join(tmp, "remake.md"), remake_docx)
    md_to_docx(os.path.join(tmp, "sibling.md"), sib_docx)
    p = cli("check", remake_docx, "--card", text_card, "--fingerprints", text_fp)
    check("document check: a same-order rewrite saved as .docx fails against a Markdown card",
          p.returncode == 1 and "order" in p.stdout and "PATTERN FAIL" in p.stdout, last_copy_line(p.stdout))
    p = cli("check", sib_docx, "--card", text_card, "--fingerprints", text_fp)
    check("document check: a reshuffled sibling saved as .docx passes against a Markdown card",
          p.returncode == 0 and "PATTERN PASS" in p.stdout, summary_line(p.stdout))
    ref_docx = os.path.join(d, "ref-text.docx")
    md_to_docx(os.path.join(tmp, "ref.md"), ref_docx)
    cli("measure", ref_docx, "-o", os.path.join(d, "m-ref-text.json"))
    cli("card", os.path.join(d, "m-ref-text.json"), "-o", os.path.join(d, "ref-text.json"),
        "--fingerprints", os.path.join(d, "ref-text-fp.json"))
    p = cli("check", os.path.join(tmp, "remake.md"), "--card", os.path.join(d, "ref-text.json"),
            "--fingerprints", os.path.join(d, "ref-text-fp.json"))
    check("text check: a same-order rewrite in Markdown fails against a card learned from .docx",
          p.returncode == 1 and "order" in p.stdout, last_copy_line(p.stdout))

    # a part read many times counts once toward the unpacked limit (a master picture behind every slide)
    big = os.path.join(d, "repeat.zip")
    with zipfile.ZipFile(big, "w") as z:
        z.writestr("a.bin", b"x" * 300000)
    keep = ss_docs.MAX_TOTAL
    ss_docs.MAX_TOTAL = 1000000
    try:
        pk = ss_docs.Pack(big, "test")
        for _ in range(10):
            pk.bytes("a.bin")
        repeat_ok, why = True, "10 reads of a 0.3 MB part under a 1 MB limit"
    except StyleError as e:
        repeat_ok, why = False, str(e).replace(d, "")
    finally:
        ss_docs.MAX_TOTAL = keep
    check("documents: a part read many times counts once toward the size limit", repeat_ok, why)

    # a DTD is refused in any encoding, not only in UTF-8
    bad = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE a [<!ENTITY e "boom">]><a>&e;</a>'.encode("utf-16")
    try:
        ss_docs.parse_xml(bad, "utf16.xml")
        refused = False
    except StyleError:
        refused = True
    check("documents: XML with a DTD in UTF-16 is refused", refused, "refused" if refused else "parsed")

    # two monthly sheets share their month header and nothing else: no copy alarm on the words
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"]
    rng = random.Random(4)

    def monthly(path, labels):
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("Item," + ",".join(months) + "\n")
            for lab in labels:
                f.write(lab + "," + ",".join(str(rng.randrange(100, 999)) for _ in months) + "\n")
    ref_csv, new_csv = os.path.join(d, "ref-months.csv"), os.path.join(d, "new-months.csv")
    monthly(ref_csv, ["Rent", "Power", "Water", "Phone", "Travel", "Food", "Repairs", "Books"])
    monthly(new_csv, ["Seeds", "Tools", "Fuel", "Feed", "Labour", "Freight", "Fees", "Spares"])
    cli("measure", ref_csv, "-o", os.path.join(d, "m-months.json"))
    cli("card", os.path.join(d, "m-months.json"), "-o", os.path.join(d, "months.json"),
        "--fingerprints", os.path.join(d, "months-fp.json"))
    p = cli("check", new_csv, "--card", os.path.join(d, "months.json"), "--fingerprints", os.path.join(d, "months-fp.json"))
    check("sheet check: a shared month header is not a copied text", "shares a run" not in p.stdout, last_copy_line(p.stdout))
    # while a long note copied into a cell still is
    note = ("Figures are shown before tax and include every branch that reported by the end of the second week of "
            "the following month")
    with open(new_csv, "a", encoding="utf-8") as f:
        f.write(f"\"{note}\"\n")
    with open(ref_csv, "a", encoding="utf-8") as f:
        f.write(f"\"{note}\"\n")
    cli("measure", ref_csv, "-o", os.path.join(d, "m-months.json"))
    cli("card", os.path.join(d, "m-months.json"), "-o", os.path.join(d, "months.json"),
        "--fingerprints", os.path.join(d, "months-fp.json"))
    p = cli("check", new_csv, "--card", os.path.join(d, "months.json"), "--fingerprints", os.path.join(d, "months-fp.json"))
    check("sheet check: a long note copied into a cell is still found", "shares a run" in p.stdout, last_copy_line(p.stdout))

# ---------------------------------------------------------------- documents: plans for the copy scenarios
def deck_slides(plan, bank, seed, pic_seed):
    rng = random.Random(seed)
    out = []
    for i, s in enumerate(plan):
        out.append({"title": sentence(rng, bank, s["title"])[:-1],
                    "bullets": [sentence(rng, bank, n)[:-1] for n in s["bullets"]],
                    "pictures": [png(pic_seed + i)] if s["picture"] else [],
                    "body_box": (0.07, 0.27, s["body_w"], 0.6), "bg": s["bg"]})
    return out


def deck_plan(seed, n=14):
    rng = random.Random(seed)
    return [{"title": rng.randrange(2, 6), "bullets": [rng.randrange(3, 10) for _ in range(rng.randrange(1, 6))],
             "picture": rng.random() < 0.35, "body_w": rng.choice([0.45, 0.6, 0.75, 0.86]),
             "bg": "E7E6E6" if rng.random() < 0.3 else None} for _ in range(n)]


def doc_blocks(plan, bank, seed, pictures):
    rng = random.Random(seed)
    out, k = [], 0
    for i, para in enumerate(plan):
        if i % 5 == 0:
            out.append(("h", sentence(rng, bank, 3)[:-1]))
        if para and para[0] == "list":
            out += [("li", sentence(rng, bank, 4)[:-1]) for _ in range(para[1])]
        else:
            out.append(("p", [(" ".join(sentence(rng, bank, n, q) for n, q in para), False)]))
        if i % 7 == 3 and k < len(pictures):
            out.append(("pic", k))
            k += 1
    return out


def book_plan(seed, n=8):
    rng = random.Random(seed)
    return [{"cols": rng.randrange(2, 9), "rows": rng.randrange(4, 26), "formula": rng.random() < 0.5} for _ in range(n)]


def book_sheets(plan, bank, seed):
    rng = random.Random(seed)
    sheets = []
    for i, p in enumerate(plan):
        rows = [[sentence(rng, bank, 1)[:-1] for _ in range(p["cols"])]]
        for r in range(2, p["rows"] + 1):
            row = [sentence(rng, bank, 2)[:-1]] + [round(rng.uniform(1, 999), 2) for _ in range(p["cols"] - 1)]
            if p["formula"]:
                row[-1] = ("=", f"SUM(B{r}:{col_name(p['cols'] - 1)}{r})", 1)
            rows.append(row)
        sheets.append({"name": f"Sheet {i + 1}", "rows": rows})
    return sheets


# ---------------------------------------------------------------- documents: checks
def near(a, b, tol=1e-3):
    return a is not None and b is not None and abs(a - b) <= tol


def nears(xs, ys, tol=1e-3):
    return xs is not None and len(xs) == len(ys) and all(near(x, y, tol) for x, y in zip(xs, ys))


def check_documents(tmp, np=None):
    import ss_docs
    from ss_common import StyleError
    d = os.path.join(tmp, "docs")
    os.makedirs(d, exist_ok=True)

    # PowerPoint: inheritance from layout, master and theme; backgrounds; hidden slides; shrink-to-fit
    known = os.path.join(d, "known.pptx")
    write_pptx(known, [
        {"title": "Alpha beta gamma", "bullets": ["one two three four five"] * 4},
        {"title": "Dark room", "title_sz": 4000, "bg": "101820", "body_pr": '<a:normAutofit fontScale="50000"/>',
         "body_rpr": '><a:solidFill><a:schemeClr val="bg1"/></a:solidFill></a:rPr>', "bullets": ["light words on dark"],
         "plain": ["not a bullet here"]},
        {"title": "Green field", "full_rect": "accent1", "pictures": [png(1)]},
        {"title": "Hidden slide words", "bullets": ["never counted at all"], "hidden": True}])
    info, v, fp, text = ss_docs.measure(known, "slides")
    g = (0.2126 * 0x2E + 0.7152 * 0x7D + 0.0722 * 0x32) / 255
    ok = (info["units"] == 3 and v.get("slide_text") == [23, 10, 2] and v.get("slide_bullets") == [4, 1, 0]
          and v.get("title_size") == [44, 40, 44] and v.get("body_size") == [28, 14] and v.get("slide_images") == [0, 0, 1]
          and nears(v.get("bg_luma"), [1.0, 0.0897, g]) and nears(v.get("type_ratio"), [44 / 28, 40 / 14])
          and nears(v.get("aspect"), [16 / 9]) and v.get("typefaces") == [2] and v.get("colors_used") == [1]
          and "Hidden slide words" in text)
    check("slides: text, bullets, sizes and backgrounds through layout, master and theme (a hidden slide is not measured, but its words reach the copy check)", ok,
          f"{info['units']} slides, text {v.get('slide_text')}, bullets {v.get('slide_bullets')}, title pt {v.get('title_size')}, "
          f"body pt {v.get('body_size')}, background {[round(x, 3) for x in v.get('bg_luma', [])]}, faces {v.get('typefaces')}")
    contrast = v.get("text_contrast", [])
    check("slides: text contrast against the slide's own background", len(contrast) == 3 and near(contrast[0], 21, 0.01)
          and contrast[1] > 15 and 3 < contrast[2] < 5, f"WCAG {[round(c, 1) for c in contrast]}")

    # Word: style chain, docDefaults, spacing inherited attribute by attribute, lists, tables, pictures, margins
    known_doc = os.path.join(d, "known.docx")
    write_docx(known_doc, [("h", "Overview of the plan"),
                           ("p", [("Alpha beta gamma delta. ", False), ("Bold run here.", True)], {"jc": "both"}),
                           ("p", [("Third sentence comes now. Fourth one ends it.", False)], {"after": 0}),
                           ("li", "Item one"), ("li", "Item two"), ("table", [["cell a", "cell b"]]), ("pic", 0)],
               pictures=[png(2)])
    info, v, fp, text = ss_docs.measure(known_doc, "document")
    # the heading is bold through its style; chars are counted without spaces at the ends of runs
    chars = [len("Overview of the plan"), len("Alpha beta gamma delta."), len("Bold run here."),
             len("Third sentence comes now. Fourth one ends it."), len("Item one"), len("Item two"), len("cell a"), len("cell b")]
    bold = (chars[0] + chars[2]) / sum(chars)
    ok = (v.get("body_size") == [11, 11, 11, 11] and nears(v.get("type_ratio"), [18 / 11])
          and nears(v.get("line_spacing"), [276 / 240] * 4) and nears(v.get("paragraph_space"), [8, 0, 8, 8])
          and nears(v.get("margin_share"), [2880 / 11906]) and nears(v.get("justified_share"), [0.5])
          and nears(v.get("image_rate"), [2.5]) and nears(v.get("table_rate"), [2.5]) and v.get("typefaces") == [1]
          and v.get("sentence_length") == [4, 3, 4, 4, 2, 2] and nears(v.get("bold_share"), [bold]))
    check("document: Word styles, inherited spacing, lists, tables, pictures and margins", ok,
          f"body pt {v.get('body_size')}, line {v.get('line_spacing')}, after {v.get('paragraph_space')}, "
          f"margins {[round(x, 3) for x in v.get('margin_share', [])]}, sentences {v.get('sentence_length')}, "
          f"bold {[round(x, 3) for x in v.get('bold_share', [])]}")

    # Excel: shared strings, number formats, formulas, merged ranges, charts, hidden sheets
    known_xl = os.path.join(d, "known.xlsx")
    write_xlsx(known_xl, [{"name": "Data", "chart": True, "merged": ["A5:C5"],
                           "rows": [["Name", "Score", "Double"], ["Ann", 1.5, ("=", "B2*2", 3)], ["Bo", 2.25, ("=", "B3*2", 4.5)],
                                    ["Cy", 3, ("=", "B4*2", 6)], ["Total row"]]},
                          {"name": "Secret", "hidden": True, "rows": [["never"], ["read"]]}])
    info, v, fp, text = ss_docs.measure(known_xl, "sheet")
    ok = (info["units"] == 1 and v.get("sheet_columns") == [3] and v.get("sheet_rows") == [5]
          and nears(v.get("numeric_share"), [6 / 13]) and nears(v.get("formula_share"), [3 / 13])
          and v.get("decimals") == [2, 3, 2, 3, 2, 3] and v.get("header_styled") == [1.0] and v.get("merged_rate") == [1]
          and v.get("chart_rate") == [1] and "never" in text)
    check("sheet: numbers, formulas, number formats, merges and charts (a hidden sheet is not measured, but its words reach the copy check)", ok,
          f"{info['units']} sheet, {v.get('sheet_columns')} x {v.get('sheet_rows')}, numeric {v.get('numeric_share')}, "
          f"formulas {v.get('formula_share')}, decimals {v.get('decimals')}, charts {v.get('chart_rate')}")

    # OpenDocument: zipped text and slides, flat spreadsheet
    odt = os.path.join(d, "known.odt")
    write_odf(odt, "text",
              '<style:default-style style:family="paragraph"><style:text-properties fo:font-size="12pt" style:font-name="Lora"/>'
              '</style:default-style><style:style style:name="Heading_1" style:family="paragraph"><style:text-properties '
              'fo:font-size="20pt" fo:font-weight="bold"/></style:style>',
              '<style:style style:name="P1" style:family="paragraph"><style:paragraph-properties fo:text-align="justify" '
              'fo:line-height="150%" fo:margin-bottom="0.5cm"/></style:style><style:style style:name="T1" style:family="text">'
              '<style:text-properties fo:font-weight="bold"/></style:style><style:page-layout style:name="pm1">'
              '<style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" fo:margin-left="2cm" '
              'fo:margin-right="2cm"/></style:page-layout>',
              '<text:h text:style-name="Heading_1" text:outline-level="1">A heading</text:h>'
              '<text:p text:style-name="P1">One two three. <text:span text:style-name="T1">Four five.</text:span> Six seven.</text:p>'
              '<text:list><text:list-item><text:p>Listed item</text:p></text:list-item></text:list>'
              '<table:table><table:table-row><table:table-cell><text:p>cell</text:p></table:table-cell></table:table-row></table:table>'
              '<text:p><draw:frame><draw:image xlink:href="Pictures/a.png"/></draw:frame></text:p>',
              {"Pictures/a.png": png(3)})
    info, v, fp, text = ss_docs.measure(odt, "document")
    ok = (nears(v.get("line_spacing"), [1.5, 1.0]) and nears(v.get("paragraph_space"), [14.173, 0.0], 0.01)
          and nears(v.get("type_ratio"), [20 / 12]) and nears(v.get("margin_share"), [4 / 21])
          and nears(v.get("justified_share"), [1.0]) and v.get("image_rate") == [5.0] and v.get("table_rate") == [5.0]
          and v.get("sentence_length") == [3, 2, 2, 2] and fp.get("media"))
    check("document: OpenDocument text styles, page and pictures", ok,
          f"line {v.get('line_spacing')}, after {[round(x, 2) for x in v.get('paragraph_space', [])]}, "
          f"ratio {v.get('type_ratio')}, margins {[round(x, 3) for x in v.get('margin_share', [])]}, sentences {v.get('sentence_length')}")
    odp = os.path.join(d, "known.odp")
    write_odf(odp, "presentation",
              '<style:style style:name="Default-title" style:family="presentation"><style:text-properties fo:font-size="40pt"/>'
              '</style:style><style:style style:name="Default-outline1" style:family="presentation"><style:text-properties '
              'fo:font-size="24pt"/></style:style>',
              '<style:style style:name="dp1" style:family="drawing-page"><style:drawing-page-properties draw:fill="solid" '
              'draw:fill-color="#101820"/></style:style><style:style style:name="dp2" style:family="drawing-page">'
              '<style:drawing-page-properties presentation:visibility="hidden"/></style:style><style:page-layout style:name="PM1"><style:page-layout-properties '
              'fo:page-width="28cm" fo:page-height="15.75cm"/></style:page-layout>',
              '<draw:page draw:style-name="dp1"><draw:frame presentation:class="title" presentation:style-name="Default-title" '
              'svg:x="1cm" svg:y="1cm" svg:width="26cm" svg:height="3cm"><draw:text-box><text:p>Slide title words</text:p>'
              '</draw:text-box></draw:frame><draw:frame presentation:class="outline" presentation:style-name="Default-outline1" '
              'svg:x="1cm" svg:y="5cm" svg:width="26cm" svg:height="9cm"><draw:text-box><text:list><text:list-item><text:p>'
              'First point here</text:p></text:list-item><text:list-item><text:p>Second point here</text:p></text:list-item>'
              '</text:list></draw:text-box></draw:frame></draw:page><draw:page><draw:frame presentation:class="title" '
              'presentation:style-name="Default-title" svg:x="1cm" svg:y="1cm" svg:width="26cm" svg:height="3cm"><draw:text-box>'
              '<text:p>Plain</text:p></draw:text-box></draw:frame></draw:page><draw:page draw:style-name="dp2"><draw:frame '
              'presentation:class="title" presentation:style-name="Default-title" svg:x="1cm" svg:y="1cm" svg:width="26cm" '
              'svg:height="3cm"><draw:text-box><text:p>Hidden page words</text:p></draw:text-box></draw:frame></draw:page>')
    info, v, fp, text = ss_docs.measure(odp, "slides")
    ok = (info["units"] == 2 and v.get("slide_text") == [9, 1] and v.get("slide_bullets") == [2, 0]
          and v.get("title_size") == [40, 40] and v.get("body_size") == [24] and nears(v.get("bg_luma"), [0.0897, 1.0])
          and nears(v.get("aspect"), [28 / 15.75]) and "Hidden page words" in text)
    check("slides: OpenDocument presentation (a hidden page is not measured, but its words reach the copy check)", ok, f"text {v.get('slide_text')}, bullets {v.get('slide_bullets')}, "
          f"title pt {v.get('title_size')}, background {[round(x, 3) for x in v.get('bg_luma', [])]}")
    fods = os.path.join(d, "known.fods")
    write_odf(fods, "spreadsheet", '<number:number-style style:name="N2"><number:number number:decimal-places="2"/>'
              '</number:number-style>', '<style:style style:name="ce1" style:family="table-cell" style:data-style-name="N2"/>'
              '<style:style style:name="ta2" style:family="table"><style:table-properties table:display="false"/></style:style>',
              '<table:table table:name="T"><table:table-row><table:table-cell office:value-type="string"><text:p>Item</text:p>'
              '</table:table-cell><table:table-cell office:value-type="string"><text:p>Cost</text:p></table:table-cell>'
              '</table:table-row><table:table-row table:number-rows-repeated="2"><table:table-cell office:value-type="string">'
              '<text:p>Pen</text:p></table:table-cell><table:table-cell table:style-name="ce1" office:value-type="float" '
              'office:value="1.5" table:formula="of:=1+0.5"><text:p>1.50</text:p></table:table-cell></table:table-row>'
              '<table:table-row table:number-rows-repeated="1048570"><table:table-cell table:number-columns-repeated="1024"/>'
              '</table:table-row></table:table><table:table table:name="H" table:style-name="ta2"><table:table-row>'
              '<table:table-cell office:value-type="string"><text:p>Hidden cell words</text:p></table:table-cell>'
              '</table:table-row></table:table>', flat=True)
    info, v, fp, text = ss_docs.measure(fods, "sheet")
    ok = (v.get("sheet_columns") == [2] and v.get("sheet_rows") == [3] and nears(v.get("numeric_share"), [2 / 6])
          and nears(v.get("formula_share"), [2 / 6]) and v.get("decimals") == [2, 2] and info["units"] == 1
          and "Hidden cell words" in text)
    check("sheet: flat OpenDocument spreadsheet with repeated rows (a hidden table is not measured, but its words "
          "reach the copy check)", ok,
          f"{v.get('sheet_columns')} x {v.get('sheet_rows')}, numeric {v.get('numeric_share')}, decimals {v.get('decimals')}")

    # EPUB, RTF, CSV
    epub = os.path.join(d, "known.epub")
    chap = ('<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title>'
            '<style>p {{ margin: 0 }}</style></head><body><h1>{h}</h1><p>{a}</p><p>{b}</p>{extra}</body></html>')
    write_zip(epub, {"META-INF/container.xml": '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:'
                     'opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/'
                     'oebps-package+xml"/></rootfiles></container>',
                     "OEBPS/content.opf": '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                     '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="c2.xhtml" '
                     'media-type="application/xhtml+xml"/><item id="i1" href="img/a.png" media-type="image/png"/></manifest>'
                     '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>',
                     "OEBPS/c1.xhtml": chap.format(h="Part one", a="Short one. Then a longer second sentence.", b="Third here.",
                                                   extra='<img src="img/a.png"/>'),
                     "OEBPS/c2.xhtml": chap.format(h="Part two", a="Fourth sentence now.", b="Fifth and last one.",
                                                   extra="<table><tr><td>x</td></tr></table>"),
                     "OEBPS/img/a.png": png(4)}, "application/epub+zip")
    info, v, fp, text = ss_docs.measure(epub, "document")
    ok = (v.get("sentence_length") == [2, 5, 2, 3, 4] and v.get("image_rate") == [10 * 1 / 4] and v.get("table_rate") == [10 * 1 / 4]
          and len(fp.get("media", [])) == 1 and "margin" not in text)
    check("document: EPUB chapters in spine order, pictures and tables", ok,
          f"sentences {v.get('sentence_length')}, pictures {v.get('image_rate')}, tables {v.get('table_rate')}")
    rtf = os.path.join(d, "known.rtf")
    open(rtf, "wb").write(
        b"{\\rtf1\\ansi\\ansicpg874\\deff0{\\fonttbl{\\f0\\fnil\\fcharset222 Tahoma;}{\\f1\\froman Times New Roman;}}"
        b"{\\colortbl;\\red200\\green30\\blue30;}{\\*\\generator Hand 1.0;}{\\stylesheet{\\s0 Normal;}}\n"
        b"\\paperw11906\\paperh16838\\margl1440\\margr1440\n"
        b"\\pard\\outlinelevel0\\fs40\\b Heading here\\b0\\par\n"
        b"\\pard\\qj\\sl360\\slmult1\\sa200\\fs24 First sentence is here. {\\b Bold bit.} Third one.\\par\n"
        b"\\pard\\sa200\\fs24\\cf1 \\u3626?\\u3623?\\u3633?\\u3626?\\u3604?\\u3637? \\'a4\\'c3\\'d1\\'ba\\par\n"
        b"{\\*\\shppict{\\pict\\pngblip 89504e470d0a1a0a}}{\\nonshppict{\\pict\\wmetafile8 0100090000}}\\par\n}")
    info, v, fp, text = ss_docs.measure(rtf, "document")
    ok = ("สวัสดี ครับ" in text and nears(v.get("line_spacing"), [1.5, 1.0]) and nears(v.get("paragraph_space"), [10, 10])
          and v.get("body_size") == [12, 12] and nears(v.get("type_ratio"), [20 / 12]) and nears(v.get("justified_share"), [0.5])
          and nears(v.get("margin_share"), [2880 / 11906]) and v.get("colors_used") == [1] and v.get("image_rate") == [5.0]
          and "Hand" not in text and "Normal" not in text)
    check("document: RTF formatting, code page 874 and Unicode Thai, pictures", ok,
          f"Thai {'ok' if 'สวัสดี ครับ' in text else 'missing'}, line {v.get('line_spacing')}, after {v.get('paragraph_space')}, "
          f"pt {v.get('body_size')}, colours {v.get('colors_used')}, pictures {v.get('image_rate')}")
    csvp = os.path.join(d, "known.csv")
    open(csvp, "w", encoding="utf-8").write("name;score\nA;1.50\nB;2.25\nC;3\n")
    info, v, fp, text = ss_docs.measure(csvp, "sheet")
    check("sheet: CSV with a sniffed delimiter", v.get("sheet_columns") == [2] and nears(v.get("numeric_share"), [3 / 8])
          and v.get("decimals") == [2, 2, 0], f"{v.get('sheet_columns')} columns, numeric {v.get('numeric_share')}, "
          f"decimals {v.get('decimals')}")

    # the words of any document on the text route
    p = cli("measure", known_doc, "--medium", "text", "-o", os.path.join(d, "m-wordsonly.json"))
    m = json.load(open(os.path.join(d, "m-wordsonly.json"), encoding="utf-8"))
    check("text route: a .docx read for its words only", m["medium"] == "text" and m["refs"][0]["values"]["sentence_length"]
          == [4, 3, 4, 4, 2, 2], p.stdout.strip().splitlines()[0])

    # files that must be refused, and formats that need a converter
    evil = os.path.join(d, "evil.docx")
    write_zip(evil, {"word/document.xml": '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x "xxxxxxxx">]><w:document '
                     f'{XW}><w:body><w:p><w:r><w:t>&x;&x;</w:t></w:r></w:p></w:body></w:document>'})
    p = cli("measure", evil, "-o", os.path.join(d, "m-evil.json"), ok_codes=(2,))
    check("document: XML with a DTD or entities is refused", "refused" in p.stderr, p.stderr.strip()[-120:])
    old = ss_docs.MAX_PART
    try:
        ss_docs.MAX_PART = 1000
        try:
            ss_docs.measure(known, "slides")
            refused = False
        except StyleError as e:
            refused = "refused" in str(e)
    finally:
        ss_docs.MAX_PART = old
    check("document: a part bigger than the size limit is refused", refused, "MAX_PART lowered to 1000 bytes")
    key = os.path.join(d, "deck.key")
    open(key, "wb").write(b"PK\x03\x04 not really keynote")
    if ss_docs.soffice():
        skip("document: a missing converter is named", "LibreOffice is installed, so .key converts")
    else:
        p = cli("measure", key, "-o", os.path.join(d, "m-key.json"), ok_codes=(2,))
        check("document: a missing converter is named", "LibreOffice" in p.stderr, p.stderr.strip()[-120:])

    # third-party writers: macOS textutil turns the Word fixture into .doc, .odt and .rtf
    if shutil.which("textutil"):
        got = {}
        for fmt in ("doc", "odt", "rtf"):
            out = os.path.join(d, f"textutil.{fmt}")
            subprocess.run(["textutil", "-convert", fmt, known_doc, "-output", out], capture_output=True, check=True)
            try:
                got[fmt] = ss_docs.measure(out, "document")[1].get("sentence_length")
            except StyleError as e:
                got[fmt] = str(e)
        # textutil keeps the paragraphs and lists but drops heading styles (the heading comes back as a sentence) and,
        # in .doc, the table: the sentences of the prose must all come back, in order
        want = [4, 3, 4, 4, 2, 2]
        ok = all(isinstance(x, list) and any(x[i:i + len(want)] == want for i in range(len(x))) for x in got.values())
        check("document: .doc, .odt and .rtf written by textutil read the same sentences", ok,
              "; ".join(f"{k} {x}" for k, x in got.items()))
    else:
        skip("document: .doc, .odt and .rtf written by textutil", "textutil is macOS only")

    # PDF, when pypdf or pdftotext is there
    pdf = os.path.join(d, "known.pdf")
    write_pdf(pdf, [[(24, 80, "Big heading"), (12, 120, "First sentence here. Second one there."), (12, 140, "Third sentence.")],
                    [(12, 80, "Fourth sentence on page two."), (12, 100, "- a listed point")]])
    try:
        import pypdf  # noqa: F401
        have_pdf = "pypdf"
    except ImportError:
        have_pdf = "pdftotext" if shutil.which("pdftotext") else None
    if have_pdf:
        info, v, fp, text = ss_docs.measure(pdf, "document")
        ok = info.get("pages") == 2 and v.get("page_text") == [10, 8] and nears(v.get("aspect"), [595 / 842]) and "Big heading" in text
        if have_pdf == "pypdf":
            ok = ok and nears(v.get("type_ratio"), [2.0]) and v.get("sentence_length") == [3, 3, 2, 5, 3]
        check(f"document: PDF pages, text and headings ({have_pdf})", ok,
              f"pages {info.get('pages')}, text per page {v.get('page_text')}, ratio {v.get('type_ratio')}, "
              f"sentences {v.get('sentence_length')}")
        info, v, fp, text = ss_docs.measure(pdf, "slides")
        check("slides: a PDF read as a deck with --medium slides", info["units"] == 2 and v.get("slide_text") == [10, 8],
              f"{info['units']} slides, text {v.get('slide_text')}")
        cli("measure", pdf, "-o", os.path.join(d, "m-pdf.json"))
        cli("card", os.path.join(d, "m-pdf.json"), "-o", os.path.join(d, "pdf.json"), "--fingerprints", os.path.join(d, "pdf-fp.json"))
        p = cli("check", pdf, "--card", os.path.join(d, "pdf.json"), "--fingerprints", os.path.join(d, "pdf-fp.json"))
        check("document check: a PDF measures, cards and fails as its own copy", p.returncode == 1 and "PATTERN FAIL" in p.stdout,
              last_copy_line(p.stdout))
        if have_pdf == "pypdf":
            nested = os.path.join(d, "nested.pdf")
            write_pdf(nested, [[(24, 80, "Big heading"), (12, 120, "First sentence here. Second one there."),
                                (12, 140, "Third sentence.")]], nested=True)
            info, v, fp, text = ss_docs.measure(nested, "document")
            check("document: PDF text inside scaled form XObjects keeps its real size (a Canva export)",
                  nears(v.get("body_size"), [12.0]) and nears(v.get("type_ratio"), [2.0]) and len(fp.get("media", [])) == 1,
                  f"body {v.get('body_size')} pt, ratio {v.get('type_ratio')}, pictures {len(fp.get('media', []))}")
    else:
        skip("document: PDF", "needs pypdf (pip install pypdf) or poppler's pdftotext")

    # copy scenarios: same as the text route, one per document medium
    plan = deck_plan(4)
    write_pptx(os.path.join(d, "deck-ref.pptx"), deck_slides(plan, WORDS, 1, 100))
    shutil.copy(os.path.join(d, "deck-ref.pptx"), os.path.join(d, "deck-copy.pptx"))
    write_pptx(os.path.join(d, "deck-remake.pptx"), deck_slides(plan, WORDS2, 2, 200))
    shuffled = plan[:]
    random.Random(8).shuffle(shuffled)
    write_pptx(os.path.join(d, "deck-sibling.pptx"), deck_slides(shuffled, WORDS2, 3, 300))
    rng = random.Random(6)
    write_pptx(os.path.join(d, "deck-far.pptx"),
               [{"title": sentence(rng, WORDS2, 6)[:-1], "plain": [sentence(rng, WORDS2, 40) for _ in range(3)], "bg": "101820",
                 "body_rpr": '><a:solidFill><a:schemeClr val="bg1"/></a:solidFill></a:rPr>', "body_box": (0.02, 0.02, 0.96, 0.96)}
                for _ in range(10)], size=(9144000, 6858000), sizes=(6000, 1400), fonts=("Courier New", "Courier New"))
    deck_pair(d, "slides", "deck", ".pptx")

    tplan = text_plan(1)
    write_docx(os.path.join(d, "doc-ref.docx"), doc_blocks(tplan, WORDS, 1, [png(400 + i) for i in range(4)]),
               pictures=[png(400 + i) for i in range(4)])
    shutil.copy(os.path.join(d, "doc-ref.docx"), os.path.join(d, "doc-copy.docx"))
    write_docx(os.path.join(d, "doc-remake.docx"), doc_blocks(tplan, WORDS2, 2, [png(500 + i) for i in range(4)]),
               pictures=[png(500 + i) for i in range(4)])
    shuffled = tplan[:]
    random.Random(5).shuffle(shuffled)
    write_docx(os.path.join(d, "doc-sibling.docx"), doc_blocks(shuffled, WORDS2, 3, [png(600 + i) for i in range(4)]),
               pictures=[png(600 + i) for i in range(4)])
    rng = random.Random(9)
    write_docx(os.path.join(d, "doc-far.docx"), [("p", [(" ".join(sentence(rng, WORDS2, 40) for _ in range(30)), False)])],
               body_half=32, line=480, after=0, margin=720, font="Courier New")
    deck_pair(d, "document", "doc", ".docx")

    bplan = book_plan(3)
    write_xlsx(os.path.join(d, "book-ref.xlsx"), book_sheets(bplan, WORDS, 1))
    shutil.copy(os.path.join(d, "book-ref.xlsx"), os.path.join(d, "book-copy.xlsx"))
    write_xlsx(os.path.join(d, "book-remake.xlsx"), book_sheets(bplan, WORDS2, 2))
    shuffled = bplan[:]
    random.Random(2).shuffle(shuffled)
    write_xlsx(os.path.join(d, "book-sibling.xlsx"), book_sheets(shuffled, WORDS2, 3))
    rng = random.Random(7)
    write_xlsx(os.path.join(d, "book-far.xlsx"), [{"name": f"S{i}", "rows": [[sentence(rng, WORDS2, 3)[:-1] for _ in range(40)]
                                                                            for _ in range(3)]} for i in range(3)],
               bold_header=False, font="Courier New")
    deck_pair(d, "sheet", "book", ".xlsx")

    # a picture saved again with other bytes is still the reference's picture (needs numpy and ffmpeg)
    resaved = deck_slides(shuffled_deck(plan), WORDS2, 3, 300)
    first = next(i for i, s in enumerate(plan) if s["picture"])
    resaved[0]["pictures"] = [png(100 + first, level=1)]
    write_pptx(os.path.join(d, "deck-resaved.pptx"), resaved)
    same_bytes = png(100 + first, level=1) == png(100 + first)
    p = cli("check", os.path.join(d, "deck-resaved.pptx"), "--card", os.path.join(d, "slides.json"),
            "--fingerprints", os.path.join(d, "slides-fp.json"))
    if np is not None and shutil.which("ffmpeg"):
        check("slides check: a reference picture saved again with other bytes fails the pattern side",
              not same_bytes and "PATTERN FAIL" in p.stdout and "look like" in p.stdout, last_copy_line(p.stdout))
    else:
        check("slides check: without numpy, pictures are compared by bytes and the gap is said",
              "bytes only" in p.stdout, summary_line(p.stdout))

    # a line break inside a Word paragraph still ends a sentence, as it does in a Markdown file, even where the
    # lines meet on a number or an English word (a space there would not end a Thai sentence)
    br = os.path.join(d, "thai-break.docx")
    write_docx(br, [("p", [("ราคา 500 บาท", False), ("<BR>", False), ("จ่ายด้วย QR", False), ("<BR>", False),
                           ("ขอบคุณ Team", False)])])
    with zipfile.ZipFile(br) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts["word/document.xml"] = parts["word/document.xml"].replace(
        b'<w:r><w:t xml:space="preserve">&lt;BR&gt;</w:t></w:r>', b"<w:r><w:br/></w:r>")
    with zipfile.ZipFile(br, "w") as z:
        for n, data in parts.items():
            z.writestr(n, data)
    info, v, fp, text = ss_docs.measure(br, "document")
    check("document: a line break inside a Thai paragraph ends a sentence", v.get("sentence_length") == [10, 10, 10],
          f"sentences {v.get('sentence_length')}")

    # the copy check across writing media, sizes counted once, DTDs in any encoding, sheet labels
    check_review_cases(tmp, d)
    return [os.path.join(d, f"{m}.json") for m in ("slides", "document", "sheet")]


def shuffled_deck(plan):
    out = plan[:]
    random.Random(8).shuffle(out)
    return out


def deck_pair(d, medium, stem, ext):
    paths = {k: os.path.join(d, f"{stem}-{k}{ext}") for k in ("ref", "copy", "remake", "sibling", "far")}
    cli("measure", paths["ref"], "-o", os.path.join(d, f"m-{medium}.json"))
    cli("card", os.path.join(d, f"m-{medium}.json"), "-o", os.path.join(d, f"{medium}.json"),
        "--fingerprints", os.path.join(d, f"{medium}-fp.json"))
    run_pair(d, medium, paths["copy"], paths["remake"], paths["sibling"], paths["far"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", help="write fixtures here and keep them")
    a = ap.parse_args()
    tmp = a.keep or tempfile.mkdtemp(prefix="style-study-check-")
    os.makedirs(tmp, exist_ok=True)
    def section(name, fn, *args):
        try:
            return fn(*args)
        except Exception as e:  # report, do not hide, a crash; the other sections still run
            check(f"{name}: crashed", False, f"{type(e).__name__}: {e}")
            return None

    try:
        section("package", check_package)
        cards = []
        got = section("text", check_text, tmp)
        if got:
            cards.append(got[0])
            section("lint", check_lint, tmp, *got)
            section("contracts", check_contracts, tmp)
        try:
            import numpy as np
        except ImportError:
            np = None
        have_ffmpeg = shutil.which("ffmpeg") and shutil.which("ffprobe")
        if np is None or not have_ffmpeg:
            for name in ("video", "audio", "image"):
                skip(name, "needs numpy and ffmpeg: run this script with a Python that has numpy")
        else:
            for name, fn in (("video", check_video), ("audio", check_audio), ("image", check_image)):
                c = section(name, fn, np, tmp)
                if c:
                    cards.append(c)
        got = section("documents", check_documents, tmp, np if have_ffmpeg else None)
        if got:
            cards += [c for c in got if os.path.exists(c)]
        if cards:
            section("card and brief", check_card_and_brief, cards)
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    width = max(len(n) for _, n, _ in results)
    for status, name, detail in results:
        print(f"{status}  {name.ljust(width)}  {detail}")
    failed = sum(s == "FAIL" for s, _, _ in results)
    passed = sum(s == "PASS" for s, _, _ in results)
    print(f"check-skill: {passed} passed, {failed} failed, {sum(s == 'SKIP' for s, _, _ in results)} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
