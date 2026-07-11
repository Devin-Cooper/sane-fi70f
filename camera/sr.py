"""Y-only super-resolution of the fi-70F sub-frames by iterative back-projection (#3)."""
import numpy as np
from .subframes import estimate_shifts, fourier_shift


def gaussian_y(img, sigma):
    """Circular Gaussian blur along the Y axis (axis 0), via its frequency response."""
    if sigma < 1e-6:
        return np.asarray(img, dtype=np.float64).copy()
    H = img.shape[0]
    fy = np.fft.fftfreq(H)
    G = np.exp(-2.0 * (np.pi * sigma * fy) ** 2)          # FT of a Gaussian
    return np.real(np.fft.ifft(np.fft.fft(img, axis=0) * G[:, None], axis=0))


def _positions(H, delta, f):
    """HR-grid Y positions sampled by native rows 0..H-1 of a plane at offset `delta`."""
    return (np.arange(H) + delta) * f


def forward_y(hr, delta, sigma, f):
    """Simulate a plane's observation: blur HR by the sensor LSF (σ in native px) then sample at
    the plane's sub-pixel offset. hr is fH×W; returns H×W (H = fH//f)."""
    fH, W = hr.shape; H = fH // f
    hrb = gaussian_y(hr, sigma * f)
    pos = _positions(H, delta, f)
    lo = np.clip(np.floor(pos).astype(int), 0, fH - 2); fr = (pos - lo)[:, None]
    return (1 - fr) * hrb[lo] + fr * hrb[lo + 1]


def backproject_y(resid, delta, sigma, f, fH):
    """Exact adjoint of forward_y: splat the residual to the HR grid then blur (blur is self-adjoint)."""
    H, W = resid.shape
    hr = np.zeros((fH, W))
    pos = _positions(H, delta, f)
    lo = np.clip(np.floor(pos).astype(int), 0, fH - 2); fr = (pos - lo)[:, None]
    np.add.at(hr, lo, (1 - fr) * resid)
    np.add.at(hr, lo + 1, fr * resid)
    return gaussian_y(hr, sigma * f)


def gain_match(planes, ref=0):
    """Rescale each plane to the reference by a least-squares linear fit plane ≈ a·R + b."""
    R = np.asarray(planes[ref], dtype=np.float64); out = []
    for p in planes:
        p = np.asarray(p, dtype=np.float64)
        a, b = np.polyfit(R.ravel(), p.ravel(), 1)
        out.append((p - b) / (a if abs(a) > 1e-9 else 1.0))
    return out


def _align_and_prep(subframes):
    """Gain-match to R, then X-align each plane (undo the 600-dpi X offset); keep the Y dither."""
    raw = subframes.planes
    shifts = estimate_shifts(raw)
    gm = gain_match(raw)
    planes = [fourier_shift(p, 0.0, -dx) for p, (dy, dx) in zip(gm, shifts)]
    deltas = [dy for (dy, dx) in shifts]
    return planes, deltas


def _upsample_y(img, f):
    fH = img.shape[0] * f
    pos = np.arange(fH) / f
    lo = np.clip(np.floor(pos).astype(int), 0, img.shape[0] - 2); fr = (pos - lo)[:, None]
    return (1 - fr) * img[lo] + fr * img[lo + 1]


def superres_y(subframes, factor=2, sigma=0.45, iters=15, lam=None):
    """Iterative back-projection Y super-resolution. Returns an (factor·H)×W HR image on R's scale."""
    planes, deltas = _align_and_prep(subframes)
    H, W = planes[0].shape; fH = factor * H
    hr = _upsample_y(planes[0], factor)
    lam = lam if lam is not None else 0.5
    for _ in range(iters):
        upd = np.zeros((fH, W))
        for p, d in zip(planes, deltas):
            upd += backproject_y(p - forward_y(hr, d, sigma, factor), d, sigma, factor, fH)
        hr = hr + (lam / len(planes)) * upd
    return hr


def interp_baseline_y(subframes, factor=2):
    """Baseline: place all planes' samples at their true Y positions and interpolate to the HR grid."""
    planes, deltas = _align_and_prep(subframes)
    H, W = planes[0].shape; fH = factor * H
    pos = np.concatenate([_positions(H, d, factor) for d in deltas])       # 3H positions
    order = np.argsort(pos); pos_s = pos[order]
    vals = np.concatenate(planes, axis=0)[order]                            # 3H×W in the same order
    grid = np.arange(fH)
    ii = np.clip(np.searchsorted(pos_s, grid) - 1, 0, len(pos_s) - 2)
    x0 = pos_s[ii]; x1 = pos_s[ii + 1]; fr = ((grid - x0) / np.maximum(x1 - x0, 1e-9))[:, None]
    return (1 - fr) * vals[ii] + fr * vals[ii + 1]
