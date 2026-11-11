"""Cheap-VNA dynamic range: score the LiteVNA band with a 70 dB noise floor.

vna_fallback_study.py limits only the BAND. The error model keeps its 95 dB
dynamic range, which a lab VNA has and a LiteVNA-64 (about 70 dB at 6 GHz)
does not. This repeats the LiteVNA band with Instrument(dynamic_range_db=70),
so the two penalties are measured together rather than one being assumed.

    python scripts/vna_dynrange_study.py
"""
from __future__ import annotations
import csv, importlib.util, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from bonesim.detect.metrics import detect_snr
from bonesim.experiment import N_REPEATS, build_matrix
from bonesim.forward.base import ScanData
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_selective, subtract_empty_scene
from bonesim.process.migrate import migrate
from bonesim.stats.analysis import auc

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("bs", ROOT / "scripts" / "run_band_study.py")
bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)
DR = 70.0
LO, HI = 3.0e9, 6.3e9

def score(path, repeat):
    d = bs.crop(ScanData.load(path), LO, HI)
    ref = ScanData(d.f, d.x, np.ones_like(d.s11), d.z_antenna, {})
    inst = Instrument(seed=repeat, dynamic_range_db=DR)
    clean = remove_clutter_selective(inst.apply_post(subtract_empty_scene(d, ref)), bs.EPS_AVG)[0]
    return detect_snr(migrate(clean, bs.EPS_AVG), clean, z_window=bs.Z_WINDOW, x_margin=bs.X_MARGIN).ratio_db

def main():
    have = {p.stem: p for p in list((ROOT/"runs"/"matrix_colab").glob("*.npz")) + list((ROOT/"runs"/"matrix").glob("*.npz"))}
    rows = []
    for c in build_matrix():
        p = have.get(c.key)
        if p is None: continue
        for r in range(N_REPEATS):
            rows.append((c.specimen, c.state, c.overlay, c.kerf, c.state != "intact", r, score(p, r)))
    with open(ROOT/"runs"/"band_scores_lite_dr70.csv", "w", newline="") as fh:
        fh.write("specimen,state,overlay,kerf,fractured,repeat,score\n")
        for x in rows: fh.write(",".join(str(v) for v in x) + "\n")
    sc = np.array([x[6] for x in rows]); fr = np.array([x[4] for x in rows]); ov = np.array([x[2] for x in rows])
    print(f"LiteVNA band 3.0-6.3 GHz at {DR:.0f} dB dynamic range, n={len(rows)}")
    print(f"  AUC {auc(sc, fr):.4f}  intact max {sc[~fr].max():.1f}  fract min {sc[fr].min():.1f}  sep {sc[fr].min()-sc[~fr].max():+.1f} dB")
    for o in sorted(set(ov)):
        m = ov == o
        print(f"  {o*1e3:>3.0f} mm  sep {sc[m&fr].min()-sc[m&~fr].max():+6.1f} dB")

if __name__ == "__main__":
    main()
