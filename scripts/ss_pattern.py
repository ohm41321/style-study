"""The pattern side of a check: did new work take the reference's order or its material?

Style is a distribution and does not care about order; pattern is the order and the material itself.
So the copy check asks four questions, each answerable without the reference files (only
fingerprints.json is needed):

  order     does the new work's sequence of units (shots, paragraphs, seconds of sound, images) follow
            the reference's sequence more closely than shuffled versions of itself would? Each feature
            track is resampled on a 0-1 timeline, its overall arc (a quadratic trend) removed, and
            correlated with the reference's. A generic arc such as "builds to the end" is style and is
            removed before the test; the specific sequence is pattern.
  material  near-duplicate frames or images (dHash close and grey layout correlated), shared runs of text, or reused
            stretches of audio.
  palette   the same chromatic colour set (warning only: a palette can be a look or a brand).
  names     forbidden names from the card appearing in new text.
"""

import math
import random

from ss_common import mean, pearson

L = 32
PERMS = 300
ORDER_R = 0.5
ORDER_P = 0.02
MIN_UNITS = 5
HASH_BITS = 8  # dHash distance that counts as a near-duplicate when there is no layout to confirm it
HASH_WIDE = 12  # with layouts on both sides: a dHash this close is a candidate...
THUMB_R = 0.9  # ...and is a near-duplicate only if the grey layouts also correlate this well
TEXT_SPAN = {"en": 12, "th": 40}  # words / characters of shared run that count as copied
TEXT_SHARE = 0.05
AUDIO_RUN = 8  # seconds of matching consecutive audio
AUDIO_COS = 0.97
PALETTE_DE = 6.0


def resample(rows, weights, n=L):
    total = sum(weights)
    if total <= 0:
        weights = [1.0] * len(rows)
        total = float(len(rows))
    edges, acc = [], 0.0
    for w in weights:
        acc += w
        edges.append(acc)
    out, j = [], 0
    for k in range(n):
        t = (k + 0.5) / n * total
        while j < len(edges) - 1 and edges[j] < t:
            j += 1
        out.append(rows[j])
    return out


def detrend(track):
    """Residuals of a least-squares quadratic over x in [-1, 1]."""
    n = len(track)
    xs = [2 * (k + 0.5) / n - 1 for k in range(n)]
    # normal equations for a + b x + c x^2
    s = [sum(x ** p for x in xs) for p in range(5)]
    t = [sum(y * x ** p for x, y in zip(xs, track)) for p in range(3)]
    m = [[s[0], s[1], s[2]], [s[1], s[2], s[3]], [s[2], s[3], s[4]]]
    coef = solve3(m, t)
    if coef is None:
        mu = mean(track)
        return [y - mu for y in track]
    a, b, c = coef
    return [y - (a + b * x + c * x * x) for x, y in zip(xs, track)]


def solve3(m, v):
    a = [row[:] + [v[i]] for i, row in enumerate(m)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(a[r][i]))
        if abs(a[p][i]) < 1e-12:
            return None
        a[i], a[p] = a[p], a[i]
        for r in range(3):
            if r != i:
                f = a[r][i] / a[i][i]
                a[r] = [x - f * y for x, y in zip(a[r], a[i])]
    return [a[i][3] / a[i][i] for i in range(3)]


def tracks(seq_rows, weights):
    grid = resample(seq_rows, weights)
    nf = len(seq_rows[0])
    return [detrend([row[f] for row in grid]) for f in range(nf)]


def score(ref_tracks, new_rows, new_weights):
    nt = tracks(new_rows, new_weights)
    rs = [pearson(a, b) for a, b in zip(ref_tracks, nt)
          if max(a) - min(a) > 1e-9 and max(b) - min(b) > 1e-9]
    return mean(rs) if rs else 0.0


