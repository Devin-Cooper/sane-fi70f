"""Slanted-edge SFR (ISO-12233-style) for the Y axis: measure MTF from a horizontal-ish edge."""
import numpy as np


def _edge_positions(sub):
    """Sub-pixel edge y-position per column, from the gradient centroid."""
    g = np.abs(np.diff(sub, axis=0))                      # (H-1)×W vertical gradient
    yy = np.arange(g.shape[0])[:, None] + 0.5
    w = g.sum(0) + 1e-12
    return (g * yy).sum(0) / w                            # W


def slanted_edge_mtf(img, region=None, oversample=4):
    """Return (freqs, mtf, mtf50) for the Y (vertical) MTF of a slightly-slanted horizontal edge."""
    sub = np.asarray(img, dtype=np.float64)
    if region is not None:
        y0, y1, x0, x1 = region
        sub = sub[y0:y1, x0:x1]
    H, W = sub.shape
    ey = _edge_positions(sub)                             # edge y per column
    m, c = np.polyfit(np.arange(W), ey, 1)                # linear edge fit
    # project every pixel onto distance-from-edge, bin to an oversampled ESF
    yy = np.arange(H)[:, None]; xx = np.arange(W)[None, :]
    dist = yy - (m * xx + c)                              # signed distance (px)
    lo, hi = -H / 2.0, H / 2.0
    nb = int((hi - lo) * oversample)
    idx = np.clip(((dist - lo) * oversample).astype(int).ravel(), 0, nb - 1)
    vals = sub.ravel()
    cnt = np.bincount(idx, minlength=nb)
    esf = np.bincount(idx, weights=vals, minlength=nb) / (cnt + 1e-12)
    good = cnt > 0
    esf = np.interp(np.arange(nb), np.where(good)[0], esf[good])   # fill empty bins
    lsf = np.diff(esf)                                    # line spread
    lsf = lsf - lsf[:oversample].mean()                  # de-trend baseline
    win = np.hanning(len(lsf))
    F = np.abs(np.fft.rfft(lsf * win))
    mtf = F / (F[0] + 1e-12)
    freqs = np.fft.rfftfreq(len(lsf), d=1.0 / oversample)  # cycles/native-pixel
    below = np.where(mtf < 0.5)[0]
    if len(below) == 0:
        mtf50 = freqs[-1]
    elif below[0] == 0:
        mtf50 = 0.0
    else:
        k = below[0]
        f0, f1, m0, m1 = freqs[k - 1], freqs[k], mtf[k - 1], mtf[k]
        mtf50 = f0 + (0.5 - m0) * (f1 - f0) / (m1 - m0)
    return freqs, mtf, float(mtf50)
