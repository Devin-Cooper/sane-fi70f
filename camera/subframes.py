"""Shared sub-frame foundation for the fi-70F camera-back pipeline (#2 HDR, #3/#5 super-res)."""
from dataclasses import dataclass
import numpy as np
from .pnm import read_pnm


@dataclass
class SubFrames:
    planes: list      # 3 × (H×W float64): R=long(2194), G=short(733), B=mid(1463)
    exposures: tuple  # integration times matching the planes
    res: int          # 300 or 600 dpi (from width)


def load_subframes(path, exposures=(2194, 733, 1463)):
    im = read_pnm(path)
    if im.ndim != 3 or im.shape[2] < 3:
        raise ValueError("expected an RGB16 --mode Sub-exposures image, got shape %r" % (im.shape,))
    planes = [im[..., 0].copy(), im[..., 1].copy(), im[..., 2].copy()]
    res = 600 if im.shape[1] > 1800 else 300
    return SubFrames(planes, tuple(exposures), res)


def estimate_black(planes, dark=None, pct=1.0):
    """Per-plane black level. Prefer a dark frame (lens-capped lamp-off) mean; else a low percentile.
    Dark current is exposure-dependent, so black is per-plane, never shared."""
    if dark is not None:
        return [float(np.mean(d)) for d in dark]
    return [float(np.percentile(p, pct)) for p in planes]


def fourier_shift(img, dy, dx):
    """Shift a 2-D array by sub-pixel (dy,dx) via the Fourier shift theorem: out[y,x] ≈ img[y-dy,x-dx]."""
    H, W = img.shape
    fy = np.fft.fftfreq(H)[:, None]; fx = np.fft.fftfreq(W)[None, :]
    F = np.fft.fft2(img) * np.exp(-2j * np.pi * (fy * dy + fx * dx))
    return np.real(np.fft.ifft2(F))


def _subpix_1d(a, b, maxlag=4):
    """Displacement of b vs a along one axis (b ≈ a shifted by +d), parabolic NCC peak. Amplitude-invariant."""
    a = a - a.mean(); b = b - b.mean()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    lags = list(range(-maxlag, maxlag + 1)); cc = []
    for L in lags:
        if L < 0:
            aa, bb = a[-L:], b[:len(b) + L]
        elif L > 0:
            aa, bb = a[:len(a) - L], b[L:]
        else:
            aa, bb = a, b
        n = min(len(aa), len(bb)); cc.append(float(np.dot(aa[:n], bb[:n]) / (na * nb)))
    cc = np.array(cc); k = int(cc.argmax())
    if k == 0 or k == len(cc) - 1:
        return float(lags[k])
    y0, y1, y2 = cc[k - 1], cc[k], cc[k + 1]; den = (y0 - 2 * y1 + y2)
    return float(lags[k] + (0.5 * (y0 - y2) / den if den != 0 else 0.0))


def estimate_shifts(planes, ref=0):
    """Displacement (dy,dx) of each plane vs planes[ref], from textured projections (median over cols/rows)."""
    R = planes[ref]; H, W = R.shape; out = []
    vcols = np.argsort(R.var(0))[-max(30, W // 8):]     # textured columns for dy
    hrows = np.argsort(R.var(1))[-max(30, H // 8):]     # textured rows for dx
    for p in planes:
        dy = float(np.median([_subpix_1d(R[:, x], p[:, x]) for x in vcols]))
        dx = float(np.median([_subpix_1d(R[y, :], p[y, :]) for y in hrows]))
        out.append((dy, dx))
    return out


def register(planes, shifts):
    """Align each plane to the reference by undoing its measured displacement."""
    return [fourier_shift(p, -dy, -dx) for p, (dy, dx) in zip(planes, shifts)]
