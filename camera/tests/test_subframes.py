import numpy as np, os, tempfile
from camera.pnm import read_pnm
from camera.subframes import (load_subframes, estimate_black,
                              fourier_shift, estimate_shifts, register)


def _write_ppm16(path, hxwx3):
    a = np.clip(np.rint(hxwx3), 0, 65535).astype(">u2"); H, W, _ = a.shape
    with open(path, "wb") as f:
        f.write(b"P6\n%d %d\n65535\n" % (W, H)); f.write(a.tobytes())


def test_load_subframes_splits_planes():
    im = np.zeros((3, 2, 3)); im[..., 0] = 1000; im[..., 1] = 2000; im[..., 2] = 3000
    p = os.path.join(tempfile.mkdtemp(), "s.ppm"); _write_ppm16(p, im)
    sf = load_subframes(p)
    assert len(sf.planes) == 3 and sf.exposures == (2194, 733, 1463) and sf.res == 300
    assert sf.planes[0].mean() == 1000 and sf.planes[2].mean() == 3000


def test_estimate_black_percentile_and_darkframe():
    planes = [np.full((10, 10), 5000.0) for _ in range(3)]
    for p in planes:
        p[0, :] = 12.0   # a ~10% dark region (border/shadow), as a real scan has
    b = estimate_black(planes, pct=1.0)
    assert all(0 <= x <= 50 for x in b)           # low percentile picks the dark tail (~12)
    dark = [np.full((10, 10), 12.0), np.full((10, 10), 8.0), np.full((10, 10), 10.0)]
    b2 = estimate_black(planes, dark=dark)
    assert b2 == [12.0, 8.0, 10.0]                 # dark-frame means override


def _scene(H=64, W=64):
    y, x = np.mgrid[0:H, 0:W]
    return 8000 + 4000 * np.sin(x / 5.0) + 3000 * np.cos(y / 7.0)


def test_fourier_shift_recovers_known_shift():
    a = _scene(); b = fourier_shift(a, 0.0, 0.0)
    assert np.allclose(a, b, atol=1e-6)


def test_estimate_and_register_removes_subpixel_shift():
    ref = _scene()
    g = fourier_shift(ref, 0.30, 0.0)     # plane displaced +0.30 px in y
    b = fourier_shift(ref, 0.70, 2.0)     # +0.70 y, +2 x (the 600-dpi case)
    sh = estimate_shifts([ref, g, b])
    assert abs(sh[0][0]) < 0.05 and abs(sh[0][1]) < 0.05
    assert abs(sh[1][0] - 0.30) < 0.08 and abs(sh[2][0] - 0.70) < 0.08 and abs(sh[2][1] - 2.0) < 0.15
    reg = register([ref, g, b], sh)
    inner = (slice(8, -8), slice(8, -8))     # ignore FFT wrap at edges
    assert np.corrcoef(reg[1][inner].ravel(), ref[inner].ravel())[0, 1] > 0.999
    assert np.corrcoef(reg[2][inner].ravel(), ref[inner].ravel())[0, 1] > 0.999
