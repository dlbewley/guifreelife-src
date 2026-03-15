#!/usr/bin/env python3
"""
make_stinger.py — Glitchy electro-style YouTube channel stinger generator.

Produces 1-second and/or 5-second stinger videos driven by ffmpeg + Pillow.
All inputs (channel name, keywords, source images) are configurable via
command-line flags or plain-text files, making this easy to invoke from a
Claude Code skill or CI pipeline.

QUICK START
    python3 stingers/make_stinger.py

    Reads stingers/keywords.txt and stingers/images.txt if present;
    generates defaults on first run.

EXAMPLES
    # Use defaults (reads keywords.txt / images.txt):
    python3 stingers/make_stinger.py

    # Override channel branding:
    python3 stingers/make_stinger.py \\
        --title "MY CHANNEL" --subtitle "mychannel.com"

    # Inline keywords (comma-separated) and a custom image list file:
    python3 stingers/make_stinger.py \\
        --keywords "OVN,Kubernetes,Security,Ansible" \\
        --images path/to/images.txt

    # Only the 1-second bumper, faster BPM:
    python3 stingers/make_stinger.py --duration 1s --bpm 160

    # Completely custom image set (comma-separated paths or glob):
    python3 stingers/make_stinger.py \\
        --images "static/images/*.png,static/img/banners/banner-7.jpg"

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Paths ────────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent    # stingers/
ROOT = HERE.parent              # repo root

W, H, FPS = 1920, 1080, 30

# ─── Default content files ────────────────────────────────────────────────────
DEFAULT_KEYWORDS_FILE = HERE / "keywords.txt"
DEFAULT_IMAGES_FILE   = HERE / "images.txt"

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

# ─── Config ───────────────────────────────────────────────────────────────────

@dataclass
class Config:
    title:    str        = "GUI FREE LIFE"
    subtitle: str        = "guifreelife.com"
    tagline:  str        = ""           # auto-derived from keywords if blank
    keywords: List[str]  = field(default_factory=list)
    images:   List[str]  = field(default_factory=list)
    duration: str        = "both"       # "1s" | "5s" | "both"
    bpm:      int        = 140
    output:   Path       = HERE
    no_audio: bool       = False
    seed:     int        = None

    def __post_init__(self):
        if not self.tagline and self.keywords:
            sample = self.keywords[:4]
            self.tagline = "  •  ".join(k.lower() for k in sample)

    @property
    def work(self) -> Path:
        return self.output / "_work"

# ─── Fonts ────────────────────────────────────────────────────────────────────

def _find_font(*paths):
    for p in paths:
        if Path(p).exists():
            return p
    sys.exit(f"No usable font found. Tried:\n" + "\n".join(f"  {p}" for p in paths))

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

# ─── File loaders ─────────────────────────────────────────────────────────────

def _ensure_default_files():
    """Write default keywords.txt and images.txt if they don't exist yet."""
    if not DEFAULT_KEYWORDS_FILE.exists():
        lines = [
            "# GUI Free Life — keyword flash list",
            "# One keyword per line. Lines starting with # are comments.",
            "# These flash on screen during the stinger.",
            "",
        ] + DEFAULT_KEYWORDS
        DEFAULT_KEYWORDS_FILE.write_text("\n".join(lines) + "\n")
        print(f"  created {DEFAULT_KEYWORDS_FILE.name}")

    if not DEFAULT_IMAGES_FILE.exists():
        lines = [
            "# GUI Free Life — source image list",
            "# One path per line, relative to the repo root or absolute.",
            "# Lines starting with # are comments.",
            "# A random selection is used for each render.",
            "",
        ] + DEFAULT_IMAGES
        DEFAULT_IMAGES_FILE.write_text("\n".join(lines) + "\n")
        print(f"  created {DEFAULT_IMAGES_FILE.name}")


def load_text_file(path: Path) -> List[str]:
    """Return non-empty, non-comment lines from a text file."""
    lines = []
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines


