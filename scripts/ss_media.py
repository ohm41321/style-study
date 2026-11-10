"""Video, image and audio routes: measure style with ffmpeg and numpy, and fingerprint for the copy check.

Picture work happens on small copies (128x72 grey for cuts and motion, 64x36 colour at 4 fps for
colour), so a ten-minute film fits in memory. Loudness comes from ffmpeg's ebur128 meter only; the
level numbers computed here are plain RMS dBFS and are never called LUFS.
"""

import math
import re

from ss_common import StyleError, ffprobe, media_in, numpy, run

GW, GH = 128, 72
CW, CH = 64, 36
COLOR_FPS = 4
STILL = 0.5  # a shot whose median frame change is under this many grey levels counts as still
SR = 22050
HOP = 256
NFFT = 1024
FP_HOP = 0.25  # seconds between the one-second windows of the audio copy fingerprint
# An onset is found on the log-band flux, frame by frame, then placed inside its frame at the sample where
# short-time energy rises most (REFINE windows of about 3 ms). The flux alone is biased by up to one window:
# after silence it fires on the first frame that touches the attack. check-skill.py holds this to 12 ms
# on click tracks, with and without a noise floor.
REFINE = 64


def _fps(stream):
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            n, d = stream.get(key, "0/0").split("/")
            f = float(n) / float(d) if float(d) else 0.0
        except (ValueError, ZeroDivisionError):
            f = 0.0
        if f > 0:
            return f
    return 0.0


def _video_stream(meta, path):
    vs = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vs:
        raise StyleError(f"{path}: no picture stream")
    return vs


# ---------------------------------------------------------------- picture statistics
def color_stats(np, rgb):
    """rgb: float array (..., 3) in 0-1. Returns saturation, colourfulness, warmth, hue spread."""
    px = rgb.reshape(-1, 3)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    mx, mn = px.max(1), px.min(1)
    d = mx - mn + 1e-9
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    rg = (r - g) * 255
    yb = (0.5 * (r + g) - b) * 255
    colorful = (math.hypot(float(rg.std()), float(yb.std())) + 0.3 * math.hypot(float(rg.mean()), float(yb.mean()))) / 100
    w = sat * (mx > 0.08)
    wsum = float(w.sum())
    if wsum < 1e-6:
        warmth, spread = 0.5, 0.0
    else:
        warm = (hue < 1 / 6) | (hue >= 330 / 360)
        warmth = float((w * warm).sum() / wsum)
        ang = 2 * np.pi * hue
        R = math.hypot(float((w * np.cos(ang)).sum() / wsum), float((w * np.sin(ang)).sum() / wsum))
        spread = 1.0 - R
    return {"saturation": float(sat.mean()), "colorfulness": colorful, "warmth": warmth, "hue_spread": spread}


def dhash(np, img):
    h, w = img.shape
    ys = np.linspace(0, h, 9).astype(int)
    xs = np.linspace(0, w, 10).astype(int)
    small = np.array([[img[ys[i]:max(ys[i + 1], ys[i] + 1), xs[j]:max(xs[j + 1], xs[j] + 1)].mean() for j in range(9)]
                      for i in range(8)])
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return "%016x" % int("".join("1" if x else "0" for x in bits), 2)


def thumb(np, img, g=16):
    """A g x g grey layout, zero mean, as integers -99..99: confirms a dHash match on flat graphics."""
    h, w = img.shape
    ys = np.linspace(0, h, g + 1).astype(int)
    xs = np.linspace(0, w, g + 1).astype(int)
    t = np.array([[img[ys[i]:max(ys[i + 1], ys[i] + 1), xs[j]:max(xs[j + 1], xs[j] + 1)].mean() for j in range(g)]
                  for i in range(g)], dtype=np.float64).flatten()
    t -= t.mean()
    m = float(np.abs(t).max())
    return [int(round(v)) for v in (t / m * 99 if m > 1e-9 else t)]


