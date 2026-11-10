"""Documents route: slide decks, word-processing documents and spreadsheets, read without Office.

Standard library only. OOXML (.pptx .docx .xlsx and their macro and template variants) and OpenDocument
(.odp .odt .ods, flat or zipped) are zip files of XML and are read directly, and so are .epub, .rtf, .csv and
.tsv. A PDF needs pypdf (`pip install pypdf`) or poppler's pdftotext. Older binary formats (.ppt .doc .xls),
Apple iWork (.key .pages .numbers) and other word processors are converted first: with LibreOffice when it
is installed, or with macOS textutil for word-processing files.

Each format is read into one of three plain models, so the measures do not care where a file came from:

  deck      slides, each with its text paragraphs (title or body, size, colour, bullet), element boxes,
            pictures and background colour; the deck's aspect and typefaces
  document  blocks (heading, body, list, table) with type size, line spacing, space after, bold and italic
            characters and colours; pictures, tables and the page
  book      sheets of cells (number, text, formula, style); merged ranges, charts, typefaces and colours

Pictures inside a file are hashed for the copy check (exact bytes always; by look as well when numpy and
ffmpeg are installed). Measures that need layout the file does not store (where a Word page breaks, the
size of text PowerPoint shrinks to fit) are approximations; references/mediums.md lists them.
"""

import contextlib
import csv
import hashlib
import io
import math
import os
import pathlib
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from xml.parsers import expat
from collections import Counter

import ss_text
from ss_common import StyleError

MAX_PART = 64 * 1024 * 1024  # bytes read from one part of a zip
MAX_TOTAL = 512 * 1024 * 1024  # bytes read from one file in all
MAX_CELLS = 200000  # cells read from one workbook
EMU = 12700  # EMU per point

OOXML_SLIDES = {".pptx", ".pptm", ".potx", ".potm", ".ppsx", ".ppsm"}
OOXML_DOCS = {".docx", ".docm", ".dotx", ".dotm"}
OOXML_SHEETS = {".xlsx", ".xlsm", ".xltx", ".xltm"}
ODF = {".odp": "slides", ".otp": "slides", ".fodp": "slides", ".odt": "document", ".ott": "document",
       ".fodt": "document", ".ods": "sheet", ".ots": "sheet", ".fods": "sheet"}
# formats read after a conversion: extension -> (medium, format LibreOffice writes)
CONVERT = {".ppt": ("slides", "pptx"), ".pps": ("slides", "pptx"), ".pot": ("slides", "pptx"), ".key": ("slides", "pptx"),
           ".sxi": ("slides", "pptx"), ".doc": ("document", "docx"), ".dot": ("document", "docx"),
           ".pages": ("document", "docx"), ".wpd": ("document", "docx"), ".wps": ("document", "docx"),
           ".abw": ("document", "docx"), ".hwp": ("document", "docx"), ".sxw": ("document", "docx"),
           ".wordml": ("document", "docx"), ".webarchive": ("document", "docx"), ".xls": ("sheet", "xlsx"),
           ".xlt": ("sheet", "xlsx"), ".numbers": ("sheet", "xlsx"), ".sxc": ("sheet", "xlsx")}
TEXTUTIL_IN = {".doc", ".dot", ".wordml", ".webarchive"}  # macOS textutil reads these and writes .docx


# one line of type is about 23/20 of its size: an exact line height in points becomes lines with this
LINE_EM = 23 / 20
# a PDF slide's title is its biggest line when that is at least this much over the body size
HEADING_STEP = 23 / 20


def ext_of(path):
    return os.path.splitext(path)[1].lower()


# ---------------------------------------------------------------- safe reading
def ln(el):
    """Local name of an element or attribute key, without its namespace."""
    t = el if isinstance(el, str) else el.tag
    return t.rsplit("}", 1)[-1] if isinstance(t, str) else ""


def att(el, name, default=None):
    if el is None:
        return default
    for k, v in el.attrib.items():
        if k == name or k.endswith("}" + name):
            return v
    return default


def ratt(el, name):
    """A namespaced attribute (r:id, r:embed, presentation:class...), never a plain one of the same local name:
    <p:sldId id="256" r:id="rId2"/> carries both."""
    if el is None:
        return None
    for k, v in el.attrib.items():
        if k.startswith("{") and k.endswith("}" + name):
            return v
    return None


def nsatt(el, ns, name):
    """The attribute `name` in the namespace whose URI contains `ns` (draw:style-name against presentation:style-name)."""
    if el is None:
        return None
    for k, v in el.attrib.items():
        if k.startswith("{") and k.endswith("}" + name) and ns in k[1:k.index("}")]:
            return v
    return None


def kids(el, name=None):
    return [c for c in (el if el is not None else []) if name is None or ln(c) == name]


def kid(el, name):
    for c in (el if el is not None else []):
        if ln(c) == name:
            return c
    return None


def path_to(el, *names):
    for n in names:
        el = kid(el, n)
        if el is None:
            return None
    return el


def find_all(el, name):
    return [c for c in (el.iter() if el is not None else []) if ln(c) == name]


def find(el, name):
    for c in (el.iter() if el is not None else []):
        if ln(c) == name:
            return c
    return None


class _Refused(Exception):
    pass


def _no_dtd(*_):
    raise _Refused()


def parse_xml(data, where):
    """Parse XML that has no DTD and no entity declarations, in whatever encoding it declares."""
    refused = StyleError(f"{where}: declares a DTD or entities; refused (Office files never need one)")
    if b"<!DOCTYPE" in data[:65536] or b"<!ENTITY" in data:
        raise refused
    # the byte test above misses UTF-16 and UTF-32; expat sees the declaration in any encoding and stops there,
    # before a single entity is defined
    scan = expat.ParserCreate()
    scan.StartDoctypeDeclHandler = _no_dtd
    scan.EntityDeclHandler = _no_dtd
    try:
        scan.Parse(data, True)
    except _Refused:
        raise refused
    except expat.ExpatError as e:
        raise StyleError(f"{where}: broken XML ({e})")
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise StyleError(f"{where}: broken XML ({e})")


class Pack:
    """A zip-of-XML file (OOXML, OpenDocument, EPUB) read with size limits."""

    def __init__(self, path, kind):
        self.path, self.total, self.cache = path, 0, {}
        try:
            self.z = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as e:
            raise StyleError(f"{path}: not a readable {kind} file ({e})")
        self.names = set(self.z.namelist())

    def has(self, name):
        return name in self.names

    def bytes(self, name):
        """A part's bytes. Each part counts once toward the unpacked limit, however often it is read
        (a master picture sits behind every slide)."""
        if name in self.cache:
            return self.cache[name]
        try:
            info = self.z.getinfo(name)
        except KeyError:
            raise StyleError(f"{self.path}: missing part {name}")
        if info.file_size > MAX_PART:
            raise StyleError(f"{self.path}: part {name} is over {MAX_PART >> 20} MB; refused")
        self.total += info.file_size
        if self.total > MAX_TOTAL:
            raise StyleError(f"{self.path}: over {MAX_TOTAL >> 20} MB unpacked; refused")
        with self.z.open(info) as f:
            data = f.read(MAX_PART + 1)
        if len(data) > MAX_PART:
            raise StyleError(f"{self.path}: part {name} unpacks past its stated size; refused")
        self.cache[name] = data
        return data

    def xml(self, name):
        return parse_xml(self.bytes(name), f"{self.path}: {name}")

    def rels(self, part):
        """{rId: (target part, relationship type)} for an OOXML part."""
        rp = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
        if not self.has(rp):
            return {}
        out = {}
        for r in self.xml(rp):
            if att(r, "TargetMode") == "External":
                continue
            target = att(r, "Target", "")
            full = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
            out[att(r, "Id")] = (full, att(r, "Type", "").rsplit("/", 1)[-1])
        return out

    def rel_of(self, part, kind):
        return next((t for t, k in self.rels(part).values() if k == kind), None)


# ---------------------------------------------------------------- colour
NAMED = {"black": "000000", "white": "FFFFFF", "red": "FF0000", "green": "008000", "blue": "0000FF", "yellow": "FFFF00",
         "gray": "808080", "grey": "808080", "silver": "C0C0C0", "orange": "FFA500"}


def rgb_of(hexs):
    if not hexs:
        return None
    h = hexs.strip().lstrip("#")
    if len(h) == 8:  # ARGB
        h = h[2:]
    if len(h) != 6 or not re.fullmatch(r"[0-9A-Fa-f]{6}", h):
        return None
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hex_of(rgb):
    return "%02X%02X%02X" % tuple(int(round(max(0, min(1, v)) * 255)) for v in rgb)


def luma(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(a, b):
    la = 0.2126 * _lin(a[0]) + 0.7152 * _lin(a[1]) + 0.0722 * _lin(a[2])
    lb = 0.2126 * _lin(b[0]) + 0.7152 * _lin(b[1]) + 0.0722 * _lin(b[2])
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def saturation(rgb):
    mx, mn = max(rgb), min(rgb)
    return (mx - mn) / mx if mx > 1e-6 else 0.0


def chromatic(rgb):
    """Not black, white or grey."""
    return saturation(rgb) >= 0.15 and max(rgb) >= 0.15


def lab(rgb):
    x, y, z = (sum(m * _lin(c) for m, c in zip(row, rgb)) for row in
               ((0.4124, 0.3576, 0.1805), (0.2126, 0.7152, 0.0722), (0.0193, 0.1192, 0.9505)))
    f = [v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116 for v in (x / 0.95047, y, z / 1.08883)]
    return [116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])]


def _hsl(rgb):
    mx, mn = max(rgb), min(rgb)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    r, g, b = rgb
    h = ((g - b) / d % 6) if mx == r else ((b - r) / d + 2) if mx == g else ((r - g) / d + 4)
    return h / 6, s, l


def _from_hsl(h, s, l):
    def f(n):
        k = (n + h * 12) % 12
        a = s * min(l, 1 - l)
        return l - a * max(-1, min(k - 3, 9 - k, 1))
    return (f(0), f(8), f(4))


def modify(rgb, el):
    """Apply DrawingML colour modifiers (lumMod, lumOff, tint, shade) found under a colour element."""
    for m in el:
        v = att(m, "val")
        if v is None:
            continue
        v = int(v) / 100000
        name = ln(m)
        if name in ("lumMod", "lumOff"):
            h, s, l = _hsl(rgb)
            l = l * v if name == "lumMod" else l + v
            rgb = _from_hsl(h, s, max(0, min(1, l)))
        elif name == "tint":
            rgb = tuple(c + (1 - c) * (1 - v) for c in rgb)
        elif name == "shade":
            rgb = tuple(c * v for c in rgb)
    return rgb


def palette_of(colors):
    """Chromatic colours (rgb -> weight) as a palette for the copy check: never written into a card."""
    groups = []
    for rgb, w in sorted(colors.items(), key=lambda kv: -kv[1]):
        if not chromatic(rgb):
            continue
        lb = lab(rgb)
        for g in groups:
            if math.dist(g["lab"], lb) < 8:
                g["w"] += w
                break
        else:
            groups.append({"lab": lb, "hex": "#" + hex_of(rgb).lower(), "w": w})
    total = sum(g["w"] for g in groups) or 1
    return [{"lab": [round(v, 2) for v in g["lab"]], "hex": g["hex"], "share": g["w"] / total} for g in groups]


def color_values(colors):
    """(colours besides black, white and grey, their mean saturation) from rgb -> weight."""
    pal = palette_of(colors)
    sats = [(saturation(rgb), w) for rgb, w in colors.items() if chromatic(rgb)]
    wsum = sum(w for _, w in sats)
    return len(pal), (sum(s * w for s, w in sats) / wsum if wsum else 0.0)


# ---------------------------------------------------------------- pictures
def picture_key(data):
    return hashlib.sha256(data).hexdigest()[:20]


