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
              floor); a copied track fails; a
              reshuffled sibling passes                     (needs numpy and ffmpeg)
  image       negative space and subject offset move the right way; copied images fail; a sibling set
              passes                                        (needs numpy and ffmpeg)

Run with a Python that has numpy for the media checks; without it they print SKIP. Exit 1 on any failure.
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
import tempfile
import wave

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
    check("frontmatter", bool(fm) and name == os.path.basename(SKILL) and 0 < len(desc_text) <= 1024,
          f"name={name}, description {len(desc_text)} chars")
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
