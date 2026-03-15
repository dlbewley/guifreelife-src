#!/usr/bin/env python3
"""
make_stinger.py — GUI Free Life YouTube channel stinger generator.

Produces:
    stinger_5s.mp4   – 5-second promo stinger
    stinger_1s.mp4   – 1-second bumper

Run from anywhere:
    python3 stingers/make_stinger.py

Requirements:
    ffmpeg in PATH  (tested on 8.x — no libfreetype needed)
    pip3 install Pillow
"""

import subprocess, sys, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Paths ────────────────────────────────────────────────────────────────────
HERE    = Path(__file__).parent          # stingers/
ROOT    = HERE.parent                    # repo root
BANNERS = ROOT / "static" / "img" / "banners"
IMGS    = ROOT / "static" / "images"
OUT     = HERE
WORK    = HERE / "_work"

W, H, FPS = 1920, 1080, 30

# ─── Blog keywords to flash ───────────────────────────────────────────────────
KEYWORDS = [
    "OVN", "Kubernetes", "Networking", "Virtualization",
    "CoreOS", "Automation", "Security", "Ansible",
    "RHACM", "Operators", "etcd", "Prometheus",
    "OpenShift", "Hybrid Cloud", "kubeconfig",
]

# ─── Source images (priority order) ──────────────────────────────────────────
PREFERRED = [
    IMGS    / "cat-loves-ovn.png",
    IMGS    / "debug-sts-banner.jpg",
    IMGS    / "ovn-recon.png",
    IMGS    / "machineconfigs-butane.png",
    IMGS    / "cnv-vm-1.png",
    IMGS    / "cnv-trunk-1.png",
    IMGS    / "layering-cake-trans.png",
    IMGS    / "keda-dashboard-metrics.png",
    BANNERS / "banner-7.jpg",
    BANNERS / "banner-18.jpg",
    BANNERS / "banner-30.jpg",
    BANNERS / "banner-42.jpg",
    BANNERS / "banner-3.jpg",
]
# SRCS = [str(p) for p in PREFERRED.random(3) if p.exists()]
import random
existing = [p for p in PREFERRED if p.exists()]
random.shuffle(existing)
SRCS = [str(p) for p in existing]

# ─── Fonts ────────────────────────────────────────────────────────────────────
def _find(*paths):
    for p in paths:
        if Path(p).exists():
            return p
    sys.exit(f"No font found among: {paths}")

