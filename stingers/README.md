# GUI Free Life — YouTube Stingers

Glitchy electro-style promotional stingers for the **GUI Free Life** YouTube channel.

## Files

| File | Description |
|---|---|
| `stinger_5s.mp4` | 5-second promo stinger |
| `stinger_1s.mp4` | 1-second bumper / end card |
| `make_stinger.py` | Generator script |

## Regenerating

```bash
python3 stingers/make_stinger.py
```

Requirements:
- `ffmpeg` in PATH (8.x, no libfreetype needed)
- `pip3 install Pillow`

## Visual Structure — 5s Stinger

| Time | Scene | Content |
|---|---|---|
| 0.0–0.45s | Noise burst | Matrix-green terminal text: `$ OVN_`, `$ KUBERNETES_`, etc. on dark static; ghost "GUI FREE LIFE" flickers through |
| 0.45–1.15s | Image 1 | `cat-loves-ovn.png` with `[ OVN ]` `[ NETWORKING ]` `[ OPENSHIFT ]` `[ RHACM ]` in corners |
| 1.15–1.80s | Image 2 | `debug-sts-banner.jpg` with Kubernetes / Virtualization / CoreOS / Operators tags |
| 1.80–2.60s | Image 3 | `ovn-recon.png` with full **GUI FREE LIFE** title overlay |
| 2.60–3.20s | Image 4 | `cnv-trunk-1.png` with Ansible / etcd / Prometheus / Hybrid Cloud tags |
| 3.20–5.00s | Title card | Dark background — **GUI FREE LIFE** in cyan with magenta glitch offset + glow, `guifreelife.com` in green, tag footer |
| 5.00–5.35s | Blackout | Chromatic aberration burst to black |

## Visual Structure — 1s Bumper

| Time | Scene |
|---|---|
| 0.0–0.1s | Static noise flash |
| 0.1–0.65s | Image with full **GUI FREE LIFE** title |
| 0.65–1.0s | Title card slam |

## Glitch Effects

All scenes combine these ffmpeg filters:

- **Animated chromatic aberration** — `geq` shifts the R/B channels independently via `sin(T*N)` expressions, creating a jittery RGB split
- **CRT scan lines** — `geq` cosine wave dims every 3rd row, simulating a phosphor display
- **Horizontal glitch stripe** — a bright noise band drifts vertically via `sin(T*29)`
- **Digital noise** — `noise=alls=N:allf=t` adds per-frame temporal grain
- **Color grading** — boosted contrast/saturation, `colorchannelmixer` leans cyan/teal
- **Vignette** — darkened edges

## Text Rendering

Text is rendered with **Pillow** (not ffmpeg `drawtext`) to avoid a libfreetype dependency:

- **Impact** — channel title, large display text
- **SF Mono** — keyword tags, URL, code-style terminal text
- All text layers have a **Gaussian glow halo** composited beneath the fill
- Magenta horizontal shadow offset on the title gives the split-channel glitch look

## Audio

Synthesised 140 BPM electro beat via ffmpeg `aevalsrc`:

- Kick drum (75 Hz sine with fast exponential decay, on every beat)
- Snare (noise burst on beats 2 & 4)
- Open hi-hat (noise on 8th notes)
- Synth arp (C5 → E5 → G5 → B5 cycling on 16th notes)
- Sub bass (55 Hz, every beat)
