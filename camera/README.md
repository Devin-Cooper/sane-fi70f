# `camera/` — fi-70F B&W camera-back processing

Post-capture tools for the fi-70F used as a **monochrome scanning back**. They consume the
`scanimage --mode Sub-exposures` output (a 16-bit RGB image whose R/G/B channels are the three
LED-strobed sub-exposures at integration times **2194 / 733 / 1463**) and produce enhanced B&W.

- **`pnm.py`** — 16-bit PNM/PGM I/O (PIL mishandles 16-bit P6).
- **`subframes.py`** — shared foundation: load + split the three sub-exposures, per-plane black
  estimation (dark frame or percentile), and sub-pixel FFT registration. Reused by the HDR merge
  and (later) the Y-super-resolution and multi-scan super-resolution tools.
- **`hdr.py`** — HDR merge (issue #2): radiometric alignment (÷ integration time) + a
  saturation-aware weighted merge → a single **16-bit linear** grayscale.
- **`cli.py`** — command-line entry point.

## Merge HDR

```
scanimage -d "$DEV" --mode Sub-exposures --resolution 300 --format=pnm > scan.ppm
python3 -m camera.cli merge-hdr scan.ppm out.pgm --exposures 2194,733,1463 [--dark dark.ppm] [--preview out.png]
```

- **Output is 16-bit linear radiance** (PGM). Use `--preview` for a tone-mapped 8-bit PNG to eyeball;
  the PGM is the scientific artifact.
- `--dark` is a lens-capped lamp-off scan used for accurate per-plane black subtraction (dark current
  is exposure-dependent). Without it, a low percentile of each plane is used.
- `--exposures` matches the capture; **exposure control (#4)** can widen the bracket and this tool
  uses whatever ratio you pass.

## Dynamic-range expectation

The **native** bracket is only `2194:733 = 3:1 ≈ 1.58 stops`, so the native merge extends dynamic
range by ~1.5 stops (≈ 9.5 effective bits) plus a mid-tone SNR gain from overlap averaging — **not**
10–11 bits. Reaching 2–3 stops beyond 8-bit needs a **wider bracket via exposure control (#4)**
(e.g. 1:4:16 ≈ 4 stops); the merge is ratio-agnostic, so #4 amplifies it directly.

## Tests

```
python3 -m pytest camera -q
```

Unit tests run entirely on synthetic brackets (no hardware). The real dynamic-range-in-stops number
is measured on a step-wedge / high-dynamic-range scene under lamp-off broadband light (or the lens
rig), once the exposure bracket is confirmed.

## Y super-resolution

```
python3 -m camera.cli superres scan.ppm out.pgm [--factor 2] [--sigma 0.45] [--iters 15] [--baseline]
```

Reconstructs a **Y-only** higher-resolution grayscale (`--factor`× taller, default 2×) from the three
sub-pixel-Y-shifted sub-frames by iterative back-projection with a Gaussian sensor line-spread
(`--sigma`, native px). X is untouched (it's at the 600 dpi optical limit). `--baseline` gives the
non-uniform interpolation reconstructor for comparison.

**Status (be honest about it):** on *synthetic* data with a known LSF, IBP raises the slanted-edge
Y-MTF50 by ~1.2–1.3× over both a single upsampled plane and the interpolation baseline — real
deconvolved detail, not upscaling. On *real* fi-70F scans of the Gray-code target, **no significant
Y-MTF gain is measured (~1.0×)**: that target has no fine near-Nyquist Y detail to reveal
super-resolution, the sub-pixel offsets are clustered (0 / −0.25 / −0.73 ≈ ~2 effective samples), and
the short-exposure planes are noisier than the reference. A definitive hardware test needs a
resolution target (line-pairs / USAF) and, ideally, a measured sensor LSF for `--sigma`.
