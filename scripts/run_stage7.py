"""Stage 7: the statistical analysis plan of proposal section 5.

Reads whatever the matrix has solved, scores every acquisition through the same
pipeline used since Stage 2, and reports the endpoints section 5 asks for.

Only COMPLETE specimens are used. A bone missing some of its fracture states
would contribute an unbalanced set of labels and quietly bias the pooled AUC,
so partial specimens are counted and excluded rather than half-used.

    python scripts/run_stage7.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.detect.metrics import detect_snr
from bonesim.experiment import N_REPEATS, build_matrix
from bonesim.forward.base import ScanData
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_selective, subtract_empty_scene
from bonesim.process.migrate import migrate
from bonesim.stats.analysis import (Sample, auc, bootstrap_auc_ci, icc,
                                    loso_decisions, permutation_p,
                                    wilson_interval)

ROOT = Path(__file__).resolve().parent.parent
EPS_AVG = 26.0
Z_WINDOW = (0.003, 0.024)
X_MARGIN = 0.010
PRIMARY_OVERLAY = 0.006          # section 5: the primary endpoint is at 6 mm


def score_cell(path: Path, repeat: int) -> float:
    """One detector score, for one instrument realisation.

    The repeat index seeds the error model, so three repeats are three
    remounts of the same anatomy - different stage position, standoff and
    cable drift, identical bone.
    """
    d = ScanData.load(path)
    ref = ScanData(d.f, d.x, np.ones_like(d.s11), d.z_antenna, {})
    inst = Instrument(seed=repeat)
    clean = remove_clutter_selective(
        inst.apply_post(subtract_empty_scene(d, ref)), EPS_AVG)[0]
    det = detect_snr(migrate(clean, EPS_AVG), clean,
                     z_window=Z_WINDOW, x_margin=X_MARGIN)
    return det.ratio_db


CACHE = ROOT / "runs" / "stage7_scores.csv"


def collect(use_cache: bool = True) -> tuple[list[Sample], list[int], list[int]]:
    """Score every acquisition, caching the result.

    Scoring runs the full pipeline - clutter removal, migration, detection -
    on 432 acquisitions and takes several minutes. The scores depend only on
    the solved data and the pipeline, so they are cached keyed by the set of
    cells present; adding cells invalidates it automatically.
    """
    have = {p.stem: p for p in
            list((ROOT / "runs" / "matrix_colab").glob("*.npz"))
            + list((ROOT / "runs" / "matrix").glob("*.npz"))}
    cells = build_matrix()
    by_spec: dict[int, list] = {}
    for c in cells:
        by_spec.setdefault(c.specimen, []).append(c)

    complete = [s for s, g in by_spec.items()
                if all(c.key in have for c in g)]
    partial = [s for s in sorted(by_spec) if s not in complete]

    stamp = str(sorted(have))
    if use_cache and CACHE.exists():
        import csv
        with open(CACHE, newline="") as fh:
            rows = list(csv.reader(fh))
        if rows and rows[0][0] == "#stamp" and rows[0][1] == str(hash(stamp)):
            cached = [Sample(int(r[0]), r[1], float(r[2]), float(r[3]),
                             r[4] == "True", int(r[5]), float(r[6]))
                      for r in rows[1:]]
            print(f"  using cached scores for {len(cached)//N_REPEATS} "
                  f"acquisitions")
            return cached, sorted(complete), partial

    samples: list[Sample] = []
    for s in sorted(complete):
        for c in by_spec[s]:
            for r in range(N_REPEATS):
                samples.append(Sample(
                    specimen=c.specimen, state=c.state, overlay=c.overlay,
                    kerf=c.kerf, fractured=c.fractured, repeat=r,
                    score=score_cell(have[c.key], r)))

    import csv
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["#stamp", str(hash(stamp))])
        for s_ in samples:
            w.writerow([s_.specimen, s_.state, s_.overlay, s_.kerf,
                        s_.fractured, s_.repeat, s_.score])
    return samples, sorted(complete), partial


def main() -> int:
    print("scoring; this reruns the full pipeline on every acquisition\n")
    samples, complete, partial = collect()
    if len(complete) < 3:
        print(f"only {len(complete)} complete specimens - not enough for "
              f"leave-one-specimen-out. Solve more of the matrix first.")
        return 1

    n_cells = len(samples) // N_REPEATS
    print("=" * 76)
    print("Data")
    print("=" * 76)
    print(f"  complete specimens : {complete}")
    print(f"  excluded (partial) : {partial}")
    print(f"  acquisitions       : {n_cells}")
    print(f"  scores             : {len(samples)}  "
          f"({N_REPEATS} remount realisations each)")

    # Separation, before any AUC. A perfect AUC is uninterpretable on its own
    # - it can mean a huge effect or a leak - so the raw distributions are
    # reported first and the reader can see which.
    f = np.array([s.score for s in samples if s.fractured])
    i = np.array([s.score for s in samples if not s.fractured])
    print()
    print("=" * 76)
    print("0. Separation - read this before any AUC")
    print("=" * 76)
    print(f"  {'':10}{'n':>5}{'min':>9}{'median':>9}{'max':>9}")
    print(f"  {'intact':10}{i.size:>5}{i.min():>9.1f}{np.median(i):>9.1f}"
          f"{i.max():>9.1f}")
    print(f"  {'fractured':10}{f.size:>5}{f.min():>9.1f}{np.median(f):>9.1f}"
          f"{f.max():>9.1f}")
    gap = f.min() - i.max()
    print()
    print(f"  gap between highest intact and lowest fractured: {gap:+.1f} dB")
    print(f"  overlap: {'NONE' if gap > 0 else 'yes'}")
    if gap > 0:
        print(f"  So a perfect AUC below is a real separation, not a fitting")
        print(f"  artefact - but see the verdict for what it does and does not")
        print(f"  let you claim.")

    prim = [s for s in samples if s.overlay == PRIMARY_OVERLAY]

    print()
    print("=" * 76)
    print(f"1. PRIMARY ENDPOINT - AUC at {PRIMARY_OVERLAY*1e3:.0f} mm overlay, "
          f"pooled across fracture types")
    print("=" * 76)
    a = auc([s.score for s in prim], [s.fractured for s in prim])
    lo, hi = bootstrap_auc_ci(prim)
    obs, p, null = permutation_p(prim)
    print(f"  AUC              {a:.4f}")
    print(f"  95% CI           {lo:.4f} to {hi:.4f}   "
          f"(bootstrap over specimens, not measurements)")
    print(f"  permutation p    {p:.4f}   "
          f"(1000 shuffles within specimen; null mean {null.mean():.3f})")
    n_pos = sum(s.fractured for s in prim)
    print(f"  n                {n_pos} fractured vs {len(prim)-n_pos} intact")

    print()
    print("=" * 76)
    print("2. AUC by overlay - the clinical envelope of section 4.3")
    print("=" * 76)
    print(f"  {'overlay':>9}{'AUC':>9}{'95% CI':>18}{'p':>9}   n")
    for ov in sorted({s.overlay for s in samples}):
        sub = [s for s in samples if s.overlay == ov]
        a_ = auc([s.score for s in sub], [s.fractured for s in sub])
        l_, h_ = bootstrap_auc_ci(sub, n_boot=1000)
        _, p_, _ = permutation_p(sub, n_perm=500)
        print(f"  {ov*1e3:8.0f} {a_:>9.4f}{f'{l_:.3f}-{h_:.3f}':>18}"
              f"{p_:>9.4f}   {len(sub)}")

    print()
    print("=" * 76)
    print("3. AUC by fracture width - where detection gives out")
    print("=" * 76)
    intact = [s for s in samples if not s.fractured]
    print(f"  {'kerf':>9}{'AUC':>9}{'95% CI':>18}{'sens @ intact-max':>20}")
    for kerf in sorted({s.kerf for s in samples if s.fractured}):
        sub = [s for s in samples if s.kerf == kerf] + intact
        a_ = auc([s.score for s in sub], [s.fractured for s in sub])
        l_, h_ = bootstrap_auc_ci(sub, n_boot=1000)
        # Sensitivity at a threshold that admits no intact limb at all.
        thr = max(s.score for s in intact)
        pos = [s for s in samples if s.kerf == kerf]
        k = sum(s.score >= thr for s in pos)
        wl, wh = wilson_interval(k, len(pos))
        print(f"  {kerf*1e3:8.1f} {a_:>9.4f}{f'{l_:.3f}-{h_:.3f}':>18}"
              f"{f'{k}/{len(pos)} ({wl:.2f}-{wh:.2f})':>20}")

    print()
    print("=" * 76)
    print("4. Leave-one-specimen-out - the threshold is the trained part")
    print("=" * 76)
    sens, spec, acc, rows = loso_decisions(samples)
    print(f"  {'held out':>9}{'threshold':>11}{'TP':>5}{'FN':>5}"
          f"{'FP':>5}{'TN':>5}")
    for held, thr, tp, fn, fp, tn in rows:
        print(f"  {held:>9}{thr:>11.1f}{tp:>5}{fn:>5}{fp:>5}{tn:>5}")
    n_pos = sum(s.fractured for s in samples)
    n_neg = len(samples) - n_pos
    sl, sh = wilson_interval(int(round(sens * n_pos)), n_pos)
    pl, ph = wilson_interval(int(round(spec * n_neg)), n_neg)
    print(f"\n  sensitivity {sens:.4f}  ({sl:.3f}-{sh:.3f} Wilson)")
    print(f"  specificity {spec:.4f}  ({pl:.3f}-{ph:.3f} Wilson)")
    print(f"  accuracy    {acc:.4f}")

    print()
    print("=" * 76)
    print("5. Repeatability across remounts")
    print("=" * 76)
    groups = {}
    for s in samples:
        groups.setdefault((s.specimen, s.state, s.overlay), []).append(s.score)
    vals = list(groups.values())
    spread = [np.std(v) for v in vals]
    print(f"  ICC(1,1)            {icc(vals):.4f}")
    print(f"  within-measurement  sd {np.mean(spread):.3f} dB "
          f"(median {np.median(spread):.3f})")
    print(f"  between-measurement sd {np.std([np.mean(v) for v in vals]):.3f} dB")

    print()
    print("=" * 76)
    print("6. Verdict")
    print("=" * 76)
    ok = a > 0.9 and p < 0.05
    print(f"  primary AUC {a:.4f} [{lo:.3f}, {hi:.3f}], p = {p:.4f}")
    if ok:
        print("  The detector separates fractured from intact at 6 mm of "
              "overlay,")
        print("  on bones the threshold was not fitted to.")
    else:
        print("  Does not meet AUC > 0.9 with p < 0.05. Reportable either way "
              "(section 5.7).")

    if a >= 0.999:
        print()
        print("  WHAT A PERFECT AUC DOES NOT MEAN. With no overlap, AUC is")
        print("  saturated: it says the separation exceeds what this experiment")
        print("  can resolve, not that it is infinite. The honest claim is a")
        print(f"  lower bound - the classes are {gap:.0f} dB apart under this")
        print("  error model - and the binding assumption is the ERROR MODEL,")
        print("  not the physics. A real bench has cable flex, operator")
        print("  variation, specimen preparation and tissue heterogeneity that")
        print("  bonesim.perturb.errors does not model.")
        print()
        print("  To measure the actual limit rather than a bound, push until it")
        print("  fails: thinner kerf than 0.2 mm needs a finer grid; thicker")
        print("  overlay than 10 mm is one line in experiment.py; a harsher")
        print("  error model is the cheapest of the three.")
    if partial:
        print(f"\n  NOTE: {len(partial)} specimens excluded as incomplete. "
              f"These numbers will move")
        print(f"  when the matrix finishes; treat them as preliminary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
