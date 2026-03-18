#!/usr/bin/env python3
"""
make_stinger.py — Glitchy electro-style YouTube channel stinger generator.

Produces 1-second and/or 5-second stinger videos driven by ffmpeg + Pillow.
All inputs (channel name, keywords, source images, audio) are configurable via
command-line flags or plain-text / TOML files.

QUICK START
    python3 dev/stingers/make_stinger.py

    Reads dev/stingers/keywords.txt, dev/stingers/images.txt, dev/stingers/audio.toml;
    all three are generated with defaults on first run.

EXAMPLES
    # Defaults (reads all three config files):
    python3 dev/stingers/make_stinger.py

    # Override channel branding:
    python3 dev/stingers/make_stinger.py --title "MY CHANNEL" --subtitle "mychannel.com"

    # Switch audio style preset:
    python3 dev/stingers/make_stinger.py --audio-style industrial

    # Inline keywords + fast BPM, 1-second bumper only:
    python3 dev/stingers/make_stinger.py \\
        --keywords "OVN,Kubernetes,Security,Ansible" \\
        --duration 1s --bpm 160

    # Custom image set (glob or comma-separated paths):
    python3 dev/stingers/make_stinger.py --images "static/images/*.png"

    # Fine-grained audio control via TOML:
    python3 dev/stingers/make_stinger.py --audio dev/stingers/my_audio.toml

AUDIO STYLE PRESETS
    electro       4/4 kick, arp, minor-pentatonic synth  (default)
    industrial    hard and dark; sawtooth, tritone, distortion
    chiptune      8-bit square-wave arp, fast tempo
    drum_n_bass   174 BPM, heavy sub bass, dorian arp
    ambient       slow, no kick/snare, lydian pads
    minimal       kick + sub bass only, stripped back
    glitch        chromatic, stuttery, square wave, distorted

REQUIREMENTS
    ffmpeg in PATH  (8.x; no libfreetype needed)
    pip3 install Pillow
"""

import argparse
import glob as globmod
import random
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Paths ────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent    # dev/stingers/


def _find_repo_root(start: Path) -> Path:
    """Walk up from start until we find a .git directory (repo root)."""
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return start.parent   # fallback: one level up


ROOT = _find_repo_root(HERE)    # repo root

W, H, FPS = 1920, 1080, 30

RESOLUTIONS = {"hd": (1920, 1080), "4k": (3840, 2160)}


def fs(n: int) -> int:
    """Scale a 1080p pixel/font value to the current output resolution."""
    return max(1, int(n * H / 1080))

# ─── Default config file paths ───────────────────────────────────────────────
DEFAULT_KEYWORDS_FILE = HERE / "keywords.txt"
DEFAULT_IMAGES_FILE   = HERE / "images.txt"
DEFAULT_AUDIO_FILE    = HERE / "audio.toml"

DEFAULT_KEYWORDS = [
    "OVN", "Kubernetes", "Networking", "Virtualization",
    "CoreOS", "Automation", "Security", "Ansible",
    "RHACM", "Operators", "etcd", "Prometheus",
    "OpenShift", "Hybrid Cloud", "kubeconfig",
]
DEFAULT_IMAGES = [
    "static/images/cat-loves-ovn.png",
    "static/images/debug-sts-banner.jpg",
    "static/images/ovn-recon.png",
    "static/images/machineconfigs-butane.png",
    "static/images/cnv-vm-1.png",
    "static/images/cnv-trunk-1.png",
    "static/images/layering-cake-trans.png",
    "static/images/keda-dashboard-metrics.png",
    "static/img/banners/banner-7.jpg",
    "static/img/banners/banner-18.jpg",
    "static/img/banners/banner-30.jpg",
    "static/img/banners/banner-42.jpg",
    "static/img/banners/banner-3.jpg",
]

# ─── Audio: music theory helpers ──────────────────────────────────────────────

# Base frequencies at octave 4 (A4 = 440 Hz standard)
NOTE_FREQ = {
    "C": 261.63, "C#": 277.18, "Db": 277.18,
    "D": 293.66, "D#": 311.13, "Eb": 311.13,
    "E": 329.63, "F":  349.23,
    "F#": 369.99, "Gb": 369.99,
    "G": 392.00, "G#": 415.30, "Ab": 415.30,
    "A": 440.00, "A#": 466.16, "Bb": 466.16,
    "B": 493.88,
}

# Scale definitions as semitone intervals from root (first 4 used for arp)
SCALE_INTERVALS = {
    "minor_pentatonic": [0, 3, 7, 10],
    "major":            [0, 4, 7, 12],
    "major_pentatonic": [0, 2, 4,  7],
    "dorian":           [0, 3, 7, 10],
    "lydian":           [0, 4, 8, 12],
    "chromatic":        [0, 1, 6, 11],
    "tritone":          [0, 6, 12, 18],
    "blues":            [0, 3, 6,  7],
}

RHYTHM_DIVISOR = {"16th": 4, "8th": 2, "quarter": 1}


def scale_freqs(root: str, octave: int, scale: str) -> List[float]:
    """Return 4 Hz values for an arp from root/octave/scale."""
    base = NOTE_FREQ.get(root, NOTE_FREQ["C"]) * (2 ** (octave - 4))
    intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["minor_pentatonic"])[:4]
    return [round(base * (2 ** (i / 12)), 2) for i in intervals]


