import numpy as np, os, tempfile
from camera.pnm import read_pnm, write_pgm16


def test_pgm16_roundtrip():
    a = (np.arange(6 * 4).reshape(6, 4) * 1000).astype(np.float64)  # up to 23000 < 65535
    p = os.path.join(tempfile.mkdtemp(), "t.pgm")
    write_pgm16(p, a)
    b = read_pnm(p)
    assert b.shape == (6, 4, 1)
    assert np.array_equal(b[..., 0], a)


def test_read_p6_16bit(tmp_path):
    # hand-build a 2x1 RGB16 big-endian PPM: pixel0 = (257,514,771), pixel1=(1028,1285,1542)
    p = tmp_path / "t.ppm"
    hdr = b"P6\n2 1\n65535\n"
    vals = [257, 514, 771, 1028, 1285, 1542]
    body = b"".join(int(v).to_bytes(2, "big") for v in vals)
    p.write_bytes(hdr + body)
    a = read_pnm(str(p))
    assert a.shape == (1, 2, 3)
    assert list(a[0, 0]) == [257, 514, 771] and list(a[0, 1]) == [1028, 1285, 1542]
