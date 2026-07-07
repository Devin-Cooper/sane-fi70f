# Ricoh / Fujitsu fi-70F on SANE (epjitsu) — reverse-engineering findings

Status: **full, gap-free, correctly-calibrated colour scans of the fi-70F on Linux.** Read path,
descramble geometry, and the calibration operating point are all solved and hardware-verified
against the Windows PaperStream output. The only remaining difference from Windows is the output
**tone curve** (gamma), which is a SANE-appropriate, user-adjustable choice — see *Remaining
difference*. Everything below is verified on real hardware (a fi-70F on firmware `0000`) and, where
noted, against a USBPcap trace of the Windows driver plus a purpose-built self-decoding target.

Tracking issue: <https://gitlab.com/sane-project/backends/-/issues/833>

> **2026-07-07 update.** An earlier iteration of this document described the descramble as 3 heads
> of **433** px at plane offsets **68/2258/4448** with a constant rotation `SHIFT_S0=939` and 24
> interpolated "dead" pixels per head. **That was wrong** (it left ~2 seam gaps / a blurred seam).
> Using a self-decoding Gray-code target as an oracle, the true geometry is now solved and the
> seams are gap-free with no interpolation — details below. The read-path / trailer story is
> unchanged and still correct.

---

## How it was verified (the oracle)

We printed a **self-decoding target**: the top band is a 9-track **Gray-code absolute-position
encoder** — every output column encodes its own true X (`pos p = (x−90)/4`, 265 positions). Below
it are neutral-gray and per-channel step wedges. Because every column self-identifies, the scan is
its own ruler:

- **Descramble is correct ⟺ decoding the 9 tracks down each output column yields a continuous
  `0…264` ramp with no jumps.** A seam gap shows up as a jump in the ramp.
- **Colour is correct ⟺ the neutral wedge reads `R≈G≈B`.**

Ground truth is the Windows PaperStream scan of the same physical target (a lossless 1240×1748
image), plus its cold-start USBPcap. We also captured our own scan's raw over `usbmon` and confirmed
it is **byte-structurally identical** to the Windows raw — so *emission was never the problem*; both
descramble to a flat white (ours σ≈5.7, Windows σ≈4.5 across columns).

---

## TL;DR #1 (read path) — strip the 8-byte block trailer

The fi-70F closes **every 87-line scan block with an 8-byte trailer** (`02 <len:3> 00 00 80 00`),
so each device block is `87 × 6000 + 8 = 522008` bytes. The driver must **strip that trailer**.

Leaving it inline (we originally believed "no trailer on this device") embeds ~20 trailers in the
raw buffer, shifting every block 8 bytes late — which *looked* like a per-block horizontal "drift"
we once curve-fit with `shift = 939 + 429.75·block`. Strip the trailer and the drift vanishes
(measured per-block jump `430.374 px → 0.008 px`); the descramble becomes a plain fixed per-line
permutation. *Lesson: index by absolute device-stream position, never by transfer block.*

## TL;DR #2 (geometry) — 3 heads of 432, tiled with no dead pixels

The "seam gaps" were **not** an emission or calibration problem — they were a descramble bug:
plane offset `+68` and head width `409/433` were both wrong. `68/3` is **non-integer**, so the
`+68` "dead-lead" *misaligned the 3-way byte interleave*; and 409 truncated exactly the head-edge
pixels that fill the seams. With the correct geometry the three heads tile continuously.

## TL;DR #3 (colour) — match Windows' coarse operating point, not just the fine-cal

The cyan cast is set by the **coarse (analog) operating point**. Windows converges to *per-channel*
gains `0x37/0x35/0x34` and offsets `0x22/0x23/0x21`; the old code forced a single shared gain at the
wrong target, so red stayed under-gained. Sending Windows' converged c6 verbatim + a real per-pixel
fine-cal table makes the neutral wedge neutral.

---

## Device overview

