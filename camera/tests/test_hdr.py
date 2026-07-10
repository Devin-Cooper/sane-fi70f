import numpy as np
from camera.hdr import radiometric, hat_weight, merge, merge_hdr, to_pgm16
from camera.subframes import SubFrames, fourier_shift


def test_radiometric_puts_planes_on_common_scale():
    # same scene radiance, two exposures -> after ÷exposure they agree
    G = np.full((5, 5), 0.5)
    pL = 10 + 2194 * G; pS = 10 + 733 * G
    L = radiometric([pL, pS], [10, 10], [2194, 733])
    assert np.allclose(L[0], L[1], atol=1e-9) and np.allclose(L[0], 0.5, atol=1e-9)


def test_hat_weight_zero_at_black_and_saturation():
    raw = np.array([[10., 12000., 65535.]])
    w = hat_weight(raw, black=10.0, sat=65535.0)
    assert w[0, 0] == 0 and w[0, 2] == 0 and w[0, 1] > 0


def test_merge_recovers_highlights_from_short_and_shadows_from_long():
    H = W = 32; y, x = np.mgrid[0:H, 0:W]; G = (x / (W - 1.0))            # radiance ramp 0..1
    black = [12., 10., 11.]; exp = [2194., 733., 1463.]; k = 40.0
    planes = [np.clip(black[i] + k * exp[i] * G, 0, 65535) for i in range(3)]  # long clips at high G
    L = radiometric(planes, black, exp)
    out = merge(planes, L, black)
    # out is proportional to G (linear); check monotone + high correlation
    assert np.corrcoef(out.ravel(), G.ravel())[0, 1] > 0.999
    # brightest column (long plane saturated there) still increases vs mid column
    assert out[:, -1].mean() > out[:, W // 2].mean()


def test_merge_hdr_end_to_end_with_shift_and_clip():
    H = W = 48; y, x = np.mgrid[0:H, 0:W]; G = (x / (W - 1.0)) * 0.9 + 0.05     # radiance 0.05..0.95
    black = [12., 10., 11.]; exp = (2194., 733., 1463.); k = 45.0
    base = [np.clip(black[i] + k * exp[i] * G, 0, 65535) for i in range(3)]
    # apply the real sub-pixel Y dither to G,B (registration must undo it)
    planes = [base[0], fourier_shift(base[1], 0.245, 0.0), fourier_shift(base[2], 0.723, 0.0)]
    sf = SubFrames([p.copy() for p in planes], exp, 300)
    L = merge_hdr(sf)
    inner = (slice(6, -6), slice(6, -6))
    assert np.corrcoef(L[inner].ravel(), G[inner].ravel())[0, 1] > 0.995
    out = to_pgm16(L)
    assert out.max() <= 65535 and out.min() >= 0 and out[inner].std() > 0