def wave_expr(t: str, freq: float, waveform: str) -> str:
    """
    Return an aevalsrc sub-expression for one tonal note.
    t        : time variable string (e.g. 't')
    freq     : frequency in Hz
    waveform : 'sine' | 'square' | 'saw'
    """
    f = freq
    if waveform == "square":
        # Gibbs-limited 4-harmonic Fourier approximation
        return (f"(sin(2*PI*{t}*{f:.2f})"
                f"+sin(2*PI*{t}*{f*3:.2f})/3"
                f"+sin(2*PI*{t}*{f*5:.2f})/5"
                f"+sin(2*PI*{t}*{f*7:.2f})/7)*0.849")
    elif waveform == "saw":
        # 4-harmonic descending Fourier series
        return (f"(sin(2*PI*{t}*{f:.2f})"
                f"-sin(2*PI*{t}*{f*2:.2f})/2"
                f"+sin(2*PI*{t}*{f*3:.2f})/3"
                f"-sin(2*PI*{t}*{f*4:.2f})/4)*0.831")
    else:  # sine
        return f"sin(2*PI*{t}*{f:.2f})"

# ─── AudioConfig ──────────────────────────────────────────────────────────────

@dataclass
class AudioConfig:
    """All parameters controlling audio synthesis."""
    style:        str   = "electro"
    bpm:          int   = 140
    master:       float = 0.65
    layers:       List[str] = field(
        default_factory=lambda: ["kick", "snare", "hat", "arp", "bass"])
    # Kick drum
    kick_freq:    float = 75.0    # fundamental Hz
    kick_decay:   float = 50.0    # higher = shorter / punchier
    kick_vol:     float = 0.85
    # Snare
    snare_vol:    float = 0.55
    snare_decay:  float = 90.0
    # Hi-hat
    hat_vol:      float = 0.18
    hat_rhythm:   str   = "8th"   # 16th | 8th | quarter
    # Arp / melody
    arp_scale:    str   = "minor_pentatonic"
    arp_root:     str   = "C"
    arp_octave:   int   = 5
    arp_rhythm:   str   = "16th"  # 16th | 8th | quarter
    arp_vol:      float = 0.28
    arp_wave:     str   = "sine"  # sine | square | saw
    # Sub bass
    bass_freq:    float = 55.0
    bass_decay:   float = 6.0
    bass_vol:     float = 0.40
    # FX
    distort:      bool  = False   # tanh saturation on master bus
    distort_drive: float = 2.5   # saturation amount (1=mild, 5=heavy)


# Named style presets — fields override AudioConfig defaults
AUDIO_PRESETS: dict = {
    "electro": dict(
        bpm=140,
        kick_freq=75,  kick_decay=50,  kick_vol=0.85,
        snare_vol=0.55, snare_decay=90,
        hat_vol=0.18,  hat_rhythm="8th",
        arp_scale="minor_pentatonic", arp_root="C", arp_octave=5,
        arp_rhythm="16th", arp_vol=0.28, arp_wave="sine",
        bass_freq=55,  bass_decay=6,   bass_vol=0.40,
        master=0.65, distort=False,
        layers=["kick", "snare", "hat", "arp", "bass"],
    ),
    "industrial": dict(
        bpm=148,
        kick_freq=60,  kick_decay=60,  kick_vol=1.00,
        snare_vol=0.70, snare_decay=60,
        hat_vol=0.25,  hat_rhythm="16th",
        arp_scale="tritone",  arp_root="C", arp_octave=4,
        arp_rhythm="16th", arp_vol=0.35, arp_wave="saw",
        bass_freq=45,  bass_decay=4,   bass_vol=0.55,
        master=0.70, distort=True, distort_drive=3.0,
        layers=["kick", "snare", "hat", "arp", "bass"],
    ),
    "chiptune": dict(
        bpm=160,
        kick_freq=120, kick_decay=80,  kick_vol=0.70,
        snare_vol=0.40, snare_decay=120,
        hat_vol=0.20,  hat_rhythm="16th",
        arp_scale="major", arp_root="C", arp_octave=6,
        arp_rhythm="16th", arp_vol=0.45, arp_wave="square",
        bass_freq=110, bass_decay=12,  bass_vol=0.30,
        master=0.60, distort=False,
        layers=["kick", "snare", "hat", "arp", "bass"],
    ),
    "drum_n_bass": dict(
        bpm=174,
        kick_freq=65,  kick_decay=45,  kick_vol=0.90,
        snare_vol=0.65, snare_decay=70,
        hat_vol=0.15,  hat_rhythm="16th",
        arp_scale="dorian", arp_root="D", arp_octave=4,
        arp_rhythm="8th", arp_vol=0.30, arp_wave="sine",
        bass_freq=50,  bass_decay=5,   bass_vol=0.55,
        master=0.65, distort=False,
        layers=["kick", "snare", "hat", "arp", "bass"],
    ),
    "ambient": dict(
        bpm=80,
        kick_freq=60,  kick_decay=20,  kick_vol=0.0,
        snare_vol=0.0, snare_decay=60,
        hat_vol=0.08,  hat_rhythm="quarter",
        arp_scale="lydian", arp_root="G", arp_octave=5,
        arp_rhythm="quarter", arp_vol=0.35, arp_wave="sine",
        bass_freq=55,  bass_decay=2,   bass_vol=0.20,
        master=0.50, distort=False,
        layers=["hat", "arp", "bass"],
    ),
    "minimal": dict(
        bpm=128,
        kick_freq=75,  kick_decay=45,  kick_vol=0.90,
        snare_vol=0.0, snare_decay=90,
        hat_vol=0.0,   hat_rhythm="8th",
        arp_scale="minor_pentatonic", arp_root="A", arp_octave=4,
        arp_rhythm="8th", arp_vol=0.20, arp_wave="sine",
        bass_freq=55,  bass_decay=5,   bass_vol=0.50,
        master=0.60, distort=False,
        layers=["kick", "bass"],
    ),
    "glitch": dict(
        bpm=130,
        kick_freq=80,  kick_decay=55,  kick_vol=0.80,
        snare_vol=0.60, snare_decay=80,
        hat_vol=0.22,  hat_rhythm="16th",
        arp_scale="chromatic", arp_root="C", arp_octave=5,
        arp_rhythm="16th", arp_vol=0.30, arp_wave="square",
        bass_freq=60,  bass_decay=8,   bass_vol=0.40,
        master=0.65, distort=True, distort_drive=2.0,
        layers=["kick", "snare", "hat", "arp", "bass"],
    ),
}


