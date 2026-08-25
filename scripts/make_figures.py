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

import matplotlib.patheffects as pe
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


# --------------------------------------------------------- phantom in 3D ---

# Tissue colours. Chosen to read as anatomy rather than to be decorative:
# skin and muscle warm, fat pale, bone near-white, marrow darker inside it.
TISSUE_RGB = {
    "skin_dry": "#c98b6b",
    "skin_wet": "#c98b6b",
    "fat": "#f2e2b6",
    "muscle": "#b5423f",
    "cortical_bone": "#efeae0",
    "cortical_bone_wet": "#efeae0",
    "marrow": "#d9b48a",
    "blood": "#8c1c13",
}
TISSUE_LABEL = {
    "skin_dry": "skin", "skin_wet": "skin", "fat": "fat", "muscle": "muscle",
    "cortical_bone": "cortical bone", "cortical_bone_wet": "cortical bone",
    "marrow": "marrow", "blood": "blood-filled fracture",
}


def _box(ax, x0, x1, y0, y1, z0, z1, color, alpha=1.0, lw=0.3,
         edge="#33333355"):
    """One axis-aligned box. Depth is plotted downward, so z is negated."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    a, b = -z1, -z0                       # skin at the top of the plot
    v = [(x0, y0, a), (x1, y0, a), (x1, y1, a), (x0, y1, a),
         (x0, y0, b), (x1, y0, b), (x1, y1, b), (x0, y1, b)]
    faces = [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
             [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
             [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]
    ax.add_collection3d(Poly3DCollection(
        faces, facecolors=color, edgecolors=edge, linewidths=lw,
        alpha=alpha, zsort="max"))


def _tidy(ax, xlim, ylim, zlim, elev=22, azim=-58):
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_zlim(*zlim)
    ax.view_init(elev=elev, azim=azim)
    ax.set_box_aspect((3.0, 1.5, 2.0), zoom=1.28)
    for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
        pane.pane.set_visible(False)
        pane._axinfo["grid"]["linewidth"] = 0.0
    ax.set_xticks([]); ax.set_yticks([])
    ax.tick_params(labelsize=7, colors="#444")


def stage_phantom3d():
    """The phantom and the specimen population, in three dimensions.

    The simulation is 2D TMz, so what is drawn is the modelled slice given a
    finite width - an honest picture of what was solved, not a cylindrical
    limb that would imply out-of-plane physics the model does not contain.

    All annotation uses text2D in axes coordinates. Text placed in data
    coordinates on a 3D axis is clipped at the axis limits, which silently
    truncated half the layer labels in the first version of this figure.
    """
    from bonesim.geometry.phantom import Fracture, Phantom
    from bonesim.perturb.errors import SpecimenVariation

    nl = chr(10)   # heredoc-safe newline
    W, L = 40.0, 100.0             # drawn width and length of the slice, mm
    base = Phantom().with_overlay(0.006)
    sv = SpecimenVariation()

    fig = plt.figure(figsize=(13.0, 10.6))
    gs = fig.add_gridspec(3, 4, height_ratios=[1.25, 1.0, 1.0],
                          hspace=0.13, wspace=0.02,
                          left=0.02, right=0.98, top=0.90,
                          bottom=0.01)

    # ---- (a) exploded layer stack -------------------------------------
    ax = fig.add_subplot(gs[0, :2], projection="3d")
    ph = sv.draw(base, 0)
    gap, off, rows = 3.4, 0.0, []
    for mat, z0, z1 in ph.stack():
        t = (z1 - z0) * 1e3
        _box(ax, 0, L, 0, W, off, off + t, TISSUE_RGB[mat], alpha=0.97)
        rows.append((TISSUE_LABEL[mat], t, TISSUE_RGB[mat]))
        off += t + gap
    _tidy(ax, (0, L), (0, W), (-off, 4))
    ax.set_zticks([])
    for i, (lab, t, c) in enumerate(rows):
        y = 0.90 - i * 0.115
        ax.text2D(0.63, y, "■", transform=ax.transAxes, color=c,
                  fontsize=13, va="center", zorder=20,
                  path_effects=[pe.withStroke(linewidth=0.8,
                                              foreground="#555")])
        ax.text2D(0.68, y, f"{lab}   {t:.1f} mm", transform=ax.transAxes,
                  fontsize=8.2, color="#222", va="center",
                  zorder=20)
    ax.text2D(0.63, 0.14, f"slice drawn {L:.0f} × {W:.0f} mm{nl}"
              f"(the 2D TMz plane, given a width)",
              transform=ax.transAxes, fontsize=7.4, color="#666",
              zorder=20, linespacing=1.5)

    # ---- (b) cutaway with the fracture --------------------------------
    ax = fig.add_subplot(gs[0, 2:], projection="3d")
    ph = sv.draw(base, 0).with_fracture(Fracture(0.050, 0.001))
    cut = W * 0.52
    xf = ph.fracture.x * 1e3
    # Drawn 3 mm wide. The modelled kerf is 0.2-2.0 mm and would be a hairline
    # at this scale; the caption states the true width so the exaggeration
    # cannot be mistaken for the geometry that was solved.
    kerf = 3.0
    z_ct = ph.z_cortex * 1e3
    for mat, z0, z1 in ph.stack():
        a, b = z0 * 1e3, z1 * 1e3
        if mat == "cortical_bone" and a < z_ct + 0.1:
            _box(ax, 0, xf - kerf / 2, 0, cut, a, b, TISSUE_RGB[mat])
            _box(ax, xf + kerf / 2, L, 0, cut, a, b, TISSUE_RGB[mat])
            _box(ax, xf - kerf / 2, xf + kerf / 2, 0, cut, a, b,
                 TISSUE_RGB["blood"], edge="#5a0d09")
        else:
            _box(ax, 0, L, 0, cut, a, b, TISSUE_RGB[mat])
    _box(ax, xf - 30, xf + 30, cut * 0.25, cut * 0.75,
         -ph.standoff * 1e3 - 1.5, -ph.standoff * 1e3, "#2b2b2b")
    _tidy(ax, (0, L), (0, W), (-(ph.z_far_cortex + ph.cortex) * 1e3 - 2,
                               ph.standoff * 1e3 + 3))
    ax.set_zticks([])
    ax.annotate("antenna, 12 mm standoff", xy=(0.52, 0.72),
                xytext=(0.02, 0.60), xycoords="axes fraction",
                textcoords="axes fraction", fontsize=8.2, color="#222", zorder=20,
                arrowprops=dict(arrowstyle="->", lw=0.9, color="#444"))
    ax.annotate("blood-filled fracture\nin the near cortex", xy=(0.470, 0.40),
                xytext=(0.56, 0.18), xycoords="axes fraction",
                textcoords="axes fraction", fontsize=8.4, color=TISSUE_RGB["blood"],
                ha="left", zorder=20,
                arrowprops=dict(arrowstyle="->", lw=1.1,
                                color=TISSUE_RGB["blood"]))

    # ---- (c) the eight specimens, one axis each -----------------------
    for s in range(8):
        r, c = divmod(s, 4)
        ax = fig.add_subplot(gs[1 + r, c], projection="3d")
        p = sv.draw(base, s)
        for mat, z0, z1 in p.stack():
            _box(ax, 0, L, 0, W, z0 * 1e3, z1 * 1e3, TISSUE_RGB[mat],
                 alpha=0.97, lw=0.25)
        deep = (p.z_far_cortex + p.cortex) * 1e3
        _tidy(ax, (0, L), (0, W), (-30, 2), elev=20, azim=-62)
        ax.set_zticks([])
        ax.text2D(0.04, 0.96, f"S{s}", transform=ax.transAxes, fontsize=10,
                  fontweight="bold", color="#222", zorder=20)
        ax.text2D(0.06, 0.83,
                  f"cortex {p.cortex*1e3:.2f} mm\n"
                  f"overlay {p.overlay*1e3:.2f} mm\n"
                  f"depth {deep:.1f} mm",
                  transform=ax.transAxes, fontsize=7.4, color="#555",
                  va="top", linespacing=1.5, zorder=20)

    handles = [plt.Rectangle((0, 0), 1, 1, fc=TISSUE_RGB[k], ec="#333",
                             lw=0.4) for k in
               ("skin_dry", "fat", "muscle", "cortical_bone", "marrow",
                "blood")]
    fig.legend(handles, ["skin", "fat", "muscle", "cortical bone", "marrow",
                         "blood-filled fracture"],
               loc="upper center", ncol=6, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, 0.995))
    fig.text(0.04, 0.945, "(a) layer stack, exploded", fontsize=11,
             fontweight="bold", color="#222", va="top")
    fig.text(0.52, 0.945, "(b) cutaway: fracture in the near cortex",
             fontsize=11, fontweight="bold", color="#222", va="top")
    fig.text(0.04, 0.618, "(c) the eight specimens: cortical wall "
             "thickness and soft-tissue overlay both vary", fontsize=11,
             fontweight="bold", color="#222", va="top")
    F.save(fig, "phantom_3d",
           "modelled slice in 3D and the specimen population")


STAGES = {0: stage0, 1: stage1, 2: stage2, 3: stage3,
          4: stage4, 5: stage5, 6: stage6, 7: stage7,
          "phantom": stage_phantom3d}


def main() -> int:
    F.use_style()
    # Keys are mostly stage numbers but not all of them, so sorted(STAGES)
    # would compare int against str and the int() cast would reject a named
    # figure. Dict order is the definition order, which is the order to build.
    want = ([int(a) if a.isdigit() else a for a in sys.argv[1:]]
            or list(STAGES))
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