def resolve_images(spec: str, base: Path = ROOT) -> List[str]:
    """
    Resolve an image spec to a list of existing file paths.

    spec may be:
      - a path to a .txt file (one path per line)
      - a comma-separated list of paths or globs
    """
    spec = spec.strip()
    paths: List[str] = []

    # Single .txt file?
    candidate = Path(spec)
    if candidate.suffix == ".txt" and candidate.exists():
        raw_paths = load_text_file(candidate)
    else:
        raw_paths = [s.strip() for s in spec.split(",") if s.strip()]

    for raw in raw_paths:
        # Try glob expansion (handles wildcards)
        expanded = globmod.glob(raw) or globmod.glob(str(base / raw))
        if expanded:
            paths.extend(expanded)
        else:
            # Exact path, absolute or relative to repo root
            p = Path(raw)
            if not p.is_absolute():
                p = base / raw
            if p.exists():
                paths.append(str(p))

    return [str(Path(p).resolve()) for p in paths if Path(p).exists()]


def resolve_keywords(spec: str) -> List[str]:
    """
    Resolve a keyword spec to a list of strings.

    spec may be:
      - a path to a .txt file (one keyword per line)
      - a comma-separated list of keywords
    """
    spec = spec.strip()
    candidate = Path(spec)
    if candidate.suffix == ".txt" and candidate.exists():
        return load_text_file(candidate)
    return [s.strip() for s in spec.split(",") if s.strip()]

# ─── Pillow text rendering ────────────────────────────────────────────────────

def make_font(path, size):
    return ImageFont.truetype(path, size)

def text_size(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]

def glow_text(img, draw, x, y, text, font,
              fill_color, glow_color, glow_radius=12, glow_alpha=180):
    """Draw text with a soft glow halo behind it."""
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    for dx in range(-2, 3, 2):
        for dy in range(-1, 2, 2):
            gd.text((x + dx, y + dy), text, font=font,
                    fill=(*glow_color, glow_alpha))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    img.alpha_composite(glow_layer)
    draw.text((x, y), text, font=font, fill=fill_color)


