import numpy as np
from camera.mtf import slanted_edge_mtf


def _erf(x):
    # vectorised erf via numpy (Abramowitz-Stegun 7.1.26)
    x = np.asarray(x, dtype=np.float64); s = np.sign(x); x = np.abs(x)
    t = 1 / (1 + 0.3275911 * x)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


def _slanted_edge(H=64, W=96, sigma=0.8, slope=0.12):
    """A dark-over-bright horizontal edge, slightly slanted, Gaussian-blurred by sigma (px)."""
    from math import sqrt
    y = np.arange(H)[:, None]; x = np.arange(W)[None, :]
    edge_y = H / 2.0 + slope * (x - W / 2.0)
    d = (y - edge_y)                        # signed distance from edge (px)
    img = 0.5 * (1 + _erf(d / (sigma * sqrt(2))))
    return img * 200 + 20                    # arbitrary contrast/offset


def test_mtf_matches_analytic_gaussian():
    sigma = 0.8
    img = _slanted_edge(sigma=sigma)
    freqs, mtf, mtf50 = slanted_edge_mtf(img)
    analytic = 0.1874 / sigma            # ~0.234 cyc/px
    assert abs(mtf50 - analytic) < 0.05
    assert mtf[0] > 0.99                  # normalised at DC


def test_mtf50_drops_for_more_blur():
    _, _, m_sharp = slanted_edge_mtf(_slanted_edge(sigma=0.6))
    _, _, m_blur = slanted_edge_mtf(_slanted_edge(sigma=1.2))
    assert m_sharp > m_blur               # blurrier edge -> lower MTF50
