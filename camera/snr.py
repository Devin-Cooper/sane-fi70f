"""Equalise-for-SNR: average the three (radiometrically-equal) sub-exposures for a √N SNR gain (#4)."""
import numpy as np


def average_frames(subframes):
    """Mean-match the three planes to the reference, then average -> a √N-SNR grayscale.
    With equal integration times (exposure-mode=equalise) the three planes are radiometrically
    equal, so this averages independent per-read noise for a ~√3 (1.7x) noise reduction. Uses
    MEAN matching (not a slope fit) because the equalise target is a flat/uniform field, on which
    a slope fit is degenerate; mean matching also corrects the per-LED brightness under lamp-on."""
    planes = [np.asarray(p, dtype=np.float64) for p in subframes.planes]
    ref_mean = planes[0].mean()
    norm = [p * (ref_mean / p.mean()) if p.mean() != 0 else p for p in planes]
    return np.mean(norm, axis=0)


def patch_sigma(img, region=None):
    """Noise sigma on a flat patch. For a flat field the raw std over the patch is the noise level."""
    a = np.asarray(img, dtype=np.float64)
    if region is not None:
        y0, y1, x0, x1 = region
        a = a[y0:y1, x0:x1]
    return float(a.std())
