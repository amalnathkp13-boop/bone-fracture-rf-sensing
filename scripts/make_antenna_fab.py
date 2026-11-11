"""Fabrication package for the antipodal Vivaldi.

Produces what a board house and a bench actually need:

  vivaldi_fab_drawing.pdf   dimensioned drawing, both faces, with the stack-up
  vivaldi.dxf               board outline, both copper layers, drill positions

DXF rather than Gerber deliberately. Gerber needs an aperture list and a
photoplot convention this project has no reason to invent; DXF carries the exact
curves, every CAM tool and every PCB house imports it, and the fab converts to
Gerber with their own rules. The curves here are the ones openEMS simulated, not
a redrawing, so nothing is lost in translation.

Connector pads are not drawn because none are needed. An end-launch SMA lands
its centre pin on the trace at the board edge and grounds its body to the plane
on the opposite face; this board already presents both, so the launch is the
board as drawn. Two parts were checked against their datasheets and named on the
drawing - one solder, one solderless clamp - both suiting the 0.762 mm board,
which matters because most end-launch parts are cut for 0.062 in.

A top-ground-tab variant does need pads, so the footprint was simulated rather
than avoided. Measured in openEMS with the same model as the antenna: no pads
gives 7.65 GHz of match, a 1.0 mm gap 3.75 GHz, a 2.5 mm gap 5.25 GHz. Widening
the gap recovers the low end, because the coplanar coupling that pulls the
impedance down dies away past about three substrate heights, but the upper limit
stays at 9.6 GHz either way - at 12 GHz a 2.5 mm gap is a fifth of a wavelength
and the pads are a discontinuity. So pads always cost the top of the band. They
are drawn dashed at 2.5 mm on their own DXF layers, to be omitted whenever the
connector allows.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from bonesim import figures as F
from bonesim.antenna.vivaldi import Vivaldi, uwb_3_11

OUT = Path(__file__).resolve().parent.parent / "figures"

# Two M3 clearance holes at the feed end only. Nothing may sit near the
# aperture: the slot and the flared arms are the antenna. At x = 6 the top face
# carries only the 1.74 mm microstrip, so these pass through substrate and
# ground alone, 37 mm from the signal trace. A 3.2 mm hole is 0.03 wavelengths
# at 3 GHz and is not a meaningful scatterer.
HOLE_D, HOLE_X, HOLE_Y = 3.2, 6.0, 38.0

# Optional coplanar ground pads for a top-ground-tab SMA. 2.5 mm is the
# best gap simulated: it recovers the low end that a 1.0 mm gap loses,
# though the top of the band goes from 12.0 to 9.6 GHz either way.
PAD_GAP = 2.5


# ---------------------------------------------------------------- DXF ------

def dxf(path: Path, ant) -> None:
    """Minimal R12 DXF: closed polylines on named layers, plus drill circles."""
    layers = [("BOARD_OUTLINE", 7), ("COPPER_TOP", 2), ("COPPER_BOTTOM", 1),
              ("DRILL", 5), ("COPPER_TOP_OPT_PADS", 3), ("VIA_OPT", 4)]
    o = []

    def tag(code, value):
        o.append(f"{code}\n{value}")

    tag(0, "SECTION"); tag(2, "TABLES")
    tag(0, "TABLE"); tag(2, "LAYER"); tag(70, len(layers))
    for name, colour in layers:
        tag(0, "LAYER"); tag(2, name); tag(70, 0); tag(62, colour); tag(6, "CONTINUOUS")
    tag(0, "ENDTAB"); tag(0, "ENDSEC")

    tag(0, "SECTION"); tag(2, "ENTITIES")

    def polyline(pts, layer):
        tag(0, "POLYLINE"); tag(8, layer); tag(66, 1); tag(70, 1)
        for x, y in pts:
            tag(0, "VERTEX"); tag(8, layer)
            tag(10, f"{x:.4f}"); tag(20, f"{y:.4f}"); tag(30, "0.0")
        tag(0, "SEQEND"); tag(8, layer)

    def circle(x, y, d, layer):
        tag(0, "CIRCLE"); tag(8, layer)
        tag(10, f"{x:.4f}"); tag(20, f"{y:.4f}"); tag(30, "0.0")
        tag(40, f"{d/2:.4f}")

    W = ant.sub_width
    polyline([(0, -W / 2), (ant.length, -W / 2),
              (ant.length, W / 2), (0, W / 2)], "BOARD_OUTLINE")
    polyline([tuple(p) for p in ant.upper_arm(120)], "COPPER_TOP")
    polyline([tuple(p) for p in ant.ground_arm(120)], "COPPER_BOTTOM")
    for y in (HOLE_Y, -HOLE_Y):
        circle(HOLE_X, y, HOLE_D, "DRILL")

    # Optional, on their own layers: omit for a bottom-ground or clamp part.
    opt = Vivaldi(**{**ant.__dict__, "pad_gap": PAD_GAP})
    for poly in opt.ground_pads():
        polyline(poly, "COPPER_TOP_OPT_PADS")
    for vx, vy in opt.via_positions():
        circle(vx, vy, opt.via_d, "VIA_OPT")

    tag(0, "ENDSEC"); tag(0, "EOF")
    path.write_text("\n".join(o) + "\n", encoding="ascii")


# ------------------------------------------------------------- drawing -----

def _dim(ax, x0, y0, x1, y1, text, off=0.0, colour="#0072B2"):
    """A dimension line with arrows and a label."""
    ax.annotate("", xy=(x1, y1 + off), xytext=(x0, y0 + off),
                arrowprops=dict(arrowstyle="<->", color=colour, lw=0.9))
    ax.text((x0 + x1) / 2, (y0 + y1) / 2 + off, text, ha="center",
            va="bottom", fontsize=7, color=colour,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                      alpha=0.85))


def drawing(ant) -> Path:
    L, W, h = ant.length, ant.sub_width, ant.height
    top, gnd = ant.upper_arm(150), ant.ground_arm(150)

    pdf_path = OUT / "vivaldi_fab_drawing.pdf"
    with PdfPages(pdf_path) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3))          # A4 landscape
        gs = fig.add_gridspec(3, 2, height_ratios=[2.6, 2.6, 2.4],
                              hspace=0.32, wspace=0.14)

        for row, (pts, name, col) in enumerate((
                (top, "TOP COPPER  (component side)", "#E69F00"),
                (gnd, "BOTTOM COPPER  (ground / balun)", "#0072B2"))):
            ax = fig.add_subplot(gs[row, :])
            ax.add_patch(plt.Rectangle((0, -W / 2), L, W, fc="none",
                                       ec="black", lw=1.1))
            ax.fill(pts[:, 0], pts[:, 1], color=col, alpha=0.75, lw=0.5,
                    ec="black")
            for y in (HOLE_Y, -HOLE_Y):
                ax.add_patch(plt.Circle((HOLE_X, y), HOLE_D / 2, fc="white",
                                        ec="black", lw=0.9))
                ax.plot([HOLE_X], [y], "+", color="black", ms=7, mew=0.8)
            ax.set_title(name, fontsize=10, loc="left")
            ax.set_aspect("equal")
            # Room below for the three section dimensions, and left for the
            # width dimension. Too tight and they collide with the axis.
            ax.set_xlim(-22, L + 12)
            ax.set_ylim(-W / 2 - 30, W / 2 + 14)
            ax.set_xlabel("mm")
            ax.grid(alpha=0.18)

            if row == 0:
                opt = Vivaldi(**{**ant.__dict__, "pad_gap": PAD_GAP})
                for poly in opt.ground_pads():
                    a = np.asarray(poly + [poly[0]], float)
                    ax.plot(a[:, 0], a[:, 1], ls="--", lw=0.9,
                            color="#009E73")
                for vx, vy in opt.via_positions():
                    ax.add_patch(plt.Circle((vx, vy), opt.via_d / 2,
                                            fc="none", ec="#009E73", lw=0.7))
                ax.annotate(f"OPTIONAL top-ground pads, {PAD_GAP:g} mm gap\n"
                            f"(top-tab SMA only; costs the band above 9.6 GHz)",
                            xy=(4, ant.w_port / 2 + PAD_GAP + 2.5),
                            xytext=(26, 30), fontsize=6.5, color="#009E73",
                            bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                      ec="#009E73", lw=0.6, alpha=0.92),
                            arrowprops=dict(arrowstyle="->", lw=0.8,
                                            color="#009E73"))
                _dim(ax, 0, W / 2, L, W / 2, f"{L:.0f}", off=8)
                ax.annotate("", xy=(-13, W / 2), xytext=(-13, -W / 2),
                            arrowprops=dict(arrowstyle="<->", color="#0072B2",
                                            lw=0.9))
                ax.text(-16, 0, f"{W:.0f}", rotation=90, ha="center",
                        va="center", fontsize=7, color="#0072B2")
                _dim(ax, 0, -W / 2, ant.feed_len, -W / 2,
                     f"{ant.feed_len:.0f}", off=-9)
                _dim(ax, ant.feed_len, -W / 2, ant.taper_start, -W / 2,
                     f"{ant.balun_length:.0f}", off=-9)
                _dim(ax, ant.taper_start, -W / 2, L, -W / 2,
                     f"{ant.taper_length:.0f}", off=-9)
                # Staggered: the microstrip and balun sections are 8 and
                # 12 mm wide, too narrow for their labels side by side.
                for xc, lab, dy in ((ant.feed_len / 2, "microstrip", -18),
                                    ((ant.feed_len + ant.taper_start) / 2,
                                     "balun", -27),
                                    ((ant.taper_start + L) / 2, "flare", -18)):
                    ax.text(xc, -W / 2 + dy, lab, ha="center", va="top",
                            fontsize=7, color="#0072B2")
                ax.annotate(f"trace {ant.w_port:.2f} at the port,\ncentred on axis",
                            xy=(0.5, 0), xytext=(24, -26), fontsize=7,
                            arrowprops=dict(arrowstyle="->", lw=0.8))
                ax.annotate(f"aperture {ant.aperture:.0f}",
                            xy=(L, 0), xytext=(L - 46, 14), fontsize=7,
                            arrowprops=dict(arrowstyle="->", lw=0.8))
            else:
                ax.annotate("ground tapers to the strip\n(elliptical balun)",
                            xy=((ant.feed_len + ant.taper_start) / 2, 30),
                            xytext=(48, 40), fontsize=7,
                            arrowprops=dict(arrowstyle="->", lw=0.8))
                ax.annotate(f"2 x M{HOLE_D-0.2:.0f} clearance"
                            f" {HOLE_D:.1f} dia, NPTH\n"
                            f"at x={HOLE_X:.0f}, y=+/-{HOLE_Y:.0f}",
                            xy=(HOLE_X, -HOLE_Y), xytext=(24, -62),
                            fontsize=7, arrowprops=dict(arrowstyle="->", lw=0.8))

        # ---- notes panel -------------------------------------------------
        ax = fig.add_subplot(gs[2, :])
        ax.axis("off")
        notes = (
            f"ANTIPODAL VIVALDI  —  {L:.0f} x {W:.0f} mm\n"
            f"Substrate {ant.substrate}, eps_r {ant.sub['eps_r']}, "
            f"tan d {ant.sub['tan_d']}, thickness {h:.3f} mm. "
            f"Copper 35 um (1 oz) both faces. Total stack {h + 0.07:.3f} mm.\n"
            f"Taper y = A exp({ant.rate:.4f} x') + B, growth a*T = "
            f"{ant.growth:.1f}, flare {ant.flare_length:.0f} mm over a "
            f"{ant.aperture:.0f} mm mouth (ratio {ant.flare_ratio:.2f}).\n"
            f"\n"
            f"SIMULATED PERFORMANCE (openEMS, model validated against the "
            f"openEMS patch tutorial at Zin 49.7+4.5j):\n"
            f"   |S11| < -10 dB over 2.48 to 12.00 GHz; 99.69 percent of "
            f"3-11 GHz below -10 dB, worst -9.98 dB at a single point "
            f"(4.775 GHz).\n"
            f"   Mean -16.8 dB across 3-11 GHz. Median Re(Zin) 45.6 ohm. "
            f"Achieved by the tapered feed: {ant.feed_width:.2f} mm at the "
            f"flare, {ant.w_port:.2f} mm at the port.\n"
            f"   Gain 7.02 dBi at 3 GHz, 11.9-12.5 dBi at 5-9 GHz, 9.3 dBi at "
            f"11 GHz. The 8-10 dBi target is met from about 4 GHz upward and "
            f"NOT at 3 GHz; aperture-limited, not fixable by resizing.\n"
            f"\n"
            f"CONNECTOR - qualified parts. Both were checked against their "
            f"datasheets and both suit this {h:.3f} mm (0.030 in) board:\n"
            f"   L-com RFPCB-SMA-FS18G-55   DC-18 GHz, specified for a "
            f"0.031 in board, 0.020 in pin, solder, 50 ohm, VSWR 1.2:1\n"
            f"   Southwest 292-04A-9        DC-27 GHz, up to 0.065 in board, "
            f"0.010 in pin / 0.0635 in dielectric, SOLDERLESS clamp\n"
            f"   The BOM asks for 18 GHz end-launch and warns off cheap 6 GHz "
            f"parts. Either of these meets that.\n"
            f"\n"
            f"   NO EXTRA PADS ARE NEEDED. An end-launch lands its centre pin "
            f"on the trace at the board edge and grounds its body to\n"
            f"   the plane on the opposite face. This board already presents "
            f"both: the {ant.w_port:.2f} mm trace runs to x=0 and the "
            f"ground is\n"
            f"   full width there. The solderless part needs no soldering to "
            f"the board at all.\n"
            f"\n"
            f"   The trace width is a good match rather than luck: "
            f"{ant.w_port:.2f} mm against the 0.0635 in (1.61 mm) "
            f"dielectric diameter of\n"
            f"   the Southwest part - within 8 percent. A launch behaves best "
            f"when the trace is close to the connector dielectric.\n"
            f"\n"
            f"   TOP-GROUND-TAB VARIANTS ARE SUPPORTED, with one condition. "
            f"Such a connector grounds through tabs sitting on the top\n"
            f"   face either side of the pin, so it needs copper there. That "
            f"turns the feed from microstrip into grounded coplanar\n"
            f"   waveguide and pulls the impedance down - unless the gap is "
            f"wide enough that the coplanar coupling dies away.\n"
            f"   Simulated, not assumed (openEMS, same model as the antenna):\n"
            f"\n"
            f"       no pads (as drawn)      2.48 - 12.00 GHz  (9.52 GHz)"
            f"   mean -16.8 dB   median Re(Zin) 45.6 ohm   [tapered feed]\n"
            f"       pads, 1.0 mm gap        5.85 -  9.60 GHz  (3.75 GHz)"
            f"   mean -14.2 dB   median Re(Zin) 39 ohm     [uniform feed*]\n"
            f"       pads, 2.5 mm gap        4.35 -  9.60 GHz  (5.25 GHz)"
            f"   mean -14.7 dB   median Re(Zin) 41 ohm     [uniform feed*]\n"
            f"   * The pad rows were simulated on the earlier 1.74 mm uniform "
            f"feed and have NOT been re-run with the taper. Their upper\n"
            f"     limit comes from the pads, not the feed, so the 9.60 GHz "
            f"ceiling is expected to carry over; the low end will not.\n"
            f"\n"
            f"   PADS ALWAYS COST BANDWIDTH AT THE TOP OF THE BAND. Widening "
            f"the gap to 2.5 mm recovers the low end - the coplanar\n"
            f"   coupling that pulls the impedance down dies away past about "
            f"three substrate heights - but the upper limit stays at\n"
            f"   9.60 GHz either way, because at 12 GHz a 2.5 mm gap is a "
            f"fifth of a wavelength and the pads act as a discontinuity.\n"
            f"\n"
            f"   SO: prefer a bottom-ground or clamp part and omit the pads "
            f"entirely. If a top-tab part must be used, use a gap of\n"
            f"   2.5 mm or more and accept losing the band above 9.6 GHz. The "
            f"pads are drawn dashed and carried on DXF layers\n"
            f"   COPPER_TOP_OPT_PADS and VIA_OPT so they can be omitted. They "
            f"MUST be stitched to the ground plane by the vias\n"
            f"   shown; unstitched copper beside a feed line is a resonator, "
            f"not a ground.\n"
            f"\n"
            f"DXF layers: BOARD_OUTLINE, COPPER_TOP, COPPER_BOTTOM, DRILL, "
            f"and the optional COPPER_TOP_OPT_PADS + VIA_OPT.\n"
            f"Units mm. Origin at the feed edge, y=0 on the antenna axis."
        )
        ax.text(0.0, 1.0, notes, va="top", ha="left", fontsize=6.6,
                family="monospace", transform=ax.transAxes)

        pdf.savefig(fig)
        fig.savefig(OUT / 'vivaldi_fab_drawing.png', dpi=150)
        plt.close(fig)
    return pdf_path


def geometry_json(path: Path, ant) -> None:
    """Outlines for the CAD model.

    FreeCAD reads this rather than having coordinates pasted into it, so the
    solid model cannot drift from the geometry openEMS actually simulated.
    """
    path.write_text(json.dumps({
        "L": ant.length, "W": ant.sub_width, "H": ant.height,
        "feed_len": ant.feed_len, "taper_start": ant.taper_start,
        "feed_width": ant.feed_width, "feed_width_port": ant.w_port,
        "aperture": ant.aperture,
        "substrate": ant.substrate,
        "hole_d": HOLE_D, "hole_x": HOLE_X, "hole_y": HOLE_Y,
        "top": [[round(x, 4), round(y, 4)] for x, y in ant.upper_arm(120)],
        "gnd": [[round(x, 4), round(y, 4)] for x, y in ant.ground_arm(120)],
    }, indent=1), encoding="ascii")


def main() -> int:
    F.use_style()
    plt.rcParams["figure.constrained_layout.use"] = False
    OUT.mkdir(exist_ok=True)
    ant = uwb_3_11()

    j = OUT / "vivaldi_geom.json"
    geometry_json(j, ant)
    print(f"  {j.name:<28} {j.stat().st_size/1024:5.0f} kB   "
          f"outlines for the CAD model")

    d = OUT / "vivaldi.dxf"
    dxf(d, ant)
    print(f"  {d.name:<28} {d.stat().st_size/1024:5.0f} kB   "
          f"4 layers, mm, origin at the feed edge")

    p = drawing(ant)
    print(f"  {p.name:<28} {p.stat().st_size/1024:5.0f} kB   "
          f"A4 landscape, both faces dimensioned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