def order_test(ref_seq, new_seq, seed=7):
    """{'r':..., 'p':..., 'alarm':bool} or None when either sequence is too short to judge."""
    rr, rw = ref_seq["rows"], ref_seq.get("weights") or [1.0] * len(ref_seq["rows"])
    nr, nw = new_seq["rows"], new_seq.get("weights") or [1.0] * len(new_seq["rows"])
    if len(rr) < MIN_UNITS or len(nr) < MIN_UNITS or len(rr[0]) != len(nr[0]):
        return None
    ref_tracks = tracks(rr, rw)
    r_obs = score(ref_tracks, nr, nw)
    rng = random.Random(seed)
    idx = list(range(len(nr)))
    hits = 0
    for _ in range(PERMS):
        rng.shuffle(idx)
        if score(ref_tracks, [nr[i] for i in idx], [nw[i] for i in idx]) >= r_obs:
            hits += 1
    p = (hits + 1) / (PERMS + 1)
    return {"r": r_obs, "p": p, "alarm": r_obs >= ORDER_R and p <= ORDER_P}


def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _corr(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na > 0 and nb > 0 else 0.0


def duplicate_frames(ref_hashes, new_hashes, single=False, ref_thumbs=None, new_thumbs=None):
    """How many new frames/images are near-duplicates of some reference frame.

    dHash alone is noisy on flat graphics (UI, posters): most of its bits compare two near-equal cells. So
    when both sides carry layouts, a match needs a close hash AND a correlated layout; a photo that
    shares only a composition habit (sky above, ground below) fails the hash, and a flat graphic that
    shares only a few noisy hash bits fails the layout.
    """
    confirm = (ref_thumbs and new_thumbs and len(ref_thumbs) == len(ref_hashes) and len(new_thumbs) == len(new_hashes))
    matched = 0
    for i, h in enumerate(new_hashes):
        for j, r in enumerate(ref_hashes):
            d = hamming(h, r)
            if confirm:
                if d <= HASH_WIDE and _corr(new_thumbs[i], ref_thumbs[j]) >= THUMB_R:
                    break
            elif d <= HASH_BITS:
                break
        else:
            continue
        matched += 1
    n = len(new_hashes)
    need = 1 if single else max(2, math.ceil(0.2 * n))
    return {"matched": matched, "of": n, "alarm": n > 0 and matched >= need}


def _de(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def palette_match(ref_pal, new_pal):
    """Warn when every chromatic colour of the new palette has a twin in the reference palette."""
    chrom = lambda pal: [c for c in pal if math.hypot(c["lab"][1], c["lab"][2]) >= 12 and c["share"] >= 0.04]
    rc, nc = chrom(ref_pal), chrom(new_pal)
    if len(rc) < 2 or len(nc) < 2:
        return {"warn": False, "note": "fewer than two chromatic colours on one side; not compared"}
    near = [min(_de(c["lab"], r["lab"]) for r in rc) for c in nc]
    back = [min(_de(r["lab"], c["lab"]) for c in nc) for r in rc]
    warn = max(near) < PALETTE_DE and mean(back) < PALETTE_DE
    return {"warn": warn, "worst_delta_e": max(near), "note": "same chromatic colour set" if warn else ""}


def audio_reuse(ref_fp, new_fp):
    """Longest run of consecutive new seconds whose best match is consecutive reference seconds."""
    rf = [(row, lv) for row, lv in zip(ref_fp.get("frames", []), ref_fp.get("levels", []))]
    nf = [(row, lv) for row, lv in zip(new_fp.get("frames", []), new_fp.get("levels", []))]
    if not rf or not nf:
        return {"run": 0, "alarm": False}

    def unit(v):
        n = math.sqrt(sum(x * x for x in v))
        return [x / n for x in v] if n > 1e-9 else None

    ru = [unit(r) if lv > -50 else None for r, lv in rf]
    best = []
    for row, lv in nf:
        u = unit(row) if lv > -50 else None
        if u is None:
            best.append(None)
            continue
        bj, bc = None, -1.0
        for j, r in enumerate(ru):
            if r is None:
                continue
            c = sum(x * y for x, y in zip(u, r))
            if c > bc:
                bj, bc = j, c
        best.append(bj if bc >= AUDIO_COS else None)
    longest, run = 0, 0
    for i, j in enumerate(best):
        if j is not None and i > 0 and best[i - 1] is not None and j == best[i - 1] + 1:
            run += 1
        else:
            run = 1 if j is not None else 0
        longest = max(longest, run)
    return {"run": longest, "alarm": longest >= AUDIO_RUN}