def audio_config_from_preset(name: str) -> AudioConfig:
    preset = AUDIO_PRESETS.get(name, AUDIO_PRESETS["electro"])
    cfg = AudioConfig(style=name)
    for k, v in preset.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def apply_toml_overrides(cfg: AudioConfig, toml_data: dict) -> AudioConfig:
    """Overlay values from audio.toml onto an AudioConfig."""
    a = toml_data.get("audio", {})

    def _set(attr, section, key, default=None):
        val = section.get(key, default)
        if val is not None:
            setattr(cfg, attr, val)

    _set("bpm",    a, "bpm")
    _set("master", a, "master")
    if "layers" in a:
        cfg.layers = a["layers"]

    k = a.get("kick", {})
    _set("kick_freq",  k, "freq")
    _set("kick_decay", k, "decay")
    _set("kick_vol",   k, "volume")

    s = a.get("snare", {})
    _set("snare_vol",   s, "volume")
    _set("snare_decay", s, "decay")

    h = a.get("hat", {})
    _set("hat_vol",    h, "volume")
    _set("hat_rhythm", h, "rhythm")

    p = a.get("arp", {})
    _set("arp_scale",  p, "scale")
    _set("arp_root",   p, "root")
    _set("arp_octave", p, "octave")
    _set("arp_rhythm", p, "rhythm")
    _set("arp_vol",    p, "volume")
    _set("arp_wave",   p, "waveform")

    b = a.get("bass", {})
    _set("bass_freq",  b, "freq")
    _set("bass_decay", b, "decay")
    _set("bass_vol",   b, "volume")

    fx = a.get("fx", {})
    _set("distort",       fx, "distort")
    _set("distort_drive", fx, "distort_drive")

    return cfg

# ─── Config ───────────────────────────────────────────────────────────────────

@dataclass
class Config:
    title:    str        = "GUI FREE LIFE"
    subtitle: str        = "guifreelife.com"
    tagline:  str        = ""
    keywords: List[str]  = field(default_factory=list)
    images:   List[str]  = field(default_factory=list)
    duration:   str        = "both"
    stem:       str        = "stinger"   # output filename base: {stem}_5s.mp4
    output:     Path       = HERE
    seed:       Optional[int] = None
    audio:      AudioConfig = field(default_factory=AudioConfig)
    resolution: str        = "hd"       # hd | 4k
    intensity:  str        = "normal"   # normal | extreme

    @property
    def res_suffix(self) -> str:
        return "" if self.resolution == "hd" else f"_{self.resolution}"

    @property
    def img_fx(self) -> tuple:
        """Extra filters applied to image segments in extreme mode."""
        if self.intensity == "extreme":
            return (scan_jitter(row_h=fs(4), shift=fs(60)), rgb_bleed(amp=fs(12)))
        return ()

    @property
    def col_fx(self) -> tuple:
        """Extra filters applied to colour segments in extreme mode."""
        if self.intensity == "extreme":
            return (_extra_glitch_stripe(),)
        return ()

    def __post_init__(self):
        if not self.tagline and self.keywords:
            self.tagline = "  •  ".join(k.lower() for k in self.keywords[:4])

    @property
    def work(self) -> Path:
        return self.output / f"_work_{self.stem}"

# ─── Fonts ────────────────────────────────────────────────────────────────────

def _find_font(*paths):
    for p in paths:
        if Path(p).exists():
            return p
    sys.exit("No usable font found. Tried:\n" + "\n".join(f"  {p}" for p in paths))