def render_keyword_overlay(keywords: List[str], out_path: Path):
    """Four corner keyword tags on a transparent RGBA canvas."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = make_font(FONT_MONO_PATH, 46)
    margin = 55
    positions = [("left","top"), ("right","top"),
                 ("left","bottom"), ("right","bottom")]

    for i, kw in enumerate(keywords[:4]):
        label = f"[ {kw.upper()} ]"
        tw, th = text_size(draw, label, font)
        side_x, side_y = positions[i]
        x = margin if side_x == "left" else W - tw - margin
        y = margin if side_y == "top"  else H - th - margin
        glow_text(img, draw, x, y, label, font,
                  fill_color=rgba(CYAN, 220),
                  glow_color=MAGENTA,
                  glow_radius=10, glow_alpha=130)

    img.save(str(out_path), "PNG")


def render_title_overlay(cfg: Config, tag_line_override: str, out_path: Path):
    """Title + subtitle + tag line on a transparent canvas (used over images)."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_big = make_font(FONT_DISPLAY_PATH, 180)
    tw, th   = text_size(draw, cfg.title, font_big)
    tx = (W - tw) // 2
    ty = (H - th) // 2 - 40

    # Dark backing box
    pad = 18
    box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(box).rectangle(
        [tx - pad, ty - pad, tx + tw + pad, ty + th + pad],
        fill=(0, 0, 0, 140))
    img.alpha_composite(box)
    draw = ImageDraw.Draw(img)

    # Magenta glitch-offset shadow
    draw.text((tx + 8, ty), cfg.title, font=font_big, fill=rgba(MAGENTA, 160))
    glow_text(img, draw, tx, ty, cfg.title, font_big,
              fill_color=rgba(CYAN, 255), glow_color=CYAN,
              glow_radius=16, glow_alpha=120)
    draw = ImageDraw.Draw(img)

    font_sub = make_font(FONT_MONO_PATH, 60)
    sw, sh   = text_size(draw, cfg.subtitle, font_sub)
    glow_text(img, draw, (W - sw) // 2, ty + th + 30, cfg.subtitle, font_sub,
              fill_color=rgba(GREEN, 230), glow_color=GREEN,
              glow_radius=8, glow_alpha=90)
    draw = ImageDraw.Draw(img)

    font_tag = make_font(FONT_MONO_PATH, 36)
    tgw, tgh = text_size(draw, tag_line_override, font_tag)
    draw.text(((W - tgw) // 2, H - tgh - 55),
              tag_line_override, font=font_tag, fill=rgba(WHITE, 80))

    img.save(str(out_path), "PNG")


def render_noise_overlay(cfg: Config, keywords: List[str], out_path: Path):
    """Matrix-green terminal keyword list + ghost title for the static scene."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = make_font(FONT_MONO_PATH, 70)
    n    = min(len(keywords), 5)
    step = H // (n + 1)

    for i, kw in enumerate(keywords[:n]):
        y = step * (i + 1) - 35
        glow_text(img, draw, 60, y, f"$ {kw.upper()}_", font,
                  fill_color=rgba(GREEN, 230), glow_color=GREEN,
                  glow_radius=8, glow_alpha=100)
        draw = ImageDraw.Draw(img)

    font_ghost = make_font(FONT_DISPLAY_PATH, 120)
    gtw, gth   = text_size(draw, cfg.title, font_ghost)
    draw.text(((W - gtw) // 2, (H - gth) // 2),
              cfg.title, font=font_ghost, fill=rgba(CYAN, 35))

    img.save(str(out_path), "PNG")


def render_glitch_title_overlay(cfg: Config, out_path: Path):
    """Full-bleed title card overlay: title, subtitle, tag footer."""
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_big = make_font(FONT_DISPLAY_PATH, 180)
    tw, th   = text_size(draw, cfg.title, font_big)
    tx = (W - tw) // 2
    ty = (H - th) // 2 - 40

    # Wide glow layer
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow_layer).text((tx, ty), cfg.title,
                                   font=font_big, fill=rgba(CYAN, 100))
    img.alpha_composite(
        glow_layer.filter(ImageFilter.GaussianBlur(radius=24)))
    draw = ImageDraw.Draw(img)

    draw.text((tx + 14, ty), cfg.title, font=font_big, fill=rgba(MAGENTA, 200))
    draw.text((tx,      ty), cfg.title, font=font_big, fill=rgba(CYAN, 255))

    font_sub = make_font(FONT_MONO_PATH, 60)
    sw, sh   = text_size(draw, cfg.subtitle, font_sub)
    glow_text(img, draw, (W - sw) // 2, ty + th + 28, cfg.subtitle, font_sub,
              fill_color=rgba(GREEN, 235), glow_color=GREEN,
              glow_radius=8, glow_alpha=90)
    draw = ImageDraw.Draw(img)

    font_tag = make_font(FONT_MONO_PATH, 36)
    tgw, _   = text_size(draw, cfg.tagline, font_tag)
    draw.text(((W - tgw) // 2, H - 65),
              cfg.tagline, font=font_tag, fill=rgba(WHITE, 75))

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

def chroma_geq(strength=6):
    s = strength
    return (f"geq="
            f"r='r(X+{s}*sin(T*17),Y+2*cos(T*9))':"
            f"g='g(X,Y)':"
            f"b='b(X-{s}*cos(T*13),Y-2*sin(T*11))'")

SCANLINES = ("geq="
             "lum='lum(X,Y)*(0.55+0.45*cos(Y*PI/1.5))':"
             "cb='cb(X,Y)':"
             "cr='cr(X,Y)'")

GLITCH_STRIPE = ("geq="
                 "lum='lum(X,Y)+if(between(Y,floor(500+300*sin(T*29)),"
                 "floor(516+300*sin(T*29))),random(1)*90,0)':"
                 "cb='cb(X,Y)':"
                 "cr='cr(X,Y)'")

def base_glitch_chain(noise=18, chroma=5):
    return ",".join([
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
        "eq=contrast=1.5:brightness=-0.07:saturation=2.0",
        "colorchannelmixer=rr=0.65:gg=0.92:bb=1.18",
        f"noise=alls={noise}:allf=t",
        chroma_geq(chroma),
        SCANLINES,
        "vignette=PI/3.2",
    ])

# ─── Segment generators ───────────────────────────────────────────────────────

def seg_from_image(img_path, overlay_png, dur, out, noise=18, chroma=5):
    glitch = base_glitch_chain(noise=noise, chroma=chroma)
    run([
        "-loop", "1", "-i", img_path,
        "-loop", "1", "-i", str(overlay_png),
        "-filter_complex", f"[0:v]{glitch}[v];[v][1:v]overlay=0:0[out]",
        "-map", "[out]",
        "-t", str(dur), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ], f"img({Path(img_path).name}) → {out.name}")


def seg_from_color(bg_color, overlay_png, dur, out,
                   noise=60, chroma=8):
    is_noise_scene = "0a1a14" in bg_color
    filters = [
        f"noise=alls={noise}:allf=t",
        *( ["colorchannelmixer=rr=0.04:gg=0.28:bb=0.22",
            "eq=contrast=2.2:brightness=0.05"] if is_noise_scene else [] ),
        chroma_geq(chroma),
        SCANLINES,
        GLITCH_STRIPE,
        "vignette=PI/2.8",
    ]
    run([
        "-f", "lavfi", "-i", f"color={bg_color}:s={W}x{H}:r={FPS}",
        "-loop", "1", "-i", str(overlay_png),
        "-filter_complex",
        f"[0:v]{','.join(filters)}[v];[v][1:v]overlay=0:0[out]",
        "-map", "[out]",
        "-t", str(dur), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ], f"color({bg_color}) → {out.name}")


def seg_blackout(dur, out):
    run([
        "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}",
        "-filter_complex",
        "[0:v]noise=alls=12:allf=t,"
        "geq=r='r(X+20*sin(T*80),Y)':g='g(X,Y)':b='b(X-20*cos(T*70),Y)'[out]",
        "-map", "[out]",
        "-t", str(dur), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ], f"blackout → {out.name}")

# ─── Audio synthesis ──────────────────────────────────────────────────────────

def make_audio(dur, bpm=140, out_path=None):
    b = 60.0 / bpm
    s = b / 4.0
    e = b / 2.0
    kick  = f"0.85*sin(2*PI*t*75)*exp(-50*mod(t,{b:.4f}))*lt(mod(t,{b:.4f}),0.07)"
    snare = (f"0.55*(2*random(floor((t+{b/2:.4f})/{b:.4f}))-1)"
             f"*exp(-90*mod(t+{b/2:.4f},{b:.4f}))"
             f"*lt(mod(t+{b/2:.4f},{b:.4f}),0.04)")
    hat   = (f"0.18*(2*random(floor(t/{e:.4f})+7)-1)"
             f"*exp(-400*mod(t,{e:.4f}))*lt(mod(t,{e:.4f}),0.012)")
    arp   = "+".join(
        f"0.28*sin(2*PI*t*{f})*exp(-18*mod(t,{s:.4f}))"
        f"*lt(mod(t,{s:.4f}),{s*0.65:.4f})*eq(mod(floor(t/{s:.4f}),4),{i})"
        for i, f in enumerate([523, 659, 784, 988])
    )
    bass  = f"0.4*sin(2*PI*t*55)*exp(-6*mod(t,{b:.4f}))*lt(mod(t,{b:.4f}),{b*0.6:.4f})"
    expr  = f"({kick}+{snare}+{hat}+{arp}+{bass})*0.65"
    run([
        "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100",
        "-t", str(dur), "-ar", "44100", "-ac", "1", str(out_path),
    ], "audio synthesis")

# ─── Concat + mux ─────────────────────────────────────────────────────────────

def concat_and_mux(segments, audio_path, out_path):
    cf  = out_path.parent / "_work" / "concat_list.txt"
    tmp = out_path.parent / "_work" / "concat_raw.mp4"
    cf.write_text("\n".join(f"file '{Path(s).resolve()}'" for s in segments) + "\n")
    run(["-f","concat","-safe","0","-i",str(cf),"-c","copy",str(tmp)],
        "concat segments")
    run(["-i",str(tmp),"-i",str(audio_path),
         "-c:v","copy","-c:a","aac","-b:a","192k","-shortest",str(out_path)],
        f"mux → {out_path.name}")

# ─── Stinger builders ─────────────────────────────────────────────────────────

def _pick(images: List[str], n: int) -> List[str]:
    """Return up to n images; if fewer exist just cycle."""
    if not images:
        sys.exit("  ✗  no source images found")
    if len(images) >= n:
        return images[:n]
    return [images[i % len(images)] for i in range(n)]


def build_5s(cfg: Config):
    print("\n▶  5-second stinger")
    kw   = cfg.keywords
    imgs = _pick(cfg.images, 6)
    w    = cfg.work
    segs = []

    # 0: noise burst (0.45s)
    ov = w / "ov_noise.png"
    render_noise_overlay(cfg, kw[:5], ov)
    p  = w / "5s_00_noise.mp4"
    seg_from_color("0x0a1a14", ov, 0.45, p, noise=95, chroma=9)
    segs.append(str(p))

    # 1: image — first keyword group (0.7s)
    ov = w / "ov_kw1.png"
    render_keyword_overlay(kw[0:4], ov)
    p  = w / "5s_01.mp4"
    seg_from_image(imgs[0], ov, 0.7, p, noise=22, chroma=7)
    segs.append(str(p))

    # 2: image — second keyword group (0.65s)
    ov = w / "ov_kw2.png"
    render_keyword_overlay(kw[4:8], ov)
    p  = w / "5s_02.mp4"
    seg_from_image(imgs[1], ov, 0.65, p, noise=16, chroma=4)
    segs.append(str(p))

    # 3: image — title emerges (0.8s)
    ov = w / "ov_title_img.png"
    render_title_overlay(cfg, "  •  ".join(k.lower() for k in kw[8:11]), ov)
    p  = w / "5s_03.mp4"
    seg_from_image(imgs[2], ov, 0.8, p, noise=20, chroma=9)
    segs.append(str(p))

    # 4: image — third keyword group (0.6s)
    ov = w / "ov_kw3.png"
    render_keyword_overlay(kw[11:15] if len(kw) > 11 else kw[-4:], ov)
    p  = w / "5s_04.mp4"
    seg_from_image(imgs[3], ov, 0.6, p, noise=25, chroma=6)
    segs.append(str(p))

    # 5: title card (1.8s)
    ov = w / "ov_title_card.png"
    render_glitch_title_overlay(cfg, ov)
    p  = w / "5s_05_title.mp4"
    seg_from_color("0x06060e", ov, 1.8, p, noise=14, chroma=10)
    segs.append(str(p))

    # 6: blackout (0.35s)
    p = w / "5s_06_black.mp4"
    seg_blackout(0.35, p)
    segs.append(str(p))

    audio_path = w / "audio_5s.wav"
    if not cfg.no_audio:
        make_audio(5.35, bpm=cfg.bpm, out_path=audio_path)
        out = cfg.output / "stinger_5s.mp4"
        concat_and_mux(segs, audio_path, out)
    else:
        cf  = w / "concat_list.txt"
        tmp = w / "concat_raw.mp4"
        out = cfg.output / "stinger_5s.mp4"
        cf.write_text("\n".join(f"file '{Path(s).resolve()}'" for s in segs) + "\n")
        run(["-f","concat","-safe","0","-i",str(cf),"-c","copy",str(out)],
            "concat segments (no audio)")

    print(f"  ✓  {out}")


def build_1s(cfg: Config):
    print("\n▶  1-second stinger")
    kw   = cfg.keywords
    imgs = _pick(cfg.images, 1)
    w    = cfg.work
    segs = []

    # 0: static flash (0.1s)
    ov = w / "1s_ov_noise.png"
    render_noise_overlay(cfg, kw[:2], ov)
    p  = w / "1s_00_noise.mp4"
    seg_from_color("0x0a1a14", ov, 0.1, p, noise=95, chroma=9)
    segs.append(str(p))

    # 1: image + full title (0.55s)
    ov = w / "1s_ov_img.png"
    render_title_overlay(cfg, "  •  ".join(k.lower() for k in kw[:3]), ov)
    p  = w / "1s_01.mp4"
    seg_from_image(imgs[0], ov, 0.55, p, noise=28, chroma=12)
    segs.append(str(p))

    # 2: title slam (0.35s)
    ov = w / "1s_ov_title.png"
    render_glitch_title_overlay(cfg, ov)
    p  = w / "1s_02_title.mp4"
    seg_from_color("0x06060e", ov, 0.35, p, noise=14, chroma=15)
    segs.append(str(p))

    audio_path = w / "audio_1s.wav"
    if not cfg.no_audio:
        make_audio(1.0, bpm=cfg.bpm, out_path=audio_path)
        out = cfg.output / "stinger_1s.mp4"
        concat_and_mux(segs, audio_path, out)
    else:
        cf  = w / "concat_list.txt"
        out = cfg.output / "stinger_1s.mp4"
        cf.write_text("\n".join(f"file '{Path(s).resolve()}'" for s in segs) + "\n")
        run(["-f","concat","-safe","0","-i",str(cf),"-c","copy",str(out)],
            "concat segments (no audio)")

    print(f"  ✓  {out}")

# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> Config:
    p = argparse.ArgumentParser(
        prog="make_stinger.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument(
        "--title", "-T",
        default="GUI FREE LIFE",
        metavar="TEXT",
        help="Channel name displayed prominently. (default: 'GUI FREE LIFE')",
    )
    p.add_argument(
        "--subtitle", "-S",
        default="guifreelife.com",
        metavar="TEXT",
        help="URL or tagline shown below the title. (default: 'guifreelife.com')",
    )
    p.add_argument(
        "--tagline",
        default="",
        metavar="TEXT",
        help="Footer text on the title card. Auto-derived from keywords if omitted.",
    )
    p.add_argument(
        "--keywords", "-k",
        default=str(DEFAULT_KEYWORDS_FILE),
        metavar="FILE_OR_LIST",
        help=(
            "Keywords to flash on screen. "
            "A .txt file path (one per line) or comma-separated list. "
            f"(default: {DEFAULT_KEYWORDS_FILE.name})"
        ),
    )
    p.add_argument(
        "--images", "-i",
        default=str(DEFAULT_IMAGES_FILE),
        metavar="FILE_OR_LIST_OR_GLOB",
        help=(
            "Source images. A .txt file path, comma-separated paths, "
            "or a glob pattern. "
            f"(default: {DEFAULT_IMAGES_FILE.name})"
        ),
    )
    p.add_argument(
        "--duration", "-d",
        choices=["1s", "5s", "both"],
        default="both",
        help="Which stinger(s) to generate. (default: both)",
    )
    p.add_argument(
        "--bpm",
        type=int,
        default=140,
        metavar="N",
        help="Audio tempo in BPM. (default: 140)",
    )
    p.add_argument(
        "--output", "-o",
        default=str(HERE),
        metavar="DIR",
        help=f"Output directory. (default: {HERE})",
    )
    p.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip audio synthesis (video-only output).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Random seed for reproducible image selection.",
    )

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

    return Config(
        title    = args.title,
        subtitle = args.subtitle,
        tagline  = args.tagline,
        keywords = keywords,
        images   = images,
        duration = args.duration,
        bpm      = args.bpm,
        output   = Path(args.output),
        no_audio = args.no_audio,
        seed     = args.seed,
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    cfg = parse_args()

    print("═" * 50)
    print(f"  {cfg.title} — Stinger Generator")
    print("═" * 50)

    if not shutil.which("ffmpeg"):
        sys.exit("ERROR: ffmpeg not found in PATH")

    cfg.output.mkdir(parents=True, exist_ok=True)
    cfg.work.mkdir(parents=True, exist_ok=True)

    print(f"  title    : {cfg.title}")
    print(f"  subtitle : {cfg.subtitle}")
    print(f"  tagline  : {cfg.tagline}")
    print(f"  keywords : {len(cfg.keywords)}  ({', '.join(cfg.keywords[:5])}…)")
    print(f"  images   : {len(cfg.images)}")
    print(f"  duration : {cfg.duration}")
    print(f"  bpm      : {cfg.bpm}")
    print(f"  output   : {cfg.output}")

    if cfg.duration in ("5s", "both"):
        build_5s(cfg)
    if cfg.duration in ("1s", "both"):
        build_1s(cfg)

    shutil.rmtree(cfg.work, ignore_errors=True)

    print("\n  Done.")
    if cfg.duration in ("5s", "both"):
        print(f"  → {cfg.output / 'stinger_5s.mp4'}  (5-second promo)")
    if cfg.duration in ("1s", "both"):
        print(f"  → {cfg.output / 'stinger_1s.mp4'}  (1-second bumper)")


if __name__ == "__main__":
    main()
