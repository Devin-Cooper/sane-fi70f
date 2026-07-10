"""HDR merge of the three fi-70F sub-exposures into a single 16-bit linear radiance image (#2)."""
import numpy as np
from .subframes import estimate_black, estimate_shifts, register


def radiometric(planes, black, exposures):
    """Per-plane linear scene radiance L_i = (plane_i - black_i) / exposure_i."""
    return [(np.asarray(p) - b) / float(e) for p, b, e in zip(planes, black, exposures)]


def hat_weight(raw, black, sat=65535.0):
    """Triangle weight on the raw plane value: 0 at black and at saturation, peak in between.
    Down-weights clipped highlights (use a shorter exposure) and the noise floor (use a longer one)."""
    raw = np.asarray(raw, dtype=np.float64)
    w = np.minimum(raw - black, sat - raw)
    return np.clip(w, 0.0, None)


def merge(planes_raw, radiances, black, sat=65535.0):
    """Weighted mean of the per-plane radiances; weight = hat(raw). Where every plane is clipped/black,
    fall back to the plane whose raw value is closest to mid-scale."""
    black = np.asarray(black, dtype=np.float64)
    W = np.stack([hat_weight(p, black[i], sat) for i, p in enumerate(planes_raw)])   # 3×H×W
    L = np.stack([np.asarray(r, dtype=np.float64) for r in radiances])               # 3×H×W
    sw = W.sum(0)
    num = (W * L).sum(0)
    out = np.where(sw > 0, num / np.where(sw > 0, sw, 1.0), 0.0)
    # fallback where all weights are zero: pick the plane nearest mid-scale
    bad = sw <= 0
    if bad.any():
        mid = sat / 2.0
        dist = np.stack([np.abs(np.asarray(p) - mid) for p in planes_raw])
        pick = dist.argmin(0)
        chosen = np.choose(pick, L)
        out = np.where(bad, chosen, out)
    return out


def merge_hdr(subframes, dark=None):
    """Full pipeline: black-subtract → register (align the sub-pixel dither out) → radiometric →
    weighted merge. Returns an H×W linear radiance image."""
    planes = subframes.planes
    black = estimate_black(planes, dark=dark)
    shifts = estimate_shifts(planes)
    reg = register(planes, shifts)
    L = radiometric(reg, black, subframes.exposures)
    return merge(reg, L, black)


def to_pgm16(radiance, hi_pct=99.9):
    """Scale a linear radiance image to [0,65535], linear, clipping the top hi_pct-percentile outliers."""
    r = np.asarray(radiance, dtype=np.float64)
    r = r - r.min()
    hi = np.percentile(r, hi_pct)
    if hi <= 0:
        hi = r.max() if r.max() > 0 else 1.0
    return np.clip(r / hi * 65535.0, 0, 65535)