FONT_DISPLAY_PATH = _find_font(
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
FONT_MONO_PATH = _find_font(
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Monaco.ttf",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)

# ─── Colour palette ───────────────────────────────────────────────────────────
CYAN    = (0x00, 0xFF, 0xFF)
MAGENTA = (0xFF, 0x00, 0xFF)
GREEN   = (0x00, 0xFF, 0x66)
WHITE   = (0xFF, 0xFF, 0xFF)

def rgba(rgb, a=255):
    return (*rgb, a)

# ─── Default file generators ─────────────────────────────────────────────────

def _ensure_default_files():
    if not DEFAULT_KEYWORDS_FILE.exists():
        lines = [
            "# GUI Free Life — keyword flash list",
            "# One keyword per line. Lines starting with # are comments.",
            "", *DEFAULT_KEYWORDS,
        ]
        DEFAULT_KEYWORDS_FILE.write_text("\n".join(lines) + "\n")
        print(f"  created {DEFAULT_KEYWORDS_FILE.name}")

    if not DEFAULT_IMAGES_FILE.exists():
        lines = [
            "# GUI Free Life — source image list",
            "# One path per line, relative to repo root or absolute.",
            "# Lines starting with # are comments.",
            "", *DEFAULT_IMAGES,
        ]
        DEFAULT_IMAGES_FILE.write_text("\n".join(lines) + "\n")
        print(f"  created {DEFAULT_IMAGES_FILE.name}")

    if not DEFAULT_AUDIO_FILE.exists():
        _write_default_audio_toml(DEFAULT_AUDIO_FILE, AudioConfig())
        print(f"  created {DEFAULT_AUDIO_FILE.name}")


def _write_default_audio_toml(path: Path, _: AudioConfig = None):
    """
    Write a default audio.toml.  Only `style` is active out of the box;
    every other field is commented out — uncomment + edit to override the preset.
    Delete this file and re-run to regenerate it fresh.
    """
    scales  = " | ".join(SCALE_INTERVALS.keys())
    presets = " | ".join(AUDIO_PRESETS.keys())
    path.write_text(f"""\
# GUI Free Life — audio configuration
# Generated by make_stinger.py. Delete and re-run to regenerate.
#
# Only `style` is active by default.  Uncomment any field to override the preset.
# Preset reference: {presets}
#
# Precedence (highest → lowest):
#   --bpm CLI flag  >  this file  >  style preset defaults

[audio]
style  = "electro"    # {presets}
# bpm    = 140        # beats per minute  (also: --bpm on CLI)
# master = 0.65       # master output volume [0.0–1.0]
# layers = ["kick", "snare", "hat", "arp", "bass"]  # remove any to mute

[audio.kick]
# freq   = 75.0       # fundamental Hz — lower = deeper boom
# decay  = 50.0       # higher = punchier / shorter
# volume = 0.85

[audio.snare]
# volume = 0.55
# decay  = 90.0

[audio.hat]
# volume = 0.18
# rhythm = "8th"      # 16th | 8th | quarter

[audio.arp]
# Scales: {scales}
# scale    = "minor_pentatonic"
# root     = "C"      # C C# D D# E F F# G G# A A# B
# octave   = 5        # 3–7
# rhythm   = "16th"   # 16th | 8th | quarter
# volume   = 0.28
# waveform = "sine"   # sine | square | saw

[audio.bass]
# freq   = 55.0
# decay  = 6.0
# volume = 0.40

[audio.fx]
# distort       = false   # tanh saturation on master bus
# distort_drive = 2.5     # 1.0 = mild warmth, 5.0 = heavy clip
""")

# ─── File loaders ─────────────────────────────────────────────────────────────

def load_text_file(path: Path) -> List[str]:
    return [l.strip() for l in path.read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]


def resolve_images(spec: str, base: Path = ROOT) -> List[str]:
    spec = spec.strip()
    candidate = Path(spec)
    raw_paths = (load_text_file(candidate)
                 if candidate.suffix == ".txt" and candidate.exists()
                 else [s.strip() for s in spec.split(",") if s.strip()])
    paths = []
    for raw in raw_paths:
        expanded = globmod.glob(raw) or globmod.glob(str(base / raw))
        if expanded:
            paths.extend(expanded)
        else:
            p = Path(raw) if Path(raw).is_absolute() else base / raw
            if p.exists():
                paths.append(str(p))
    return [str(Path(p).resolve()) for p in paths if Path(p).exists()]


def resolve_keywords(spec: str) -> List[str]:
    spec = spec.strip()
    candidate = Path(spec)
    if candidate.suffix == ".txt" and candidate.exists():
        return load_text_file(candidate)
    return [s.strip() for s in spec.split(",") if s.strip()]


def load_audio_config(path: str, cli_style: Optional[str],
                      bpm_override: Optional[int]) -> AudioConfig:
    """
    Load AudioConfig with clear precedence:
      1. Start from the TOML's [audio] style (default: 'electro')
      2. Apply all TOML field overrides
      3. CLI --audio-style wins over TOML style (re-bases preset, keeps TOML fields)
      4. CLI --bpm wins over everything
    """
    toml_data: dict = {}
    p = Path(path)
    if p.exists():
        with open(p, "rb") as f:
            toml_data = tomllib.load(f)

    toml_style = toml_data.get("audio", {}).get("style", "electro")
    base_style = cli_style or toml_style          # CLI flag takes priority
    cfg = audio_config_from_preset(base_style)
    cfg.style = base_style

    if toml_data:
        apply_toml_overrides(cfg, toml_data)

    if bpm_override is not None:
        cfg.bpm = bpm_override
    return cfg

# ─── Pillow text rendering ────────────────────────────────────────────────────

def make_font(path, size):
    return ImageFont.truetype(path, size)

def text_size(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def wrap_text(draw, text: str, font, max_width: int) -> List[str]:
    """Split text into lines that each fit within max_width pixels."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]

def glow_text(img, draw, x, y, text, font,
              fill_color, glow_color, glow_radius=12, glow_alpha=180):
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    for dx in range(-2, 3, 2):
        for dy in range(-1, 2, 2):
            gd.text((x + dx, y + dy), text, font=font,
                    fill=(*glow_color, glow_alpha))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius=glow_radius)))
    draw.text((x, y), text, font=font, fill=fill_color)


def render_keyword_overlay(keywords: List[str], out_path: Path):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = make_font(FONT_MONO_PATH, fs(46))
    m    = fs(55)
    corners = [("left","top"), ("right","top"), ("left","bottom"), ("right","bottom")]
    for i, kw in enumerate(keywords[:4]):
        label = f"[ {kw.upper()} ]"
        tw, th = text_size(draw, label, font)
        sx, sy = corners[i]
        x = m if sx == "left" else W - tw - m
        y = m if sy == "top"  else H - th - m
        glow_text(img, draw, x, y, label, font,
                  fill_color=rgba(CYAN, 220), glow_color=MAGENTA,
                  glow_radius=fs(10), glow_alpha=130)
    img.save(str(out_path), "PNG")


def render_title_overlay(cfg: Config, tag_line: str, out_path: Path):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fb   = make_font(FONT_DISPLAY_PATH, fs(180))

    lines   = wrap_text(draw, cfg.title, fb, W - fs(80))
    line_h  = text_size(draw, "Ag", fb)[1]
    gap     = fs(12)
    total_h = line_h * len(lines) + gap * (len(lines) - 1)
    max_lw  = max(text_size(draw, l, fb)[0] for l in lines)
    ty      = (H - total_h) // 2 - fs(40)

    pad = fs(18)
    box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(box).rectangle(
        [(W - max_lw) // 2 - pad, ty - pad,
         (W + max_lw) // 2 + pad, ty + total_h + pad], fill=(0, 0, 0, 140))
    img.alpha_composite(box)
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        lw, _ = text_size(draw, line, fb)
        lx = (W - lw) // 2
        ly = ty + i * (line_h + gap)
        draw.text((lx + fs(8), ly), line, font=fb, fill=rgba(MAGENTA, 160))
        glow_text(img, draw, lx, ly, line, fb,
                  fill_color=rgba(CYAN, 255), glow_color=CYAN,
                  glow_radius=fs(16), glow_alpha=120)
        draw = ImageDraw.Draw(img)

    font_sub = make_font(FONT_MONO_PATH, fs(60))
    sw, _ = text_size(draw, cfg.subtitle, font_sub)
    glow_text(img, draw, (W-sw)//2, ty + total_h + fs(30), cfg.subtitle, font_sub,
              fill_color=rgba(GREEN, 230), glow_color=GREEN,
              glow_radius=fs(8), glow_alpha=90)
    draw = ImageDraw.Draw(img)
    ft = make_font(FONT_MONO_PATH, fs(36))
    tgw, tgh = text_size(draw, tag_line, ft)
    draw.text(((W-tgw)//2, H-tgh-fs(55)), tag_line, font=ft, fill=rgba(WHITE, 80))
    img.save(str(out_path), "PNG")


def render_noise_overlay(cfg: Config, keywords: List[str], out_path: Path):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = make_font(FONT_MONO_PATH, fs(70))
    n    = min(len(keywords), 5)
    step = H // (n + 1)
    for i, kw in enumerate(keywords[:n]):
        y = step * (i + 1) - fs(35)
        glow_text(img, draw, fs(60), y, f"$ {kw.upper()}_", font,
                  fill_color=rgba(GREEN, 230), glow_color=GREEN,
                  glow_radius=fs(8), glow_alpha=100)
        draw = ImageDraw.Draw(img)
    fg = make_font(FONT_DISPLAY_PATH, fs(120))
    gw, gh = text_size(draw, cfg.title, fg)
    draw.text(((W-gw)//2, (H-gh)//2), cfg.title, font=fg, fill=rgba(CYAN, 35))
    img.save(str(out_path), "PNG")


def render_glitch_title_overlay(cfg: Config, out_path: Path):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fb   = make_font(FONT_DISPLAY_PATH, fs(180))

    lines   = wrap_text(draw, cfg.title, fb, W - fs(80))
    line_h  = text_size(draw, "Ag", fb)[1]
    gap     = fs(12)
    total_h = line_h * len(lines) + gap * (len(lines) - 1)
    ty      = (H - total_h) // 2 - fs(40)

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    for i, line in enumerate(lines):
        lw, _ = text_size(draw, line, fb)
        lx = (W - lw) // 2
        ly = ty + i * (line_h + gap)
        gd.text((lx, ly), line, font=fb, fill=rgba(CYAN, 100))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius=fs(24))))

    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw, _ = text_size(draw, line, fb)
        lx = (W - lw) // 2
        ly = ty + i * (line_h + gap)
        draw.text((lx + fs(14), ly), line, font=fb, fill=rgba(MAGENTA, 200))
        draw.text((lx,          ly), line, font=fb, fill=rgba(CYAN, 255))

    font_sub = make_font(FONT_MONO_PATH, fs(60))
    sw, _ = text_size(draw, cfg.subtitle, font_sub)
    glow_text(img, draw, (W-sw)//2, ty + total_h + fs(28), cfg.subtitle, font_sub,
              fill_color=rgba(GREEN, 235), glow_color=GREEN,
              glow_radius=fs(8), glow_alpha=90)
    draw = ImageDraw.Draw(img)
    ft = make_font(FONT_MONO_PATH, fs(36))
    tgw, _ = text_size(draw, cfg.tagline, ft)
    draw.text(((W-tgw)//2, H-fs(65)), cfg.tagline, font=ft, fill=rgba(WHITE, 75))
    img.save(str(out_path), "PNG")

# ─── FFmpeg helpers ───────────────────────────────────────────────────────────

def run(args, label=""):
    cmd = ["ffmpeg", "-y", "-loglevel", "warning"] + args
    if label:
        print(f"  • {label}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"\n  ✗  ffmpeg failed [{label}]")
        print(r.stderr[-3000:])
        sys.exit(1)

def chroma_geq(s=6):
    return (f"geq=r='r(X+{s}*sin(T*17),Y+2*cos(T*9))':"
            f"g='g(X,Y)':"
            f"b='b(X-{s}*cos(T*13),Y-2*sin(T*11))'")

def _scanlines() -> str:
    period = round(H / 720, 1)   # ~1.5 px at 1080p, ~3.0 px at 4K
    return f"geq=lum='lum(X,Y)*(0.55+0.45*cos(Y*PI/{period}))':cb='cb(X,Y)':cr='cr(X,Y)'"


def _glitch_stripe() -> str:
    base = round(H * 500 / 1080)
    amp  = round(H * 300 / 1080)
    end  = round(H * 516 / 1080)
    return (f"geq=lum='lum(X,Y)+if(between(Y,floor({base}+{amp}*sin(T*29)),"
            f"floor({end}+{amp}*sin(T*29))),random(1)*90,0)':cb='cb(X,Y)':cr='cr(X,Y)'")


def _extra_glitch_stripe() -> str:
    """Second animated corruption band at a different Y position and speed."""
    base = round(H * 0.25)
    amp  = round(H * 0.14)
    end  = base + round(H * 0.012)
    return (f"geq=lum='lum(X,Y)+if(between(Y,floor({base}+{amp}*sin(T*41+1.7)),"
            f"floor({end}+{amp}*sin(T*41+1.7))),random(2)*115,0)':cb='cb(X,Y)':cr='cr(X,Y)'")


def scan_jitter(row_h: int = 4, shift: int = 60, speed: int = 18, prob: float = 0.82) -> str:
    """Randomly displace horizontal pixel bands left/right — hard digital corruption."""
    row  = f"floor(Y/{row_h})"
    time = f"floor(T*{speed})"
    seed_amt  = f"({row}*1000+{time})"
    seed_gate = f"({row}*1000+{time}+7)"
    dr = f"{shift}*(random({seed_amt})-0.5)*gt(random({seed_gate}),{prob})"
    db = f"{shift//2}*(random({seed_amt}+3)-0.5)*gt(random({seed_gate}+3),{prob+0.04:.2f})"
    return (f"geq="
            f"r='r(clip(X+{dr},0,W-1),Y)':"
            f"g='g(X,Y)':"
            f"b='b(clip(X-{db},0,W-1),Y)'")


def rgb_bleed(amp: int = 12, speed: int = 7) -> str:
    """Animated per-channel displacement — chromatic aberration on steroids."""
    return (f"geq="
            f"r='r(X+{amp}*sin(T*{speed}),Y+{amp//3}*cos(T*{speed*0.6:.1f}))':"
            f"g='g(X-{amp//4}*cos(T*{speed}+1.0),Y)':"
            f"b='b(X-{amp}*cos(T*{speed}+2.1),Y-{amp//3}*sin(T*{speed*1.4:.1f}))'")

def base_glitch_chain(noise=18, chroma=5, extra=()):
    return ",".join([
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
        "eq=contrast=1.5:brightness=-0.07:saturation=2.0",
        "colorchannelmixer=rr=0.65:gg=0.92:bb=1.18",
        f"noise=alls={noise}:allf=t",
        chroma_geq(chroma), _scanlines(), "vignette=PI/3.2",
        *extra,
    ])

# ─── Segment generators ───────────────────────────────────────────────────────

def seg_from_image(img_path, overlay_png, dur, out, noise=18, chroma=5, extra=()):
    glitch = base_glitch_chain(noise=noise, chroma=chroma, extra=extra)
    run([
        "-loop","1","-i", img_path, "-loop","1","-i", str(overlay_png),
        "-filter_complex", f"[0:v]{glitch}[v];[v][1:v]overlay=0:0[out]",
        "-map","[out]", "-t",str(dur),"-r",str(FPS),
        "-c:v","libx264","-pix_fmt","yuv420p", str(out),
    ], f"img({Path(img_path).name}) → {out.name}")


def seg_from_color(bg_color, overlay_png, dur, out, noise=60, chroma=8, extra=()):
    noise_scene = "0a1a14" in bg_color
    filters = [
        f"noise=alls={noise}:allf=t",
        *( ["colorchannelmixer=rr=0.04:gg=0.28:bb=0.22",
            "eq=contrast=2.2:brightness=0.05"] if noise_scene else [] ),
        chroma_geq(chroma), _scanlines(), _glitch_stripe(), "vignette=PI/2.8",
        *extra,
    ]
    run([
        "-f","lavfi","-i",f"color={bg_color}:s={W}x{H}:r={FPS}",
        "-loop","1","-i", str(overlay_png),
        "-filter_complex",
        f"[0:v]{','.join(filters)}[v];[v][1:v]overlay=0:0[out]",
        "-map","[out]", "-t",str(dur),"-r",str(FPS),
        "-c:v","libx264","-pix_fmt","yuv420p", str(out),
    ], f"color({bg_color}) → {out.name}")


def seg_blackout(dur, out):
    run([
        "-f","lavfi","-i",f"color=black:s={W}x{H}:r={FPS}",
        "-filter_complex",
        f"[0:v]noise=alls=12:allf=t,"
        f"geq=r='r(X+{fs(20)}*sin(T*80),Y)':g='g(X,Y)':b='b(X-{fs(20)}*cos(T*70),Y)'[out]",
        "-map","[out]", "-t",str(dur),"-r",str(FPS),
        "-c:v","libx264","-pix_fmt","yuv420p", str(out),
    ], "blackout → " + out.name)

# ─── Audio synthesis ──────────────────────────────────────────────────────────

def make_audio(dur: float, acfg: AudioConfig, out_path: Path):
    """Build an aevalsrc expression from AudioConfig and render to wav."""
    b = 60.0 / acfg.bpm          # beat (quarter note)
    s = b / 4.0                   # 16th
    e = b / 2.0                   # 8th

    def period(rhythm):
        return b / RHYTHM_DIVISOR.get(rhythm, 2)

    parts = []

    if "kick" in acfg.layers and acfg.kick_vol > 0:
        parts.append(
            f"{acfg.kick_vol:.2f}"
            f"*sin(2*PI*t*{acfg.kick_freq:.1f})"
            f"*exp(-{acfg.kick_decay:.1f}*mod(t,{b:.4f}))"
            f"*lt(mod(t,{b:.4f}),0.08)"
        )

    if "snare" in acfg.layers and acfg.snare_vol > 0:
        half = b / 2
        parts.append(
            f"{acfg.snare_vol:.2f}"
            f"*(2*random(floor((t+{half:.4f})/{b:.4f}))-1)"
            f"*exp(-{acfg.snare_decay:.1f}*mod(t+{half:.4f},{b:.4f}))"
            f"*lt(mod(t+{half:.4f},{b:.4f}),0.04)"
        )

    if "hat" in acfg.layers and acfg.hat_vol > 0:
        hp = period(acfg.hat_rhythm)
        parts.append(
            f"{acfg.hat_vol:.2f}"
            f"*(2*random(floor(t/{hp:.4f})+7)-1)"
            f"*exp(-400*mod(t,{hp:.4f}))"
            f"*lt(mod(t,{hp:.4f}),0.012)"
        )

    if "arp" in acfg.layers and acfg.arp_vol > 0:
        freqs = scale_freqs(acfg.arp_root, acfg.arp_octave, acfg.arp_scale)
        ap = period(acfg.arp_rhythm)
        for i, freq in enumerate(freqs):
            note = wave_expr("t", freq, acfg.arp_wave)
            parts.append(
                f"{acfg.arp_vol:.2f}"
                f"*({note})"
                f"*exp(-18*mod(t,{ap:.4f}))"
                f"*lt(mod(t,{ap:.4f}),{ap*0.65:.4f})"
                f"*eq(mod(floor(t/{ap:.4f}),4),{i})"
            )

    if "bass" in acfg.layers and acfg.bass_vol > 0:
        parts.append(
            f"{acfg.bass_vol:.2f}"
            f"*sin(2*PI*t*{acfg.bass_freq:.1f})"
            f"*exp(-{acfg.bass_decay:.1f}*mod(t,{b:.4f}))"
            f"*lt(mod(t,{b:.4f}),{b*0.65:.4f})"
        )

    if not parts:
        parts = ["0"]

    mix = "+".join(parts)
    if acfg.distort:
        d = acfg.distort_drive
        mix = f"tanh({d:.1f}*({mix}))/tanh({d:.1f})"

    expr = f"({mix})*{acfg.master:.2f}"

    run([
        "-f","lavfi","-i",f"aevalsrc='{expr}':s=44100",
        "-t",str(dur),"-ar","44100","-ac","1", str(out_path),
    ], f"audio ({acfg.style}, {acfg.bpm} BPM, layers={acfg.layers})")

# ─── Concat + mux ─────────────────────────────────────────────────────────────

def concat_and_mux(segments, audio_path, out_path):
    w   = audio_path.parent          # audio_path is already inside the stem work dir
    cf  = w / "concat_list.txt"
    tmp = w / "concat_raw.mp4"
    cf.write_text("\n".join(f"file '{Path(s).resolve()}'" for s in segments) + "\n")
    run(["-f","concat","-safe","0","-i",str(cf),"-c","copy",str(tmp)],
        "concat segments")
    run(["-i",str(tmp),"-i",str(audio_path),
         "-c:v","copy","-c:a","aac","-b:a","192k","-shortest",str(out_path)],
        f"mux → {out_path.name}")

# ─── Stinger builders ─────────────────────────────────────────────────────────

def _pick(images: List[str], n: int) -> List[str]:
    if not images:
        sys.exit("  ✗  no source images found")
    return [images[i % len(images)] for i in range(n)]


def build_5s(cfg: Config):
    print("\n▶  5-second stinger")
    kw, imgs, w = cfg.keywords, _pick(cfg.images, 6), cfg.work
    ifx, cfx = cfg.img_fx, cfg.col_fx
    segs = []

    ov = w / "ov_noise.png";      render_noise_overlay(cfg, kw[:5], ov)
    p  = w / "5s_00_noise.mp4";   seg_from_color("0x0a1a14", ov, 0.45, p, noise=95, chroma=9, extra=cfx)
    segs.append(str(p))

    ov = w / "ov_kw1.png";        render_keyword_overlay(kw[0:4], ov)
    p  = w / "5s_01.mp4";         seg_from_image(imgs[0], ov, 0.7, p, noise=22, chroma=7, extra=ifx)
    segs.append(str(p))

    ov = w / "ov_kw2.png";        render_keyword_overlay(kw[4:8], ov)
    p  = w / "5s_02.mp4";         seg_from_image(imgs[1], ov, 0.65, p, noise=16, chroma=4, extra=ifx)
    segs.append(str(p))

    ov = w / "ov_title_img.png"
    render_title_overlay(cfg, "  •  ".join(k.lower() for k in kw[8:11]), ov)
    p  = w / "5s_03.mp4";         seg_from_image(imgs[2], ov, 0.8, p, noise=20, chroma=9, extra=ifx)
    segs.append(str(p))

    ov = w / "ov_kw3.png";        render_keyword_overlay((kw[11:15] or kw[-4:]), ov)
    p  = w / "5s_04.mp4";         seg_from_image(imgs[3], ov, 0.6, p, noise=25, chroma=6, extra=ifx)
    segs.append(str(p))

    ov = w / "ov_title_card.png"; render_glitch_title_overlay(cfg, ov)
    p  = w / "5s_05_title.mp4";   seg_from_color("0x06060e", ov, 1.8, p, noise=14, chroma=10, extra=cfx)
    segs.append(str(p))

    p  = w / "5s_06_black.mp4";   seg_blackout(0.35, p)
    segs.append(str(p))

    ap  = w / "audio_5s.wav";     make_audio(5.35, cfg.audio, ap)
    out = cfg.output / f"{cfg.stem}_5s{cfg.res_suffix}.mp4"
    concat_and_mux(segs, ap, out)
    print(f"  ✓  {out}")


def build_1s(cfg: Config):
    print("\n▶  1-second stinger")
    kw, imgs, w = cfg.keywords, _pick(cfg.images, 1), cfg.work
    ifx, cfx = cfg.img_fx, cfg.col_fx
    segs = []

    ov = w / "1s_ov_noise.png";  render_noise_overlay(cfg, kw[:2], ov)
    p  = w / "1s_00_noise.mp4"; seg_from_color("0x0a1a14", ov, 0.1, p, noise=95, chroma=9, extra=cfx)
    segs.append(str(p))

    ov = w / "1s_ov_img.png"
    render_title_overlay(cfg, "  •  ".join(k.lower() for k in kw[:3]), ov)
    p  = w / "1s_01.mp4";       seg_from_image(imgs[0], ov, 0.55, p, noise=28, chroma=12, extra=ifx)
    segs.append(str(p))

    ov = w / "1s_ov_title.png"; render_glitch_title_overlay(cfg, ov)
    p  = w / "1s_02_title.mp4"; seg_from_color("0x06060e", ov, 0.35, p, noise=14, chroma=15, extra=cfx)
    segs.append(str(p))

    ap  = w / "audio_1s.wav";   make_audio(1.0, cfg.audio, ap)
    out = cfg.output / f"{cfg.stem}_1s{cfg.res_suffix}.mp4"
    concat_and_mux(segs, ap, out)
    print(f"  ✓  {out}")

# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> Config:
    p = argparse.ArgumentParser(
        prog="make_stinger.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    g_brand = p.add_argument_group("channel branding")
    g_brand.add_argument("--title",    "-T", default="GUI FREE LIFE", metavar="TEXT",
        help="Channel name on screen. (default: 'GUI FREE LIFE')")
    g_brand.add_argument("--subtitle", "-S", default="guifreelife.com", metavar="TEXT",
        help="URL / tagline below title. (default: 'guifreelife.com')")
    g_brand.add_argument("--tagline", default="", metavar="TEXT",
        help="Footer text. Auto-derived from keywords if omitted.")

    g_input = p.add_argument_group("inputs")
    g_input.add_argument("--keywords", "-k", default=str(DEFAULT_KEYWORDS_FILE),
        metavar="FILE_OR_LIST",
        help=f"Keywords: .txt file or comma-separated. (default: {DEFAULT_KEYWORDS_FILE.name})")
    g_input.add_argument("--images", "-i", default=str(DEFAULT_IMAGES_FILE),
        metavar="FILE_OR_LIST_OR_GLOB",
        help=f"Images: .txt file, comma list, or glob. (default: {DEFAULT_IMAGES_FILE.name})")

    g_audio = p.add_argument_group("audio")
    g_audio.add_argument("--audio", "-a", default=str(DEFAULT_AUDIO_FILE),
        metavar="TOML_FILE",
        help=f"Audio config TOML. (default: {DEFAULT_AUDIO_FILE.name})")
    g_audio.add_argument("--audio-style", "-A",
        choices=list(AUDIO_PRESETS.keys()), default=None,
        metavar="STYLE",
        help="Audio style preset — overrides [audio] style in TOML. "
             f"Choices: {', '.join(AUDIO_PRESETS)}")
    g_audio.add_argument("--bpm", type=int, default=None, metavar="N",
        help="BPM — overrides TOML and preset. (preset default: 140)")
    g_audio.add_argument("--layers", default=None, metavar="LIST",
        help="Comma-separated active layers. e.g. kick,bass,arp")

    g_out = p.add_argument_group("output")
    g_out.add_argument("--duration", "-d", choices=["1s","5s","both"], default="both",
        help="Which stinger(s) to generate. (default: both)")
    g_out.add_argument("--stem", default="stinger", metavar="NAME",
        help="Output filename base: {stem}_5s.mp4 / {stem}_1s.mp4. (default: stinger)")
    g_out.add_argument("--output", "-o", default=str(HERE), metavar="DIR",
        help=f"Output directory. (default: {HERE})")
    g_out.add_argument("--resolution", "-r", choices=list(RESOLUTIONS), default="hd",
        metavar="RES",
        help="Output resolution: hd (1920×1080) or 4k (3840×2160). (default: hd)")
    g_out.add_argument("--intensity", "-x", choices=["normal", "extreme"], default="normal",
        metavar="LEVEL",
        help="Visual effect intensity: normal or extreme (adds scan jitter, rgb bleed, "
             "extra glitch stripe). (default: normal)")
    g_out.add_argument("--seed", type=int, default=None, metavar="N",
        help="Random seed for reproducible image shuffle.")

    args = p.parse_args()

    _ensure_default_files()

    keywords = resolve_keywords(args.keywords)
    if not keywords:
        p.error(f"No keywords found in: {args.keywords}")
    images = resolve_images(args.images, base=ROOT)
    if not images:
        p.error(f"No existing images found from: {args.images}")

    if args.seed is not None:
        random.seed(args.seed)
    random.shuffle(images)

    # Build AudioConfig: toml style → CLI --audio-style → CLI --bpm
    audio_cfg = load_audio_config(args.audio, args.audio_style, args.bpm)
    if args.layers:
        audio_cfg.layers = [l.strip() for l in args.layers.split(",") if l.strip()]

    return Config(
        title      = args.title,
        subtitle   = args.subtitle,
        tagline    = args.tagline,
        keywords   = keywords,
        images     = images,
        duration   = args.duration,
        stem       = args.stem,
        output     = Path(args.output),
        seed       = args.seed,
        audio      = audio_cfg,
        resolution = args.resolution,
        intensity  = args.intensity,
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    cfg = parse_args()
    ac  = cfg.audio

    # Apply resolution — must happen before any render/ffmpeg calls
    global W, H
    W, H = RESOLUTIONS[cfg.resolution]

    print("═" * 52)
    print(f"  {cfg.title} — Stinger Generator")
    print("═" * 52)

    if not shutil.which("ffmpeg"):
        sys.exit("ERROR: ffmpeg not found in PATH")

    cfg.output.mkdir(parents=True, exist_ok=True)
    cfg.work.mkdir(parents=True, exist_ok=True)

    print(f"  title      : {cfg.title}")
    print(f"  subtitle   : {cfg.subtitle}")
    print(f"  tagline    : {cfg.tagline}")
    print(f"  keywords   : {len(cfg.keywords)}  ({', '.join(cfg.keywords[:5])}…)")
    print(f"  images     : {len(cfg.images)}")
    print(f"  duration   : {cfg.duration}")
    print(f"  resolution : {cfg.resolution}  ({W}×{H})")
    print(f"  intensity  : {cfg.intensity}")
    print(f"  output     : {cfg.output}")
    print(f"  audio      : style={ac.style}  bpm={ac.bpm}  "
          f"layers=[{', '.join(ac.layers)}]")
    print(f"               arp={ac.arp_scale}/{ac.arp_root}{ac.arp_octave} "
          f"wave={ac.arp_wave}  distort={ac.distort}")

    if cfg.duration in ("5s", "both"):
        build_5s(cfg)
    if cfg.duration in ("1s", "both"):
        build_1s(cfg)

    shutil.rmtree(cfg.work, ignore_errors=True)

    print("\n  Done.")
    if cfg.duration in ("5s", "both"):
        print(f"  → {cfg.output / f'{cfg.stem}_5s{cfg.res_suffix}.mp4'}  (5-second promo)")
    if cfg.duration in ("1s", "both"):
        print(f"  → {cfg.output / f'{cfg.stem}_1s{cfg.res_suffix}.mp4'}  (1-second bumper)")


if __name__ == "__main__":
    main()