- USB `05ca:0308`, firmware-upload device (`Comp70fFirmFile`, an `NDL1` blob, from PaperStream IP).
  Revisions seen: `70f_0000.nal` (this unit) and `70f_0A00.nal` (@tete17's). Config:
  `firmware .../70f_0000.nal` + `usb 0x05ca 0x0308`.
- 3-read-head CIS sensor, 300 dpi, colour. Belongs in **epjitsu** (with fi-60F/fi-65F), not fujitsu.

## Read path (`read_from_scanner`, `sane_read`)

The fi-70F **free-runs** the whole page from a single `0x1B 0xD2` with no inter-block pacing.
What makes a full page stream end-to-end:

1. **Buffer the whole page as ONE block** (`block_img.height = fullscan.height`); descramble once.
2. **Request `0xFE00` (65024) bytes per bulk-IN**; don't clamp to the block remainder.
3. **Strip the 8-byte per-block trailer** (`522008 = 87×6000 + 8`), tracking device-stream position
   (`dev_pos`) so a trailer split across a read is handled correctly.
4. **Keep the captured SET_WINDOW `ypix = 0x6d8` (1752, 8-aligned)**.

## Descramble (`descramble_raw`, `MODEL_FI70F`, main scan) — SOLVED

Each raw 6000-byte line is 3 colour planes at byte offsets **0 / 2190 / 4380** (plane stride 2190).
Within a plane the 3 read-heads are **byte-interleaved**: head *h*, pixel *k* = `plane[k*3 + h]`,
each head **432** px wide (`432 × 3 = 1296` bytes/plane). The heads tile (horizontally mirrored)
into the **1240-px** output; output column *x* reads:

| output column x | head (interleave) | in-head pixel |
|---|---|---|
| `x ≤ 402` | 2 | `402 − x` |
| `403 ≤ x ≤ 834` | 1 | `834 − x` |
| `x ≥ 835` | 0 | `1265 − x` |

with byte `= pixel*3 + interleave`, and `R = plane0[byte]`, `G = plane1[byte]`, `B = plane2[byte]`.
The heads tile at pitch 432 with ~1 px overlap — **no rotation, no dead-lead skip, no interpolation.**
(The derivation: correlate each golden column's full vertical profile against every raw byte-column
→ an assumption-free raw→output map at corr 0.95–0.98; it collapses to the table above. This matches
@tete17's independent `3×432 → 1296` segment model.)

**Verification:** decoding the encoder over a fresh Linux scan gives **265/265 positions, zero ramp
jumps** (continuous `0…264`), row-aligned to the Windows golden at per-column corr ≈ 0.95. The old
409/433 geometry left ~2 seam gaps.

## Calibration — coarse operating point + per-pixel fine-cal

The brightness pipeline is coarse (analog gain/offset/exposure via the `0x1B 0xC6` payload) → fine
(per-pixel `[offset,gain]` via `0xC3`/`0xC4`) → LUT (`0xC5`).

- **Coarse:** send the fi-70F's converged operating point verbatim — offset `0x22/0x23/0x21`, gain
  `0x37/0x35/0x34`, exposure `0x0892/0x02dd/0x05b7` (`coarseCalData_FI70F`). These are Windows'
  converged values (traced through its c6 bisection in the USBPcap). The stock epjitsu coarse loop
  drives a *single shared* gain to an average target, which can't reach these per-channel gains —
  that was the real cyan cause, so `coarsecal()` sends the fixed payload for `MODEL_FI70F` instead
  of bisecting.
- **Fine:** a real per-pixel flat-field table (`fineCalData_FI70F`, 2000 px × 3 × 2 B). The built-in
  2-point sweep **pegs red** here — the sensor's red barely responds to the `0xff→0xbf` fine-gain
  probe, so red maxes out still under target and stays under-corrected. The table used is the one
  Windows computes for this sensor (captured from the trace); `finecal()` memcpys it (env
  `FI70F_FINECAL=<file>` / `=compute` override the default for experiments).

**Verification (fresh Linux scan vs the Windows golden):**

| metric | old build | this build | Windows |
|---|---|---|---|
| encoder ramp | ~2 seam gaps | **265/265, 0 jumps** | 265/265 |
| neutral-wedge max channel deviation | ~70 (cyan) | **7.6** | ~3 |
| white uniformity (σ across columns) | — | **3.1** (flat) | 6.9 |

## Remaining difference — tone / gamma (not a defect)

Our midtones read ~37 counts darker and blacks ~11 lighter than the Windows golden (neutral wedge
patch "175": ours ≈ 94 vs Windows ≈ 131; the "0" patch: ours ≈ 14 vs 1). This is the **`0xC5`
gamma LUT**: PaperStream bakes in a contrasty curve (crushed blacks, boosted mids), while SANE's
`send_lut` generates a more linear curve driven by the user's gamma/brightness/contrast options.
Colour balance and geometry match; only the baked-in contrast differs, which is arguably the right
default for SANE. Windows' exact `0xC5` LUT is captured and can be replayed if an identical tone is
ever wanted.

## Method notes / credits

- Cross-checked against a USBPcap trace of Windows PaperStream (trailer; the `0xC7/0xC6/0xC3/0xC4/
  0xC5` cal sequence and c6 convergence; 1240-px output) and a self-decoding Gray-code target.
- **Trust the data, not the render:** every claim here is a number (decoded encoder positions,
  per-channel wedge values, raw byte structure), because rendered images repeatedly misled this
  effort.
- Complementary to **@tete17**'s `0A00`-firmware `MODEL_FI70F`; the `3×432→1296` geometry agrees.
- Reverse-engineering and write-up done with heavy assistance from **Claude (Anthropic)**; every
  finding verified on real hardware.
