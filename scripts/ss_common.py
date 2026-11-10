"""Shared helpers for style-study: statistics, file kinds, JSON, ffmpeg calls.

Only the standard library is imported here, so the text route runs on a bare Python 3.9+.
"""

import json
import math
import os
import shutil
import subprocess
import sys

SCHEMA_CARD = "style-study/1"
SCHEMA_FP = "style-study/fingerprints-1"

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".gif"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif"}
TEXT_EXT = {".txt", ".md", ".markdown", ".srt", ".vtt", ".html", ".htm", ".rst"}
MEDIA = ("video", "image", "audio", "text")


class StyleError(Exception):
    """A problem the user can fix (bad input, missing tool). Printed without a traceback."""


def kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in TEXT_EXT:
        return "text"
    return None


def quantile(values, q):
    """Linear-interpolated quantile of a non-empty list (same rule as numpy's default)."""
    xs = sorted(float(v) for v in values)
    if not xs:
        raise ValueError("quantile of an empty list")
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def summary(values):
    vals = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return None
    return {"p10": quantile(vals, 0.1), "p50": quantile(vals, 0.5), "p90": quantile(vals, 0.9), "n": len(vals)}


def mean(values):
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def pearson(a, b):
    n = len(a)
    if n < 3 or n != len(b):
        return 0.0
    ma, mb = mean(a), mean(b)
    da = [x - ma for x in a]
    db = [y - mb for y in b]
    va = sum(x * x for x in da)
    vb = sum(y * y for y in db)
    if va <= 1e-12 or vb <= 1e-12:
        return 0.0
    return sum(x * y for x, y in zip(da, db)) / math.sqrt(va * vb)


def round_floats(obj, digits=4):
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    return obj


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise StyleError(f"{path}: file not found")
    except json.JSONDecodeError as e:
        raise StyleError(f"{path}: not valid JSON ({e})")


def save_json(obj, path):
    text = json.dumps(round_floats(obj), ensure_ascii=False, indent=2) + "\n"
    if path in (None, "-"):
        sys.stdout.write(text)
        return
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def need_tool(name):
    if not shutil.which(name):
        raise StyleError(f"{name} is not on PATH; install it (for example `brew install ffmpeg` or your package manager)")


def run(cmd, binary=True):
    """Run a command and return its CompletedProcess; raise StyleError with the tool's last error line."""
    need_tool(cmd[0])
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "replace").strip().splitlines()
        raise StyleError(f"{cmd[0]} failed: {err[-1] if err else 'no message'}")
    return p


def numpy():
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        raise StyleError("this medium needs numpy: create a venv and `pip install numpy`, then run the script with that Python")
    return np


def media_in(path):
    """ffmpeg input arguments for a local file. The file: prefix stops a name that starts with '-' or holds
    'xxx:' from being read as an option or a protocol, and the whitelist stops a playlist inside a
    reference from opening anything but local files."""
    return ["-protocol_whitelist", "file", "-i", "file:" + os.path.abspath(path)]


def ffprobe(path):
    p = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", "-protocol_whitelist", "file",
             "file:" + os.path.abspath(path)])
    return json.loads(p.stdout.decode("utf-8", "replace"))


def ref_id(i):
    return f"r{i + 1}"
