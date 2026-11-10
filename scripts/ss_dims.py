"""The measured dimensions, the cross-medium axes, and the starting numbers a brief translates them to.

Each dimension: label, unit, scale ("log" compares ratios, "lin" differences), tol (the slack added
around the card's p10-p90 range when checking new work: log10 units for "log", the dimension's own
units for "lin"), core (a core dimension out of range fails the style side on its own).

Axis bands are coarse on purpose: they let a style learned in one medium steer work in another. The
band edges and the starting numbers in TRANSLATE are rules of thumb, not measurements; references/
translate.md says how they were chosen and how to override them.
"""

DIMS = {
    # video (picture). Frame change is the mean absolute change between neighbouring frames on a
    # 128x72 grey copy, in 0-255 grey levels.
    "shot_length": ("Shot length", "s", "log", 0.10, True),
    "cuts_per_minute": ("Hard cuts per minute", "/min", "log", 0.10, True),
    "motion": ("Movement inside a shot", "frame change", "log", 0.15, True),
    "still_share": ("Time spent in still shots", "share", "lin", 0.15, False),
    "cut_on_accent": ("Cuts that land on an audio accent", "share", "lin", 0.15, False),
    # picture, shared by video and image
    "luma": ("Brightness", "0-1", "lin", 0.08, False),
    "contrast": ("Contrast", "0-1", "lin", 0.05, False),
    "saturation": ("Saturation", "0-1", "lin", 0.07, False),
    "colorfulness": ("Colourfulness", "Hasler/100", "lin", 0.08, False),
    "warmth": ("Warm share of the colour", "share", "lin", 0.12, False),
    "hue_spread": ("Spread of hues", "0-1", "lin", 0.12, False),
    # image only
    "edge_density": ("Detail (edge energy)", "0-1", "lin", 0.02, False),
    "negative_space": ("Empty space", "share", "lin", 0.10, False),
    "subject_offset": ("Subject distance from centre", "0-1", "lin", 0.10, False),
    "aspect": ("Aspect ratio", "w/h", "log", 0.05, False),
    # audio (also measured on a video's soundtrack, with an audio_ prefix)
    "loudness": ("Integrated loudness", "LUFS", "lin", 1.5, False),
    "loudness_range": ("Loudness range", "LU", "lin", 2.0, False),
    "plr": ("Peak to loudness", "dB", "lin", 2.0, False),
    "tempo": ("Tempo", "BPM", "log", 0.03, False),
    "onset_rate": ("Onsets per second", "/s", "log", 0.12, True),
    "dynamics": ("Level swing inside 10 s", "dB", "lin", 3.0, False),
    "quiet_share": ("Time 12 dB or more under the median level", "share", "lin", 0.10, False),
    "centroid": ("Spectral centroid", "Hz", "log", 0.08, True),
    "flatness": ("Noisiness (spectral flatness)", "0-1", "lin", 0.05, False),
    "low_share": ("Energy under 250 Hz", "share", "lin", 0.08, False),
    "mid_share": ("Energy 250 Hz - 2 kHz", "share", "lin", 0.08, False),
    "high_share": ("Energy over 2 kHz", "share", "lin", 0.06, False),
    "width": ("Stereo width (side under mid)", "dB", "lin", 3.0, False),
    # text
    "sentence_length": ("Sentence length", "words (en) or characters (th)", "log", 0.08, True),
    "paragraph_sentences": ("Sentences per paragraph", "sentences", "log", 0.12, True),
    "question_rate": ("Questions", "share of sentences", "lin", 0.08, False),
    "exclaim_rate": ("Exclamations", "share of sentences", "lin", 0.06, False),
    "digit_rate": ("Sentences with numbers", "share", "lin", 0.10, False),
    "emoji_rate": ("Emoji", "per sentence", "lin", 0.10, False),
    "first_person_rate": ("First person (I, we / ผม, เรา)", "share of sentences", "lin", 0.12, False),
    "second_person_rate": ("Second person (you / คุณ)", "share of sentences", "lin", 0.12, False),
    "polite_end_rate": ("Polite endings (ครับ, ค่ะ)", "share of sentences", "lin", 0.15, False),
    "soft_end_rate": ("Soft endings (นะ, จ้า, เลย)", "share of sentences", "lin", 0.12, False),
    "latin_mix": ("English mixed into Thai", "share of characters", "lin", 0.05, False),
    "comma_rate": ("Commas", "per sentence", "lin", 0.40, False),
    "contraction_rate": ("Contractions", "per 100 words", "lin", 1.00, False),
    "word_length": ("Word length", "letters", "lin", 0.25, False),
    "variety": ("Vocabulary variety (MATTR 50)", "0-1", "lin", 0.04, False),
    "list_share": ("List blocks", "share of blocks", "lin", 0.12, False),
    "heading_share": ("Headings", "share of blocks", "lin", 0.10, False),
}