def picture_looks(media):
    """dHash and grey layout of each picture, or None when numpy or ffmpeg is missing. Vector formats that
    ffmpeg cannot decode (EMF, WMF, SVG) are skipped; their exact hash still counts."""
    try:
        import numpy  # noqa: F401
    except ImportError:
        return None
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return None
    import ss_media
    hashes, thumbs = [], []
    with tempfile.TemporaryDirectory(prefix="style-study-") as tmp:
        for i, (key, data) in enumerate(sorted(media.items())):
            if not data or data[:4] in (b"\x01\x00\x00\x00", b"\xd7\xcd\xc6\x9a") or b"<svg" in data[:512]:
                continue
            p = os.path.join(tmp, f"p{i}.img")
            with open(p, "wb") as f:
                f.write(data)
            try:
                got = ss_media.picture_hash(p)
            except StyleError:
                continue
            if got:
                hashes.append(got[0])
                thumbs.append(got[1])
    return {"dhash": hashes, "thumbs": thumbs}


# ---------------------------------------------------------------- conversions
def soffice():
    for name in ("soffice", "libreoffice"):
        if shutil.which(name):
            return shutil.which(name)
    mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    return mac if os.path.exists(mac) else None


@contextlib.contextmanager
def readable(path):
    """Yield a path in a format this module reads, converting older and foreign formats first."""
    ext = ext_of(path)
    if ext not in CONVERT:
        yield path
        return
    medium, to = CONVERT[ext]
    with tempfile.TemporaryDirectory(prefix="style-study-") as tmp:
        exe = soffice()
        if exe:
            out = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + "." + to)
            cmd = [exe, "--headless", "--norestore", f"-env:UserInstallation={pathlib.Path(tmp, 'profile').as_uri()}",
                   "--convert-to", to, "--outdir", tmp, os.path.abspath(path)]
        elif ext in TEXTUTIL_IN and shutil.which("textutil"):
            out = os.path.join(tmp, "converted.docx")
            cmd = ["textutil", "-convert", "docx", "-output", out, os.path.abspath(path)]
        else:
            raise StyleError(f"{path}: reading {ext} needs LibreOffice (libreoffice.org, or `brew install --cask "
                             f"libreoffice`); or export it to .{to} or .pdf and measure that")
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise StyleError(f"{path}: conversion took over 5 minutes; export it to .{to} by hand")
        if p.returncode != 0 or not os.path.exists(out):
            err = p.stderr.decode("utf-8", "replace").strip().splitlines()
            raise StyleError(f"{path}: could not convert to .{to} ({err[-1] if err else 'no output'})")
        yield out


def medium_of_file(path):
    ext = ext_of(path)
    if ext in OOXML_SLIDES:
        return "slides"
    if ext in OOXML_DOCS or ext in (".rtf", ".epub", ".pdf"):
        return "document"
    if ext in OOXML_SHEETS or ext in (".csv", ".tsv"):
        return "sheet"
    if ext in ODF:
        return ODF[ext]
    if ext in CONVERT:
        return CONVERT[ext][0]
    return None


def load(path, medium):
    """Read a file into the model of `medium` (deck, document or book)."""
    own = medium_of_file(path)
    if own is None:
        raise StyleError(f"{path}: not a document format style.py reads")
    ext = ext_of(path)
    if ext == ".pdf" and medium in ("slides", "document"):
        return read_pdf(path, medium == "slides")
    if own != medium:
        raise StyleError(f"{path}: a {ext} file is {own}, not {medium}; measure it with --medium {own}")
    with readable(path) as src:
        e = ext_of(src)
        if e in OOXML_SLIDES:
            return read_pptx(src)
        if e in OOXML_DOCS:
            return read_docx(src)
        if e in OOXML_SHEETS:
            return read_xlsx(src)
        if e in (".csv", ".tsv"):
            return read_csv(src)
        if e == ".rtf":
            return read_rtf(src)
        if e == ".epub":
            return read_epub(src)
        if e in ODF:
            return read_odf(src, ODF[e])
    raise StyleError(f"{path}: no reader for {ext}")


# ---------------------------------------------------------------- PowerPoint
TITLE_PH = {"title", "ctrTitle"}
SKIP_PH = {"dt", "ftr", "sldNum", "hdr"}


def _color(el, theme, cmap):
    """rgb from a DrawingML fill or colour element (solidFill, srgbClr, schemeClr...), or None."""
    if el is None:
        return None
    if ln(el) in ("solidFill", "bgRef", "fillRef", "fontRef"):
        el = next(iter(el), None)
        if el is None:
            return None
    name = ln(el)
    rgb = None
    if name == "srgbClr":
        rgb = rgb_of(att(el, "val"))
    elif name == "sysClr":
        rgb = rgb_of(att(el, "lastClr")) or rgb_of(NAMED.get(att(el, "val", ""), ""))
    elif name == "prstClr":
        rgb = rgb_of(NAMED.get(att(el, "val", "").lower(), ""))
    elif name == "schemeClr":
        key = att(el, "val", "")
        key = cmap.get(key, key)
        rgb = theme.get(key)
    elif name == "scrgbClr":
        rgb = tuple(int(att(el, k, "0")) / 100000 for k in ("r", "g", "b"))
    if rgb is None:
        return None
    return modify(rgb, el)


def _fill(sppr, theme, cmap):
    """Fill colour of a shape's properties; gradients count as their first stop."""
    if sppr is None:
        return None
    for c in sppr:
        n = ln(c)
        if n == "solidFill":
            return _color(c, theme, cmap)
        if n == "gradFill":
            gs = find(c, "gs")
            return _color(next(iter(gs), None), theme, cmap) if gs is not None else None
        if n in ("noFill", "blipFill", "pattFill"):
            return None
    return None


def _theme(pk, part):
    colors, fonts = {}, {}
    if not part or not pk.has(part):
        return colors, fonts
    root = pk.xml(part)
    cs = find(root, "clrScheme")
    for c in kids(cs):
        v = next(iter(c), None)
        if v is not None:
            colors[ln(c)] = _color(v, {}, {})
    for kind in ("majorFont", "minorFont"):
        f = find(root, kind)
        if f is None:
            continue
        fonts[kind + ":latin"] = att(kid(f, "latin"), "typeface", "")
        fonts[kind + ":cs"] = att(kid(f, "cs"), "typeface", "") or next(
            (att(x, "typeface") for x in kids(f, "font") if att(x, "script") == "Thai"), "")
    return colors, fonts


def _xfrm(el):
    """(x, y, w, h) in EMU from an element holding a:xfrm or p:xfrm, or None."""
    x = find(el, "xfrm") if el is not None else None
    if x is None:
        return None
    off, ext = kid(x, "off"), kid(x, "ext")
    if off is None or ext is None:
        return None
    return (int(att(off, "x", 0)), int(att(off, "y", 0)), int(att(ext, "cx", 0)), int(att(ext, "cy", 0)))


def _ph(sp):
    nv = next((c for c in sp if ln(c).startswith("nv")), None)
    ph = find(nv, "ph") if nv is not None else None
    if ph is None:
        return None
    return (att(ph, "type", "obj"), att(ph, "idx", "0"))


class _Holder:
    """A slide layout or master: its placeholders, background and (for a master) text styles."""

    def __init__(self, pk, part):
        self.root = pk.xml(part)
        self.part = part
        self.phs = []
        tree = find(self.root, "spTree")
        for sp in kids(tree):
            ph = _ph(sp) if ln(sp) in ("sp", "pic", "graphicFrame") else None
            if ph:
                self.phs.append((ph[0], ph[1], sp))
        self.bg = path_to(self.root, "cSld", "bg")

    def match(self, ptype, idx):
        title = ptype in TITLE_PH
        for t, i, sp in self.phs:
            if (t in TITLE_PH) == title and (t == ptype or (i == idx and idx != "0")):
                return sp
        for t, i, sp in self.phs:
            if idx != "0" and i == idx:
                return sp
        if not title:
            for t, i, sp in self.phs:
                if t in ("body", "obj") and ptype in ("body", "obj", "subTitle"):
                    return sp
        return None


