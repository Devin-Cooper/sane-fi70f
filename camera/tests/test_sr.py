import numpy as np
from camera.sr import (gaussian_y, forward_y, backproject_y,
                      gain_match, superres_y, interp_baseline_y, _upsample_y)
from camera.subframes import SubFrames
from camera.mtf import slanted_edge_mtf


def test_gaussian_y_preserves_dc_and_blurs():
    a = np.zeros((21, 3)); a[10] = 1.0
    b = gaussian_y(a, 1.5)
    assert abs(b.sum(0)[0] - 1.0) < 1e-9         # DC preserved
    assert b[10, 0] < 1.0 and b[9, 0] > 0        # spread


def test_forward_backproject_are_adjoint():
    rng = np.random.default_rng(0)
    fH, W, f = 40, 5, 2
    hr = rng.standard_normal((fH, W)); y = rng.standard_normal((fH // f, W))
    fwd = forward_y(hr, delta=-0.245, sigma=0.45, f=f)            # H×W
    bp = backproject_y(y, delta=-0.245, sigma=0.45, f=f, fH=fH)   # fH×W
    lhs = float((fwd * y).sum()); rhs = float((hr * bp).sum())
    assert abs(lhs - rhs) < 1e-8


def test_gain_match_puts_planes_on_reference_scale():
    R = np.linspace(10, 200, 50).reshape(50, 1) * np.ones((50, 8))
    planes = [R, 3.0 * R + 5.0, 0.5 * R - 2.0]     # scaled/offset copies
    gm = gain_match(planes)
    for g in gm:
        assert np.corrcoef(g.ravel(), R.ravel())[0, 1] > 0.999
        assert abs(g.mean() - R.mean()) < 1e-6


def _hr_scene(fH=160, W=64):
    # a clean, slightly-slanted horizontal edge at HR resolution (no added texture -> the SFR
    # edge-finder stays clean; the sensor LSF blur is applied by the forward model)
    y = np.arange(fH)[:, None]; x = np.arange(W)[None, :]
    edge_y = fH / 2.0 + 0.15 * (x - W / 2.0)
    return 0.5 * (1 + np.tanh((y - edge_y) * 1.2)) * 180 + 20


def _make_planes(hr, deltas, sigma, f):
    return [forward_y(hr, d, sigma, f) for d in deltas]


def test_ibp_beats_interp_and_single_on_recovered_mtf():
    f, sigma = 2, 0.55; deltas = [0.0, -0.245, -0.723]
    hr = _hr_scene()
    planes = _make_planes(hr, deltas, sigma, f)
    sf = SubFrames([p.copy() for p in planes], (2194, 733, 1463), 300)
    ibp = superres_y(sf, factor=f, sigma=sigma, iters=40)
    base = interp_baseline_y(sf, factor=f)
    single = _upsample_y(planes[0], f)                   # fair linear-upsample reference
    reg = (slice(10, -10), slice(6, -6))
    _, _, m_ibp = slanted_edge_mtf(ibp[reg])
    _, _, m_base = slanted_edge_mtf(base[reg])
    _, _, m_single = slanted_edge_mtf(single[reg])
    # IBP must beat BOTH the single-plane (real Y-resolution gain) and the interpolation
    # baseline (proves it's deconvolution, not upscaling). Naive interp can be worse than a
    # single plane -- combining blurred sub-samples without deconvolution doesn't add detail.
    assert m_ibp > m_single and m_ibp > m_base
    assert m_ibp > 1.15 * m_single                       # meaningful gain (~1.25x here)
    assert np.corrcoef(ibp[reg].ravel(), hr[reg].ravel())[0, 1] > 0.98
