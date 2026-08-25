"""Regenerate every figure in the report, from saved data.

Proposal 8.1 asks for "analysis code in a version-controlled repository, with a
README that reproduces every figure". This is that script: one function per
stage, each reading only committed inputs or cached run data, so no figure
depends on a plot someone made by hand once.

    python scripts/make_figures.py            # everything available
    python scripts/make_figures.py 3 4        # only those stages
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np

from bonesim import figures as F
from bonesim.detect.metrics import detect_snr
from bonesim.forward.base import ScanData
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import (remove_clutter_selective,
                                     remove_clutter_svd, subtract_empty_scene)
from bonesim.process.migrate import migrate

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
C0 = 299_792_458.0
EPS_AVG = 26.0          # autofocused in Stage 3; fixed here so panels compare


def _clean(d: ScanData, eps=EPS_AVG, selective=True):
    ref = ScanData(d.f, d.x, np.ones_like(d.s11), d.z_antenna, {})
    c = Instrument().apply_post(subtract_empty_scene(d, ref))
    return remove_clutter_selective(c, eps)[0] if selective else \
        remove_clutter_svd(c, k=1)


# --------------------------------------------------------------- stage 0 ---

def stage0():
    """Solver verification: two echoes, predicted then found."""
    p = RUNS / "fig_stage0.npz"
    if not p.exists():
        print("  stage 0: runs/fig_stage0.npz missing, skipped")
        return
    z = np.load(p)
    dt = float(z["dt"])
    a, b, c = z["A_rod"], z["B_slab"], z["C_free"]
    t = np.arange(a.size) * dt * 1e12                  # ps

    # Same geometry constants as config/smoketest_*.in
    y_src, y_slab, y_rod_top, eps_slab = 0.050, 0.045, 0.036, 5.0
    t_slab = 2 * (y_src - y_slab) / C0 * 1e12
    t_rod = 2 * ((y_src - y_slab) / C0
                 + (y_slab - y_rod_top) * np.sqrt(eps_slab) / C0) * 1e12

    def first_break(sig):
        env = np.abs(sig)
        return t[int(np.argmax(env > 0.2 * env.max()))]

    t0 = first_break(c)

    fig, ax = plt.subplots(2, 1, figsize=(6.4, 4.6), sharex=True)
    ax[0].plot(t, c / np.abs(c).max(), color=F.GREY, lw=1.2)
    ax[0].set_ylabel("free space\n(normalised)")
    ax[0].set_title("Stage 0 — the raw trace is useless; differencing recovers "
                    "the echoes")
    F.annotate(ax[0], "direct source-to-receiver coupling\n"
                      "pulse is ~140 ps wide, echoes arrive at 33 and 168 ps",
               "upper right")

    for sig, ref, lab, col, tp in ((b, c, "slab surface  (B − C)", F.BLUE, t_slab),
                                   (a, b, "PEC rod  (A − B)", F.ORANGE, t_rod)):
        d = sig - ref
        ax[1].plot(t - t0, d / np.abs(d).max(), color=col, label=lab)
        ax[1].axvline(tp, color=col, ls=":", lw=1.1)
        meas = first_break(d) - t0
        ax[1].plot([meas], [0], marker="v", color=col, ms=6, clip_on=False)
    ax[1].set_xlabel("time referenced to the direct break (ps)")
    ax[1].set_ylabel("differenced\n(normalised)")
    ax[1].set_xlim(-20, 400)
    ax[1].legend(loc="upper right")
    F.annotate(ax[1], "dotted = predicted analytically\n"
                      "▼ = measured   errors 0.3 and 1.3 ps\n"
                      "(time step is 1.18 ps)", "lower right")
    F.save(fig, "stage0_solver_verification",
           "solver reproduces both predicted echoes")


# --------------------------------------------------------------- stage 1 ---

def stage1():
    """Tissue models: dispersion, the Debye fit, and the 60 GHz argument."""
    from bonesim.materials import tissues as T
    from bonesim.materials.debye import fit_debye

    f = np.geomspace(1e9, 1e11, 400)
    band = np.geomspace(3e9, 11e9, 200)

    fig, ax = plt.subplots(1, 3, figsize=(11.0, 3.4))

    # (a) permittivity and conductivity across the working band
    for name, col in (("muscle", F.BLUE), ("blood", F.RED),
                      ("cortical_bone", F.GREEN), ("fat", F.ORANGE)):
        t = T.get(name)
        ax[0].plot(band / 1e9, t.eps_real(band), color=col, label=name)
    ax[0].set_xlabel("frequency (GHz)")
    ax[0].set_ylabel(r"$\epsilon_r$")
    ax[0].set_title("(a) dispersion across the working band")
    ax[0].legend(loc="center right")
    F.annotate(ax[0], "blood fills the fracture;\nthe contrast against bone\n"
                      "is 5.5× at 8.3 GHz", "upper right")

    # (b) how well two Debye poles reproduce Cole-Cole
    for name, col in (("muscle", F.BLUE), ("cortical_bone", F.GREEN)):
        t = T.get(name)
        fit = fit_debye(t, 3e9, 11e9, n_poles=2)
        ax[1].plot(band / 1e9, t.eps_real(band), color=col, lw=2.4, alpha=0.45,
                   label=f"{name}, Cole-Cole")
        ax[1].plot(band / 1e9, fit.eps_real(band), color=col, ls="--", lw=1.2,
                   label=f"{name}, 2-pole Debye")
    ax[1].set_xlabel("frequency (GHz)")
    ax[1].set_ylabel(r"$\epsilon_r$")
    ax[1].set_title("(b) FDTD needs Debye, not Cole-Cole")
    ax[1].legend(loc="center right")
    F.annotate(ax[1], "worst error 0.23%\nacross all seven tissues",
               "upper right")

    # (c) the central physics claim of the whole proposal
    d_field = T.MUSCLE.penetration_depth(f) * 1e3
    ax[2].loglog(f / 1e9, d_field, color=F.BLUE, label="muscle, field depth")
    ax[2].axhspan(3, 8, color=F.RED, alpha=0.13)
    ax[2].axvspan(3, 11, color=F.GREEN, alpha=0.10)
    ax[2].axvline(60, color=F.RED, ls="--", lw=1.2)
    d60 = float(T.MUSCLE.penetration_depth(60e9)) * 1e3
    ax[2].plot([60], [d60], "o", color=F.RED, ms=5)
    ax[2].set_xlabel("frequency (GHz)")
    ax[2].set_ylabel("penetration depth (mm)")
    ax[2].set_title("(c) why 60 GHz cannot image bone")
    ax[2].legend(loc="lower left")
    F.annotate(ax[2], f"tibia sits under 3–8 mm (red)\n"
                      f"at 60 GHz: {d60:.2f} mm\n"
                      f"green = the 3–11 GHz band used", "upper right")
    F.save(fig, "stage1_tissue_models",
           "Gabriel Cole-Cole, the Debye fit, and the 60 GHz argument")


# --------------------------------------------------------------- stage 2 ---

def stage2():
    """The processing chain, on analytic data where it is fast to show."""
    from bonesim.forward.analytic import AnalyticForward
    from bonesim.geometry.phantom import Fracture, Phantom

    f = np.linspace(3e9, 11e9, 201)
    x = np.arange(0.020, 0.0801, 0.001)
    fwd = AnalyticForward()
    ph = Phantom().with_fracture(Fracture(0.050, 0.001))
    d = fwd.scan(ph, f, x)
    raw = subtract_empty_scene(d, fwd.empty_scene(ph, f, x))
    s = np.linalg.svd(raw.s11, compute_uv=False)

    fig, ax = plt.subplots(1, 3, figsize=(11.0, 3.4))

    im = ax[0].imshow(np.abs(raw.s11), aspect="auto", cmap="viridis",
                      extent=[x[0] * 1e3, x[-1] * 1e3, f[-1] / 1e9, f[0] / 1e9])
    ax[0].set_xlabel("scan position (mm)")
    ax[0].set_ylabel("frequency (GHz)")
    ax[0].set_title("(a) raw |S11| — the fracture is invisible")
    ax[0].grid(False)
    fig.colorbar(im, ax=ax[0], label="|S11|")

    ax[1].semilogy(np.arange(1, 13), s[:12] / s[0], "o-", color=F.BLUE, ms=4)
    ax[1].set_xlabel("singular component")
    ax[1].set_ylabel(r"$\sigma_i / \sigma_0$")
    ax[1].set_title("(b) clutter dominates the spectrum")
    F.annotate(ax[1], "component 0 holds 99.999% of\nthe energy: the skin "
                      "reflection.\nThe fracture is 43 dB below it.",
               "upper right")

    img = migrate(remove_clutter_svd(raw, k=1), 9.0)
    F.image_axes(ax[2], img)
    ax[2].axvline(50.0, color="white", ls=":", lw=1.0, alpha=0.8)
    ax[2].set_title("(c) after SVD removal and migration")
    F.annotate(ax[2], "dotted = true fracture position", "upper left")
    F.save(fig, "stage2_processing_chain",
           "why clutter removal is not optional")


# --------------------------------------------------------------- stage 3 ---

def stage3():
    """First full-wave result: the fracture, found."""
    fr = ScanData.load(RUNS / "stage3_fractured.npz")
    it = ScanData.load(RUNS / "stage3_intact.npz")
    ref = ScanData(fr.f, fr.x, np.ones_like(fr.s11), fr.z_antenna, {})
    raw_f = Instrument().apply_post(subtract_empty_scene(fr, ref))
    raw_i = Instrument().apply_post(subtract_empty_scene(it, ref))
    s_f = np.linalg.svd(raw_f.s11, compute_uv=False)
    s_i = np.linalg.svd(raw_i.s11, compute_uv=False)

    fig, ax = plt.subplots(1, 3, figsize=(11.0, 3.4))

    ax[0].semilogy(np.arange(1, 9), s_f[:8] / s_f[0], "o-", color=F.RED,
                   ms=4, label="fractured")
    ax[0].semilogy(np.arange(1, 9), s_i[:8] / s_i[0], "s--", color=F.BLUE,
                   ms=4, label="intact")
    ax[0].set_xlabel("singular component")
    ax[0].set_ylabel(r"$\sigma_i / \sigma_0$")
    ax[0].set_title("(a) the fracture lives in component 2")
    ax[0].legend()
    F.annotate(ax[0], "~1000× more energy in\ncomponent 2 when fractured.\n"
                      "This is why k=1, not the\nproposal's k=2 or 3.",
               "upper right")

    # Both panels share the fractured peak as their 0 dB reference, so an
    # empty scene looks empty instead of having its noise floor stretched.
    prepared = []
    for d in (raw_i, raw_f):
        cl = remove_clutter_selective(d, EPS_AVG)[0]
        prepared.append((cl, migrate(cl, EPS_AVG)))
    ref = float(np.abs(prepared[1][1].data).max())

    for a, (cl, img), title in ((ax[1], prepared[0], "(b) intact"),
                                (ax[2], prepared[1], "(c) fractured")):
        F.image_axes(a, img, ref=ref, db_floor=-15.0)
        det = detect_snr(img, cl, z_window=(0.003, 0.020), x_margin=0.010)
        a.set_title(f"{title} — {det.ratio_db:.0f} dB")
        if title.startswith("(c)"):
            a.plot([det.x_peak * 1e3], [det.z_peak * 1e3], "o", mfc="none",
                   mec="white", ms=13, mew=1.4)
            F.annotate(a, f"found at x={det.x_peak*1e3:.1f} mm\n"
                          f"true 50.0 mm  →  0.2 mm error", "upper left")
    F.save(fig, "stage3_full_wave",
           "1 mm fracture under 6 mm overlay, no inverse crime")


# --------------------------------------------------------------- stage 4 ---

def stage4():
    """The brass-rod gate, and the depth sweep."""
    from bonesim.process.autofocus import autofocus
    from bonesim.process.clutter import remove_clutter_svd

    cases = [("norod", None, "control, no rod"),
             ("rod12", 0.012, "rod at 12 mm"),
             ("rod20", 0.020, "rod at 20 mm"),
             ("rod28", 0.028, "rod at 28 mm")]
    fig, ax = plt.subplots(1, 4, figsize=(13.0, 3.3))

    for a, (tag, z_true, label) in zip(ax, cases):
        p = RUNS / f"stage4_{tag}.npz"
        if not p.exists():
            a.set_visible(False)
            continue
        d = ScanData.load(p)
        ref = ScanData(d.f, d.x, np.ones_like(d.s11), d.z_antenna, {})
        c = Instrument().apply_post(subtract_empty_scene(d, ref))
        # Autofocus per case, exactly as run_stage4 does. A fixed permittivity
        # would put the recovered marker somewhere the reported result never
        # claimed, and the figure has to agree with the table.
        eps = autofocus(remove_clutter_svd(c, k=1), 4.0, 45.0,
                        n_coarse=21).eps_avg
        cl = remove_clutter_selective(c, eps)[0]
        img = migrate(cl, eps)
        det = detect_snr(img, cl, z_window=(0.005, 0.035), x_margin=0.010)

        # Each panel to its own peak. The question this row answers is "is the
        # rod found at each depth", not "how does amplitude fall" - the SNR in
        # each title already carries that, and a shared reference simply makes
        # the deepest rod invisible.
        F.image_axes(a, img, db_floor=-18.0)
        title = f"{label}\n{det.ratio_db:.0f} dB"
        if z_true is not None:
            title += f",  eps_avg {eps:.0f}"
        a.set_title(title)
        if z_true is not None:
            a.plot([50.0], [z_true * 1e3], "+", color="white", ms=14, mew=1.6)
            a.plot([det.x_peak * 1e3], [det.z_peak * 1e3], "o", mfc="none",
                   mec="white", ms=13, mew=1.6)
        if tag != "norod":
            a.set_ylabel("")
    F.annotate(ax[0], "black: nothing to find", "upper left")
    fig.suptitle("Stage 4 — the §9 gate: a 6 mm PEC rod found at every depth, "
                 "past the claimed 20 mm range.  + true,  o recovered",
                 fontsize=10)
    F.save(fig, "stage4_brass_rod_gate",
           "each panel scaled to its own peak; SNR in the titles carries "
           "the falloff")


# --------------------------------------------------------------- stage 5 ---

def stage5():
    """The antenna: geometry, and how far the match got."""
    from bonesim.antenna.vivaldi import Vivaldi, uwb_3_11
    nl = chr(10)   # heredoc-safe newline

    p = RUNS / "fig_stage5.npz"
    fig, ax = plt.subplots(1, 2, figsize=(10.6, 3.8),
                           gridspec_kw={"width_ratios": [1.25, 1]})

    ant = uwb_3_11()
    top, gnd = ant.upper_arm(80), ant.ground_arm(80)
    ax[0].fill(top[:, 0], top[:, 1], color=F.ORANGE, alpha=0.85,
               label="top face: microstrip + flare")
    ax[0].fill(gnd[:, 0], gnd[:, 1], color=F.BLUE, alpha=0.45,
               label="bottom face: ground, balun, flare")
    ax[0].axvline(ant.feed_len, color=F.GREY, ls=":", lw=1.0)
    ax[0].axvline(ant.taper_start, color=F.GREY, ls=":", lw=1.0)
    ax[0].set_xlabel("x (mm)")
    ax[0].set_ylabel("y (mm)")
    ax[0].set_aspect("equal")
    ax[0].set_title(f"(a) {ant.length:.0f} × {ant.sub_width:.0f} mm on "
                    f"{ant.substrate}")
    ax[0].legend(loc="lower right")
    F.annotate(ax[0], "dotted: microstrip → balun → flare", "upper left")

    # Both curves come from the same solver settings (-30 dB end criterion),
    # so the comparison is like for like rather than old-run against new.
    base = RUNS / "corrugations" / "plain_e3_s11.npz"
    tap = RUNS / "feedtaper" / "w450_l12_s11.npz"
    if base.exists() and tap.exists():
        zb, zt = np.load(base), np.load(tap)
        f = zb["f"] / 1e9
        dbb = 20 * np.log10(np.abs(zb["s11"]))
        dbt = 20 * np.log10(np.abs(zt["s11"]))
        ax[1].axvspan(3, 11, color=F.GREEN, alpha=0.10)
        # Shade what the taper recovered: matched now, not matched before.
        gained = (dbt <= -10) & (dbb > -10)
        ax[1].fill_between(f, -40, 0, where=gained, color=F.ORANGE,
                           alpha=0.22, step="mid")
        ax[1].plot(f, dbb, color=F.GREY, lw=1.1,
                   label="uniform 1.74 mm feed")
        ax[1].plot(f, dbt, color=F.BLUE, lw=1.5,
                   label="tapered 4.5 to 1.74 mm")
        ax[1].axhline(-10, color=F.RED, ls="--", lw=1.1)
        ax[1].set_xlabel("frequency (GHz)")
        ax[1].set_ylabel("|S11| (dB)")
        ax[1].set_ylim(-40, 0)
        ax[1].set_xlim(2, 12)
        ax[1].set_title("(b) match: 2.48 to 12.00 GHz")
        ax[1].legend(loc="lower left", fontsize=7)
        band = (zb["f"] >= 3e9) & (zb["f"] <= 11e9)
        F.annotate(ax[1], f"green = 3-11 GHz target{nl}"
                          f"orange = recovered by the taper{nl}"
                          f"covered {(dbt[band] <= -10).mean()*100:.1f}%, worst {dbt[band].max():.2f} dB",
                   "upper right")
    F.save(fig, "stage5_antenna",
           "the taper recovers 2.48-4.35 GHz; worst in band -9.98 dB")


# --------------------------------------------------------------- stage 6 ---

def stage6():
    """The matrix so far: detection against overlay."""
    # Dedupe by stem. Two cells were solved locally before the matrix moved to
    # Colab and exist in both directories; concatenating the globs counted them
    # twice, which showed up as "194 of 192" in the caption and, worse, plotted
    # those two intact points twice. Later entries win, matching the precedence
    # in run_stage7.py so both read the same cell for a duplicated stem.
    cells = sorted({p.stem: p for p in
                    sorted(RUNS.glob("matrix_colab/*.npz"))
                    + sorted(RUNS.glob("matrix/*.npz"))}.values())
    if len(cells) < 4:
        print(f"  stage 6: only {len(cells)} cells available, skipped")
        return
    by = {}
    for p in cells:
        d = ScanData.load(p)
        cl = _clean(d)
        det = detect_snr(migrate(cl, EPS_AVG), cl, z_window=(0.003, 0.024),
                         x_margin=0.010)
        by[p.stem] = det

    fig, ax = plt.subplots(1, 2, figsize=(10.0, 3.6))
    overlays = [0.0, 3.0, 6.0, 10.0]
    for state, col, mk in (("intact", F.BLUE, "s"), ("hairline", F.RED, "o"),
                           ("kerf04", F.ORANGE, "^")):
        xs, ys = [], []
        for ov in overlays:
            k = f"s00_{state}_ov{ov:04.1f}"
            if k in by:
                xs.append(ov)
                ys.append(by[k].ratio_db)
        if xs:
            lab = {"intact": "intact", "hairline": "0.2 mm kerf",
                   "kerf04": "0.4 mm kerf"}[state]
            ax[0].plot(xs, ys, mk + "-", color=col, ms=5, label=lab)
    ax[0].set_xlabel("soft-tissue overlay (mm)")
    ax[0].set_ylabel("detector score (dB)")
    ax[0].set_title("(a) the clinical envelope")
    ax[0].legend()
    F.annotate(ax[0], "specimen 0 only —\nno CI or LOSO until the\n"
                      "matrix completes", "lower left")

    seps, xs = [], []
    for ov in overlays:
        i, h = f"s00_intact_ov{ov:04.1f}", f"s00_hairline_ov{ov:04.1f}"
        if i in by and h in by:
            xs.append(ov)
            seps.append(by[h].ratio_db - by[i].ratio_db)
    ax[1].bar([str(int(v)) for v in xs], seps, color=F.GREEN, width=0.55)
    ax[1].set_xlabel("soft-tissue overlay (mm)")
    ax[1].set_ylabel("separation, fractured − intact (dB)")
    ax[1].set_title("(b) a 0.2 mm kerf survives 10 mm of overlay")
    for i, v in enumerate(seps):
        ax[1].text(i, v + 1.2, f"{v:.0f}", ha="center", fontsize=8)
    F.save(fig, "stage6_matrix_preview",
           f"{len(cells)} of 192 acquisitions")


def stage7():
    """The statistical result: separation, envelope, and the saturation."""
    import csv
    from bonesim.stats.analysis import auc, roc_curve
    nl = chr(10)   # heredoc-safe newline for the annotations

    cache = RUNS / "stage7_scores.csv"
    if not cache.exists():
        print("  stage 7: run scripts/run_stage7.py first, skipped")
        return
    rows = list(csv.reader(open(cache)))[1:]
    sc = np.array([float(r[6]) for r in rows])
    fr = np.array([r[4] == "True" for r in rows])
    ov = np.array([float(r[2]) for r in rows])
    kf = np.array([float(r[3]) for r in rows])

    fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.5))

    # (a) the distributions, which is what a perfect AUC actually means
    bins = np.linspace(0, 110, 45)
    ax[0].hist(sc[~fr], bins=bins, color=F.BLUE, alpha=0.85, label="intact")
    ax[0].hist(sc[fr], bins=bins, color=F.RED, alpha=0.85, label="fractured")
    ax[0].axvspan(sc[~fr].max(), sc[fr].min(), color=F.GREY, alpha=0.18)
    ax[0].set_xlabel("detector score (dB)")
    ax[0].set_ylabel("count")
    ax[0].set_title("(a) the classes do not overlap")
    ax[0].legend(loc="upper center")
    F.annotate(ax[0], f"gap {sc[fr].min()-sc[~fr].max():.0f} dB{nl}"
                      f"AUC = 1.000 is a lower{nl}bound, not a measurement",
               "upper right")

    # (b) score against overlay, both classes
    for lab, mask, col, mk in (("fractured", fr, F.RED, "o"),
                               ("intact", ~fr, F.BLUE, "s")):
        xs = sorted(set(ov))
        mean = [sc[mask & (ov == o)].mean() for o in xs]
        sd = [sc[mask & (ov == o)].std() for o in xs]
        ax[1].errorbar([o*1e3 for o in xs], mean, yerr=sd, fmt=mk + "-",
                       color=col, ms=5, capsize=3, label=lab)
    ax[1].set_xlabel("soft-tissue overlay (mm)")
    ax[1].set_ylabel("detector score (dB)")
    ax[1].set_title("(b) the clinical envelope")
    ax[1].legend()
    F.annotate(ax[1], f"the control rises with overlay;{nl}the margin"
                      f"{nl}narrows but never closes", "lower right")

    # (c) score against kerf, at the hardest overlay
    hard = ov == 0.010
    ax[2].axhline(sc[~fr & hard].max(), color=F.BLUE, ls="--", lw=1.2,
                  label="worst intact, 10 mm")
    ks = sorted(set(kf[fr]))
    ax[2].plot([k*1e3 for k in ks],
               [sc[fr & hard & (kf == k)].min() for k in ks],
               "o-", color=F.RED, ms=5, label="weakest fractured, 10 mm")
    ax[2].set_xscale("log")
    ax[2].set_xlabel("fracture width (mm)")
    ax[2].set_ylabel("detector score (dB)")
    ax[2].set_title("(c) worst case at the thickest overlay")
    ax[2].legend(loc="center right")
    F.annotate(ax[2], f"even the smallest kerf the grid{nl}can represent,{nl}"
                      f"under the thickest overlay,{nl}clears every intact limb",
               "lower left")
    F.save(fig, "stage7_statistics",
           "separation, envelope, and worst case")


STAGES = {0: stage0, 1: stage1, 2: stage2, 3: stage3,
          4: stage4, 5: stage5, 6: stage6, 7: stage7}


def main() -> int:
    F.use_style()
    want = [int(a) for a in sys.argv[1:]] or sorted(STAGES)
    print(f"writing to {F.FIGDIR}\n")
    for s in want:
        print(f"stage {s}")
        try:
            STAGES[s]()
        except FileNotFoundError as exc:
            print(f"  skipped: {exc}")
        except Exception as exc:                        # noqa: BLE001
            print(f"  FAILED: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