def read_pptx(path):
    pk = Pack(path, "PowerPoint")
    pres = pk.xml("ppt/presentation.xml")
    sz = find(pres, "sldSz")
    W, H = (int(att(sz, "cx", 12192000)), int(att(sz, "cy", 6858000))) if sz is not None else (12192000, 6858000)
    prels = pk.rels("ppt/presentation.xml")
    order = [prels[ratt(s, "id")][0] for s in find_all(find(pres, "sldIdLst"), "sldId") if ratt(s, "id") in prels]
    default_style = find(pres, "defaultTextStyle")
    deck = {"aspect": W / H if H else None, "slides": [], "hidden": [], "media": {}, "fonts": Counter()}
    holders, themes = {}, {}

    def holder(part):
        if part not in holders:
            holders[part] = _Holder(pk, part)
        return holders[part]

    for part in order:
        root = pk.xml(part)
        hidden = att(root, "show") == "0"
        layout_part = pk.rel_of(part, "slideLayout")
        layout = holder(layout_part) if layout_part else None
        master_part = pk.rel_of(layout_part, "slideMaster") if layout_part else None
        master = holder(master_part) if master_part else None
        theme_part = pk.rel_of(master_part, "theme") if master_part else None
        if theme_part not in themes:
            themes[theme_part] = _theme(pk, theme_part)
        tcolors, tfonts = themes[theme_part]
        cmap_el = find(master.root, "clrMap") if master else None
        cmap = {k: v for k, v in (cmap_el.attrib.items() if cmap_el is not None else [])}
        cmap = {**{"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}, **{ln(k): v for k, v in cmap.items()}}
        # a hidden slide is not measured (its typefaces stay out of the style) but its words and pictures still
        # reach the copy check: hiding a copied slide must not hide the copy
        into = {"media": deck["media"], "fonts": Counter()} if hidden else deck
        (deck["hidden"] if hidden else deck["slides"]).append(
            _slide(pk, part, root, layout, master, tcolors, tfonts, cmap, default_style, W, H, into))
    if not deck["slides"]:
        raise StyleError(f"{path}: no visible slides")
    return deck


def _bg(holders, theme, cmap):
    for h in holders:
        if h is None:
            continue
        if h.bg is None:
            continue
        pr = kid(h.bg, "bgPr")
        if pr is not None:
            if kid(pr, "blipFill") is not None:
                return None, True
            return _fill(pr, theme, cmap), False
        ref = kid(h.bg, "bgRef")
        if ref is not None:
            return _color(ref, theme, cmap), False
    return (theme.get(cmap.get("bg1", "lt1")) or (1.0, 1.0, 1.0)), False


def _slide(pk, part, root, layout, master, theme, tfonts, cmap, default_style, W, H, deck):
    rels = pk.rels(part)

    class SlideBg:
        bg = path_to(root, "cSld", "bg")
    bg, bg_picture = _bg([SlideBg, layout, master], theme, cmap)
    slide = {"paras": [], "boxes": [], "pictures": [], "elements": 0, "bg": bg, "colors": Counter(), "picture_bg": bg_picture}
    if bg and not bg_picture:
        slide["colors"][bg] += 1
    styles = find(master.root, "txStyles") if master else None

    def level_chain(sp, kind, ph):
        chain = []
        lst = path_to(kid(sp, "txBody"), "lstStyle")
        chain.append(lst)
        if ph:
            for h in (layout, master):
                inh = h.match(*ph) if h else None
                chain.append(path_to(kid(inh, "txBody"), "lstStyle") if inh is not None else None)
        style_name = {"title": "titleStyle", "body": "bodyStyle"}.get(kind, "otherStyle")
        chain.append(kid(styles, style_name) if styles is not None else None)
        chain.append(default_style)
        return [c for c in chain if c is not None]

    def lvl_prop(chain, lvl, getter):
        for c in chain:
            node = kid(c, f"lvl{lvl}pPr")
            if node is not None:
                v = getter(node)
                if v is not None:
                    return v
        return None

    def walk(tree, xf):
        for sp in kids(tree):
            name = ln(sp)
            if name == "grpSp":
                g = find(kid(sp, "grpSpPr"), "xfrm")
                if g is not None and kid(g, "chOff") is not None and kid(g, "chExt") is not None:
                    o, e, co, ce = (kid(g, k) for k in ("off", "ext", "chOff", "chExt"))
                    sx = int(att(e, "cx", 1)) / max(1, int(att(ce, "cx", 1)))
                    sy = int(att(e, "cy", 1)) / max(1, int(att(ce, "cy", 1)))
                    ox, oy = int(att(o, "x", 0)) - int(att(co, "x", 0)) * sx, int(att(o, "y", 0)) - int(att(co, "y", 0)) * sy

                    def inner(b, ox=ox, oy=oy, sx=sx, sy=sy, xf=xf):
                        return xf((ox + b[0] * sx, oy + b[1] * sy, b[2] * sx, b[3] * sy))
                    walk(sp, inner)
                else:
                    walk(sp, xf)
                continue
            if name not in ("sp", "pic", "graphicFrame", "cxnSp"):
                continue
            ph = _ph(sp)
            if ph and ph[0] in SKIP_PH:
                continue
            box = _xfrm(kid(sp, "spPr") if name in ("sp", "pic", "cxnSp") else sp)
            if box is None and ph:
                for h in (layout, master):
                    inh = h.match(*ph) if h else None
                    if inh is not None:
                        box = _xfrm(kid(inh, "spPr") if ln(inh) != "graphicFrame" else inh)
                        if box:
                            break
            box = xf(box) if box else None
            kind = "title" if ph and ph[0] in TITLE_PH else "body" if ph else "other"
            area = box[2] * box[3] / (W * H) if box and W and H else 0
            if name == "pic":
                blip = find(sp, "blip")
                rid = ratt(blip, "embed")
                if rid in rels and pk.has(rels[rid][0]):
                    data = pk.bytes(rels[rid][0])
                    key = picture_key(data)
                    deck["media"][key] = data
                    slide["pictures"].append(key)
                slide["elements"] += 1
                if box:
                    slide["boxes"].append(box)
                continue
            if name == "graphicFrame":
                slide["elements"] += 1
                if box:
                    slide["boxes"].append(box)
                for tc in find_all(sp, "tc"):
                    for p in find_all(tc, "p"):
                        t = "".join(x.text or "" for x in find_all(p, "t")).strip()
                        if t:
                            slide["paras"].append({"text": t, "kind": "other", "bullet": False, "size": None, "color": None})
                continue
            if name == "cxnSp":
                continue
            fill = _fill(kid(sp, "spPr"), theme, cmap)
            if fill is None and kid(sp, "spPr") is not None and kid(kid(sp, "spPr"), "noFill") is None:
                fill = _color(path_to(sp, "style", "fillRef"), theme, cmap) if not ph else None
            body = kid(sp, "txBody")
            paras = []
            if body is not None:
                chain = level_chain(sp, kind, ph)
                scale = 1.0
                fit = find(kid(body, "bodyPr"), "normAutofit")
                if fit is not None and att(fit, "fontScale"):
                    scale = int(att(fit, "fontScale")) / 100000
                for p in kids(body, "p"):
                    ppr = kid(p, "pPr")
                    lvl = int(att(ppr, "lvl", 0)) + 1 if ppr is not None else 1
                    runs = [r for r in kids(p) if ln(r) in ("r", "fld")]
                    text = "".join((kid(r, "t").text or "") if kid(r, "t") is not None else "" for r in runs)
                    if not text.strip():
                        continue
                    sizes, cols = Counter(), Counter()
                    for r in runs:
                        t = (kid(r, "t").text or "") if kid(r, "t") is not None else ""
                        rpr = kid(r, "rPr")
                        sz = att(rpr, "sz") or lvl_prop(chain, lvl, lambda n: att(kid(n, "defRPr"), "sz"))
                        size = int(sz) / 100 * scale if sz else 18.0 * scale
                        sizes[round(size, 1)] += len(t)
                        col = _color(kid(rpr, "solidFill"), theme, cmap) if rpr is not None else None
                        if col is None:
                            col = lvl_prop(chain, lvl, lambda n: _color(kid(kid(n, "defRPr"), "solidFill"), theme, cmap))
                        if col is None:
                            col = theme.get(cmap.get("tx1", "dk1"))
                        if col is not None:
                            cols[col] += len(t)
                        thai = bool(ss_text.THAI.search(t))
                        face = att(kid(rpr, "cs" if thai else "latin"), "typeface") if rpr is not None else None
                        if not face:
                            face = lvl_prop(chain, lvl, lambda n: att(kid(kid(n, "defRPr"), "cs" if thai else "latin"), "typeface"))
                        face = _theme_face(face, tfonts, kind, thai)
                        if face:
                            deck["fonts"][face] += len(t)
                    if ppr is not None and kid(ppr, "buNone") is not None:
                        bullet = False
                    elif ppr is not None and (kid(ppr, "buChar") is not None or kid(ppr, "buAutoNum") is not None):
                        bullet = True
                    else:
                        bullet = lvl_prop(chain, lvl, lambda n: False if kid(n, "buNone") is not None else
                                          True if (kid(n, "buChar") is not None or kid(n, "buAutoNum") is not None) else None) or False
                        bullet = bullet and kind == "body"
                    size = sizes.most_common(1)[0][0] if sizes else None
                    color = cols.most_common(1)[0][0] if cols else None
                    for c, w in cols.items():
                        slide["colors"][c] += w
                    paras.append({"text": text, "kind": kind, "bullet": bullet, "size": size, "color": color})
            if paras or fill is not None:
                full = area >= 0.9
                if full and fill is not None and not paras:
                    slide["bg"], slide["picture_bg"] = fill, False  # a full-slide rectangle is the background
                    slide["colors"][fill] += 1
                    continue
                slide["elements"] += 1
                if box:
                    slide["boxes"].append(box)
                if fill is not None:
                    slide["colors"][fill] += 1
            slide["paras"].extend(paras)

    walk(find(root, "spTree"), lambda b: b)
    if att(root, "showMasterSp") != "0":
        for h in (layout, master):
            if h is None:
                continue
            for sp in kids(find(h.root, "spTree")):
                if ln(sp) == "pic" and not _ph(sp):
                    blip = find(sp, "blip")
                    hrels = pk.rels(h.part)
                    rid = ratt(blip, "embed")
                    if rid in hrels and pk.has(hrels[rid][0]):
                        data = pk.bytes(hrels[rid][0])
                        deck["media"][picture_key(data)] = data
                    box = _xfrm(kid(sp, "spPr"))
                    if box:
                        slide["boxes"].append(box)
    slide["W"], slide["H"] = W, H
    return slide


def _theme_face(face, tfonts, kind, thai):
    if not face:
        face = "+mj" if kind == "title" else "+mn"
    if face.startswith("+"):
        major = face.startswith("+mj")
        key = ("majorFont" if major else "minorFont") + (":cs" if thai or face.endswith("-cs") else ":latin")
        face = tfonts.get(key) or tfonts.get(key.split(":")[0] + ":latin") or ""
    return face.strip() or None


# ---------------------------------------------------------------- deck measures
def coverage(boxes, W, H, grid=40):
    if not boxes or not W or not H:
        return 0.0
    cells = set()
    for x, y, w, h in boxes:
        x0, y0 = max(0, x / W), max(0, y / H)
        x1, y1 = min(1, (x + w) / W), min(1, (y + h) / H)
        if x1 <= x0 or y1 <= y0:
            continue
        for i in range(int(x0 * grid), min(grid, int(math.ceil(x1 * grid)))):
            for j in range(int(y0 * grid), min(grid, int(math.ceil(y1 * grid)))):
                cells.add((i, j))
    return len(cells) / (grid * grid)


def measure_deck(deck, where):
    slides = deck["slides"]
    alltext = "\n".join(p["text"] for s in slides for p in s["paras"])
    lang = ss_text.language(alltext) if alltext.strip() else "en"
    v = {}

    def add(k, x):
        if x is not None:
            v.setdefault(k, []).append(float(x))
    colors = Counter()
    rows = []
    for s in slides:
        paras = s["paras"]
        title = next((p for p in paras if p["kind"] == "title"), None)
        body = [p for p in paras if p["kind"] != "title"]
        units = sum(ss_text.text_units(p["text"], lang) for p in paras)
        add("slide_text", units)
        add("slide_bullets", sum(1 for p in body if p["bullet"]))
        if s.get("elements") is not None and "boxes" in s:
            add("slide_elements", s["elements"])
        add("slide_images", len(s["pictures"]))
        if title:
            add("title_length", ss_text.text_units(title["text"], lang))
        tsize = title["size"] if title and title.get("size") else None
        bsizes = Counter()
        for p in body:
            if p.get("size"):
                bsizes[p["size"]] += len(p["text"])
        bsize = bsizes.most_common(1)[0][0] if bsizes else None
        add("title_size", tsize)
        add("body_size", bsize)
        if tsize and bsize:
            add("type_ratio", tsize / bsize)
        fill = None
        if "boxes" in s:
            fill = coverage(s["boxes"], s.get("W"), s.get("H"))
            add("slide_fill", fill)
        bg = s.get("bg")
        if bg is not None and not s.get("picture_bg"):
            add("bg_luma", luma(bg))
            ratios = [contrast_ratio(p["color"], bg) for p in paras if p.get("color")]
            if ratios:
                add("text_contrast", sorted(ratios)[len(ratios) // 2])
        colors.update(s.get("colors", {}))
        rows.append([math.log1p(units), float(sum(1 for p in body if p["bullet"])), float(len(s["pictures"])),
                     fill if fill is not None else 0.0, luma(bg) if bg is not None else 0.5, 1.0 if title else 0.0])
    n_colors, sat = color_values(colors)
    if colors:
        add("colors_used", n_colors)
        add("color_saturation", sat)
    if deck["fonts"]:
        add("typefaces", len(deck["fonts"]))
    add("aspect", deck.get("aspect"))
    prose = deck_prose(deck)
    text_seq = {"features": [], "rows": []}
    try:
        _, tv, tfp, _ = ss_text.measure_string(prose, where, lang)
        text_seq = tfp.get("seq") or text_seq
        for k in ("sentence_length", "question_rate", "exclaim_rate", "digit_rate", "emoji_rate", "first_person_rate",
                  "second_person_rate", "polite_end_rate", "soft_end_rate", "latin_mix", "contraction_rate", "word_length"):
            if tv.get(k):
                v[k] = tv[k]
    except StyleError:
        pass
    hidden = "\n\n".join(p["text"] for s in deck.get("hidden", []) for p in s["paras"])
    fp = _words_fp(alltext + ("\n\n" + hidden if hidden else ""), lang)
    fp["seq"] = {"features": ["log_text", "bullets", "pictures", "fill", "bg_luma", "has_title"], "rows": rows}
    fp["text_seq"] = text_seq
    fp.update(_media_fp(deck["media"], colors))
    info = {"units": len(slides), "unit": "slides", "lang": lang, "aspect": deck.get("aspect")}
    return info, v, fp, prose + ("\n\n" + hidden if hidden else "")


def _markdown(items):
    """(kind, text) pairs as Markdown blocks. Consecutive list items form one list block, as they do in a
    Markdown file, so a document and its Markdown twin give the text route the same paragraphs."""
    out, run = [], []
    for kind, text in items:
        if kind == "list":
            run.append("- " + text.replace("\n", " "))
            continue
        if run:
            out.append("\n".join(run))
            run = []
        # a line break inside a body paragraph stays: Thai often ends a sentence with one
        out.append(text if kind == "body" else "#" * max(1, min(6, kind)) + " " + text.replace("\n", " "))
    if run:
        out.append("\n".join(run))
    return "\n\n".join(out)


def deck_prose(deck):
    """A deck's words as Markdown: titles as headings, bullets as list items, other text as paragraphs."""
    return _markdown([(1 if p["kind"] == "title" else "list" if p["bullet"] else "body", p["text"])
                      for s in deck["slides"] for p in s["paras"]])


def doc_prose(doc):
    """A document's prose as Markdown; table cells are left out (they are not sentences)."""
    return _markdown([(b["level"] or 1 if b["kind"] == "heading" else b["kind"], b["text"])
                      for b in doc["blocks"] if b["kind"] in ("heading", "list", "body")])


def book_text(book):
    out = []
    for s in book["sheets"]:
        out.append("\n".join(c["text"] for c in sorted(s["cells"], key=lambda c: (c["row"] or 0, c["col"] or 0))))
    return "\n\n".join(out)


def _words_fp(text, lang):
    n = ss_text.shingle_size(lang)
    toks = ss_text.tokens_for_shingles(text, lang)
    return {"lang": lang, "shingle_n": n, "shingles": sorted(set(ss_text.shingle_hashes(toks, n)))}


def _cells_fp(cells, lang):
    """Shingles from inside each cell only. Runs across cells are labels in a row (January to December, Q1 to
    Q4), which any two sheets on the same subject share; a long note or description copied into a cell is
    still one cell and still found."""
    n = ss_text.shingle_size(lang)
    found = set()
    for text in cells:
        toks = ss_text.tokens_for_shingles(text, lang)
        if len(toks) >= n:
            found.update(ss_text.shingle_hashes(toks, n))
    return {"lang": lang, "shingle_n": n, "shingles": sorted(found)}


def _media_fp(media, colors):
    fp = {"media": sorted(media), "palette": palette_of(colors)}
    looks = picture_looks(media) if media else {"dhash": [], "thumbs": []}
    if looks is not None:
        fp["media_dhash"], fp["media_thumbs"] = looks["dhash"], looks["thumbs"]
    return fp


# ---------------------------------------------------------------- Word
def _on(el, name):
    """A Word toggle property (w:b, w:i) under rPr: True, False or None when absent."""
    x = kid(el, name)
    if x is None:
        return None
    return att(x, "val", "true") not in ("0", "false", "off")


class _WordStyles:
    def __init__(self, root, theme_fonts):
        self.by_id, self.default_p = {}, None
        self.theme_fonts = theme_fonts
        dd = find(root, "docDefaults") if root is not None else None
        self.d_rpr = path_to(dd, "rPrDefault", "rPr")
        self.d_ppr = path_to(dd, "pPrDefault", "pPr")
        for s in kids(root, "style") if root is not None else []:
            sid = att(s, "styleId")
            self.by_id[sid] = s
            if att(s, "type") == "paragraph" and att(s, "default") in ("1", "true"):
                self.default_p = sid

    def chain(self, sid):
        out, seen = [], set()
        while sid and sid in self.by_id and sid not in seen:
            seen.add(sid)
            s = self.by_id[sid]
            out.append(s)
            sid = att(kid(s, "basedOn"), "val")
        return out

    def name(self, sid):
        return (att(kid(self.by_id.get(sid), "name"), "val", "") or "").lower()

    def ppr(self, sid, direct):
        """Effective paragraph property nodes, most specific first."""
        return [x for x in [direct] + [kid(s, "pPr") for s in self.chain(sid)] + [self.d_ppr] if x is not None]

    def rpr(self, psid, rsid, direct):
        return [x for x in [direct] + [kid(s, "rPr") for s in self.chain(rsid)] + [kid(s, "rPr") for s in self.chain(psid)]
                + [self.d_rpr] if x is not None]


def _first(nodes, fn):
    for n in nodes:
        v = fn(n)
        if v is not None:
            return v
    return None


def _word_runs(el):
    for c in el:
        n = ln(c)
        if n == "r":
            yield c
        elif n in ("hyperlink", "ins", "smartTag", "fldSimple", "sdt", "sdtContent", "customXml", "dir", "bdo"):
            yield from _word_runs(c)


def _word_text(r):
    out = []
    for c in r:
        n = ln(c)
        if n == "t":
            out.append(c.text or "")
        elif n in ("tab", "ptab"):
            out.append(" ")
        elif n in ("br", "cr"):
            out.append("\n")
        elif n == "noBreakHyphen":
            out.append("-")
    return "".join(out)


def read_docx(path):
    pk = Pack(path, "Word")
    part = "word/document.xml"
    root = pk.xml(part)
    rels = pk.rels(part)
    theme_part = next((t for t, k in rels.values() if k == "theme"), None)
    _, tfonts = _theme(pk, theme_part)
    sroot = pk.xml("word/styles.xml") if pk.has("word/styles.xml") else None
    st = _WordStyles(sroot, tfonts)
    doc = {"blocks": [], "media": {}, "pictures": 0, "tables": 0, "page": None, "fonts": Counter(), "colors": Counter()}

    def pictures(el):
        for b in find_all(el, "blip") + find_all(el, "imagedata"):
            rid = ratt(b, "embed") or ratt(b, "id")
            if rid in rels and pk.has(rels[rid][0]):
                data = pk.bytes(rels[rid][0])
                doc["media"][picture_key(data)] = data
                doc["pictures"] += 1

    def para(p, in_table=False):
        ppr = kid(p, "pPr")
        sid = att(kid(ppr, "pStyle"), "val") or st.default_p
        pnodes = st.ppr(sid, ppr)
        name = st.name(sid)
        m = re.match(r"heading (\d)", name)
        level = int(m.group(1)) if m else 1 if name == "title" else None
        if level is None:
            ol = _first(pnodes, lambda n: att(kid(n, "outlineLvl"), "val"))
            if ol is not None and int(ol) < 9:
                level = int(ol) + 1
        num = _first(pnodes, lambda n: att(path_to(n, "numPr", "numId"), "val"))
        kind = "table" if in_table else "heading" if level else "list" if num not in (None, "0") else "body"
        sizes, chars, bold, italic, text = Counter(), 0, 0, 0, []
        for r in _word_runs(p):
            t = _word_text(r)
            pictures(r)
            if not t:
                continue
            text.append(t)
            n = len(t.strip())
            rnodes = st.rpr(sid, att(path_to(r, "rPr", "rStyle"), "val"), kid(r, "rPr"))
            thai = bool(ss_text.THAI.search(t))
            sz = _first(rnodes, lambda x: att(kid(x, "szCs" if thai else "sz"), "val")) or \
                _first(rnodes, lambda x: att(kid(x, "sz"), "val"))
            sizes[int(sz) / 2 if sz else 10.0] += n
            chars += n
            if _first(rnodes, lambda x: _on(x, "bCs" if thai else "b")):
                bold += n
            if _first(rnodes, lambda x: _on(x, "iCs" if thai else "i")):
                italic += n
            col = _first(rnodes, lambda x: att(kid(x, "color"), "val"))
            rgb = rgb_of(col) if col and col.lower() != "auto" else (0.0, 0.0, 0.0)
            if rgb:
                doc["colors"][rgb] += n
            fonts = _first(rnodes, lambda x: kid(x, "rFonts"))
            face = None
            if fonts is not None:
                face = att(fonts, "cs" if thai else "ascii") or att(fonts, "hAnsi")
                tf = att(fonts, "cstheme" if thai else "asciiTheme") or att(fonts, "hAnsiTheme")
                if not face and tf:
                    face = tfonts.get(("majorFont" if tf.startswith("major") else "minorFont") + (":cs" if thai else ":latin"))
            if not face:
                face = tfonts.get("minorFont:cs" if thai else "minorFont:latin")
            if face:
                doc["fonts"][face] += n
        joined = "".join(text).strip()
        if not joined:
            return
        size = sizes.most_common(1)[0][0] if sizes else None
        line = after = None
        # each spacing attribute is inherited on its own: a paragraph may set `after` and take `line` from its style
        got = _first(pnodes, lambda n: (att(kid(n, "spacing"), "line"), att(kid(n, "spacing"), "lineRule", "auto"))
                     if att(kid(n, "spacing"), "line") else None)
        if got:
            line = int(got[0]) / 240 if got[1] == "auto" else (int(got[0]) / 20) / (LINE_EM * (size or 10))
        auto_after = _first(pnodes, lambda n: att(kid(n, "spacing"), "afterAutospacing"))
        got = _first(pnodes, lambda n: att(kid(n, "spacing"), "after"))
        if auto_after in ("1", "true", "on"):
            after = 14.0
        elif got is not None:
            after = int(got) / 20
        jc = _first(pnodes, lambda n: att(kid(n, "jc"), "val"))
        doc["blocks"].append({"kind": kind, "level": level or 0, "text": joined, "size": size, "chars": chars, "bold": bold,
                              "italic": italic, "line": line if line is not None else 1.0, "after": after if after is not None else 0.0,
                              "justified": jc in ("both", "distribute")})

    def body(el, in_table=False):
        for c in el:
            n = ln(c)
            if n == "p":
                para(c, in_table)
            elif n == "tbl":
                if not in_table:
                    doc["tables"] += 1
                for p in find_all(c, "p"):
                    para(p, True)
            elif n in ("sdt", "sdtContent", "customXml"):
                body(c, in_table)
            elif n == "sectPr":
                pg, mar = kid(c, "pgSz"), kid(c, "pgMar")
                if pg is not None:
                    w, h = int(att(pg, "w", 11906)), int(att(pg, "h", 16838))
                    lr = (int(att(mar, "left", 1440)) + int(att(mar, "right", 1440))) if mar is not None else 2880
                    doc["page"] = {"w": w / 20, "h": h / 20, "margins": lr / 20}
    body(kid(root, "body"))
    return doc


# ---------------------------------------------------------------- Excel
BUILTIN_DECIMALS = {1: 0, 2: 2, 3: 0, 4: 2, 9: 0, 10: 2, 11: 2, 37: 0, 38: 0, 39: 2, 40: 2, 48: 1}
THEME_ORDER = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"]


def decimals_of(code):
    code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code.split(";")[0])
    if not re.search(r"[0#?]", code):
        return None
    m = re.search(r"\.([0#?]+)", code)
    return len(m.group(1)) if m else 0


def _col_index(ref):
    m = re.match(r"([A-Z]+)(\d+)", ref or "")
    if not m:
        return None, None
    c = 0
    for ch in m.group(1):
        c = c * 26 + ord(ch) - 64
    return c, int(m.group(2))


def read_xlsx(path):
    pk = Pack(path, "Excel")
    wb = pk.xml("xl/workbook.xml")
    rels = pk.rels("xl/workbook.xml")
    theme_part = next((t for t, k in rels.values() if k == "theme"), None)
    tcolors, _ = _theme(pk, theme_part)
    shared = []
    if pk.has("xl/sharedStrings.xml"):
        for si in kids(pk.xml("xl/sharedStrings.xml"), "si"):
            shared.append("".join(t.text or "" for t in find_all(si, "t") if ln(t) == "t"))
    fonts, fills, xfs, fmts = [], [], [], {}
    if pk.has("xl/styles.xml"):
        sr = pk.xml("xl/styles.xml")
        for f in find_all(find(sr, "numFmts"), "numFmt"):
            fmts[int(att(f, "numFmtId", 0))] = att(f, "formatCode", "")

        def xcolor(c):
            if c is None:
                return None
            if att(c, "rgb"):
                return rgb_of(att(c, "rgb"))
            if att(c, "theme") is not None:
                i = int(att(c, "theme"))
                return tcolors.get(THEME_ORDER[i]) if i < len(THEME_ORDER) else None
            return None
        for f in kids(find(sr, "fonts"), "font"):
            fonts.append({"size": float(att(kid(f, "sz"), "val", 11)), "bold": _on(f, "b") or False,
                          "name": att(kid(f, "name"), "val"), "color": xcolor(kid(f, "color"))})
        for f in kids(find(sr, "fills"), "fill"):
            pf = kid(f, "patternFill")
            solid = pf is not None and att(pf, "patternType") == "solid"
            fills.append(xcolor(kid(pf, "fgColor")) if solid else None)
        for x in kids(find(sr, "cellXfs"), "xf"):
            nf = int(att(x, "numFmtId", 0))
            xfs.append({"font": int(att(x, "fontId", 0)), "fill": int(att(x, "fillId", 0)), "numfmt": nf,
                        "decimals": BUILTIN_DECIMALS.get(nf) if nf in BUILTIN_DECIMALS else decimals_of(fmts[nf]) if nf in fmts else None})
    book = {"sheets": [], "media": {}, "fonts": Counter(), "colors": Counter()}
    budget = MAX_CELLS
    for s in find_all(find(wb, "sheets"), "sheet"):
        rid = ratt(s, "id")
        if rid not in rels:
            continue
        part = rels[rid][0]
        if not pk.has(part):
            continue
        hidden = att(s, "state") in ("hidden", "veryHidden")
        root = pk.xml(part)
        sheet = {"name": att(s, "name"), "cells": [], "merged": len(find_all(find(root, "mergeCells"), "mergeCell")), "charts": 0}
        for c in find_all(find(root, "sheetData"), "c"):
            if budget <= 0:
                break
            t, v, f = att(c, "t", "n"), kid(c, "v"), kid(c, "f")
            if t == "inlineStr":
                text = "".join(x.text or "" for x in find_all(c, "t"))
            elif v is None or v.text is None:
                if f is None:
                    continue
                text = ""
            elif t == "s":
                i = int(v.text)
                text = shared[i] if i < len(shared) else ""
            else:
                text = v.text
            if not text.strip() and f is None:
                continue
            budget -= 1
            col, row = _col_index(att(c, "r"))
            xf = xfs[int(att(c, "s", 0))] if xfs and int(att(c, "s", 0)) < len(xfs) else {"font": 0, "fill": 0, "decimals": None, "numfmt": 0}
            font = fonts[xf["font"]] if xf["font"] < len(fonts) else {"size": 11.0, "bold": False, "name": None, "color": None}
            fill = fills[xf["fill"]] if xf["fill"] < len(fills) else None
            kind = "num" if t in ("n",) and text else "text" if t in ("s", "str", "inlineStr") else "bool" if t == "b" else "error" if t == "e" else "text"
            dec = xf["decimals"]
            if kind == "num" and xf["numfmt"] == 0:
                dec = _shown_decimals(text)
            sheet["cells"].append({"row": row, "col": col, "kind": kind, "formula": f is not None, "text": text,
                                   "bold": font["bold"], "filled": fill is not None, "size": font["size"], "decimals": dec})
            if hidden:
                continue
            if font["name"]:
                book["fonts"][font["name"]] += 1
            if font["color"]:
                book["colors"][font["color"]] += 1
            if fill:
                book["colors"][fill] += 1
        drawing = next((t for t, k in pk.rels(part).values() if k == "drawing"), None)
        if drawing and pk.has(drawing):
            droot = pk.xml(drawing)
            sheet["charts"] = len(find_all(droot, "chart"))
            drels = pk.rels(drawing)
            for b in find_all(droot, "blip"):
                rid = ratt(b, "embed")
                if rid in drels and pk.has(drels[rid][0]):
                    data = pk.bytes(drels[rid][0])
                    book["media"][picture_key(data)] = data
        # like a hidden slide: not measured, still checked for copied words and pictures
        book.setdefault("hidden", []).append(sheet) if hidden else book["sheets"].append(sheet)
    if not book["sheets"]:
        raise StyleError(f"{path}: no visible sheets")
    return book


def _shown_decimals(text):
    try:
        x = float(text)
    except ValueError:
        return None
    s = repr(round(x, 10))
    return len(s.split(".")[1].rstrip("0")) if "." in s and "e" not in s else 0


def read_csv(path):
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        sample = f.read(65536)
        f.seek(0)
        if path.lower().endswith(".tsv"):
            dialect = csv.excel_tab
        else:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
        cells = []
        for r, row in enumerate(csv.reader(f, dialect), 1):
            for c, text in enumerate(row, 1):
                if not text.strip():
                    continue
                num = re.fullmatch(r"\s*[-+]?[\d,]*\.?\d+([eE][-+]?\d+)?\s*%?\s*", text) is not None
                dec = len(text.strip().rstrip("%").split(".")[1]) if num and "." in text else 0 if num else None
                cells.append({"row": r, "col": c, "kind": "num" if num else "text", "formula": False, "text": text,
                              "bold": None, "filled": None, "size": None, "decimals": dec})
                if len(cells) >= MAX_CELLS:
                    break
            if len(cells) >= MAX_CELLS:
                break
    if not cells:
        raise StyleError(f"{path}: no cells")
    return {"sheets": [{"name": os.path.basename(path), "cells": cells, "merged": None, "charts": None}], "media": {},
            "fonts": Counter(), "colors": Counter()}


def measure_book(book, where):
    v = {}

    def add(k, x):
        if x is not None:
            v.setdefault(k, []).append(float(x))
    rows_fp = []
    labels, decs, sizes = [], [], []
    for s in book["sheets"]:
        cells = s["cells"]
        if not cells:
            continue
        cols = {c["col"] for c in cells if c["col"]}
        rows = {c["row"] for c in cells if c["row"]}
        nums = [c for c in cells if c["kind"] == "num"]
        add("sheet_columns", len(cols))
        add("sheet_rows", len(rows))
        add("numeric_share", len(nums) / len(cells))
        add("formula_share", sum(c["formula"] for c in cells) / len(cells))
        first = min(rows) if rows else None
        head = [c for c in cells if c["row"] == first]
        styled = None
        if head and head[0]["bold"] is not None:
            styled = 1.0 if sum(bool(c["bold"] or c["filled"]) for c in head) >= 0.5 * len(head) else 0.0
            add("header_styled", styled)
        add("merged_rate", s["merged"])
        add("chart_rate", s["charts"])
        decs += [c["decimals"] for c in nums if c["decimals"] is not None][:2000]
        labels += [len(c["text"].strip()) for c in cells if c["kind"] == "text" and c["text"].strip()][:2000]
        sizes += [c["size"] for c in cells if c["size"]][:2000]
        rows_fp.append([math.log1p(len(cols)), math.log1p(len(rows)), len(nums) / len(cells),
                        sum(c["formula"] for c in cells) / len(cells), float(s["charts"] or 0), styled or 0.0])
    v["decimals"] = [float(d) for d in decs] or None
    v["label_length"] = [float(x) for x in labels] or None
    v["body_size"] = [float(x) for x in sizes] or None
    v = {k: x for k, x in v.items() if x}
    if book["fonts"]:
        add("typefaces", len(book["fonts"]))
    if book["colors"]:
        n, sat = color_values(book["colors"])
        add("colors_used", n)
        add("color_saturation", sat)
    alltext = book_text(book)
    lang = ss_text.language(alltext) if alltext.strip() else "en"
    hidden = book_text({"sheets": book.get("hidden", [])})
    cells = [c["text"] for sh in book["sheets"] + book.get("hidden", []) for c in sh["cells"]]
    fp = _cells_fp(cells, lang)
    fp["seq"] = {"features": ["log_columns", "log_rows", "numeric", "formulas", "charts", "header"], "rows": rows_fp}
    fp.update(_media_fp(book["media"], book["colors"]))
    info = {"units": len(book["sheets"]), "unit": "sheets", "lang": lang}
    return info, v, fp, alltext + ("\n\n" + hidden if hidden.strip() else "")


# ---------------------------------------------------------------- documents: measures
def measure_doc(doc, where):
    blocks = doc["blocks"]
    prose = doc_prose(doc)
    alltext = "\n\n".join(b["text"] for b in blocks)
    lang = ss_text.language(alltext) if alltext.strip() else "en"
    v = {}
    text_seq = {"features": [], "rows": []}
    try:
        _, tv, tfp, _ = ss_text.measure_string(prose, where, lang)
        v.update(tv)
        text_seq = tfp.get("seq") or text_seq
    except StyleError:
        pass

    def add(k, x):
        if x is not None:
            v.setdefault(k, []).append(float(x))
    body = [b for b in blocks if b["kind"] in ("body", "list")]
    sizes = Counter()
    for b in body:
        if b.get("size"):
            sizes[b["size"]] += b.get("chars") or len(b["text"])
            add("body_size", b["size"])
    base = sizes.most_common(1)[0][0] if sizes else None
    for b in blocks:
        if b["kind"] == "heading" and b.get("size") and base:
            add("type_ratio", b["size"] / base)
    for b in body:
        add("line_spacing", b.get("line"))
        add("paragraph_space", b.get("after"))
    for i in range(0, len(blocks), 10):
        g = blocks[i:i + 10]
        chars = sum(b.get("chars") or 0 for b in g)
        if chars and any(b.get("bold") is not None for b in g):
            add("bold_share", sum(b.get("bold") or 0 for b in g) / chars)
            add("italic_share", sum(b.get("italic") or 0 for b in g) / chars)
        gb = [b for b in g if b["kind"] == "body" and b.get("justified") is not None]
        if gb:
            add("justified_share", sum(b["justified"] for b in gb) / len(gb))
    paras = max(1, len(body))
    if doc.get("pictures") is not None:
        add("image_rate", 10 * doc["pictures"] / paras)
    if doc.get("tables") is not None:
        add("table_rate", 10 * doc["tables"] / paras)
    page = doc.get("page")
    if page and page.get("w") and page.get("h"):
        add("aspect", page["w"] / page["h"])
        if page.get("margins") is not None:
            add("margin_share", page["margins"] / page["w"])
    for units in doc.get("page_units") or []:
        if units:
            v.setdefault("page_text", []).append(float(units))
    if doc.get("fonts"):
        add("typefaces", len(doc["fonts"]))
    if doc.get("colors"):
        n, sat = color_values(doc["colors"])
        add("colors_used", n)
        add("color_saturation", sat)
    if not v:
        raise StyleError(f"{where}: nothing to measure (no text and no layout found)")
    rows = [[math.log1p(len(b["text"])), 1.0 if b["kind"] == "heading" else 0.0, 1.0 if b["kind"] == "list" else 0.0,
             1.0 if b["kind"] == "table" else 0.0, (b.get("size") or base or 0.0) / (base or 1.0),
             (b.get("bold") or 0) / max(1, b.get("chars") or len(b["text"]))] for b in blocks]
    fp = _words_fp(alltext, lang)
    fp["seq"] = {"features": ["log_chars", "is_heading", "is_list", "is_table", "size", "bold"], "rows": rows}
    fp["text_seq"] = text_seq  # the text route's paragraphs, for an order check against another written medium
    fp.update(_media_fp(doc.get("media") or {}, doc.get("colors") or Counter()))
    n_sent = len(v.get("sentence_length", []))
    info = {"units": n_sent or len(blocks), "unit": "sentences" if n_sent else "blocks", "lang": lang}
    if doc.get("page_units"):
        info["pages"] = len(doc["page_units"])
    return info, v, fp, alltext


# ---------------------------------------------------------------- OpenDocument
def _len_pt(s):
    m = re.fullmatch(r"\s*(-?[\d.]+)\s*(pt|cm|mm|in|pc|px)?\s*", s or "")
    if not m:
        return None
    x = float(m.group(1))
    return x * {"pt": 1, "cm": 28.3465, "mm": 2.83465, "in": 72, "pc": 12, "px": 0.75, None: 1}[m.group(2)]


class _OdfStyles:
    def __init__(self, roots):
        self.styles, self.defaults, self.faces, self.decimals = {}, {}, {}, {}
        for root in roots:
            for el in root.iter():
                n = ln(el)
                if n == "style":
                    self.styles[(att(el, "family"), att(el, "name"))] = el
                elif n == "default-style":
                    self.defaults[att(el, "family")] = el
                elif n == "font-face":
                    self.faces[att(el, "name")] = (att(el, "font-family") or att(el, "name") or "").strip("'\"")
                elif n in ("number-style", "percentage-style", "currency-style"):
                    num = kid(el, "number")
                    num = num if num is not None else kid(el, "scientific-number")
                    if num is not None:
                        self.decimals[att(el, "name")] = int(att(num, "decimal-places", 0))

    def prop(self, family, name, group, key):
        seen = set()
        while name and (family, name) not in seen:
            seen.add((family, name))
            el = self.styles.get((family, name))
            if el is None:
                break
            v = att(kid(el, group), key)
            if v is not None:
                return v
            name = att(el, "parent-style-name")
        return att(kid(self.defaults.get(family), group), key)

    def style(self, family, name):
        return self.styles.get((family, name))


def _odf_roots(pk_or_path, flat):
    if flat:
        with open(pk_or_path, "rb") as f:
            data = f.read(MAX_PART + 1)
        if len(data) > MAX_PART:
            raise StyleError(f"{pk_or_path}: over {MAX_PART >> 20} MB; refused")
        root = parse_xml(data, pk_or_path)
        return root, [root]
    pk = pk_or_path
    content = pk.xml("content.xml")
    roots = [content] + ([pk.xml("styles.xml")] if pk.has("styles.xml") else [])
    return content, roots


def read_odf(path, medium):
    flat = ext_of(path).startswith(".fod")
    pk = None if flat else Pack(path, "OpenDocument")
    content, roots = _odf_roots(path if flat else pk, flat)
    st = _OdfStyles(roots)
    media = {}

    def picture(href):
        if pk is not None and href and pk.has(href):
            data = pk.bytes(href)
            media[picture_key(data)] = data
            return picture_key(data)
        return None
    body = find(content, "body")
    if medium == "document":
        return _odt(find(body, "text"), st, picture, media, roots)
    if medium == "slides":
        return _odp(find(body, "presentation"), st, picture, media, roots)
    return _ods(find(body, "spreadsheet"), st, picture, media)


def _odf_text(el):
    out = [el.text or ""]
    for c in el:
        n = ln(c)
        if n == "s":
            out.append(" " * int(att(c, "c", 1)))
        elif n == "tab":
            out.append(" ")
        elif n == "line-break":
            out.append("\n")
        elif n in ("span", "a", "meta"):
            out.append(_odf_text(c))
        out.append(c.tail or "")
    return "".join(out)


def _odf_page(st, roots):
    for root in roots:
        for el in root.iter():
            if ln(el) == "page-layout":
                pr = kid(el, "page-layout-properties")
                w, h = _len_pt(att(pr, "page-width")), _len_pt(att(pr, "page-height"))
                if w and h:
                    ml, mr = _len_pt(att(pr, "margin-left") or "0") or 0, _len_pt(att(pr, "margin-right") or "0") or 0
                    return {"w": w, "h": h, "margins": ml + mr}
    return None


def _odt(text_root, st, picture, media, roots):
    doc = {"blocks": [], "media": media, "pictures": 0, "tables": 0, "page": _odf_page(st, roots), "fonts": Counter(),
           "colors": Counter()}

    def run_props(pstyle, tstyle, key):
        v = st.prop("text", tstyle, "text-properties", key) if tstyle else None
        return v if v is not None else st.prop("paragraph", pstyle, "text-properties", key)

    def para(p, kind, level=0):
        for fr in find_all(p, "frame"):
            img = kid(fr, "image")
            if img is not None and picture(att(img, "href")):
                doc["pictures"] += 1
        text = _odf_text(p).strip()
        if not text:
            return
        ps = att(p, "style-name")
        size = _len_pt(run_props(ps, None, "font-size") or "") or 12.0
        chars = len(text)
        bold = italic = 0
        pieces = [(ps, None, p.text or "")]
        for c in p:
            pieces += [(ps, att(c, "style-name") if ln(c) == "span" else None, _odf_text(c) if ln(c) in ("span", "a") else ""),
                       (ps, None, c.tail or "")]
        for _, ts, t in pieces:
            n = len(t.strip())
            if run_props(ps, ts, "font-weight") == "bold":
                bold += n
            if run_props(ps, ts, "font-style") == "italic":
                italic += n
            col = rgb_of(run_props(ps, ts, "color") or "#000000")
            if col and n:
                doc["colors"][col] += n
            face = run_props(ps, ts, "font-name")
            if face and n:
                doc["fonts"][st.faces.get(face, face)] += n
        lh = st.prop("paragraph", ps, "paragraph-properties", "line-height")
        line = float(lh[:-1]) / 100 if lh and lh.endswith("%") else ((_len_pt(lh) or 0) / (LINE_EM * size) if lh else 1.0)
        after = _len_pt(st.prop("paragraph", ps, "paragraph-properties", "margin-bottom") or "0") or 0.0
        align = st.prop("paragraph", ps, "paragraph-properties", "text-align")
        doc["blocks"].append({"kind": kind, "level": level, "text": text, "size": size, "chars": chars, "bold": bold,
                              "italic": italic, "line": line, "after": after, "justified": align == "justify"})

    def walk(el, in_list=False, in_table=False):
        for c in el:
            n = ln(c)
            if n == "h":
                para(c, "table" if in_table else "heading", int(att(c, "outline-level", 1)))
            elif n == "p":
                para(c, "table" if in_table else "list" if in_list else "body")
            elif n in ("list", "list-item", "list-header"):
                walk(c, True, in_table)
            elif n == "table":
                if not in_table:
                    doc["tables"] += 1
                walk(c, in_list, True)
            elif n in ("table-row", "table-cell", "table-rows", "table-header-rows", "section", "index-body"):
                walk(c, in_list, in_table)
    if text_root is not None:
        walk(text_root)
    return doc


def _odp(pres, st, picture, media, roots):
    page_layout = _odf_page(st, roots) or {"w": 28 * 28.3465, "h": 15.75 * 28.3465}
    W, H = page_layout["w"], page_layout["h"]
    deck = {"aspect": W / H, "slides": [], "media": media, "fonts": Counter()}
    for page in kids(pres, "page"):
        dps = att(page, "style-name")
        fill = st.prop("drawing-page", dps, "drawing-page-properties", "fill")
        bg = rgb_of(st.prop("drawing-page", dps, "drawing-page-properties", "fill-color")) if fill == "solid" else (1.0, 1.0, 1.0)
        slide = {"paras": [], "boxes": [], "pictures": [], "elements": 0, "bg": bg, "colors": Counter(), "W": W, "H": H,
                 "picture_bg": fill == "bitmap"}
        hidden = st.prop("drawing-page", dps, "drawing-page-properties", "visibility") == "hidden"
        fonts, deck["fonts"] = deck["fonts"], (Counter() if hidden else deck["fonts"])
        for fr in kids(page):
            n = ln(fr)
            if n not in ("frame", "custom-shape", "rect", "ellipse", "g"):
                continue
            cls = nsatt(fr, "presentation", "class") or ""
            if cls in ("page-number", "footer", "date-time", "header"):
                continue
            box = None
            x, y, w, h = (_len_pt(att(fr, k) or "") for k in ("x", "y", "width", "height"))
            if None not in (x, y, w, h):
                box = (x, y, w, h)
            kind = "title" if cls == "title" else "body" if cls in ("outline", "subtitle", "text") else "other"
            img = kid(fr, "image")
            if img is not None and kid(fr, "text-box") is None:
                key = picture(att(img, "href"))
                if key:
                    slide["pictures"].append(key)
                slide["elements"] += 1
                if box:
                    slide["boxes"].append(box)
                continue
            gs = nsatt(fr, "drawing", "style-name")
            pstyle = nsatt(fr, "presentation", "style-name")
            ffill = st.prop("graphic", gs, "graphic-properties", "fill") or st.prop("presentation", pstyle, "graphic-properties", "fill")
            fcol = rgb_of(st.prop("graphic", gs, "graphic-properties", "fill-color")) if ffill == "solid" else None
            paras = []
            for p in find_all(fr, "p"):
                t = _odf_text(p).strip()
                if not t:
                    continue
                ps = att(p, "style-name")
                spans = [att(c, "style-name") for c in p if ln(c) == "span"]
                size = None
                for ts in spans + [None]:
                    raw = (st.prop("text", ts, "text-properties", "font-size") if ts else None) or \
                        st.prop("paragraph", ps, "text-properties", "font-size") or \
                        st.prop("presentation", pstyle, "text-properties", "font-size")
                    size = _len_pt(raw or "")
                    if size:
                        break
                col = rgb_of((st.prop("text", spans[0], "text-properties", "color") if spans else None)
                             or st.prop("paragraph", ps, "text-properties", "color")
                             or st.prop("presentation", pstyle, "text-properties", "color") or "#000000")
                face = (st.prop("text", spans[0], "text-properties", "font-name") if spans else None) or \
                    st.prop("paragraph", ps, "text-properties", "font-name") or st.prop("presentation", pstyle, "text-properties", "font-name")
                if face:
                    deck["fonts"][st.faces.get(face, face)] += len(t)
                if col:
                    slide["colors"][col] += len(t)
                in_list = any(ln(a) == "list-item" for a in fr.iter() if p in list(a))
                paras.append({"text": t, "kind": kind, "bullet": kind == "body" and cls == "outline" or in_list, "size": size, "color": col})
            if paras or fcol is not None:
                if box and W and H and box[2] * box[3] / (W * H) >= 0.9 and fcol is not None and not paras:
                    slide["bg"] = fcol
                    continue
                slide["elements"] += 1
                if box:
                    slide["boxes"].append(box)
                if fcol is not None:
                    slide["colors"][fcol] += 1
            slide["paras"].extend(paras)
        if slide["bg"]:
            slide["colors"][slide["bg"]] += 1
        deck["fonts"] = fonts
        deck.setdefault("hidden", []).append(slide) if hidden else deck["slides"].append(slide)
    if not deck["slides"]:
        raise StyleError("no slides found")
    return deck


def _ods(sheet_root, st, picture, media):
    book = {"sheets": [], "media": media, "fonts": Counter(), "colors": Counter()}
    budget = MAX_CELLS
    for table in kids(sheet_root, "table"):
        sheet = {"name": att(table, "name"), "cells": [], "merged": 0, "charts": len(find_all(table, "object"))}
        hidden = st.prop("table", att(table, "style-name"), "table-properties", "display") == "false"
        r = 0
        for row in [x for x in table.iter() if ln(x) == "table-row"]:
            reps = min(int(att(row, "number-rows-repeated", 1)), 1000)
            cells_in_row = []
            col = 0
            for cell in [c for c in row if ln(c) in ("table-cell", "covered-table-cell")]:
                crep = min(int(att(cell, "number-columns-repeated", 1)), 1000)
                if ln(cell) == "covered-table-cell":
                    col += crep
                    continue
                if int(att(cell, "number-columns-spanned", 1)) > 1 or int(att(cell, "number-rows-spanned", 1)) > 1:
                    sheet["merged"] += 1
                vt = att(cell, "value-type")
                text = "\n".join(_odf_text(p) for p in kids(cell, "p"))
                formula = att(cell, "formula") is not None
                for _ in range(crep):
                    col += 1
                    if not text.strip() and not formula:
                        continue
                    cells_in_row.append((col, vt, text, formula, att(cell, "style-name")))
            for _ in range(reps):
                r += 1
                for col_i, vt, text, formula, cs in cells_in_row:
                    if budget <= 0:
                        break
                    budget -= 1
                    kind = "num" if vt in ("float", "percentage", "currency") else "text" if vt in (None, "string") else vt
                    sel = st.style("table-cell", cs) if cs else None
                    ds = att(sel, "data-style-name") if sel is not None else None
                    dec = st.decimals.get(ds) if ds else (_shown_decimals(text) if kind == "num" else None)
                    bold = st.prop("table-cell", cs, "text-properties", "font-weight") == "bold" if cs else False
                    bgc = rgb_of(st.prop("table-cell", cs, "table-cell-properties", "background-color") or "") if cs else None
                    size = _len_pt(st.prop("table-cell", cs, "text-properties", "font-size") or "") if cs else None
                    face = st.prop("table-cell", cs, "text-properties", "font-name") if cs else None
                    if face and not hidden:
                        book["fonts"][st.faces.get(face, face)] += 1
                    if bgc and not hidden:
                        book["colors"][bgc] += 1
                    sheet["cells"].append({"row": r, "col": col_i, "kind": kind, "formula": formula, "text": text,
                                           "bold": bold, "filled": bgc is not None, "size": size or 10.0, "decimals": dec})
        for fr in find_all(table, "image"):
            picture(att(fr, "href"))
        book.setdefault("hidden", []).append(sheet) if hidden else book["sheets"].append(sheet)
    if not book["sheets"]:
        raise StyleError("no sheets found")
    return book


# ---------------------------------------------------------------- EPUB
def read_epub(path):
    pk = Pack(path, "EPUB")
    cont = pk.xml("META-INF/container.xml")
    opf_path = att(find(cont, "rootfile"), "full-path")
    if not opf_path or not pk.has(opf_path):
        raise StyleError(f"{path}: no package document")
    opf = pk.xml(opf_path)
    base = posixpath.dirname(opf_path)
    items = {att(i, "id"): (posixpath.normpath(posixpath.join(base, att(i, "href", ""))), att(i, "media-type", ""))
             for i in find_all(find(opf, "manifest"), "item")}
    doc = {"blocks": [], "media": {}, "pictures": 0, "tables": 0, "page": None, "fonts": None, "colors": None}
    for ref in find_all(find(opf, "spine"), "itemref"):
        href, mt = items.get(att(ref, "idref"), (None, None))
        if not href or not pk.has(href):
            continue
        raw = pk.bytes(href).decode("utf-8", "replace")
        doc["tables"] += len(re.findall(r"(?i)<table\b", raw))
        doc["pictures"] += len(re.findall(r"(?i)<img\b|<image\b", raw))
        raw = re.sub(r"(?is)<table\b.*?</table>", "\n\n", raw)  # counted above; cells are not prose
        for b in ss_text.blocks_of(ss_text.clean_markdown(ss_text.html_text(raw))):
            level = 1 if b["kind"] == "heading" else 0
            doc["blocks"].append({"kind": b["kind"] if b["kind"] in ("heading", "list") else "body", "level": level,
                                  "text": b["text"], "size": None, "chars": None, "bold": None, "italic": None,
                                  "line": None, "after": None, "justified": None})
    for href, mt in items.values():
        if mt.startswith("image/") and pk.has(href):
            data = pk.bytes(href)
            doc["media"][picture_key(data)] = data
    return doc


# ---------------------------------------------------------------- RTF
RTF_SKIP = {"stylesheet", "info", "header", "footer", "headerl", "headerr", "headerf", "footerl", "footerr", "footerf",
            "footnote", "listtable", "listoverridetable", "rsidtbl", "xmlnstbl", "generator", "themedata",
            "colorschememapping", "latentstyles", "datastore", "fldinst", "object", "listtext", "pntext", "pntxta",
            "pntxtb", "bkmkstart", "bkmkend", "annotation", "atnid", "atnauthor", "comment"}
RTF_CODEPAGES = {874: "cp874", 1250: "cp1250", 1251: "cp1251", 1252: "cp1252", 1253: "cp1253", 1254: "cp1254",
                 932: "cp932", 936: "gbk", 949: "cp949", 950: "cp950", 10000: "mac_roman"}
RTF_CHARS = {"emdash": "—", "endash": "–", "lquote": "'", "rquote": "'", "ldblquote": '"', "rdblquote": '"',
             "bullet": "•", "tab": " ", "line": "\n", "cell": " ", "~": " ", "_": "-", "-": ""}


def read_rtf(path):
    """RTF read as a stream of control words: paragraph and character formatting, fonts, colours, pictures."""
    with open(path, "rb") as f:
        data = f.read(MAX_PART + 1)
    if len(data) > MAX_PART:
        raise StyleError(f"{path}: over {MAX_PART >> 20} MB; refused")
    raw = data.decode("latin-1")
    if not raw.startswith("{\\rtf"):
        raise StyleError(f"{path}: not an RTF file")
    doc = {"blocks": [], "media": {}, "pictures": 0, "tables": 0, "page": None, "fonts": Counter(), "colors": Counter()}
    fonts, colortbl, color_cur = {}, [], [0, 0, 0]
    page = {"paperw": 12240, "paperh": 15840, "margl": 1800, "margr": 1800}
    codepage = [1252]
    PARA0 = {"sa": 0, "sl": 0, "slmult": 0, "qj": False, "outline": None, "list": False, "table": False}
    state = {"fs": 24, "b": False, "i": False, "f": 0, "cf": 0, "skip": False, "dest": None, "uc": 1}
    para = dict(PARA0)
    stack, buf, runs, font_buf, pict_buf, raw_bytes = [], [], [], [], [], []
    pend_skip = 0

    def emit(t):
        if state["skip"] or not t:
            return
        if state["dest"] == "fontentry":
            for i, piece in enumerate(t.split(";")):
                if i:  # a ';' ends a font name
                    fonts[state["f"]] = "".join(font_buf).strip()
                    font_buf.clear()
                font_buf.append(piece)
            return
        if state["dest"] in ("fonttbl", "colortbl", "pict"):
            return
        buf.append(t)
        runs.append((len(t.strip()), state["fs"] / 2, state["b"], state["i"], state["f"], state["cf"]))

    def flush_bytes():
        if raw_bytes:
            emit(bytes(raw_bytes).decode(RTF_CODEPAGES.get(codepage[0], "cp1252"), "replace"))
            raw_bytes.clear()

    def end_para():
        text = "".join(buf).strip()
        if text:
            sizes, chars, bold, italic = Counter(), 0, 0, 0
            for n, size, b, i, f, cf in runs:
                if not n:
                    continue
                sizes[size] += n
                chars += n
                bold += n if b else 0
                italic += n if i else 0
                if fonts.get(f):
                    doc["fonts"][fonts[f]] += n
                col = colortbl[cf] if 0 <= cf < len(colortbl) and colortbl[cf] else (0.0, 0.0, 0.0)
                doc["colors"][col] += n
            size = sizes.most_common(1)[0][0] if sizes else 12.0
            sl = para["sl"]
            line = (sl / 240 if para["slmult"] else abs(sl) / 20 / (LINE_EM * size)) if sl else 1.0
            kind = ("table" if para["table"] else "heading" if para["outline"] is not None else "list" if para["list"]
                    else "body")
            if kind == "table" and (not doc["blocks"] or doc["blocks"][-1]["kind"] != "table"):
                doc["tables"] += 1
            doc["blocks"].append({"kind": kind, "level": (para["outline"] or 0) + 1, "text": text, "size": size,
                                  "chars": chars, "bold": bold, "italic": italic, "line": line, "after": para["sa"] / 20,
                                  "justified": para["qj"]})
        buf.clear()
        runs.clear()

    # a backslash before a line break is a paragraph mark (macOS TextEdit and textutil write them)
    token = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(\r\n|\n|\r|.)|([{}])|[\r\n]+|([^\\{}\r\n]+)")
    for m in token.finditer(raw):
        word, num, hexb, sym, brace, text = m.groups()
        if hexb is not None:
            if pend_skip:
                pend_skip -= 1
            elif state["dest"] == "pict":
                pass
            else:
                raw_bytes.append(int(hexb, 16))
            continue
        flush_bytes()
        if brace == "{":
            stack.append(dict(state))
            continue
        if brace == "}":
            if state["dest"] == "pict" and pict_buf and not state.get("nonshp"):
                try:
                    blob = bytes.fromhex("".join(pict_buf))
                    doc["media"][picture_key(blob)] = blob
                    doc["pictures"] += 1
                except ValueError:
                    pass
            if state["dest"] == "pict":
                pict_buf.clear()
            if state["dest"] == "fontentry" and "".join(font_buf).strip():
                fonts[state["f"]] = "".join(font_buf).strip()
            if state["dest"] == "fontentry":
                font_buf.clear()
            if stack:
                state.clear()
                state.update(stack.pop())
            continue
        if text is not None:
            if pend_skip:
                k = min(pend_skip, len(text))
                text, pend_skip = text[k:], pend_skip - k
            if state["dest"] == "pict":
                pict_buf.append(re.sub(r"[^0-9a-fA-F]", "", text))
            elif state["dest"] == "colortbl":
                for _ in range(text.count(";")):
                    colortbl.append(tuple(c / 255 for c in color_cur) if color_cur != [None] * 3 else None)
                    color_cur = [0, 0, 0]
            else:
                emit(text)
            continue
        if sym is not None:
            if sym in ("\r\n", "\n", "\r"):
                end_para()
            elif sym == "*":
                state["skip"] = True
            elif sym in "\\{}":
                emit(sym)
            elif sym in RTF_CHARS:
                emit(RTF_CHARS[sym])
            continue
        n = int(num) if num is not None else None
        if word == "ansicpg" and n:
            codepage[0] = n
        elif word == "fonttbl":
            state["dest"] = "fonttbl"
        elif word == "f" and state["dest"] in ("fonttbl", "fontentry"):
            if state["dest"] == "fontentry" and "".join(font_buf).strip():
                fonts[state["f"]] = "".join(font_buf).strip()
            font_buf.clear()
            state["dest"], state["f"] = "fontentry", n or 0
        elif word == "colortbl":
            state["dest"] = "colortbl"
            color_cur = [None] * 3
        elif word in ("red", "green", "blue") and state["dest"] == "colortbl":
            if color_cur == [None] * 3:
                color_cur = [0, 0, 0]
            color_cur[("red", "green", "blue").index(word)] = n or 0
        elif word in RTF_SKIP:
            state["skip"] = True
        elif word == "nonshppict":  # the fallback copy of a picture that \shppict already holds
            state["skip"] = state["nonshp"] = True
        elif word == "pict":
            state["dest"] = "pict"
        elif word in ("par", "sect", "page", "row"):
            end_para()
        elif word in RTF_CHARS:
            emit(RTF_CHARS[word])
        elif word == "pard":
            para = dict(PARA0)
        elif word == "plain":
            state.update({"fs": 24, "b": False, "i": False, "f": 0, "cf": 0})
        elif word == "fs":
            state["fs"] = n or 24
        elif word in ("b", "i"):
            state[word] = n != 0
        elif word in ("f", "cf"):
            state[word] = n or 0
        elif word in ("sa", "sl", "slmult"):
            para[word] = n or 0
        elif word == "qj":
            para["qj"] = True
        elif word in ("ql", "qc", "qr"):
            para["qj"] = False
        elif word == "outlinelevel":
            para["outline"] = n
        elif word in ("ls", "ilvl", "pnlvlblt", "pnlvlbody"):
            para["list"] = True
        elif word == "intbl":
            para["table"] = True
        elif word == "u" and n is not None:
            emit(chr(n % 65536))
            pend_skip = state["uc"]
        elif word == "uc":
            state["uc"] = n or 0
        elif word in page and n is not None:
            page[word] = n
    flush_bytes()
    end_para()
    doc["page"] = {"w": page["paperw"] / 20, "h": page["paperh"] / 20, "margins": (page["margl"] + page["margr"]) / 20}
    return doc


# ---------------------------------------------------------------- PDF
def read_pdf(path, as_slides):
    try:
        import pypdf
    except ImportError:
        pypdf = None
    if pypdf is not None:
        pages = _pdf_pypdf(pypdf, path)
    elif shutil.which("pdftotext"):
        pages = _pdf_poppler(path)
    else:
        raise StyleError(f"{path}: reading PDF needs pypdf (`pip install pypdf`) or poppler's pdftotext "
                         "(`brew install poppler`, or your package manager)")
    if not any(p["lines"] for p in pages):
        raise StyleError(f"{path}: no text layer (a scanned PDF?); export the pages as images and measure them as images")
    alltext = "\n".join(l["text"] for p in pages for l in p["lines"])
    lang = ss_text.language(alltext)
    if as_slides:
        return _pdf_deck(pages, lang)
    return _pdf_doc(pages, lang)


def _mult(a, b):
    """PDF matrix product a x b, both as [a b c d e f]."""
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


IDENTITY = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def _pdf_get(d, key):
    try:
        v = d.get(key) if d is not None else None
        return v.get_object() if hasattr(v, "get_object") else v
    except Exception:
        return None


class _PdfSpace:
    """The transform pypdf leaves out. pypdf reads a form XObject with a fresh CTM, so text drawn inside a form
    (Canva puts every page in one) loses the page's own scale and the form's /Matrix. This follows each Do and
    keeps the matrix that maps the form's space to the page. A form is entered on its first operator, so the
    text pypdf flushes at the Do itself still belongs to the outer level."""

    def __init__(self, resources):
        self.stack = [(IDENTITY, resources)]
        self.pending = None

    def _enter(self):
        if self.pending is not None:
            self.stack.append(self.pending)
            self.pending = None

    def before(self, op, operands, cm, tm):
        self._enter()
        if op != b"Do" or not operands:
            return
        outer, res = self.stack[-1]
        entry = (outer, res)
        try:
            xo = _pdf_get(_pdf_get(res, "/XObject"), operands[0])
            if xo is not None and xo.get("/Subtype") == "/Form":
                matrix = [float(x) for x in (xo.get("/Matrix") or IDENTITY)][:6]
                matrix = matrix if len(matrix) == 6 else IDENTITY
                entry = (_mult(_mult(matrix, [float(x) for x in cm]), outer), _pdf_get(xo, "/Resources") or res)
        except Exception:
            pass
        self.pending = entry

    def after(self, op, operands, cm, tm):
        if op != b"Do":
            return
        if self.pending is not None:  # an image, an empty form, or one pypdf skipped
            self.pending = None
        elif len(self.stack) > 1:
            self.stack.pop()

    def size(self, size, cm, tm):
        try:
            m = _mult([float(x) for x in tm], _mult([float(x) for x in cm], self.stack[-1][0]))
            return (size or 0) * math.hypot(m[2], m[3])
        except Exception:
            return size or 0


def _pdf_images(resources, depth=0, seen=None):
    """Picture XObjects on a page, including those inside its form XObjects (bounded, each object once)."""
    seen = set() if seen is None else seen
    out = []
    xo = _pdf_get(resources, "/XObject")
    if xo is None or depth > 6:
        return out
    for k in list(xo.keys()):
        try:
            ref = xo.raw_get(k) if hasattr(xo, "raw_get") else xo[k]
            o = ref.get_object()
            ident = (getattr(ref, "idnum", None), getattr(ref, "generation", None)) if hasattr(ref, "idnum") else id(o)
            if ident in seen:
                continue
            seen.add(ident)
            if o.get("/Subtype") == "/Image":
                out.append(o)
            elif o.get("/Subtype") == "/Form":
                out.extend(_pdf_images(_pdf_get(o, "/Resources"), depth + 1, seen))
        except Exception:
            continue
        if len(seen) > 5000:
            break
    return out


def _pdf_pypdf(pypdf, path):
    try:
        reader = pypdf.PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise StyleError(f"{path}: the PDF is password protected")
    except StyleError:
        raise
    except Exception as e:  # pypdf raises its own error types for broken files
        raise StyleError(f"{path}: pypdf could not read it ({e})")
    pages = []
    for page in reader.pages:
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        if int(page.get("/Rotate", 0) or 0) % 180:
            w, h = h, w
        pieces = []
        space = _PdfSpace(_pdf_get(page, "/Resources"))

        def visit(text, cm, tm, font, size, pieces=pieces, space=space):
            if not text:
                return
            name = ""
            try:
                name = str(font.get("/BaseFont", "")).lstrip("/") if font else ""
            except Exception:
                name = ""
            real = space.size(size, cm, tm) if tm and cm else (size or 0)
            pieces.append((text, real, re.sub(r"^[A-Z]{6}\+", "", name)))
        try:
            page.extract_text(visitor_text=visit, visitor_operand_before=space.before, visitor_operand_after=space.after)
        except Exception as e:
            raise StyleError(f"{path}: pypdf could not read the text ({e})")
        lines, cur, cur_size, fonts = [], [], Counter(), Counter()
        for text, size, face in pieces:
            parts = text.split("\n")
            for i, part in enumerate(parts):
                if part:
                    cur.append(part)
                    cur_size[round(size, 1)] += len(part.strip())
                    if face:
                        fonts[face] += len(part.strip())
                if i < len(parts) - 1:
                    t = "".join(cur).strip()
                    if t:
                        lines.append({"text": t, "size": cur_size.most_common(1)[0][0] if cur_size else None})
                    cur, cur_size = [], Counter()
        t = "".join(cur).strip()
        if t:
            lines.append({"text": t, "size": cur_size.most_common(1)[0][0] if cur_size else None})
        images, image_data = [], {}
        for o in _pdf_images(_pdf_get(page, "/Resources")):
            try:
                data = o.get_data()
            except Exception:
                continue
            filters = o.get("/Filter")
            filters = [str(f) for f in (filters if isinstance(filters, list) else [filters])]
            key = picture_key(data)
            images.append(key)
            if filters and filters[-1] in ("/DCTDecode", "/JPXDecode"):
                image_data[key] = data
        pages.append({"w": w, "h": h, "lines": lines, "images": images, "image_data": image_data, "fonts": fonts})
    return pages


def _pdf_poppler(path):
    p = subprocess.run(["pdftotext", "-enc", "UTF-8", os.path.abspath(path), "-"], capture_output=True, timeout=300)
    if p.returncode != 0:
        raise StyleError(f"{path}: pdftotext failed ({p.stderr.decode('utf-8', 'replace').strip()[-200:]})")
    w = h = None
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", os.path.abspath(path)], capture_output=True, timeout=60).stdout.decode("utf-8", "replace")
        m = re.search(r"Page size:\s*([\d.]+) x ([\d.]+)", info)
        if m:
            w, h = float(m.group(1)), float(m.group(2))
    pages = []
    for chunk in p.stdout.decode("utf-8", "replace").split("\f"):
        lines = [{"text": l.strip(), "size": None} for l in chunk.splitlines() if l.strip()]
        pages.append({"w": w, "h": h, "lines": lines, "images": [], "fonts": Counter()})
    if pages and not pages[-1]["lines"]:
        pages.pop()
    return pages


def _joins(prev, line, typical):
    """Does `line` continue the paragraph that `prev` ends? (PDF text arrives line by line.)"""
    if prev.endswith((".", "!", "?", ":", "…", "。")) and len(prev) < 0.85 * typical:
        return False
    if re.match(r"^\s*([-•▪●◦*]|\d+[.)])\s", line):
        return False
    return len(prev) >= 0.6 * typical or not prev.endswith((".", "!", "?"))


def _pdf_doc(pages, lang):
    sizes = Counter()
    for p in pages:
        for l in p["lines"]:
            if l["size"]:
                sizes[l["size"]] += len(l["text"])
    base = sizes.most_common(1)[0][0] if sizes else None
    doc = {"blocks": [], "media": {}, "pictures": 0, "tables": None, "page": None, "fonts": Counter(), "colors": None,
           "page_units": []}
    first = next((p for p in pages if p["w"] and p["h"]), None)
    if first:
        doc["page"] = {"w": first["w"], "h": first["h"], "margins": None}
    for p in pages:
        doc["fonts"].update(p["fonts"])
        for k in p["images"]:
            doc["media"][k] = p.get("image_data", {}).get(k, b"")
            doc["pictures"] += 1
        doc["page_units"].append(sum(ss_text.text_units(l["text"], lang) for l in p["lines"]))
        typical = sorted(len(l["text"]) for l in p["lines"])[int(0.8 * (len(p["lines"]) - 1))] if p["lines"] else 0
        cur = None
        for l in p["lines"]:
            head = base and l["size"] and l["size"] >= 1.2 * base and len(l["text"]) < 0.8 * max(1, typical)
            listy = re.match(r"^\s*([-•▪●◦*]|\d+[.)])\s", l["text"])
            if head:
                cur = None
                doc["blocks"].append({"kind": "heading", "level": 1, "text": l["text"], "size": l["size"], "chars": len(l["text"]),
                                      "bold": None, "italic": None, "line": None, "after": None, "justified": None})
                continue
            if cur is not None and not listy and _joins(cur["text"], l["text"], typical):
                glue = "" if lang == "th" and ss_text.THAI.search(cur["text"][-1:]) and ss_text.THAI.search(l["text"][:1]) else " "
                cur["text"] += glue + l["text"]
                cur["chars"] += len(l["text"])
                continue
            text = re.sub(r"^\s*([-•▪●◦*]|\d+[.)])\s*", "", l["text"]) if listy else l["text"]
            cur = {"kind": "list" if listy else "body", "level": 0, "text": text, "size": l["size"], "chars": len(text),
                   "bold": None, "italic": None, "line": None, "after": None, "justified": None}
            doc["blocks"].append(cur)
    if not doc["fonts"]:
        doc["fonts"] = None
    return doc


def _pdf_deck(pages, lang):
    deck = {"aspect": None, "slides": [], "media": {}, "fonts": Counter()}
    for p in pages:
        if deck["aspect"] is None and p["w"] and p["h"]:
            deck["aspect"] = p["w"] / p["h"]
        deck["fonts"].update(p["fonts"])
        sizes = Counter()
        for l in p["lines"]:
            if l["size"]:
                sizes[l["size"]] += len(l["text"])
        body = sizes.most_common(1)[0][0] if sizes else None
        biggest = max((l for l in p["lines"] if l["size"]), key=lambda l: l["size"], default=None)
        paras = []
        for l in p["lines"]:
            is_title = biggest is not None and l is biggest and body and l["size"] >= HEADING_STEP * body
            listy = re.match(r"^\s*([-•▪●◦*]|\d+[.)])\s", l["text"])
            paras.append({"text": re.sub(r"^\s*([-•▪●◦*]|\d+[.)])\s*", "", l["text"]) if listy else l["text"],
                          "kind": "title" if is_title else "body", "bullet": bool(listy), "size": l["size"], "color": None})
        for k in p["images"]:
            deck["media"][k] = p.get("image_data", {}).get(k, b"")
        deck["slides"].append({"paras": paras, "pictures": list(p["images"]), "bg": None, "colors": Counter()})
    return deck


# ---------------------------------------------------------------- entry points
def measure(path, medium):
    model = load(path, medium)
    if medium == "slides":
        return measure_deck(model, path)
    if medium == "document":
        return measure_doc(model, path)
    return measure_book(model, path)


def prose_of(path):
    """The words of any document, for the text route (`--medium text`)."""
    medium = medium_of_file(path)
    if medium is None:
        raise StyleError(f"{path}: not a document format style.py reads")
    model = load(path, medium)
    return deck_prose(model) if medium == "slides" else doc_prose(model) if medium == "document" else book_text(model)
