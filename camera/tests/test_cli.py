import numpy as np, os
from camera.cli import main
from camera.pnm import read_pnm


def _ppm16(path, im):
    a = np.clip(np.rint(im), 0, 65535).astype(">u2"); H, W, _ = a.shape
    with open(path, "wb") as f:
        f.write(b"P6\n%d %d\n65535\n" % (W, H)); f.write(a.tobytes())


def test_cli_merge_hdr_writes_pgm16(tmp_path):
    H = W = 32; y, x = np.mgrid[0:H, 0:W]; G = x / (W - 1.0)
    im = np.stack([12 + 2194 * 40 * G, 10 + 733 * 40 * G, 11 + 1463 * 40 * G], axis=2)
    src = str(tmp_path / "in.ppm"); dst = str(tmp_path / "out.pgm"); _ppm16(src, im)
    rc = main(["merge-hdr", src, dst])
    assert rc == 0 and os.path.exists(dst)
    out = read_pnm(dst); assert out.shape == (H, W, 1) and out.max() > 0


def test_cli_superres_writes_taller_pgm(tmp_path):
    from camera.cli import main
    H = W = 40; y, x = np.mgrid[0:H, 0:W]
    im = np.stack([100 + 60 * np.sin(y / 3.0)] * 3, axis=2) + 5000
    src = str(tmp_path / "in.ppm"); dst = str(tmp_path / "sr.pgm")
    a = np.clip(np.rint(im), 0, 65535).astype(">u2")
    with open(src, "wb") as f:
        f.write(b"P6\n%d %d\n65535\n" % (W, H)); f.write(a.tobytes())
    rc = main(["superres", src, dst, "--factor", "2", "--iters", "5"])
    assert rc == 0
    out = read_pnm(dst); assert out.shape == (2 * H, W, 1)      # 2x taller in Y
