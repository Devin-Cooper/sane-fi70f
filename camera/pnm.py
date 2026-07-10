"""Minimal netpbm (PNM) I/O for the fi-70F sub-exposure pipeline.
PIL mangles 16-bit P6, so parse manually; 16-bit PNM samples are big-endian (netpbm spec)."""
import numpy as np


def _rdtok(f):
    tok = b""
    while True:
        c = f.read(1)
        if c == b"#":
            f.readline(); continue
        if c == b"":
            return tok
        if c.isspace():
            if tok:
                return tok
            continue
        tok += c


def read_pnm(path):
    """Read a P5 (gray) or P6 (RGB) PNM, 8- or 16-bit, into an H×W×C float64 array."""
    with open(path, "rb") as f:
        magic = _rdtok(f); W = int(_rdtok(f)); H = int(_rdtok(f)); maxval = int(_rdtok(f))
        C = 3 if magic == b"P6" else 1
        raw = np.frombuffer(f.read(), dtype=np.uint8)
    if maxval > 255:
        pr = raw[:(len(raw) // 2) * 2].reshape(-1, 2)
        vals = ((pr[:, 0].astype(np.uint32) << 8) | pr[:, 1]).astype(np.float64)
    else:
        vals = raw.astype(np.float64)
    return vals[:H * W * C].reshape(H, W, C)


def write_pgm16(path, arr):
    """Write a 2-D array as a 16-bit (big-endian) P5 PGM, clipped to [0, 65535]."""
    a = np.clip(np.rint(np.asarray(arr)), 0, 65535).astype(">u2")
    H, W = a.shape
    with open(path, "wb") as f:
        f.write(b"P5\n%d %d\n65535\n" % (W, H))
        f.write(a.tobytes())
