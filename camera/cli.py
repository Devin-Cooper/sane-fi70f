"""Command-line entry point for the fi-70F camera-back tools."""
import argparse
import sys
from .subframes import load_subframes
from .hdr import merge_hdr, to_pgm16
from .sr import superres_y, interp_baseline_y
from .snr import average_frames
from .pnm import write_pgm16


def main(argv=None):
    ap = argparse.ArgumentParser(prog="camera")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge-hdr", help="merge 3 sub-exposures -> 16-bit linear PGM")
    m.add_argument("input")
    m.add_argument("output")
    m.add_argument("--exposures", default="2194,733,1463")
    m.add_argument("--dark", default=None, help="lens-capped lamp-off RGB16 dark frame")
    m.add_argument("--preview", default=None, help="optional tone-mapped 8-bit PNG preview")
    s = sub.add_parser("superres", help="Y super-resolution of 3 sub-exposures -> taller 16-bit PGM")
    s.add_argument("input")
    s.add_argument("output")
    s.add_argument("--factor", type=int, default=2)
    s.add_argument("--sigma", type=float, default=0.45)
    s.add_argument("--iters", type=int, default=15)
    s.add_argument("--baseline", action="store_true", help="interp baseline instead of IBP")
    av = sub.add_parser("average", help="equalise-for-SNR: average the 3 sub-exposures (sqrt-N noise cut)")
    av.add_argument("input")
    av.add_argument("output")
    a = ap.parse_args(argv)
    if a.cmd == "merge-hdr":
        exps = tuple(int(x) for x in a.exposures.split(","))
        sf = load_subframes(a.input, exposures=exps)
        dark = None
        if a.dark:
            d = load_subframes(a.dark, exposures=exps)
            dark = d.planes
        L = merge_hdr(sf, dark=dark)
        out = to_pgm16(L)
        write_pgm16(a.output, out)
        if a.preview:
            _write_preview(a.preview, out)
        print("merge-hdr: wrote %s (%dx%d, 16-bit linear)" % (a.output, out.shape[1], out.shape[0]))
        return 0
    if a.cmd == "superres":
        sf = load_subframes(a.input)
        hr = (interp_baseline_y(sf, factor=a.factor) if a.baseline
              else superres_y(sf, factor=a.factor, sigma=a.sigma, iters=a.iters))
        out = to_pgm16(hr)
        write_pgm16(a.output, out)
        print("superres: wrote %s (%dx%d, %dx Y)" % (a.output, out.shape[1], out.shape[0], a.factor))
        return 0
    if a.cmd == "average":
        sf = load_subframes(a.input)
        out = to_pgm16(average_frames(sf))
        write_pgm16(a.output, out)
        print("average: wrote %s (%dx%d, sqrt-N SNR)" % (a.output, out.shape[1], out.shape[0]))
        return 0
    return 2


def _write_preview(path, pgm16):
    """Optional 8-bit tone-mapped preview (sqrt tone curve) via PIL if available; skip if not."""
    try:
        from PIL import Image
        import numpy as np
        v = pgm16 / 65535.0
        v = np.sqrt(v)  # simple display gamma
        Image.fromarray((v * 255).astype("uint8"), "L").save(path)
    except Exception as e:
        print("preview skipped (%s)" % e, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
