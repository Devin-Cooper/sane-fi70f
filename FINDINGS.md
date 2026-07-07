# Ricoh / Fujitsu fi-70F on SANE (epjitsu) — reverse-engineering findings

Status: **first working colour scans of the fi-70F on Linux.** Geometry (read path +
descramble) is solved and hardware-verified; calibration is bright and correct except for a
residual per-channel colour cast (see *Open issues*). Everything below is verified against real
hardware (a fi-70F on firmware `0000`) and, where noted, against a USBPcap trace of the Windows
PaperStream driver.

Tracking issue: <https://gitlab.com/sane-project/backends/-/issues/833>

---

## TL;DR — the one thing that mattered

The fi-70F closes **every 87-line scan block with an 8-byte trailer** (`02 <len:3> 00 00 80 00`),
so each device block is `87 × 6000 + 8 = 522008` bytes. The driver must **strip that trailer**.

We originally believed the opposite ("no 8-byte trailer on this device") and left the trailers
inline in the image buffer. Because we buffer the whole page as one transfer, ~20 trailers ended
up embedded in the raw data, shifting every block 8 bytes late. That accumulating 8-byte/block
error *looked* like a mysterious **per-block horizontal "drift"** (~one head-width rotation per
block), which we then "corrected" with an empirical per-block circular shift
(`shift = 939 + 429.75·block`). It fit the data but was a curve-fit to a bug.

**Strip the trailer and the drift vanishes** (measured per-block jump: `430.374 px → 0.008 px`).
The descramble then collapses to a plain **fixed per-line permutation** — exactly like `canon_dr`'s
3-head `COLOR_INTERLACE` modes — with a single constant offset and no per-block term at all.

Lesson (courtesy of a prior-art pass over the SANE tree): *no* production backend descrambles a
segmented sensor with a line- or block-dependent shift. If you find yourself needing one, suspect
the byte framing first.

---

## Device overview

- USB `05ca:0308`, firmware-upload device. Firmware blob is `Comp70fFirmFile` (an `NDL1` blob)
  from the PaperStream IP package. Two revisions seen in the wild: `70f_0000.nal` (this unit) and
  `70f_0A00.nal` (@tete17's unit). Config: `firmware .../70f_0000.nal` + `usb 0x05ca 0x0308` in
  `epjitsu.conf`.
- 3-segment CIS sensor (three read-heads), 300 dpi, flatbed, colour.
- Belongs in the **epjitsu** backend (with the fi-60F/fi-65F), not fujitsu — per @kitno455.

## Read path (`read_from_scanner`, `sane_read`)

The fi-70F **free-runs** the whole page from a single `0x1B 0xD2` with no inter-block pacing.
Reading it in the normal per-block cadence (read → descramble → read) starves/overruns its FIFO
and stalls the carriage after ~1 block ("reading slower gets more lines" is the classic tell).
What makes a full page stream end-to-end:

1. **Buffer the whole page as ONE block** — `block_img.height = fullscan.height`; run descramble
   once at the end. Removes the read→descramble→read gaps.
2. **Request `0xFE00` (65024) bytes per bulk-IN** (matches Windows); don't clamp the request to
   the block remainder (a partial request stalls the pipe — same as the S1300i).
3. **Strip the 8-byte per-block trailer.** Each device block is `522008` bytes = `87×6000` image
   bytes + an 8-byte trailer. We track the device-stream position (`dev_pos`) and copy image bytes
   only, so a trailer split across a 65024-byte read is handled correctly.
4. **Keep the captured SET_WINDOW `ypix = 0x6d8` (1752, 8-aligned)**; overwriting it with the real
   scan height (1749, not a multiple of 8) also stalls after ~1 block.

Confirmed against the trace: 20 device blocks of `522008` + a final partial, no commands
mid-stream.

## Descramble (`descramble_raw`, `MODEL_FI70F`, main scan)

After the trailer is stripped, each raw 6000-byte line descrambles by a **fixed permutation**:

- 3 colour planes at byte offsets **68 / 2258 / 4448** (plane stride **2190**), plane width **433**.
- Within a plane the 3 heads are **byte-interleaved**: head *i*, pixel *k* = `plane[k*3 + i]`.
- Tile the heads `[h0 | h1 | h2]` → **1299** px, stack the 3 planes → RGB, **mirror** horizontally,
  then rotate by a **single constant offset** (`FI70F_SHIFT_S0 = 939`) to place the paper edge.
- **No per-block term.** (The old `+429.75·block` was the trailer artifact — see TL;DR.)

Verification: on a trailer-stripped capture the per-block boundary jump is `0.008 px` and a
position-encoded chirp target reconstructs with straight, continuous vertical bars top-to-bottom.

### Seams / dead pixels

Each head has exactly **24 masked pixels at its leading edge** (head-pixel 0..23 read a hard `0`;
pixel 24 jumps to full scale; the trailing edge has **none**). After descramble these land as 3
now-**stationary** dark seams. Two ways to handle them:

- **Interpolate** the 24 px per head (current backend: `FI70F_DEAD_LEAD=24`, `FI70F_DEAD_TRAIL=0`).
  Keeps the 1299-px width; blurs ~24 px of content where a seam crosses a line.
- **Crop** the 24 masked px per head and butt the heads → **1240 px**, which is exactly what the
  Windows driver outputs (1240 = 3 × ~413). Seamless, no invented pixels. *Recommended, not yet
  implemented here.*

## Calibration

- Brightness pipeline = coarse (analog) gain → fine (per-pixel) gain → LUT. Exposure is baked into
  the SET_WINDOW blob; the per-channel integration constants (`2194 / 733 / 1463`) come from the
  device's `0x1B 0xC7` response.
- **Coarse-gain target must be raised for the fi-70F.** The shared fi-60F default (88/92) leaves
  the fi-70F's weaker CIS near-black with a cyan cast. Raising it (`FI70F_COARSE_GAIN_MIN/MAX =
  150/160`) yields a bright, correct, cyan-free *white/black* response. This is gated to
  `MODEL_FI70F`; other models are untouched.
- The hardware 2-point fine-cal can't measure a slope here (the cal window is blind to the fine
  gain), so fine gain is held at maximum.

## Open issues

1. **Residual cyan cast (per-channel *nonlinear* response).** Blacks are true 0 and whites are
   ~neutral, but the **red channel under-responds through the midtones** (mid-gray reads
   ≈ R86 / G145 / B157). Measured proof that this is *not* fixable by per-channel gain or 2-point
   white/black anchoring (R stays ~60 below G after correction) — it needs a **per-channel tone
   LUT** built from a reliable grayscale/step reference. A clean calibration target + software LUT
   is the planned fix.
2. **Crop to 1240** to match Windows exactly (removes the seam-interpolation blur).

## Method notes / credits

- The protocol was cross-checked against a USBPcap trace of the Windows PaperStream driver
  (the trailer, the `0xC7`/`0xC6`/`0xC3`/`0xC4`/`0xC5` cal sequence, the 1240-px output width).
- Prior-art pass over the SANE tree (`genesys` segment model, `canon_dr` `COLOR_INTERLACE_2510`,
  `pixma` reorder) confirmed the fixed-permutation model and the "index by absolute stream
  position, never by transfer block" rule.
- Complementary work by **@tete17**, who built a `MODEL_FI70F` on the `0A00` firmware and was
  blocked on exactly the carriage-stop this read path fixes.
- Reverse-engineering and write-up done with heavy assistance from **Claude (Anthropic)**; every
  finding here is verified on real hardware.
