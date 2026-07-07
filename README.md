# sane-fi70f — Ricoh/Fujitsu fi-70F support for the SANE `epjitsu` backend

Work-in-progress support for the **Ricoh/Fujitsu fi-70F** flatbed scanner (USB `05ca:0308`) in
the SANE `epjitsu` backend. This repository holds our patch, the full modified backend, the
reverse-engineering write-up, and proof images.

This is the **first working colour scan of the fi-70F on Linux.** Read path and descramble
geometry are solved and hardware-verified; calibration is bright and correct apart from a
residual per-channel colour cast.

Upstream tracking issue: **[sane-project/backends#833](https://gitlab.com/sane-project/backends/-/issues/833)**

## Status

| Area | State |
|---|---|
| Firmware upload, detection | ✅ works |
| Full-page scan (read path) | ✅ works — free-running page, strip the 8-byte per-block trailer |
| Descramble geometry | ✅ solved — fixed permutation, **no drift** (per-block jump 0.008 px) |
| Coarse (analog) calibration | ✅ fi-70F-specific gain target (bright, no gross cast) |
| Seam / dead-pixel handling | ⚠️ interpolated (24 masked px/head); crop-to-1240 planned |
| Per-channel colour cast | ⬜ open — red under-responds in midtones; needs a tone LUT |

See **[FINDINGS.md](FINDINGS.md)** for the full technical story, including the root-cause
(the 8-byte block trailer) that made an apparent per-block "drift" disappear.

## What's here

- `backend/epjitsu.c`, `backend/epjitsu.h` — the full modified backend (against
  `sane-project/backends` @ `ca8d120`).
- `fi70f-epjitsu.patch` — the diff only, for applying onto an upstream checkout.
- `images/` — before/after proof (drift symptom, geometry fixed, colour before/after).

## Build & use

```sh
git clone https://gitlab.com/sane-project/backends.git
cd backends
git checkout ca8d120
git apply /path/to/fi70f-epjitsu.patch      # or copy backend/epjitsu.{c,h} over
./configure && make -C backend libepjitsu_la-epjitsu.lo && make && sudo make install
```

Extract the firmware `Comp70fFirmFile` (an `NDL1` blob) from the PaperStream IP package, rename it
`70f_0000.nal` (or `70f_0A00.nal` to match your firmware revision), drop it in the epjitsu firmware
dir, and add to `epjitsu.conf`:

```
firmware /usr/share/sane/epjitsu/70f_0000.nal
usb 0x05ca 0x0308
```

Then `scanimage -d "epjitsu:libusb:BBB:DDD" --mode Color --resolution 300 --format=pnm > scan.pnm`.

## Before / after

The apparent per-block "drift" (3 jagged dark seam bars marching across the page) was entirely the
un-stripped 8-byte block trailer. Strip it and the seams stand still:

| Drift symptom (trailer left in) | Geometry fixed (trailer stripped) |
|---|---|
| ![](images/01-drift-symptom-seam-bars.png) | ![](images/02-geometry-fixed.png) |

## Credits

Reverse-engineered by **Devin Cooper** with heavy assistance from **Claude (Anthropic)**;
complementary to **@tete17**'s `0A00`-firmware work on issue #833. All findings verified on real
hardware. Not affiliated with or endorsed by Ricoh/Fujitsu or the SANE project.
