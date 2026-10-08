"""Generate every figure defined in figs_*.py next to this file.

Each figs_*.py module exposes `FIGS = {"fig-NN-name": make_fn}` where make_fn() returns an svg.Fig.

    python3 scripts/figures/build.py              # all figures
    python3 scripts/figures/build.py fig-09       # only names starting with fig-09
    python3 scripts/figures/build.py --out DIR    # output dir (default: <book>/chapters/images)

Overflow warnings ("WARN overflow: ...") mean a label is wider than its box: fix before inserting.
"""

import argparse
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix", nargs="?", default="")
    ap.add_argument("--out", default=str(HERE.parents[1] / "chapters" / "images"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(HERE.glob("figs_*.py")):
        mod = importlib.import_module(path.stem)
        for name, make in mod.FIGS.items():
            if not name.startswith(args.prefix):
                continue
            fig = make()
            (out / f"{name}.svg").write_text(fig.svg(), encoding="utf-8")
            warn = "  WARN " + "; ".join(fig.warnings) if fig.warnings else ""
            print(f"{name}.svg{warn}")


if __name__ == "__main__":
    main()