MEDIUM_DIMS = {
    "video": ["shot_length", "cuts_per_minute", "motion", "still_share", "luma", "contrast", "saturation",
              "colorfulness", "warmth", "hue_spread", "cut_on_accent"],
    "image": ["luma", "contrast", "saturation", "colorfulness", "warmth", "hue_spread", "edge_density",
              "negative_space", "subject_offset", "aspect"],
    "audio": ["loudness", "loudness_range", "plr", "tempo", "onset_rate", "dynamics", "quiet_share", "centroid",
              "flatness", "low_share", "mid_share", "high_share", "width"],
    "text": ["sentence_length", "paragraph_sentences", "question_rate", "exclaim_rate", "digit_rate", "emoji_rate",
             "first_person_rate", "second_person_rate", "polite_end_rate", "soft_end_rate", "latin_mix",
             "comma_rate", "contraction_rate", "word_length", "variety", "list_share", "heading_share"],
}


def spec(key):
    """Registry entry for a key, including audio_ keys measured on a video's soundtrack."""
    base = key[6:] if key.startswith("audio_") else key
    label, unit, scale, tol, core = DIMS[base]
    if key.startswith("audio_"):
        label, core = "Soundtrack: " + label[0].lower() + label[1:], False
    return {"label": label, "unit": unit, "scale": scale, "tol": tol, "core": core}


# ---------------------------------------------------------------- axes
# axis -> list of (medium, dimension, edges, band names low->high). The first source a card has wins.
BANDS3 = {
    "tempo": ("slow", "medium", "fast"),
    "energy": ("calm", "lively", "busy"),
    "variation": ("even", "moderate", "wide"),
    "brightness": ("dark", "mid", "bright"),
    "contrast": ("soft", "medium", "hard"),
    "color": ("muted", "moderate", "vivid"),
    "warmth": ("cool", "neutral", "warm"),
    "space": ("dense", "balanced", "airy"),
}

# (dimension, [edge1, edge2], higher_value_means) ; "spread:" uses p90/p10 of the dimension
AXIS_SOURCES = {
    "tempo": [("shot_length", [1.5, 3.5], "low"), ("sentence_length@en", [10, 18], "low"),
              ("sentence_length@th", [35, 70], "low"), ("tempo", [90, 120], "high"),
              ("audio_tempo", [90, 120], "high")],
    "energy": [("motion", [2.0, 6.0], "high"), ("onset_rate", [1.5, 4.0], "high"),
               ("edge_density", [0.04, 0.09], "high"), ("exclaim_rate", [0.02, 0.10], "high")],
    "variation": [("spread:shot_length", [2.5, 4.0], "high"), ("dynamics", [4.0, 9.0], "high"),
                  ("spread:sentence_length", [2.5, 4.0], "high"), ("spread:luma", [1.4, 2.2], "high")],
    "brightness": [("luma", [0.35, 0.60], "high"), ("centroid", [1200, 2600], "high")],
    "contrast": [("contrast", [0.15, 0.25], "high"), ("plr", [9.0, 14.0], "high")],
    "color": [("saturation", [0.20, 0.40], "high")],
    "warmth": [("warmth", [0.35, 0.60], "high")],
    "space": [("negative_space", [0.30, 0.55], "high"), ("still_share", [0.15, 0.40], "high"),
              ("quiet_share", [0.05, 0.20], "high"), ("paragraph_sentences", [2.5, 5.0], "low")],
}


def axes_of(measured, lang=None):
    """Band per axis from a card's measured block: {axis: {"band": .., "from": dim, "value": ..}}."""
    out = {}
    for axis, sources in AXIS_SOURCES.items():
        for dim, edges, direction in sources:
            key, need_lang = (dim.split("@") + [None])[:2]
            if need_lang and need_lang != lang:
                continue
            spread = key.startswith("spread:")
            name = key[7:] if spread else key
            m = measured.get(name)
            if not m:
                continue
            if spread:
                lo = max(m["p10"], 1e-6)
                value = m["p90"] / lo
            else:
                value = m["p50"]
            idx = 0 if value < edges[0] else 1 if value < edges[1] else 2
            if direction == "low":
                idx = 2 - idx
            out[axis] = {"band": BANDS3[axis][idx], "from": key, "value": round(float(value), 3)}
            break
    return out