def _lab(np, rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def palette(np, rgb, k=6, iters=15):
    """k-means in Lab on a deterministic sample. Kept for the copy check only, never put in a card."""
    px = rgb.reshape(-1, 3)
    step = max(1, len(px) // 20000)
    px = px[::step]
    lab = _lab(np, px)
    order = np.argsort(lab[:, 0])
    centers = lab[order[np.linspace(0, len(order) - 1, k).astype(int)]].copy()
    for _ in range(iters):
        dist = ((lab[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        lab_of = dist.argmin(1)
        for j in range(k):
            sel = lab_of == j
            if sel.any():
                centers[j] = lab[sel].mean(0)
    out = []
    for j in range(k):
        sel = lab_of == j
        if not sel.any():
            continue
        mean_rgb = np.clip(px[sel].mean(0), 0, 1)
        out.append({"lab": [round(float(v), 2) for v in centers[j]],
                    "hex": "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in mean_rgb),
                    "share": float(sel.mean())})
    return sorted(out, key=lambda c: -c["share"])


# ---------------------------------------------------------------- video
def measure_video(path, max_seconds=600.0):
    np = numpy()
    meta = ffprobe(path)
    vs = _video_stream(meta, path)
    fps = _fps(vs)
    rate = fps if 0 < fps <= 30.5 else 30.0
    pre = "" if 0 < fps <= 30.5 else "fps=30,"
    raw = run(["ffmpeg", "-v", "error", "-t", str(max_seconds), *media_in(path), "-an", "-vf",
               f"{pre}scale={GW}:{GH}:flags=area,format=gray", "-f", "rawvideo", "-"]).stdout
    gray = np.frombuffer(raw, np.uint8)[: len(raw) // (GW * GH) * GW * GH].reshape(-1, GH, GW)  # uint8: 10 min is 0.2 GB
    if len(gray) < 3:
        raise StyleError(f"{path}: fewer than 3 frames")
    diff = np.empty(len(gray) - 1, np.float32)  # diff[k]: change from frame k to k+1
    for c in range(0, len(gray) - 1, 1024):
        e = min(len(gray) - 1, c + 1024)
        diff[c:e] = np.abs(gray[c + 1:e + 1].astype(np.int16) - gray[c:e].astype(np.int16)).mean(axis=(1, 2))
    # a hard cut is a lone spike: far above the typical change and well above both neighbours
    thresh = max(12.0, float(np.median(diff)) * 6)
    pad = np.concatenate([[0.0], diff, [0.0]])
    spike = (diff > thresh) & (diff > 2.0 * np.maximum(pad[:-2], pad[2:]))
    cut_frames = []
    for k in np.nonzero(spike)[0]:
        f = int(k) + 1
        if not cut_frames or f - cut_frames[-1] >= 3:
            cut_frames.append(f)
    bounds = [0] + cut_frames + [len(gray)]

    rawc = run(["ffmpeg", "-v", "error", "-t", str(max_seconds), *media_in(path), "-an", "-vf",
                f"fps={COLOR_FPS},scale={CW}:{CH}:flags=area,format=rgb24", "-f", "rawvideo", "-"]).stdout
    rgb = np.frombuffer(rawc, np.uint8).reshape(-1, CH, CW, 3).astype(np.float32) / 255
    ctimes = np.arange(len(rgb)) / COLOR_FPS

    shots = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        n = b - a
        inner = diff[a:b - 1] if n >= 2 else np.array([0.0])
        idx = np.linspace(a, b - 1, min(n, 24)).astype(int)
        g = gray[idx]
        t0, t1 = a / rate, b / rate
        sel = (ctimes >= t0) & (ctimes < t1)
        frames = rgb[sel] if sel.any() else rgb[[int(np.argmin(np.abs(ctimes - (t0 + t1) / 2)))]]
        cs = color_stats(np, frames)
        contrast = float(g.reshape(len(g), -1).std(axis=1).mean() / 255)
        shots.append({"t0": t0, "t1": t1, "dur": n / rate, "motion": float(np.median(inner)),
                      "luma": float(g.mean() / 255), "contrast": contrast,
                      "dhash": dhash(np, gray[(a + b) // 2]) if contrast >= 0.03 else None,
                      "thumb": thumb(np, gray[(a + b) // 2].astype(np.float32)) if contrast >= 0.03 else None, **cs})

    total = len(gray) / rate
    cut_times = [f / rate for f in cut_frames]
    win = 30.0 if total >= 45 else total
    starts = [0.0] if win >= total else list(np.arange(0.0, total - win / 2, win))
    cpm, still = [], []
    for s in starts:
        e = min(total, s + win)
        span = max(e - s, 1e-6)
        cpm.append(sum(1 for t in cut_times if s <= t < e) / span * 60)
        still.append(sum(max(0.0, min(e, sh["t1"]) - max(s, sh["t0"])) for sh in shots if sh["motion"] < STILL) / span)

    values = {
        "shot_length": [s["dur"] for s in shots],
        "cuts_per_minute": cpm,
        "motion": [max(s["motion"], 0.01) for s in shots],
        "still_share": still,
        **{k: [s[k] for s in shots] for k in ("luma", "contrast", "saturation", "colorfulness", "warmth", "hue_spread")},
    }
    fp = {
        "dhash": [s["dhash"] for s in shots if s["dhash"]],
        "thumbs": [s["thumb"] for s in shots if s["dhash"]],
        "palette": palette(np, rgb),
        "seq": {"features": ["log_dur", "luma", "contrast", "log_motion", "saturation", "warmth"],
                "rows": [[math.log(max(s["dur"], 1e-3)), s["luma"], s["contrast"], math.log1p(s["motion"]),
                          s["saturation"], s["warmth"]] for s in shots],
                "weights": [s["dur"] for s in shots]},
    }
    info = {"seconds": total, "fps": fps, "width": vs.get("width"), "height": vs.get("height"),
            "aspect": (vs.get("width") or 1) / (vs.get("height") or 1), "units": len(shots), "unit": "shots",
            "cuts": len(cut_frames), "audio": False,
            "shot_mids": [round((s["t0"] + s["t1"]) / 2, 3) for s in shots]}  # for contact sheets; never copied into a card
    if any(s.get("codec_type") == "audio" for s in meta.get("streams", [])):
        try:
            ainfo, avalues, afp, onsets = measure_audio(path, max_seconds, want_onsets=True)
        except StyleError:
            ainfo = None
        if ainfo:
            info["audio"] = True
            values.update({"audio_" + k: v for k, v in avalues.items()})
            fp["audio"] = afp
            if cut_times and len(onsets):
                near = [min(abs(t - o) for o in onsets) <= 0.06 for t in cut_times]
                values["cut_on_accent"] = [sum(near) / len(near)]
    return info, values, fp


# ---------------------------------------------------------------- images
def measure_images(paths):
    np = numpy()
    rows, values, hashes, thumbs, pixels = [], {}, [], [], []
    for path in paths:
        vs = _video_stream(ffprobe(path), path)
        w, h = int(vs.get("width") or 0), int(vs.get("height") or 0)
        if not w or not h:
            raise StyleError(f"{path}: unknown image size")
        f = min(1.0, 256.0 / max(w, h))
        ow, oh = max(8, int(round(w * f / 2)) * 2), max(8, int(round(h * f / 2)) * 2)
        raw = run(["ffmpeg", "-v", "error", *media_in(path), "-frames:v", "1", "-vf",
                   f"scale={ow}:{oh}:flags=area,format=rgb24", "-f", "rawvideo", "-"]).stdout
        rgb = np.frombuffer(raw, np.uint8)[: ow * oh * 3].reshape(oh, ow, 3).astype(np.float32) / 255
        Y = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        gx = np.abs(np.diff(Y, axis=1))[:-1, :]
        gy = np.abs(np.diff(Y, axis=0))[:, :-1]
        mag = np.sqrt(gx ** 2 + gy ** 2)
        cells = np.array([[c.mean() for c in np.array_split(r, 8, axis=1)] for r in np.array_split(mag, 8, axis=0)])
        p90 = float(np.percentile(cells, 90))
        empty = float((cells < 0.15 * p90).mean()) if p90 > 1e-6 else 1.0
        tot = float(mag.sum())
        if tot > 1e-6:
            yy, xx = np.mgrid[0:mag.shape[0], 0:mag.shape[1]]
            cx = float((mag * xx).sum() / tot) / max(1, mag.shape[1] - 1) * 2 - 1
            cy = float((mag * yy).sum() / tot) / max(1, mag.shape[0] - 1) * 2 - 1
            offset = min(1.0, math.hypot(cx, cy) / math.sqrt(2))
        else:
            offset = 0.0
        cs = color_stats(np, rgb)
        m = {"luma": float(Y.mean()), "contrast": float(Y.std()), "edge_density": float(mag.mean()),
             "negative_space": empty, "subject_offset": offset, "aspect": w / h, **cs}
        for k, v in m.items():
            values.setdefault(k, []).append(v)
        rows.append([m["luma"], m["contrast"], m["saturation"], m["warmth"], m["edge_density"], m["negative_space"]])
        if m["contrast"] >= 0.03:
            hashes.append(dhash(np, Y))
            thumbs.append(thumb(np, Y))
        pixels.append(rgb.reshape(-1, 3))
    fp = {"dhash": hashes, "thumbs": thumbs, "palette": palette(np, np.concatenate(pixels)),
          "seq": {"features": ["luma", "contrast", "saturation", "warmth", "edge_density", "negative_space"],
                  "rows": rows, "weights": [1.0] * len(rows)}}
    info = {"units": len(paths), "unit": "images"}
    return info, values, fp


def picture_hash(path):
    """(dHash, grey layout) of a picture embedded in a document, or None for a flat one (too little contrast to
    tell apart). Grid cells are relative, so the stretch to a square changes nothing between two copies."""
    np = numpy()
    raw = run(["ffmpeg", "-v", "error", *media_in(path), "-frames:v", "1", "-vf", "scale=128:128:flags=area,format=gray",
               "-f", "rawvideo", "-"]).stdout
    if len(raw) < 128 * 128:
        raise StyleError(f"{path}: not a picture ffmpeg can decode")
    Y = np.frombuffer(raw, np.uint8)[: 128 * 128].reshape(128, 128).astype(np.float32) / 255
    if float(Y.std()) < 0.03:
        return None
    return dhash(np, Y), thumb(np, Y)


# ---------------------------------------------------------------- audio
def ebur128(path, max_seconds):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-t", str(max_seconds), *media_in(path), "-vn", "-af",
               "ebur128=peak=true", "-f", "null", "-"]).stderr.decode("utf-8", "replace")
    s = err[err.rfind("Summary:"):]
    grab = lambda pat: re.search(pat, s)
    i, lra, tp = grab(r"I:\s+(-?[\d.]+) LUFS"), grab(r"LRA:\s+(-?[\d.]+) LU"), grab(r"Peak:\s+(-?[\d.]+|-inf) dBFS")
    if not i:
        raise StyleError(f"{path}: ffmpeg's loudness meter returned no summary")
    peak = float(tp.group(1)) if tp and tp.group(1) != "-inf" else None
    return float(i.group(1)), float(lra.group(1)) if lra else None, peak


def band_edges():
    return [40.0 * (10000.0 / 40.0) ** (i / 24) for i in range(25)]


def analyze_audio(np, x):
    """x: (2, n) float. Per-frame band energies, centroid, flatness and the onset envelope."""
    mono = x.mean(0)
    win = np.hanning(NFFT).astype(np.float32)
    nframes = 1 + max(0, (len(mono) - NFFT) // HOP)
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    edges = band_edges()
    bidx = [(freqs >= edges[i]) & (freqs < edges[i + 1]) for i in range(24)]
    flat_sel = (freqs >= 100) & (freqs < 8000)
    bands = np.zeros((nframes, 24), np.float32)
    cent = np.zeros(nframes, np.float32)
    flat = np.zeros(nframes, np.float32)
    power = np.zeros(nframes, np.float32)
    for c0 in range(0, nframes, 2048):
        c1 = min(nframes, c0 + 2048)
        idx = (np.arange(c0, c1)[:, None] * HOP + np.arange(NFFT)[None, :])
        fr = mono[idx] * win
        P = (np.abs(np.fft.rfft(fr, axis=1)) ** 2).astype(np.float32) + 1e-12
        for i, sel in enumerate(bidx):
            bands[c0:c1, i] = P[:, sel].sum(1)
        cent[c0:c1] = (P * freqs).sum(1) / P.sum(1)
        pf = P[:, flat_sel]
        flat[c0:c1] = np.exp(np.log(pf).mean(1)) / pf.mean(1)
        power[c0:c1] = (fr ** 2).mean(1)
    logb = 10 * np.log10(bands + 1e-10)
    env = np.maximum(0, np.diff(logb, axis=0)).sum(1)
    env = np.concatenate([[0.0], env]).astype(np.float64)
    return {"bands": bands, "logb": logb, "centroid": cent, "flatness": flat, "power": power, "env": env}


def tempo_of(np, env):
    fr = SR / HOP
    e = env - env.mean()
    if e.std() < 1e-9:
        return None
    size = 1 << (2 * len(e) - 1).bit_length()
    ac = np.fft.irfft(np.abs(np.fft.rfft(e, size)) ** 2, size)[: len(e)]
    ac /= ac[0] + 1e-12
    lo, hi = int(fr * 60 / 200), int(fr * 60 / 55)
    best, best_s = None, -1e9
    for L in range(max(lo, 2), min(hi, len(ac) // 4)):
        s = ac[L] + 0.5 * ac[2 * L] + 0.33 * ac[3 * L]
        bpm = 60 * fr / L
        s *= math.exp(-0.5 * (math.log2(bpm / 115) / 0.9) ** 2)
        if s > best_s:
            best, best_s = L, s
    if best is None:
        return None
    a, b, c = ac[best - 1], ac[best], ac[best + 1]
    den = a - 2 * b + c
    shift = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0.0
    return 60 * fr / (best + max(-0.5, min(0.5, shift)))


def onsets_of(np, env, mono):
    fr = SR / HOP
    n = len(env)
    k = max(1, int(fr))
    csum = np.concatenate([[0.0], np.cumsum(env)])
    lo = np.clip(np.arange(n) - k // 2, 0, n)
    hi = np.clip(np.arange(n) + k // 2 + 1, 0, n)
    local = (csum[hi] - csum[lo]) / np.maximum(hi - lo, 1)
    thr = local + 0.6 * env.std()
    out = []
    r = 4
    for i in range(n):
        if env[i] > thr[i] and env[i] >= env[max(0, i - r):i + r + 1].max() and env[i] > 1e-6:
            t = place_onset(np, mono, i)
            if not out or t - out[-1] >= 0.05:
                out.append(t)
    return out


def place_onset(np, mono, i):
    """Seconds of the steepest energy rise inside flux frame i (searched from one hop before it)."""
    a = max(0, (i - 1) * HOP)
    b = min(len(mono), i * HOP + NFFT + REFINE)
    seg = mono[a:b].astype(np.float64) ** 2
    if len(seg) < 3 * REFINE:
        return (i * HOP + NFFT / 2) / SR
    c = np.concatenate([[0.0], np.cumsum(seg)])
    j = np.arange(REFINE, len(seg) - REFINE + 1)
    rise = (c[j + REFINE] - c[j]) - (c[j] - c[j - REFINE])
    return (a + int(j[int(np.argmax(rise))])) / SR


def measure_audio(path, max_seconds=600.0, want_onsets=False):
    np = numpy()
    raw = run(["ffmpeg", "-v", "error", "-t", str(max_seconds), *media_in(path), "-vn", "-ac", "2", "-ar", str(SR),
               "-f", "f32le", "-"]).stdout
    x = np.frombuffer(raw, "<f4").reshape(-1, 2).T.astype(np.float32)
    if x.shape[1] < SR:
        raise StyleError(f"{path}: less than a second of audio")
    lufs, lra, tp = ebur128(path, max_seconds)
    a = analyze_audio(np, x)
    fr = SR / HOP
    onsets = onsets_of(np, a["env"], x.mean(0))
    secs = x.shape[1] / SR
    per = int(round(fr))
    nwin = int(secs)
    level, cent, flat, ons = [], [], [], []
    on = np.array(onsets)
    for w in range(nwin):
        sl = slice(w * per, (w + 1) * per)
        pw = float(a["power"][sl].mean()) if a["power"][sl].size else 0.0
        lv = 10 * math.log10(pw + 1e-12)
        level.append(lv)
        cent.append(float(np.median(a["centroid"][sl])) if pw > 1e-7 else None)
        flat.append(float(np.median(a["flatness"][sl])) if pw > 1e-7 else None)
        ons.append(int(((on >= w) & (on < w + 1)).sum()) if len(on) else 0)
    med = float(np.median(level)) if level else -120.0
    values = {
        "loudness": [lufs],
        "onset_rate": [sum(ons[i:i + 5]) / max(1, len(ons[i:i + 5])) for i in range(0, max(1, nwin - 2), 5)],
        "centroid": [c for c in cent if c],
        "flatness": [f for f in flat if f is not None],
        "quiet_share": [sum(1 for l in level[i:i + 10] if l < med - 12) / len(level[i:i + 10])
                        for i in range(0, max(1, nwin - 4), 10) if level[i:i + 10]],
        "dynamics": [float(np.percentile(level[i:i + 10], 90) - np.percentile(level[i:i + 10], 10))
                     for i in range(0, max(1, nwin - 4), 10) if len(level[i:i + 10]) >= 3],
    }
    if lra is not None:
        values["loudness_range"] = [lra]
    if tp is not None:
        values["plr"] = [tp - lufs]
    bpm = tempo_of(np, a["env"]) if len(onsets) >= 0.3 * secs else None
    if bpm:
        values["tempo"] = [bpm]
    edges = band_edges()
    lows = [i for i in range(24) if edges[i + 1] <= 250]
    mids = [i for i in range(24) if edges[i] >= 250 and edges[i + 1] <= 2000]
    shares = {"low_share": [], "mid_share": [], "high_share": []}
    for i in range(0, max(1, nwin - 2), 5):
        sl = slice(i * per, (i + 5) * per)
        e = a["bands"][sl].sum(0)
        tot = float(e.sum())
        if tot <= 1e-9:
            continue
        lo_e, mid_e = float(e[lows].sum()), float(e[mids].sum())
        shares["low_share"].append(lo_e / tot)
        shares["mid_share"].append(mid_e / tot)
        shares["high_share"].append(max(0.0, 1 - (lo_e + mid_e) / tot))
    values.update({k: v for k, v in shares.items() if v})
    mid_sig, side = (x[0] + x[1]) / 2, (x[0] - x[1]) / 2
    values["width"] = [10 * math.log10(float((side ** 2).mean()) / (float((mid_sig ** 2).mean()) + 1e-20) + 1e-20)]
    values = {k: v for k, v in values.items() if v}

    # copy fingerprint: one-second windows every FP_HOP seconds, each centred on its own mean across the bands.
    # Nothing depends on the rest of the file, so a piece cut from anywhere in the track, off the second grid,
    # louder or quieter, still lands on the reference's frames.
    step = max(1, int(round(per * FP_HOP)))
    fp_frames, fp_levels = [], []
    for s0 in range(0, max(0, a["logb"].shape[0] - per + 1), step):
        sl = slice(s0, s0 + per)
        row = a["logb"][sl].mean(0)
        fp_frames.append([round(float(v), 2) for v in row - row.mean()])
        fp_levels.append(round(10 * math.log10(float(a["power"][sl].mean()) + 1e-12), 1))
    fp = {"frames": fp_frames, "levels": fp_levels, "hop": FP_HOP,
          "seq": {"features": ["level", "log_centroid", "flatness", "onsets"],
                  "rows": [[level[i], math.log(cent[i]) if cent[i] else 0.0, flat[i] or 0.0, float(ons[i])] for i in range(nwin)],
                  "weights": [1.0] * nwin}}
    info = {"seconds": secs, "units": nwin, "unit": "seconds", "onsets": len(onsets)}
    if want_onsets:
        return info, values, fp, onsets
    return info, values, fp
