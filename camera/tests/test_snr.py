import numpy as np
from camera.subframes import SubFrames
from camera.snr import average_frames, patch_sigma


def test_average_reduces_noise_by_sqrt3():
    rng = np.random.default_rng(1)
    base = np.full((80, 80), 20000.0)
    planes = [base + rng.normal(0, 400, base.shape) for _ in range(3)]   # equal-exposure, indep noise
    sf = SubFrames([p.copy() for p in planes], (1463, 1463, 1463), 300)
    avg = average_frames(sf)
    s_single = patch_sigma(planes[0]); s_avg = patch_sigma(avg)
    ratio = s_single / s_avg
    assert 1.5 < ratio < 1.9            # ~sqrt(3)=1.73


def test_patch_sigma_measures_std():
    a = np.zeros((10, 10)); a[0, 0] = 100
    assert patch_sigma(a) > 0
