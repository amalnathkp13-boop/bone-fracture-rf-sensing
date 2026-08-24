"""Zip the parts of the repo Colab needs, ready to upload to Drive.

Deliberately not the whole tree: `runs/` holds solved B-scans and would make the
archive hundreds of megabytes, and the matrix results come back *from* Drive
rather than going to it.

What goes in is the package, the scripts, and `config/materials.in` - the Debye
fits from Stage 1, which the deck builder refuses to run without.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ("bonesim", "scripts", "config", "tests")
SKIP_SUFFIX = (".pyc", ".out", ".npz", ".h5", ".vti", ".pkl", ".log")
SKIP_DIR = ("__pycache__", ".git", "runs", ".pytest_cache")


def main() -> int:
    out = ROOT / "bonesim_colab.zip"
    n, total = 0, 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for top in INCLUDE:
            for p in sorted((ROOT / top).rglob("*")):
                if p.is_dir() or p.suffix in SKIP_SUFFIX:
                    continue
                if any(part in SKIP_DIR for part in p.parts):
                    continue
                z.write(p, p.relative_to(ROOT))
                n += 1
                total += p.stat().st_size

    size = out.stat().st_size
    print(f"wrote {out}")
    print(f"  {n} files, {total/1024:.0f} kB uncompressed, "
          f"{size/1024:.0f} kB zipped")
    if not (ROOT / "config" / "materials.in").exists():
        print("\nWARNING: config/materials.in is missing. Run "
              "scripts/fit_debye_materials.py first, or the decks will not "
              "build on Colab.")
        return 1
    print("\nUpload it to Google Drive as:  MyDrive/bonesim/bonesim_colab.zip")
    print("Then open notebooks/colab_matrix.ipynb and run all cells.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