FONT_DISPLAY_PATH = _find(
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
FONT_MONO_PATH = _find(
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
BLACK   = (0x00, 0x00, 0x00)
DARK_BG = (0x06, 0x06, 0x0e)


def rgba(rgb, a=255):
    return (*rgb, a)

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
    # Draw multiple times at slight offsets for thicker glow
    for dx in range(-2, 3, 2):
        for dy in range(-1, 2, 2):
            gd.text((x + dx, y + dy), text, font=font,
                    fill=(*glow_color, glow_alpha))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    img.alpha_composite(glow_layer)
    draw.text((x, y), text, font=font, fill=fill_color)


def render_keyword_overlay(keywords, out_path):
    """
    Place keyword tags in the four corners (and extra along right edge).
    Returns the image (also saves to out_path).
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = make_font(FONT_MONO_PATH, 46)
    margin = 55

    positions = [
        # (x_side, y_side)  — 'r' means right-align
        ("left",  "top"),
        ("right", "top"),
        ("left",  "bottom"),
        ("right", "bottom"),
    ]

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
    return img


def render_title_overlay(big_text, sub_text, tag_line, out_path):
    """
    Render the full title card overlay (transparent background).
    - big_text  : e.g. "GUI FREE LIFE"  — Impact, very large, cyan with magenta glow
    - sub_text  : e.g. "guifreelife.com" — mono, green
    - tag_line  : e.g. "openshift • kubernetes • …" — mono, dim white
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Main title ---
    font_big = make_font(FONT_DISPLAY_PATH, 180)
    tw, th = text_size(draw, big_text, font_big)
    tx = (W - tw) // 2
    ty = (H - th) // 2 - 40

    # Dark box behind title
    pad = 18
    box_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box_layer)
    bd.rectangle([tx - pad, ty - pad, tx + tw + pad, ty + th + pad],
                 fill=(0, 0, 0, 140))
    img.alpha_composite(box_layer)
    draw = ImageDraw.Draw(img)  # refresh after composite

    # Magenta offset shadow (glitch-style: only horizontal)
    draw.text((tx + 8, ty), big_text, font=font_big, fill=rgba(MAGENTA, 160))

    # Main cyan text with strong glow
    glow_text(img, draw, tx, ty, big_text, font_big,
              fill_color=rgba(CYAN, 255),
              glow_color=CYAN,
              glow_radius=16, glow_alpha=120)

    draw = ImageDraw.Draw(img)

    # --- Sub text (URL) ---
    font_sub = make_font(FONT_MONO_PATH, 60)
    sw, sh = text_size(draw, sub_text, font_sub)
    sx = (W - sw) // 2
    sy = ty + th + 30

    glow_text(img, draw, sx, sy, sub_text, font_sub,
              fill_color=rgba(GREEN, 230),
              glow_color=GREEN,
              glow_radius=8, glow_alpha=90)

    draw = ImageDraw.Draw(img)

    # --- Tag footer ---
    font_tag = make_font(FONT_MONO_PATH, 36)
    tgw, tgh = text_size(draw, tag_line, font_tag)
    tgx = (W - tgw) // 2
    tgy = H - tgh - 55
    draw.text((tgx, tgy), tag_line, font=font_tag, fill=rgba(WHITE, 80))

    img.save(str(out_path), "PNG")
    return img


def render_noise_overlay(keywords, out_path):
    """Matrix-green terminal-style keywords for the noise scene."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = make_font(FONT_MONO_PATH, 70)
    n = min(len(keywords), 5)
    step = H // (n + 1)

    for i, kw in enumerate(keywords[:n]):
        label = f"$ {kw.upper()}_"
        y = step * (i + 1) - 35

        glow_text(img, draw, 60, y, label, font,
                  fill_color=rgba(GREEN, 230),
                  glow_color=GREEN,
                  glow_radius=8, glow_alpha=100)
        draw = ImageDraw.Draw(img)

    # Ghost of main title (low alpha)
    font_ghost = make_font(FONT_DISPLAY_PATH, 120)
    gtw, gth = text_size(draw, "GUI FREE LIFE", font_ghost)
    gx = (W - gtw) // 2
    gy = (H - gth) // 2
    draw.text((gx, gy), "GUI FREE LIFE", font=font_ghost,
              fill=rgba(CYAN, 35))

    img.save(str(out_path), "PNG")
    return img


def render_glitch_title_overlay(out_path):
    """Big glitchy 'GUI FREE LIFE' with extra cyan/magenta split offset."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_big = make_font(FONT_DISPLAY_PATH, 180)
    text = "GUI FREE LIFE"
    tw, th = text_size(draw, text, font_big)
    tx = (W - tw) // 2
    ty = (H - th) // 2 - 40

    # Wide spread glow
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.text((tx, ty), text, font=font_big, fill=rgba(CYAN, 100))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=24))
    img.alpha_composite(glow_layer)
    draw = ImageDraw.Draw(img)

    # Hard magenta right-offset
    draw.text((tx + 14, ty), text, font=font_big, fill=rgba(MAGENTA, 200))
    # Main cyan
    draw.text((tx, ty), text, font=font_big, fill=rgba(CYAN, 255))

    # Sub
    font_sub = make_font(FONT_MONO_PATH, 60)
    sub = "guifreelife.com"
    sw, sh = text_size(draw, sub, font_sub)
    sx = (W - sw) // 2
    sy = ty + th + 28
    glow_text(img, draw, sx, sy, sub, font_sub,
              fill_color=rgba(GREEN, 235),
              glow_color=GREEN, glow_radius=8, glow_alpha=90)

    draw = ImageDraw.Draw(img)
    tag = "openshift  •  kubernetes  •  networking  •  automation"
    font_tag = make_font(FONT_MONO_PATH, 36)
    tgw, _ = text_size(draw, tag, font_tag)
    draw.text(((W - tgw) // 2, H - 65), tag, font=font_tag,
              fill=rgba(WHITE, 75))

    img.save(str(out_path), "PNG")
    return img

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


# Animated chromatic aberration via geq (T = time in seconds)
def chroma_geq(strength=6):
    s = strength
    return (
        f"geq="
        f"r='r(X+{s}*sin(T*17),Y+2*cos(T*9))':"
        f"g='g(X,Y)':"
        f"b='b(X-{s}*cos(T*13),Y-2*sin(T*11))'"
    )

# CRT scan lines — cosine wave, 3-pixel period
SCANLINES = (
    "geq="
    "lum='lum(X,Y)*(0.55+0.45*cos(Y*PI/1.5))':"
    "cb='cb(X,Y)':"
    "cr='cr(X,Y)'"
)

# Horizontal glitch stripe that drifts vertically
def glitch_stripe():
    return (
        "geq="
        "lum='lum(X,Y)+if(between(Y,floor(500+300*sin(T*29)),floor(516+300*sin(T*29))),random(1)*90,0)':"
        "cb='cb(X,Y)':"
        "cr='cr(X,Y)'"
    )


def base_glitch_chain(noise=18, chroma=5):
    """Return filter chain applied to the base video track."""
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
    """
    Glitched still-image segment with a Pillow-rendered text overlay.
    Uses filter_complex: glitch the image, then overlay the text PNG.
    """
    glitch = base_glitch_chain(noise=noise, chroma=chroma)
    fc = f"[0:v]{glitch}[v];[v][1:v]overlay=0:0[out]"

    run([
        "-loop", "1", "-i", img_path,
        "-loop", "1", "-i", str(overlay_png),
        "-filter_complex", fc,
        "-map", "[out]",
        "-t", str(dur), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ], f"img({Path(img_path).name}) → {out.name}")


def seg_from_color(bg_color, overlay_png, dur, out,
                   noise=60, chroma=8, extra_filters=""):
    """
    Color-source segment (noise bursts, title card) with text overlay.
    bg_color: ffmpeg color string e.g. '0x0a1a14'
    """
    base = f"color={bg_color}:s={W}x{H}:r={FPS}"
    glitch = ",".join(filter(None, [
        f"noise=alls={noise}:allf=t",
        "colorchannelmixer=rr=0.04:gg=0.28:bb=0.22" if "0a1a14" in bg_color else None,
        "eq=contrast=2.2:brightness=0.05" if "0a1a14" in bg_color else None,
        chroma_geq(chroma),
        SCANLINES,
        glitch_stripe(),
        "vignette=PI/2.8",
        extra_filters or None,
    ]))
    fc = f"[0:v]{glitch}[v];[v][1:v]overlay=0:0[out]"

    run([
        "-f", "lavfi", "-i", base,
        "-loop", "1", "-i", str(overlay_png),
        "-filter_complex", fc,
        "-map", "[out]",
        "-t", str(dur), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ], f"color({bg_color}) → {out.name}")


def seg_blackout(dur, out):
    """Flash-to-black end cap with big chromatic glitch burst."""
    fc = (
        f"[0:v]noise=alls=12:allf=t,"
        f"geq=r='r(X+20*sin(T*80),Y)':g='g(X,Y)':b='b(X-20*cos(T*70),Y)'[out]"
    )
    run([
        "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}",
        "-filter_complex", fc,
        "-map", "[out]",
        "-t", str(dur), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ], f"blackout → {out.name}")

# ─── Audio synthesis ──────────────────────────────────────────────────────────

def make_audio(dur, bpm=140):
    """Synthesise an electro beat via ffmpeg aevalsrc. Returns path to .wav."""
    out = WORK / "audio.wav"
    b = 60.0 / bpm        # quarter note
    s = b / 4.0           # 16th note
    e = b / 2.0           # 8th note

    kick  = f"0.85*sin(2*PI*t*75)*exp(-50*mod(t,{b:.4f}))*lt(mod(t,{b:.4f}),0.07)"
    snare = (
        f"0.55*(2*random(floor((t+{b/2:.4f})/{b:.4f}))-1)"
        f"*exp(-90*mod(t+{b/2:.4f},{b:.4f}))"
        f"*lt(mod(t+{b/2:.4f},{b:.4f}),0.04)"
    )
    hat = (
        f"0.18*(2*random(floor(t/{e:.4f})+7)-1)"
        f"*exp(-400*mod(t,{e:.4f}))"
        f"*lt(mod(t,{e:.4f}),0.012)"
    )
    # Synth arp: C5→E5→G5→B5 cycling on 16ths
    arp = "+".join(
        f"0.28*sin(2*PI*t*{f})"
        f"*exp(-18*mod(t,{s:.4f}))"
        f"*lt(mod(t,{s:.4f}),{s*0.65:.4f})"
        f"*eq(mod(floor(t/{s:.4f}),4),{i})"
        for i, f in enumerate([523, 659, 784, 988])
    )
    bass = f"0.4*sin(2*PI*t*55)*exp(-6*mod(t,{b:.4f}))*lt(mod(t,{b:.4f}),{b*0.6:.4f})"

    expr = f"({kick}+{snare}+{hat}+{arp}+{bass})*0.65"
    run([
        "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100",
        "-t", str(dur), "-ar", "44100", "-ac", "1",
        str(out),
    ], "audio synthesis")
    return str(out)

# ─── Concat + mux ─────────────────────────────────────────────────────────────

def concat_and_mux(segments, audio_path, out_path):
    cf = WORK / "concat_list.txt"
    cf.write_text(
        "\n".join(f"file '{Path(s).resolve()}'" for s in segments) + "\n"
    )
    tmp = WORK / "concat_raw.mp4"
    run([
        "-f", "concat", "-safe", "0", "-i", str(cf),
        "-c", "copy", str(tmp),
    ], "concat segments")
    run([
        "-i", str(tmp), "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out_path),
    ], f"mux → {out_path.name}")

# ─── Stinger builders ─────────────────────────────────────────────────────────

def build_5s():
    print("\n▶  5-second stinger")
    if not SRCS:
        sys.exit("  ✗  no source images found")

    imgs = SRCS
    segs = []

    # 0: noise burst (0.45s) — matrix terminals flicker
    ov = WORK / "ov_noise.png"
    render_noise_overlay(KEYWORDS[:5], ov)
    p  = WORK / "5s_00_noise.mp4"
    seg_from_color("0x0a1a14", ov, 0.45, p, noise=95, chroma=9)
    segs.append(str(p))

    # 1: OVN / networking image (0.7s)
    ov = WORK / "ov_net.png"
    render_keyword_overlay(["OVN", "Networking", "OpenShift", "RHACM"], ov)
    p  = WORK / "5s_01.mp4"
    seg_from_image(imgs[0], ov, 0.7, p, noise=22, chroma=7)
    segs.append(str(p))

    # 2: Virtualization / CoreOS image (0.65s)
    ov = WORK / "ov_virt.png"
    render_keyword_overlay(["Kubernetes", "Virtualization", "CoreOS", "Operators"], ov)
    p  = WORK / "5s_02.mp4"
    seg_from_image(imgs[min(1, len(imgs)-1)], ov, 0.65, p, noise=16, chroma=4)
    segs.append(str(p))

    # 3: Automation / security — title emerges (0.8s)
    ov = WORK / "ov_auto.png"
    render_title_overlay("GUI FREE LIFE", "guifreelife.com",
                         "Automation  •  Security  •  RHACM", ov)
    p  = WORK / "5s_03.mp4"
    seg_from_image(imgs[min(2, len(imgs)-1)], ov, 0.8, p, noise=20, chroma=9)
    segs.append(str(p))

    # 4: Banner image (0.6s)
    ov = WORK / "ov_banner.png"
    render_keyword_overlay(["Ansible", "etcd", "Prometheus", "Hybrid Cloud"], ov)
    p  = WORK / "5s_04.mp4"
    seg_from_image(imgs[min(5, len(imgs)-1)], ov, 0.6, p, noise=25, chroma=6)
    segs.append(str(p))

    # 5: Title card (1.8s) — the money shot
    ov = WORK / "ov_title.png"
    render_glitch_title_overlay(ov)
    p  = WORK / "5s_05_title.mp4"
    seg_from_color("0x06060e", ov, 1.8, p, noise=14, chroma=10)
    segs.append(str(p))

    # 6: Blackout (0.35s)
    p = WORK / "5s_06_black.mp4"
    seg_blackout(0.35, p)
    segs.append(str(p))

    audio = make_audio(5.35, bpm=140)
    out   = OUT / "stinger_5s.mp4"
    concat_and_mux(segs, audio, out)
    print(f"  ✓  {out}")


def build_1s():
    print("\n▶  1-second stinger")
    if not SRCS:
        return

    imgs = SRCS
    segs = []

    # 0: static flash (0.1s)
    ov = WORK / "1s_ov_noise.png"
    render_noise_overlay(KEYWORDS[:2], ov)
    p  = WORK / "1s_00_noise.mp4"
    seg_from_color("0x0a1a14", ov, 0.1, p, noise=95, chroma=9)
    segs.append(str(p))

    # 1: image + bold title (0.55s)
    ov = WORK / "1s_ov_img.png"
    render_title_overlay("GUI FREE LIFE", "guifreelife.com",
                         "OpenShift  •  Kubernetes  •  Networking", ov)
    p  = WORK / "1s_01.mp4"
    seg_from_image(imgs[0], ov, 0.55, p, noise=28, chroma=12)
    segs.append(str(p))

    # 2: title slam (0.35s)
    ov = WORK / "1s_ov_title.png"
    render_glitch_title_overlay(ov)
    p  = WORK / "1s_02_title.mp4"
    seg_from_color("0x06060e", ov, 0.35, p, noise=14, chroma=15)
    segs.append(str(p))

    audio = make_audio(1.0, bpm=140)
    out   = OUT / "stinger_1s.mp4"
    concat_and_mux(segs, audio, out)
    print(f"  ✓  {out}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("═" * 50)
    print("  GUI Free Life — Stinger Generator")
    print("═" * 50)

    if not shutil.which("ffmpeg"):
        sys.exit("ERROR: ffmpeg not found in PATH")

    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    print(f"  images  : {len(SRCS)}")
    print(f"  display : {FONT_DISPLAY_PATH}")
    print(f"  mono    : {FONT_MONO_PATH}")

    build_5s()
    build_1s()

    shutil.rmtree(WORK, ignore_errors=True)

    print("\n  Done.")
    print("  → stingers/stinger_5s.mp4  (5-second promo)")
    print("  → stingers/stinger_1s.mp4  (1-second bumper)")


if __name__ == "__main__":
    main()