# ---------------------------------------------------------------- translation for briefs
# TRANSLATE[axis][target] = {band: starting point}. "any" is the fallback for a medium with no row.
TRANSLATE = {
    "tempo": {
        "video": {"slow": "shots of 3.5-8 s, few cuts", "medium": "shots of 1.5-3.5 s", "fast": "shots of 0.6-1.5 s, cut on accents"},
        "audio": {"slow": "under 90 BPM, long notes", "medium": "90-120 BPM", "fast": "120-150 BPM, short notes"},
        "text": {"slow": "long sentences (18+ words / 70+ Thai characters)", "medium": "sentences of 10-18 words (35-70 Thai characters)",
                 "fast": "short sentences (under 10 words / 35 Thai characters), fragments allowed"},
        "image": {"slow": "one calm focal point the eye can rest on", "medium": "a clear focal point with one secondary",
                  "fast": "diagonals and a reading path that moves the eye quickly"},
        "slides": {"slow": "one idea per slide held 20 s or more", "medium": "a slide every 8-20 s",
                   "fast": "a slide every 3-8 s, under 12 words each"},
        "ui": {"slow": "long sections, transitions 400-700 ms", "medium": "transitions 250-400 ms",
               "fast": "one idea per screen, transitions 120-250 ms"},
        "any": {"slow": "unhurried: let each idea sit", "medium": "steady pace", "fast": "quick: one idea after another, no padding"},
    },
    "energy": {
        "video": {"calm": "slow drifts, little in-shot movement", "lively": "a camera move or action in most shots", "busy": "constant movement, layered action"},
        "audio": {"calm": "under 1.5 onsets/s, sustained sounds", "lively": "1.5-4 onsets/s", "busy": "4+ onsets/s, dense rhythm"},
        "text": {"calm": "no exclamations, plain verbs", "lively": "an occasional exclamation or punchy verb", "busy": "frequent exclamations and imperatives"},
        "image": {"calm": "few edges, smooth surfaces", "lively": "moderate texture", "busy": "dense detail and texture"},
        "slides": {"calm": "one element per slide", "lively": "two or three elements, light builds", "busy": "many builds and layered elements"},
        "ui": {"calm": "almost no motion", "lively": "motion on state changes only", "busy": "ambient motion and rich micro-interactions"},
        "any": {"calm": "quiet, few events", "lively": "regular events", "busy": "dense, many events"},
    },
    "variation": {
        "video": {"even": "shot lengths stay close to one another", "moderate": "some long holds among short shots", "wide": "very short and very long shots side by side"},
        "audio": {"even": "level stays within 4 dB", "moderate": "level swings 4-9 dB", "wide": "big swings: near silence against full hits"},
        "text": {"even": "sentences of similar length", "moderate": "mix of short and long sentences", "wide": "one-word lines against long sentences"},
        "any": {"even": "consistent rhythm", "moderate": "some contrast in rhythm", "wide": "strong contrast in rhythm"},
    },
    "brightness": {
        "video": {"dark": "low-key, mean brightness under 0.35", "mid": "mid-key", "bright": "high-key, mean brightness over 0.6"},
        "image": {"dark": "low-key, mean brightness under 0.35", "mid": "mid-key", "bright": "high-key, mean brightness over 0.6"},
        "audio": {"dark": "warm, rolled-off highs (centroid under 1.2 kHz)", "mid": "balanced tone", "bright": "airy, present highs (centroid over 2.6 kHz)"},
        "slides": {"dark": "dark backgrounds, light type", "mid": "mid-tone backgrounds", "bright": "light backgrounds, dark type"},
        "ui": {"dark": "dark theme", "mid": "mid-tone surfaces", "bright": "light theme"},
        "text": {"dark": "sober, serious word choice", "mid": "neutral tone", "bright": "upbeat, light word choice"},
        "any": {"dark": "dark, heavy mood", "mid": "neutral mood", "bright": "light, open mood"},
    },
    "contrast": {
        "video": {"soft": "flat, low contrast", "medium": "moderate contrast", "hard": "deep blacks against bright highlights"},
        "image": {"soft": "flat, low contrast", "medium": "moderate contrast", "hard": "deep blacks against bright highlights"},
        "audio": {"soft": "compressed, peaks close to the body", "medium": "moderate dynamics", "hard": "punchy transients well above the body"},
        "slides": {"soft": "tonal palette, gentle type contrast", "medium": "clear hierarchy", "hard": "stark black and white, big type contrast"},
        "ui": {"soft": "subtle borders and shadows", "medium": "clear surfaces", "hard": "stark contrast between surfaces and accents"},
        "any": {"soft": "gentle contrast", "medium": "clear contrast", "hard": "stark contrast"},
    },
    "color": {
        "any": {"muted": "muted colour, saturation under 0.2; build your own palette", "moderate": "moderate colour; build your own palette",
                "vivid": "vivid colour, saturation over 0.4; build your own palette"},
    },
    "warmth": {
        "any": {"cool": "cool hues dominate", "neutral": "balanced warm and cool", "warm": "warm hues dominate"},
    },
    "space": {
        "video": {"dense": "frames always full, no still moments", "balanced": "some still moments", "airy": "frequent still holds and breathing room"},
        "audio": {"dense": "no gaps", "balanced": "a few drops", "airy": "regular drops and silences"},
        "text": {"dense": "long paragraphs", "balanced": "paragraphs of 2.5-5 sentences", "airy": "short paragraphs, many line breaks"},
        "image": {"dense": "filled frame, little empty area", "balanced": "about a third empty", "airy": "more than half the frame empty"},
        "slides": {"dense": "full slides", "balanced": "generous margins", "airy": "mostly empty slides, one element"},
        "ui": {"dense": "compact density", "balanced": "comfortable spacing", "airy": "large whitespace, few elements per screen"},
        "any": {"dense": "dense", "balanced": "balanced", "airy": "lots of space"},
    },
}

TARGETS = ("video", "audio", "text", "image", "slides", "ui", "any")


def translate(axis, band, target):
    row = TRANSLATE.get(axis, {})
    pick = row.get(target) or row.get("any") or {}
    return pick.get(band)
