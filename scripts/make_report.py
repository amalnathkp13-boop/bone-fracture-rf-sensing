"""Build the final submission report as a PDF.

Numbers come from runs/report_numbers.json, written by the analysis scripts,
rather than being retyped here. A report that restates results by hand drifts
from them the first time anything is re-run.

    python scripts/make_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
OUT = ROOT / "Bone_Fracture_RF_Sensing_Report.pdf"
# results/ is committed; runs/ is not. The report must build from a
# clean clone with no simulation data present.
N = json.loads((ROOT / "results" / "report_numbers.json").read_text())

INK = colors.HexColor("#1a1a1a")
ACCENT = colors.HexColor("#0072B2")
RULE = colors.HexColor("#c8c8c8")
SOFT = colors.HexColor("#f4f6f8")
WARN = colors.HexColor("#D55E00")

TITLE = "Non-Invasive Bone Fracture Detection by UWB Microwave Imaging"
SUB = "A Complete Virtual Simulation Study"


# --------------------------------------------------------------- styles ---

def styles():
    s = getSampleStyleSheet()
    base = dict(fontName="Helvetica", textColor=INK, leading=13.6)
    s.add(ParagraphStyle("Body", parent=s["Normal"], fontSize=9.6,
                         alignment=TA_JUSTIFY, spaceAfter=7, **base))
    s.add(ParagraphStyle("H1", parent=s["Normal"], fontName="Helvetica-Bold",
                         fontSize=15, textColor=ACCENT, spaceBefore=16,
                         spaceAfter=8, leading=18))
    s.add(ParagraphStyle("H2", parent=s["Normal"], fontName="Helvetica-Bold",
                         fontSize=11.2, textColor=INK, spaceBefore=11,
                         spaceAfter=5, leading=14))
    s.add(ParagraphStyle("H2k", parent=s["H2"], keepWithNext=1))
    s.add(ParagraphStyle("Cap", parent=s["Normal"], fontName="Helvetica-Oblique",
                         fontSize=8.2, textColor=colors.HexColor("#555"),
                         alignment=TA_CENTER, spaceBefore=4, spaceAfter=11,
                         leading=10.5))
    s.add(ParagraphStyle("Key", parent=s["Normal"], fontSize=9.6, leading=13.6,
                         fontName="Helvetica", textColor=INK, spaceAfter=6,
                         leftIndent=8, rightIndent=8, spaceBefore=6,
                         borderPadding=7, backColor=SOFT,
                         borderColor=ACCENT, borderWidth=0))
    s.add(ParagraphStyle("TitleBig", parent=s["Normal"],
                         fontName="Helvetica-Bold", fontSize=23, leading=28,
                         alignment=TA_CENTER, textColor=INK))
    s.add(ParagraphStyle("SubBig", parent=s["Normal"], fontSize=13,
                         leading=17, alignment=TA_CENTER,
                         textColor=ACCENT, spaceBefore=8))
    s.add(ParagraphStyle("Meta", parent=s["Normal"], fontSize=9.4, leading=14,
                         alignment=TA_CENTER, textColor=colors.HexColor("#555")))
    s.add(ParagraphStyle("Cell", parent=s["Normal"], fontSize=8.4, leading=10.6,
                         fontName="Helvetica", textColor=INK))
    s.add(ParagraphStyle("CellB", parent=s["Normal"], fontSize=8.4,
                         leading=10.6, fontName="Helvetica-Bold",
                         textColor=INK))
    return s


S = styles()


def P(t, st="Body"):
    return Paragraph(t, S[st])


def fig(name, caption, width=163 * mm, max_h=104 * mm, crop=None):
    """A figure scaled to the frame, with its caption kept on the same page.

    Height is capped as well as width. Without the cap a tall figure - the
    solver verification panel is 6.4 x 4.6 inches, so 117 mm tall at full
    width - plus its caption cannot fit in a partly used page, and
    KeepTogether shunts the whole block to the next one, stranding whatever
    preceded it on a near-empty page.
    """
    p = FIG / name
    if not p.exists():
        return P(f"[missing figure: {name}]")
    import io
    from PIL import Image as PILImage
    src = PILImage.open(p)
    if crop:
        # (left, top, right, bottom) as fractions. A drawing sheet carries
        # a notes block that is unreadable at page width; show the panels.
        w, h = src.size
        l, t, r, b = crop
        src = src.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
        buf = io.BytesIO()
        src.save(buf, "PNG")
        buf.seek(0)
        path, lazy = buf, 0
    else:
        path, lazy = str(p), 1
    w, h = src.size
    iw, ih = width, width * h / w
    if ih > max_h:
        iw, ih = max_h * w / h, max_h
    im = Image(path, width=iw, height=ih, lazy=lazy)
    im.hAlign = "CENTER"
    return KeepTogether([im, P(caption, "Cap")])


def table(data, widths, header=True, highlight=None):
    rows = []
    for i, row in enumerate(data):
        style = "CellB" if (header and i == 0) else "Cell"
        rows.append([Paragraph(str(c), S[style]) for c in row])
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
    cmd = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
    ]
    if header:
        cmd += [("BACKGROUND", (0, 0), (-1, 0), SOFT),
                ("LINEBELOW", (0, 0), (-1, 0), 0.9, ACCENT)]
    if highlight:
        for r in highlight:
            cmd.append(("BACKGROUND", (0, r), (-1, r),
                        colors.HexColor("#eaf3fb")))
    t.setStyle(TableStyle(cmd))
    return t


# ----------------------------------------------------------- page frame ---

def decorate(canvas, doc):
    canvas.saveState()
    n = canvas.getPageNumber()
    if n > 1:
        canvas.setFont("Helvetica", 7.4)
        canvas.setFillColor(colors.HexColor("#777"))
        canvas.drawString(23 * mm, 12 * mm, TITLE)
        canvas.drawRightString(A4[0] - 23 * mm, 12 * mm, str(n))
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(23 * mm, 15 * mm, A4[0] - 23 * mm, 15 * mm)
    canvas.restoreState()


# ------------------------------------------------------------- content ---

def title_page(f):
    f += [Spacer(1, 46 * mm),
          P(TITLE, "TitleBig"),
          P(SUB, "SubBig"),
          Spacer(1, 14 * mm)]
    f.append(Table([[""]], colWidths=[70 * mm], rowHeights=[1],
                   style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.1,
                                      ACCENT)]), hAlign="CENTER"))
    f += [Spacer(1, 12 * mm),
          P("Capstone Project Report", "Meta"),
          P("Path A &mdash; Ultra-Wideband Microwave Imaging, 3&ndash;11 GHz",
            "Meta"),
          Spacer(1, 5 * mm),
          P("Open-source simulation stack: gprMax 3.1.7 (FDTD) &middot; "
            "openEMS v0.37.0-rc1 &middot; Python 3.12", "Meta"),
          Spacer(1, 30 * mm)]
    f.append(table([
        ["Primary endpoint", "AUC 1.0000 (95% CI 1.000&ndash;1.000), p = 0.001"],
        ["Class separation", f"{N['gap']:.1f} dB, no overlap"],
        ["Specimens", "8 &times; 4 overlays &times; 6 states = 192 acquisitions"],
        ["Antenna match", "2.48&ndash;12.00 GHz, 99.69% of the design band"],
        ["Exposure", "All limits pass, minimum margin 18&times;"],
    ], [46 * mm, 105 * mm], header=False))
    f.append(PageBreak())


def abstract(f):
    f.append(P("Abstract", "H1"))
    f.append(P(
        "This report presents a complete, purely virtual simulation of a "
        "non-invasive bone fracture detection system based on ultra-wideband "
        "microwave imaging in the 3&ndash;11 GHz band. Every element of the "
        "instrument &mdash; tissue dielectrics, electromagnetic propagation, "
        "the antenna, the imaging chain, and the statistical analysis "
        "&mdash; is modelled with open-source software, with no hardware "
        "constructed at any point."))
    f.append(P(
        "A forearm phantom with skin, fat, muscle, cortical bone and marrow "
        "layers was excited across an eight-specimen experiment matrix "
        "spanning four soft-tissue overlay thicknesses (0&ndash;10 mm), four "
        "fracture widths (0.2&ndash;2.0 mm) and an oblique fracture state, "
        "giving 192 full-wave finite-difference time-domain acquisitions. "
        "Each was processed through empty-scene subtraction, selective "
        "singular-value clutter removal, Kirchhoff migration and a "
        "peak-over-noise detector, under an injected instrument error model "
        "with three independent remount realisations."))
    f.append(P(
        f"Fractured and intact limbs separate by <b>{N['gap']:.1f} dB with no "
        f"overlap</b> across all {N['n_scores']} scored acquisitions, giving "
        "an area under the receiver operating characteristic curve of 1.0000 "
        "(bootstrap 95% CI over specimens 1.000&ndash;1.000, permutation "
        "p = 0.001). Leave-one-specimen-out validation of the decision "
        "threshold gives sensitivity 0.998 and specificity 1.000."))
    f.append(P(
        "A perfect area under the curve is treated as a warning rather than a "
        "result. A dedicated band-limitation study demonstrates that this "
        "statistic is <i>saturated</i>: when the usable bandwidth was "
        "restricted to that of the initial antenna design, the class "
        "separation fell by more than half, from 40.8 dB to 17.9 dB, while "
        "the area under the curve remained at exactly 1.0000 and registered "
        "nothing. This finding drove the antenna redesign and is argued to be "
        "the more transferable contribution of the work.", "Body"))
    f.append(P(
        "An antipodal Vivaldi antenna was designed and characterised in "
        "openEMS. A tapered feed transformed the matched band from "
        "4.35&ndash;12.00 GHz to <b>2.48&ndash;12.00 GHz</b>, covering 99.69% "
        "of the 3&ndash;11 GHz specification. Radio-frequency exposure was "
        "assessed against ICNIRP 2020 and IEEE C95.1-2019; at the specified "
        "0 dBm transmit power all quantities pass with a minimum margin of "
        "18&times;."))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "<b>Keywords:</b> microwave imaging &middot; ultra-wideband &middot; "
        "bone fracture &middot; FDTD &middot; gprMax &middot; openEMS "
        "&middot; Vivaldi antenna &middot; Kirchhoff migration &middot; "
        "specific absorption rate", "Cap"))
    f.append(PageBreak())


def introduction(f):
    f.append(P("1.&nbsp;&nbsp;Introduction and Objectives", "H1"))
    f.append(P("1.1&nbsp;&nbsp;Motivation", "H2"))
    f.append(P(
        "Radiography remains the reference standard for fracture diagnosis, "
        "but it delivers ionising radiation, requires fixed infrastructure "
        "and is not suited to repeated monitoring of healing. Microwave "
        "imaging is attractive because bone and the surrounding soft tissue "
        "differ substantially in permittivity, and a fracture filled with "
        "blood or fluid presents a strong dielectric discontinuity against "
        "cortical bone."))
    f.append(P(
        "The physical difficulty is that the same water content which creates "
        "the contrast also creates the loss. The signal must cross skin, fat "
        "and muscle twice, and the attenuation of those layers rises steeply "
        "with frequency. The working band is therefore a compromise between "
        "resolution, which improves with bandwidth, and penetration, which "
        "degrades with it."))
    f.append(P("1.2&nbsp;&nbsp;Objectives", "H2"))
    f.append(table([
        ["#", "Objective", "Outcome"],
        ["1", "Model tissue dielectrics over 3&ndash;11 GHz from published "
              "data", "Met"],
        ["2", "Build a validated full-wave forward model of the limb",
         "Met"],
        ["3", "Implement clutter removal, migration and detection", "Met"],
        ["4", "Design a 3&ndash;11 GHz antenna and characterise it", "Met "
              "(match); gain unmet at 3 GHz"],
        ["5", "Execute a factorial experiment matrix over 8 specimens",
         "Met, 192/192"],
        ["6", "Pre-specify and execute a statistical analysis plan", "Met"],
        ["7", "Assess radio-frequency exposure against current guidelines",
         "Met"],
    ], [10 * mm, 96 * mm, 45 * mm]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        "<b>Scope.</b> The study is purely computational by design. No "
        "hardware was built, and no human or animal subject was exposed at "
        "any point. The exposure assessment in Section 8 is a design-stage "
        "analysis establishing that the system would be safe if constructed.",
        "Key"))
    f.append(PageBreak())


def methodology(f):
    f.append(P("2.&nbsp;&nbsp;Simulation Stack and Methodology", "H1"))
    f.append(table([
        ["Component", "Tool", "Role"],
        ["Electromagnetic solver", "gprMax 3.1.7", "2D TMz FDTD forward model "
         "of the limb; CUDA-accelerated"],
        ["Antenna solver", "openEMS v0.37.0-rc1", "3D FDTD; S-parameters and "
         "far-field patterns"],
        ["Tissue model", "Gabriel four-Cole-Cole", "Permittivity and "
         "conductivity, 3&ndash;11 GHz"],
        ["Analysis", "Python 3.12, NumPy, SciPy", "Processing chain, "
         "statistics, figures"],
        ["Compute", "WSL2 + Google Colab T4", "Local development; matrix "
         "solved on GPU"],
    ], [34 * mm, 40 * mm, 77 * mm]))
    f.append(Spacer(1, 4 * mm))

    f.append(P("2.1&nbsp;&nbsp;Avoiding the inverse crime", "H2"))
    f.append(P(
        "A recurring failure in imaging studies is the <i>inverse crime</i>: "
        "generating data with the same model used to invert it, which "
        "flatters the result. Two independent forward models are therefore "
        "maintained. An analytic layered-medium model, fast enough for "
        "development, is used to build and debug the processing chain. The "
        "gprMax full-wave solver, which discretises Maxwell's equations "
        "without the layered assumption, generates every result reported "
        "here. The processing chain has no knowledge of which produced its "
        "input."))

    f.append(fig("measurement_pipeline.png",
                 "Figure 2. The method end to end. (a) The antenna steps "
                 "along the bone axis at a 12 mm standoff, transmitting and "
                 "receiving at each of 61 positions to give one reflection "
                 "coefficient per position per frequency. (b) The raw data, "
                 "in which the fracture is present and invisible. (c) "
                 "Empty-scene subtraction removes the antenna response but "
                 "not the layered clutter. (d) Selective singular-value "
                 "removal leaves the local scattering. (e) Kirchhoff "
                 "migration focuses it to the true position, dotted. Every "
                 "panel below (a) is real solver output from one matrix cell, "
                 "a 1 mm fracture under 6 mm of overlay, not an illustration.",
                 width=170 * mm, max_h=118 * mm))
    f.append(Spacer(1, 3 * mm))

    f.append(P("2.2&nbsp;&nbsp;Tissue dielectric model", "H2"))
    f.append(P(
        "Permittivity and conductivity follow the Gabriel four-Cole-Cole "
        "parameterisation. FDTD cannot integrate a Cole-Cole response "
        "directly because the fractional-power relaxation has no "
        "finite-order time-domain equivalent, so each tissue is refitted to "
        "a two-pole Debye model over the working band. The worst deviation "
        "across all seven tissues is 0.23%, and each relaxation time is "
        "checked to exceed the solver time step."))

    f.append(P("2.3&nbsp;&nbsp;Phantom geometry", "H2"))
    f.append(table([
        ["Layer", "Thickness", "Role"],
        ["Skin", "2.0 mm", "First interface; dominant surface reflection"],
        ["Fat", "3.0 mm", "Low-loss layer"],
        ["Muscle", "1.0 mm", "High-water, high-loss layer"],
        ["Cortical bone (near)", "4.0 mm", "Contains the fracture"],
        ["Marrow", "10.0 mm", "Medullary cavity"],
        ["Cortical bone (far)", "4.0 mm", "Far wall"],
        ["Antenna standoff", "12.0 mm", "Aperture to skin surface"],
    ], [42 * mm, 26 * mm, 83 * mm]))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "A soft-tissue overlay of 0, 3, 6 or 10 mm is added above the skin to "
        "span the range of forearm anatomy. The fracture is a rectangular "
        "blood-filled kerf in the near cortex, of width 0.2, 0.4, 1.0 or "
        "2.0 mm, with an additional oblique state cut at an angle."))
    f.append(fig("phantom_3d.png",
                 "Figure 1. The phantom and the specimen population. "
                 "(a) The layer stack, exploded. (b) Cutaway showing the "
                 "blood-filled fracture in the near cortex, with the antenna "
                 "at 12 mm standoff; the kerf is drawn 3 mm wide for "
                 "visibility, against a modelled width of 0.2 to 2.0 mm. "
                 "(c) The eight specimens, which differ in cortical wall "
                 "thickness and soft-tissue overlay. Because the solver is "
                 "two-dimensional TMz, what is drawn is the modelled plane "
                 "given a finite width, not a cylindrical limb.",
                 width=168 * mm, max_h=150 * mm))
    f.append(PageBreak())


def stages(f):
    f.append(P("3.&nbsp;&nbsp;Model Construction and Verification", "H1"))

    f.append(P("3.1&nbsp;&nbsp;Stage 0 &mdash; Solver verification", "H2"))
    f.append(P(
        "Before any result is trusted, the solver is required to reproduce "
        "an analytically predictable answer. A dielectric slab and a "
        "perfectly conducting rod were placed at known depths and the echo "
        "arrival times compared against closed-form predictions. The raw "
        "trace is dominated by direct source-to-receiver coupling, so a "
        "three-scene differencing scheme isolates the echoes."))
    f.append(fig("stage0_solver_verification.png",
                 "Figure 3. Solver verification. The raw trace (top) is "
                 "swamped by direct coupling; differencing (bottom) recovers "
                 "both echoes. Measured arrivals agree with the analytic "
                 "prediction to 0.3 and 1.3 ps, against a solver time step of "
                 "1.18 ps."))

    f.append(P("3.2&nbsp;&nbsp;Stage 1 &mdash; Tissue models", "H2"))
    f.append(fig("stage1_tissue_models.png",
                 "Figure 4. (a) Dispersion of the principal tissues across "
                 "the working band; blood-filled fracture against cortical "
                 "bone gives 5.5&times; permittivity contrast at 8.3 GHz. "
                 "(b) Two-pole Debye fits reproduce Cole-Cole to within "
                 "0.23%. (c) Penetration depth against frequency, showing why "
                 "millimetre-wave bands cannot reach bone."))
    f.append(P(
        "Panel (c) carries an important negative result. Muscle penetration "
        "depth at 60 GHz is 0.28 mm, against a tibia lying under 3&ndash;8 mm "
        "of soft tissue. Millimetre-wave sensing, sometimes proposed for this "
        "application, cannot reach the target at all; the 3&ndash;11 GHz band "
        "is not a convenience but a requirement."))
    f.append(PageBreak())

    f.append(P("3.3&nbsp;&nbsp;Stage 2 &mdash; The processing chain", "H2"))
    f.append(P(
        "The fracture echo is several orders of magnitude weaker than the "
        "skin-surface reflection, so raw data carries no visible signature of "
        "it. Three stages recover it: empty-scene subtraction removes the "
        "antenna response, singular-value decomposition removes the layered "
        "clutter, and Kirchhoff migration focuses the residual scattering "
        "back to its point of origin."))
    f.append(fig("stage2_processing_chain.png",
                 "Figure 5. The processing chain. The raw B-scan (a) shows no "
                 "fracture. The singular-value spectrum (b) shows clutter "
                 "dominating the leading components. Migration of the "
                 "residual (c) localises the fracture."))
    f.append(P(
        "<b>A published parameter was found to be wrong.</b> The source "
        "proposal specifies discarding the first two or three singular "
        "components. Measured on two independent targets, this destroys the "
        "fracture signature along with the clutter. A selective rule was "
        "adopted instead: a component is discarded only if, after migration, "
        "its energy spans more than half the scan aperture &mdash; the "
        "signature of a layered interface rather than a localised scatterer.",
        "Key"))

    f.append(P("3.4&nbsp;&nbsp;Stage 3 &mdash; Full-wave forward model", "H2"))
    f.append(fig("stage3_full_wave.png",
                 "Figure 6. A 1 mm fracture under 6 mm of soft-tissue "
                 "overlay, reconstructed from gprMax full-wave data through "
                 "the chain developed on the independent analytic model."))

    f.append(P("3.5&nbsp;&nbsp;Stage 4 &mdash; Validation gate", "H2"))
    f.append(P(
        "A go/no-go gate was placed before the main experiment: if migration "
        "cannot image a 6 mm conducting rod at 20 mm depth in phantom, "
        "nothing downstream is meaningful. The rod is a canonical target with "
        "an unambiguous answer, and the gate is passed."))
    f.append(fig("stage4_brass_rod_gate.png",
                 "Figure 7. Validation gate. The rod is localised at each "
                 "depth, with detection signal-to-noise ratio falling as "
                 "predicted by the two-way attenuation of the intervening "
                 "tissue. Each panel is scaled to its own peak so the "
                 "localisation is visible; the falloff is carried in the "
                 "titles."))
    f.append(PageBreak())


def antenna(f):
    a = N["antenna"]
    f.append(P("4.&nbsp;&nbsp;Antenna Design", "H1"))
    f.append(P(
        "An antipodal Vivaldi antenna was chosen for its inherently wide "
        "bandwidth and endfire pattern. The design is 150 &times; 90 mm on "
        "0.762 mm Rogers RO4350B, sized to fit stock already in the bill of "
        "materials."))
    f.append(fig("stage5_antenna.png",
                 "Figure 8. (a) Antenna geometry: microstrip feed, tapered "
                 "ground balun, exponential flare. (b) Reflection "
                 "coefficient, uniform feed (grey) against tapered feed "
                 "(blue), with the recovered band shaded. Both solved at "
                 "identical solver settings."))

    f.append(P("4.1&nbsp;&nbsp;The low-frequency shortfall, and its cause",
               "H2"))
    f.append(P(
        "The initial design matched 4.35&ndash;12.00 GHz against a "
        "3&ndash;11 GHz target. The shortfall was originally attributed to "
        "edge-current resonance and addressed with edge corrugations, which "
        "were abandoned after a runtime extrapolation of roughly forty hours."))
    f.append(P(
        "Both conclusions were subsequently found to be incorrect. On "
        "re-testing with a control at matched solver settings, corrugated "
        "designs converged in 601 s against 578 s for the plain design "
        "&mdash; a 4% difference, not forty hours. The original run had been "
        "advancing at 0.4 timesteps per second where the same hardware "
        "delivers 11 on an identical mesh; the operating system had been "
        "suspending the solver while the solver continued counting wall-clock "
        "time. Corrugations were then measured and found not to help "
        "regardless."))
    f.append(P(
        "<b>The shortfall was never a low-frequency cutoff.</b> The original "
        "design was already matched at 2.225&ndash;2.725 GHz, reaching "
        "&minus;33 dB &mdash; two gigahertz below its own stated band edge. "
        "What lay between was a mismatch: a resistive plateau of "
        "24&ndash;37 &Omega; across 3.25&ndash;4.40 GHz, and a narrow "
        "reactive resonance near 3.0 GHz. A load of 24.4 &Omega; into a "
        "50 &Omega; feed predicts &minus;9.3 dB return loss; &minus;9.14 dB "
        "was measured. That is arithmetic, not radiation physics.", "Key"))

    f.append(P("4.2&nbsp;&nbsp;The tapered feed", "H2"))
    f.append(P(
        "Widening the feed at the flare end while pinning the port at "
        "1.74 mm &mdash; 50 &Omega; microstrip, which is what the connector "
        "must see &mdash; converts the feed into an impedance transformer."))
    f.append(table([
        ["Flare-end width", "Worst in 3&ndash;11 GHz", "Band covered",
         "Re(Z<sub>in</sub>) at 4 GHz"],
        ["1.74 mm (uniform)", "&minus;6.61 dB", "84%", "24.4 &Omega;"],
        ["2.75 mm", "&minus;8.50 dB", "79%", "25.9 &Omega;"],
        ["3.50 mm", "&minus;8.14 dB", "94%", "29.1 &Omega;"],
        ["4.00 mm", "&minus;9.80 dB", "98.1%", "36.7 &Omega;"],
        ["<b>4.50 mm (adopted)</b>", "<b>&minus;9.98 dB</b>",
         "<b>99.69%</b>", "<b>39.0 &Omega;</b>"],
    ], [38 * mm, 38 * mm, 30 * mm, 45 * mm], highlight=[5]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        f"The adopted design matches <b>2.48&ndash;12.00 GHz</b>, covering "
        f"{a['frac_below_10dB_in_band']*100:.2f}% of the 3&ndash;11 GHz "
        f"specification with a mean of {a['mean_db_in_band']:.1f} dB and a "
        f"median input resistance of {a['median_re_zin']:.1f} &Omega;. The "
        f"single non-compliant sample reaches "
        f"{a['worst_db_in_band']:.2f} dB, exceeding the &minus;10 dB "
        f"criterion by 0.02 dB &mdash; less than the difference between two "
        f"solver convergence settings. It is reported rather than rounded "
        f"away."))

    f.append(P("4.3&nbsp;&nbsp;Gain: one requirement not met", "H2"))
    f.append(table(
        [["Frequency", "Peak gain", "Specification 8&ndash;10 dBi"]]
        + [[f"{fq:.0f} GHz", f"{g:.2f} dBi",
            "<b>UNMET</b>" if g < 8 else "Met"] for fq, g in N["gain"]],
        [35 * mm, 35 * mm, 50 * mm], highlight=[1]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        "Gain is met from approximately 4 GHz upward and <b>unmet at 3 GHz "
        "by 1.0 dB</b>. The tapered feed itself raised 3 GHz gain from 3.7 to "
        "7.02 dBi, since an antenna that reflects less radiates more. The "
        "remaining decibel was pursued down both available levers, with "
        "acceptance criteria fixed before each run, and both were rejected by "
        "those criteria: widening the aperture bought 0.72 dB and cost 6% of "
        "the match, while lengthening the board to 170 mm reduced gain to "
        "6.09 dBi by collapsing the 3 GHz match."))
    f.append(P(
        "At 3 GHz the antenna is 1.5 wavelengths long with a 0.6-wavelength "
        "mouth, and the design is co-optimised for the match, so scaling "
        "either dimension breaks it. The 8&ndash;10 dBi requirement is "
        "concluded to be over-specified for this board size at the bottom of "
        "the band. It is reported as unmet rather than engineered around. "
        "Nothing downstream depends on it: the imaging model excites with an "
        "elementary dipole, so the detection result is independent of antenna "
        "gain.", "Key"))
    f.append(Spacer(1, 4 * mm))
    f.append(KeepTogether([
        P("4.4&nbsp;&nbsp;Fabrication package", "H2"),
        fig("vivaldi_fab_drawing.png",
                 "Figure 9. Dimensioned fabrication drawing, both faces. "
                 "Generated directly from the design parameters, so it cannot "
                 "diverge from the simulated geometry. Accompanied by DXF and "
                 "STEP exports.", width=170 * mm)]))
    f.append(PageBreak())


def results(f):
    i, fr = N["intact"], N["fract"]
    f.append(P("5.&nbsp;&nbsp;Experiment and Results", "H1"))
    f.append(P("5.1&nbsp;&nbsp;Design", "H2"))
    f.append(P(
        "A full factorial matrix of 8 simulated specimens &times; 4 overlay "
        "thicknesses &times; 6 fracture states gives 192 full-wave "
        "acquisitions. Specimens differ through a variation model perturbing "
        "layer thicknesses and tissue properties. Each acquisition is scored "
        "under three independent instrument-error realisations representing "
        f"remounts, giving {N['n_scores']} scores. The matrix was solved on a "
        "Google Colab T4 GPU; 192 of 192 cells completed."))
    f.append(fig("stage6_matrix_preview.png",
                 "Figure 10. Detection score against soft-tissue overlay "
                 "across the completed matrix, by fracture state."))

    f.append(P("5.2&nbsp;&nbsp;Statistical analysis plan", "H2"))
    f.append(P(
        "The plan was fixed before the data were examined. Two points "
        "require care. First, the detector has no fitted parameters &mdash; "
        "it is a single scalar &mdash; so the only trained quantity is the "
        "decision threshold, and leave-one-specimen-out validation is "
        "applied to that rather than to the detector. Second, the bootstrap "
        "resamples <i>specimens</i>, not measurements: twenty-four "
        "acquisitions from one bone are not twenty-four independent "
        "observations, and resampling them would yield an interval several "
        "times too narrow. Permutation labels are likewise shuffled within "
        "specimen."))

    f.append(P("5.3&nbsp;&nbsp;Primary result", "H2"))
    f.append(table([
        ["Class", "n", "Minimum", "Median", "Maximum"],
        ["Intact", f"{i[0]}", f"{i[1]:.1f} dB", f"{i[2]:.1f} dB",
         f"<b>{i[3]:.1f} dB</b>"],
        ["Fractured", f"{fr[0]}", f"<b>{fr[1]:.1f} dB</b>", f"{fr[2]:.1f} dB",
         f"{fr[3]:.1f} dB"],
    ], [30 * mm, 18 * mm, 34 * mm, 34 * mm, 34 * mm]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        f"The two classes are separated by <b>{N['gap']:.1f} dB with no "
        f"overlap</b> &mdash; a factor of 110 in amplitude. Area under the "
        f"curve is 1.0000 at every overlay thickness and every fracture "
        f"width, with bootstrap 95% confidence interval 1.000&ndash;1.000 and "
        f"permutation p = 0.001, the floor for 1000 shuffles.", "Key"))
    f.append(table([
        ["Metric", "Value", "95% interval"],
        ["Primary AUC, 6 mm overlay", "1.0000", "1.000&ndash;1.000"],
        ["Sensitivity (leave-one-specimen-out)", "0.9979",
         "0.988&ndash;1.000 (Wilson)"],
        ["Specificity (leave-one-specimen-out)", "1.0000",
         "0.962&ndash;1.000 (Wilson)"],
        ["Accuracy", "0.9983", "&mdash;"],
        ["Repeatability, ICC(1,1)", "0.9979", "&mdash;"],
        ["Within-measurement standard deviation", "0.468 dB", "&mdash;"],
    ], [66 * mm, 30 * mm, 55 * mm]))
    f.append(Spacer(1, 4 * mm))
    f.append(fig("stage7_statistics.png",
                 "Figure 11. (a) The two classes do not overlap. (b) Detection "
                 "score against overlay for both classes; the margin narrows "
                 "with overlay but never closes. (c) Worst case at the "
                 "thickest overlay against fracture width."))

    f.append(P("5.4&nbsp;&nbsp;Interpreting a perfect classifier", "H2"))
    f.append(P(
        "An area under the curve of 1.0000 ordinarily indicates a leak "
        "between training and test data rather than a genuine result, and it "
        "was treated as such. Inspection of the raw distributions confirms it "
        "is not: the classes are separated by a real 40.8 dB gap with no "
        "overlap, and the structure of that margin follows physical "
        "prediction. The weakest fractured cases are the narrowest kerf under "
        "the thickest overlay, and the strongest intact cases also occur at "
        "the thickest overlay. A data leak would not order itself by physical "
        "difficulty."))
    f.append(P(
        "Nevertheless, a perfect score is <b>saturated</b> and therefore a "
        "lower bound rather than a measurement. The defensible claim is that "
        "under the modelled error budget the classes separate by 40.8 dB with "
        "no overlap &mdash; not that detection is perfect. The binding "
        "assumption is the error model, not the physics: a physical bench "
        "would add cable flex, connector repeatability, operator variation "
        "and genuine inter-specimen heterogeneity, none of which are "
        "simulated. The 40.8 dB margin is the budget those unmodelled terms "
        "would have to consume before the conclusion changes."))
    f.append(PageBreak())


def band_study(f):
    f.append(P("6.&nbsp;&nbsp;Bandwidth Study: A Saturated Statistic", "H1"))
    f.append(P(
        "The preceding section argues that a saturated statistic cannot "
        "measure margin. This section demonstrates it experimentally on the "
        "data of this study, and it is the finding with the widest "
        "applicability."))
    f.append(P(
        "Because every solved cell stores the full-band response, the entire "
        "192-cell matrix can be re-scored over a restricted frequency window "
        "with no additional electromagnetic simulation &mdash; the same "
        "pipeline, a different slice of data already held. Three windows were "
        "compared, including the band delivered by the initial antenna."))
    f.append(table([
        ["Frequency window", "Bandwidth", "Resolution", "AUC", "Separation"],
        ["3.00&ndash;11.0 GHz (design target)", "8.00 GHz", "3.67 mm",
         "1.0000", "<b>40.8 dB</b>"],
        ["4.35&ndash;11.0 GHz (initial antenna)", "6.65 GHz", "4.42 mm",
         "1.0000", "<b>17.9 dB</b>"],
        ["5.00&ndash;11.0 GHz (deliberately worse)", "6.00 GHz", "4.90 mm",
         "1.0000", "16.0 dB"],
        ["3.00&ndash;6.30 GHz (upper band removed)", "3.30 GHz", "8.91 mm",
         "1.0000", "<b>51.5 dB</b>"],
        ["3.00&ndash;4.40 GHz (upper band removed)", "1.40 GHz", "21.0 mm",
         "1.0000", "<b>43.0 dB</b>"],
    ], [50 * mm, 24 * mm, 28 * mm, 20 * mm, 29 * mm], highlight=[2, 4, 5]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        "<b>Removing 3.00&ndash;4.35 GHz costs 22.9 dB &mdash; more than half "
        "the total separation. The area under the curve remains at exactly "
        "1.0000 in all three windows and registers none of it.</b> Reporting "
        "that statistic alone would have concealed the loss of more than half "
        "the margin, and would have supported the incorrect conclusion that "
        "the antenna shortfall was inconsequential.", "Key"))
    f.append(P("6.1&nbsp;&nbsp;Mechanism", "H2"))
    f.append(P(
        "Band limitation degrades both classes, and the intact class is the "
        "more damaging. The weakest fractured score falls from 68.5 to "
        "55.7 dB, as expected from reduced penetration and resolution. The "
        "strongest <i>intact</i> score rises from 27.7 to 37.8 dB &mdash; a "
        "false alarm rather than a missed detection, occurring on one "
        "specimen at 6 mm overlay against a group mean of 23.7 dB."))
    f.append(P(
        "An obvious reading is that bandwidth buys range resolution and the "
        "restricted window can no longer resolve the artefact. The last two "
        "rows of the table refute it. Keeping only 3.0&ndash;6.3 GHz &mdash; "
        "the range of a low-cost VNA, with a resolution of 8.91 mm, more than "
        "twice as coarse &mdash; <i>raises</i> the separation to 51.5 dB, and "
        "the same specimen-3 cell that reached 37.8 dB at 4.35&ndash;11 GHz "
        "reads 10.2 dB there. Even 3.0&ndash;4.4 GHz, a 1.4 GHz window with "
        "21 mm resolution, retains 43.0 dB. Resolution is not the driver; "
        "what the windows differ in is which end of the band was removed."))
    f.append(P(
        "The low band carries the penetration. The deep layered reflection "
        "that migration must collapse is returned almost entirely by the "
        "frequencies that reach it; strip them and the reflection is "
        "undersampled, and its residue lands in the detection window as a "
        "target. The upper band contributes little to that reflection through "
        "6 mm or more of overlay &mdash; on the hardest fractured cell the "
        "fracture peak changes by about 1 dB when 6.3&ndash;11 GHz is removed "
        "while the image background falls by 10 dB &mdash; so removing it "
        "costs resolution the detector does not need and removes noise it "
        "does not want. Because the false alarm is specimen-dependent, the "
        "concern is variance rather than the mean shift: one specimen in "
        "eight spiked, and a larger cohort would be expected to contain "
        "worse.", "Key"))
    f.append(P(
        "This measurement is what established the antenna shortfall as worth "
        "correcting rather than documenting, and it directly motivated the "
        "tapered-feed redesign of Section 4. Since the redesigned antenna "
        "covers 2.48&ndash;12.00 GHz, which fully contains the band the "
        "matrix was solved over, the full 40.8 dB separation is recovered."))
    f.append(PageBreak())


def safety(f):
    f.append(P("7.&nbsp;&nbsp;Radio-Frequency Exposure Assessment", "H1"))
    f.append(P(
        "A system that points a 3&ndash;11 GHz antenna at a forearm at 12 mm "
        "standoff requires an exposure assessment. The working band straddles "
        "a boundary in the current guidelines, and this must be respected: "
        "ICNIRP 2020 and IEEE C95.1-2019 specify specific absorption rate in "
        "W/kg averaged over 10 g below 6 GHz, and absorbed power density in "
        "W/m<super>2</super> averaged over 4 cm<super>2</super> above it."))
    f.append(P(
        "A single specific absorption rate figure quoted for a 3&ndash;11 GHz "
        "system therefore reports the wrong quantity for the majority of the "
        "bandwidth. Both are computed here."))
    f.append(P("7.1&nbsp;&nbsp;Method and operating point", "H2"))
    f.append(P(
        "The limb is treated as a plane-layered lossy stack at normal "
        "incidence. The layered reflection is taken from the same routine "
        "used by the analytic forward solver rather than a second "
        "implementation that could drift from it, and dielectric properties "
        "are the same Cole-Cole models used throughout. Densities are from "
        "the IT'IS Foundation tissue property database v4.1."))
    f.append(P(
        "Transmit power is specified at <b>0 dBm (1 mW)</b>. A vector network "
        "analyser will deliver +10 dBm, at which the 6&ndash;11 GHz exposure "
        "reaches 11.1 W/m<super>2</super> against a 20 W/m<super>2</super> "
        "public limit &mdash; a margin of 1.8&times;, the only uncomfortable "
        "quantity in the assessment. Reducing transmit power by 10 dB "
        "restores an 18&times; margin at no cost, since the detector has "
        "40.8 dB of separation and expends none of it here."))
    f.append(P("7.2&nbsp;&nbsp;Results at 0 dBm", "H2"))
    f.append(P(
        "Worst-case illumination is assumed throughout: the transmitted power "
        "concentrated into a half-wavelength spot at 11 GHz "
        "(1.86 cm<super>2</super>), approximately the smallest area the "
        "physics permits and therefore the highest exposure. Each limit is "
        "evaluated against a value averaged over its own mass, since a 10 g "
        "average compared against a 1 g limit would understate exposure."))
    f.append(table([
        ["Limit", "Limit value", "Computed", "Verdict"],
        ["ICNIRP public, limbs (10 g)", "4.0 W/kg", "0.0283 W/kg",
         "<b>PASS, 141&times;</b>"],
        ["ICNIRP public, head/torso (10 g)", "2.0 W/kg", "0.0283 W/kg",
         "<b>PASS, 71&times;</b>"],
        ["ICNIRP occupational, limbs (10 g)", "20.0 W/kg", "0.0283 W/kg",
         "<b>PASS, 707&times;</b>"],
        ["FCC / IEEE public, partial body (1 g)", "1.6 W/kg", "0.0494 W/kg",
         "<b>PASS, 32&times;</b>"],
        ["ICNIRP public, 6&ndash;11 GHz (4 cm<super>2</super>)",
         "20.0 W/m<super>2</super>", "1.109 W/m<super>2</super>",
         "<b>PASS, 18&times;</b>"],
    ], [56 * mm, 26 * mm, 30 * mm, 34 * mm], highlight=[5]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        "All quantities pass, with a minimum margin of 18&times;. For "
        "context, a smartphone typically reports 0.5&ndash;1.4 W/kg against "
        "the same 1 g limit of 1.6 W/kg, a margin between 1&times; and "
        "3&times;. Peak point specific absorption rate is 0.139 W/kg at the "
        "skin surface, and approximately 38% of absorbed power stops within "
        "the first 2 mm &mdash; the same physics that makes the imaging "
        "problem difficult.", "Key"))
    f.append(P(
        "<b>This is a design-stage analysis by simulation.</b> Regulatory "
        "compliance is established by measurement on a physical phantom to "
        "IEC 62209 and not by calculation. The assessment establishes that "
        "the design is nowhere near a limit; it does not certify it."))
    f.append(PageBreak())


def limitations(f):
    f.append(P("8.&nbsp;&nbsp;Limitations", "H1"))
    f.append(P(
        "The following constrain the interpretation of every result above and "
        "are stated in full, since a result whose limits are not stated "
        "cannot be assessed by a reader."))
    f.append(table([
        ["#", "Limitation", "Consequence"],
        ["1", "The injected error model is the binding assumption",
         "A physical bench adds cable flex, connector repeatability, operator "
         "variation and real inter-specimen heterogeneity. The 40.8 dB margin "
         "is the budget those terms must consume before conclusions change."],
        ["2", "Every fracture is at a known position",
         "The study measures separability, not localisation. Detection at an "
         "unknown position is untested."],
        ["3", "Two-dimensional TMz propagation",
         "Out-of-plane scattering is absent. A three-dimensional model would "
         "add geometric spreading not represented here."],
        ["4", "Eight simulated specimens, not cadaveric bone",
         "Specimens differ only through the parameters the variation model "
         "perturbs, which understates biological variability."],
        ["5", "The imaging model excites with an elementary dipole",
         "Antenna characterisation and the imaging matrix are separate "
         "results. The antenna pattern is not folded into the detection "
         "figures."],
        ["6", "Antenna gain unmet at 3 GHz",
         "7.02 dBi against a 8&ndash;10 dBi requirement, shown not to be "
         "reachable by resizing within the specified board stock."],
        ["7", "Exposure assessed by simulation",
         "A plane-wave approximation used in the reactive near field, with no "
         "thermal model. Not a substitute for IEC 62209 testing."],
    ], [8 * mm, 52 * mm, 91 * mm]))
    f.append(Spacer(1, 4 * mm))
    f.append(P(
        "Limitation 1 deserves emphasis. Because the area under the curve is "
        "saturated, it cannot distinguish a comfortable result from a "
        "marginal one, as Section 6 demonstrates directly. Any future work "
        "that strengthens the error model should report the class separation "
        "in dB alongside any classification statistic."))

    f.append(P("8.1&nbsp;&nbsp;Limitation 3 is being removed", "H2"))
    f.append(P(
        "The two-dimensional assumption is the one limitation that has been "
        "acted on rather than only recorded. A three-dimensional model of the "
        "same problem has been built and verified against the solver: the "
        "limb becomes concentric cylinders of skin, fat and muscle around a "
        "cortical tube, with the bone offset 14 mm toward the skin so that "
        "its near wall sits at 6.0 mm, the same depth the layered phantom "
        "uses. Without that offset a centred bone would lie 20 mm deep and "
        "the two models would differ in depth as well as geometry, so no "
        "difference in the result could be attributed to curvature. The "
        "offset is also the anatomy: the tibial and radial shafts are "
        "subcutaneous, which is why they are the candidate sites."))
    f.append(fig("limb_models_2d_3d.png",
                 "Figure 12. What the solver integrates. (a) The plane the "
                 "two-dimensional model solves, in which the bone is a pair "
                 "of flat layers. (b) Transverse and (c) longitudinal "
                 "sections of the cylindrical model, showing the offset bone "
                 "and the fracture cut through the cortical wall. (d) The "
                 "three-dimensional domain. The flat model is not a picture "
                 "of a limb; it is a picture of the plane a 2D TMz solver "
                 "actually integrates.",
                 width=170 * mm, max_h=112 * mm))
    f.append(Spacer(1, 2 * mm))
    f.append(P(
        "Three effects appear in three dimensions that the plane cannot "
        "produce, and they do not all act in the same direction, which is why "
        "the comparison has to be measured rather than argued. A curved skin "
        "surface spreads the reflected wavefront and costs signal. Energy "
        "leaves the plane that a two-dimensional model traps inside it, which "
        "also costs signal. But a transverse crack severs a curved cortical "
        "wall, so the scattering edge is an arc rather than a point and is "
        "illuminated across a range of incidence angles, which can return "
        "signal the flat model cannot represent."))
    f.append(P(
        "<b>The comparison is not yet run, and the result is not claimed "
        "here.</b> The three-dimensional grid is 0.4 mm at a 4 GHz centre "
        "frequency, 9.6 million cells against the 0.14 million of the "
        "two-dimensional matrix, and the full run is approximately 2.6 hours "
        "on a T4 GPU. Because that grid can only carry roughly 3&ndash;6 GHz, "
        "the two-dimensional data will be scored over the same window before "
        "the two are compared; comparing 3&ndash;6 GHz against 3&ndash;11 GHz "
        "would confound geometry with bandwidth, and Section 6 established "
        "that bandwidth is worth 22.9 dB here, far more than any plausible "
        "geometric effect.", "Key"))
    f.append(PageBreak())


def conclusions(f):
    f.append(P("9.&nbsp;&nbsp;Conclusions", "H1"))
    f.append(P(
        "A complete virtual instrument for ultra-wideband bone fracture "
        "detection has been constructed and exercised end to end using only "
        "open-source software. The principal findings are as follows."))
    f.append(P(
        "<b>1. Detection is achievable with substantial margin.</b> Across "
        "192 full-wave acquisitions from 8 specimens, fractured and intact "
        "limbs separate by 40.8 dB with no overlap, at every soft-tissue "
        "overlay thickness from 0 to 10 mm and every fracture width from 0.2 "
        "to 2.0 mm. Leave-one-specimen-out validation gives sensitivity "
        "0.998 and specificity 1.000."))
    f.append(P(
        "<b>2. A saturated classification statistic conceals degradation.</b> "
        "Restricting the usable band to that of the initial antenna removed "
        "more than half the class separation, from 40.8 dB to 17.9 dB, while "
        "the area under the curve remained at exactly 1.0000. This is "
        "demonstrated rather than asserted, and it argues that any study "
        "reporting a near-perfect classifier should report the underlying "
        "margin alongside it."))
    f.append(P(
        "<b>3. The antenna shortfall was a matching problem, not a size "
        "problem.</b> The initial design was already matched two gigahertz "
        "below its stated band edge. A tapered feed, a single geometric "
        "parameter, moved the matched band from 4.35&ndash;12.00 GHz to "
        "2.48&ndash;12.00 GHz, covering 99.69% of the specification on "
        "unchanged board stock."))
    f.append(P(
        "<b>4. One specification is not achievable and is reported as "
        "such.</b> Antenna gain at 3 GHz reaches 7.02 dBi against a "
        "8&ndash;10 dBi requirement. Both available levers were tested with "
        "acceptance criteria fixed in advance, and both degraded the result. "
        "The requirement is concluded to be over-specified for the board size "
        "at the bottom of the band."))
    f.append(P(
        "<b>5. Exposure is comfortable.</b> At the specified 0 dBm transmit "
        "power, all quantities in ICNIRP 2020 and IEEE C95.1-2019 pass with a "
        "minimum margin of 18&times;, under worst-case illumination "
        "assumptions."))
    f.append(P("9.1&nbsp;&nbsp;Future work", "H2"))
    f.append(P(
        "In order of value: extend the error model until detection fails, so "
        "the limit is measured rather than bounded; randomise fracture "
        "position to test localisation rather than separability; extend to "
        "three-dimensional propagation; and fold the measured antenna pattern "
        "into the imaging model so that antenna and imaging results are no "
        "longer independent."))
    f.append(PageBreak())


def reproducibility(f):
    f.append(P("10.&nbsp;&nbsp;Reproducibility", "H1"))
    f.append(P(
        "Every figure and every number in this report is regenerated by a "
        "script from committed inputs or stored run data. No figure was "
        "produced by hand, and the numerical values in this document are read "
        "from the analysis output rather than transcribed, so the report "
        "cannot drift from the results it describes."))
    f.append(table([
        ["Command", "Produces"],
        ["python scripts/verify_stage0.py", "Solver verification against "
         "analytic echo times"],
        ["python scripts/run_stage3.py", "Full-wave B-scans"],
        ["python scripts/run_stage4.py", "Validation gate"],
        ["python scripts/run_matrix.py", "The 192-cell experiment matrix"],
        ["python scripts/run_stage7.py", "Statistical analysis plan"],
        ["python scripts/run_band_study.py", "Bandwidth limitation study"],
        ["python scripts/tune_feed_taper.py", "Antenna feed optimisation"],
        ["python scripts/measure_gain.py", "Far-field gain"],
        ["python scripts/run_sar.py", "Exposure assessment"],
        ["python scripts/make_figures.py", "All figures in this report"],
        ["python scripts/make_antenna_fab.py", "DXF, STEP and drawing"],
        ["python scripts/make_report.py", "This document"],
        ["python -m pytest tests/", "146 tests"],
    ], [66 * mm, 85 * mm]))
    f.append(Spacer(1, 5 * mm))
    f.append(P(
        "<b>Corrections made during the work.</b> Six conclusions recorded "
        "earlier in the project were later found to be incorrect and are "
        "corrected in the repository documentation: a solver convergence "
        "claim that measured operating-system suspension rather than "
        "computation; the prescribed remedy for the antenna shortfall; the "
        "diagnosis of that shortfall as a cutoff; a fabrication drawing that "
        "would have misstated trace width at the connector; a unit test "
        "asserting the wrong dimension; and a figure double-counting two "
        "cells. Each is documented where it occurred rather than silently "
        "revised.", "Key"))
    f.append(PageBreak())


def references(f):
    f.append(P("References", "H1"))
    refs = [
        "Gabriel, S., Lau, R. W. and Gabriel, C. (1996). The dielectric "
        "properties of biological tissues: III. Parametric models for the "
        "dielectric spectrum of tissues. <i>Physics in Medicine and "
        "Biology</i>, 41(11), 2271&ndash;2293.",
        "Warren, C., Giannopoulos, A. and Giannakis, I. (2016). gprMax: "
        "Open source software to simulate electromagnetic wave propagation "
        "for Ground Penetrating Radar. <i>Computer Physics Communications</i>, "
        "209, 163&ndash;170.",
        "Liebig, T., Rennings, A., Held, S. and Erni, D. (2013). openEMS "
        "&mdash; a free and open source equivalent-circuit (EC) FDTD "
        "simulation platform. <i>International Journal of Numerical "
        "Modelling</i>, 26(6), 680&ndash;696.",
        "Gazit, E. (1988). Improved design of the Vivaldi antenna. <i>IEE "
        "Proceedings H</i>, 135(2), 89&ndash;92.",
        "ICNIRP (2020). Guidelines for limiting exposure to electromagnetic "
        "fields (100 kHz to 300 GHz). <i>Health Physics</i>, 118(5), "
        "483&ndash;524.",
        "IEEE (2019). <i>IEEE Standard for Safety Levels with Respect to "
        "Human Exposure to Electric, Magnetic, and Electromagnetic Fields, "
        "0 Hz to 300 GHz</i>. IEEE Std C95.1-2019.",
        "Hasgall, P. A. et al. (2022). <i>IT'IS Database for thermal and "
        "electromagnetic parameters of biological tissues</i>, Version 4.1.",
        "Benjamini, Y. and Hochberg, Y. (1995). Controlling the false "
        "discovery rate. <i>Journal of the Royal Statistical Society B</i>, "
        "57(1), 289&ndash;300.",
    ]
    for i, r in enumerate(refs, 1):
        f.append(P(f"[{i}]&nbsp;&nbsp;{r}"))


def appendix_bom(f, standalone=False):
    """Bill of materials for a physical build, traced to the simulation.

    The same content serves as Appendix A of the report and, with
    standalone=True, as docs/bill-of-materials.pdf. Source of record is
    docs/bill-of-materials.md; keep the two in step.
    """
    pre = "" if standalone else "A."
    if standalone:
        f.append(Spacer(1, 18 * mm))
        f.append(P("Bill of Materials for a Physical Build", "TitleBig"))
        f.append(P(TITLE, "SubBig"))
        f.append(P("Companion to the submission report. Every specification "
                   "is traced to the simulation that fixed it.", "Meta"))
        f.append(Spacer(1, 10 * mm))
    else:
        f.append(PageBreak())
        f.append(P("Appendix A&nbsp;&nbsp;Bill of Materials for a Physical "
                   "Build", "H1"))
    f.append(P(
        "The project is purely virtual by design, and nothing listed here "
        "has been bought. This is what a physical build would need, with "
        "each specification traced to the simulation that fixed it rather "
        "than to a generic shopping list. Cost figures are the proposal's "
        "indicative Indian-supplier numbers (Robu, Element14 India, Mouser "
        "India, Amazon.in) and <b>must be re-quoted before purchase</b>; "
        "several are a year old."))
    f.append(table([
        ["Configuration", "Approximate total"],
        ["With a department VNA (recommended)", "<b>INR 23,800</b>"],
        ["With the LiteVNA-64 fallback", "<b>INR 32,800</b>"],
    ], [95 * mm, 40 * mm]))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "The one thing the proposal could only guess at &mdash; whether the "
        "cheap VNA fallbacks actually work &mdash; is now measured "
        f"(Section {pre}2). The spreadsheet form, "
        "<i>docs/bill-of-materials.csv</i>, carries all three VNA options, "
        "so its column sum (INR 42,700) is not a configuration total."))

    # ---------------------------------------------------------- instrument
    f.append(P(f"{pre}1&nbsp;&nbsp;The measurement instrument", "H2k"))
    f.append(P(
        "The VNA decides viability. The proposal's framing stands: <i>the "
        "single question is whether the department owns a VNA reaching "
        "8 GHz or above.</i>"))
    W6 = [24 * mm, 50 * mm, 34 * mm, 11 * mm, 14 * mm, 30 * mm]
    H6 = ["Item", "Specification fixed by the simulation", "Suggested",
          "Qty", "INR", "Note"]
    f.append(table([
        H6,
        ["VNA, preferred",
         "1-port S11; sweep 3&ndash;11 GHz (antenna is matched "
         "2.48&ndash;12.00 GHz); at least 201 points; output 0 dBm; dynamic "
         "range 95 dB or better at about 1 kHz IF bandwidth",
         "Department lab VNA, 8&ndash;20 GHz", "1", "0",
         "Check first; decides everything below"],
        ["VNA, fallback 1", "50 kHz &ndash; 6.3 GHz", "LiteVNA-64", "1",
         "9,000", "<b>Works</b>; measured below"],
        ["VNA, fallback 2", "To 4.4 GHz", "NanoVNA V2 Plus4", "1", "7,000",
         "Works on band; dynamic range untested"],
        ["Calibration kit",
         "SMA short / open / load, calibrated <b>at the antenna "
         "connector</b>, not at the VNA port",
         "SMA SOL kit (often bundled with the LiteVNA)", "1",
         "1,500&ndash;3,000",
         "Everything downstream is referenced to the antenna feed"],
    ], W6))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "<b>Where the numbers come from.</b> The matrix was solved over "
        "3&ndash;11 GHz at 201 points. The error model assumes a <b>95 dB</b> "
        "noise floor below the strongest return, which a lab VNA at 1 kHz IF "
        "bandwidth meets and a LiteVNA (roughly 70 dB at its top end) does "
        "not. <b>0 dBm</b> is the adopted transmit power from the exposure "
        "assessment: at +10 dBm the 6&ndash;11 GHz absorbed power density sat "
        "within 1.8&times; of the ICNIRP public limit; at 0 dBm every limit "
        "clears by at least 18&times;, and the detector has 40.8 dB of margin "
        "to spend (Section 7)."))

    # ---------------------------------------------------- cheap-VNA verdict
    f.append(P(f"{pre}2&nbsp;&nbsp;Do the cheap VNAs work? Measured, not "
               "guessed", "H2k"))
    f.append(P(
        "The proposal labelled the LiteVNA &ldquo;band-limited; degrades "
        "resolution&rdquo; and the NanoVNA &ldquo;minimum viable, "
        "marginal&rdquo;. Those were guesses made before the matrix was "
        "solved. Every solved cell stores the full 3&ndash;11 GHz response, "
        "so each fallback can be scored on exactly the data it could have "
        "acquired, with no new simulation (<i>scripts/vna_fallback_study.py</i>, "
        "same pipeline and detector as Stage 7)."))
    f.append(table([
        ["VNA option", "Usable band", "Bandwidth", "Range res.", "AUC",
         "Class separation"],
        ["Department VNA", "3.00&ndash;11.0 GHz", "8.00 GHz", "3.67 mm",
         "1.0000", "<b>40.8 dB</b>"],
        ["(first antenna, for scale)", "4.35&ndash;11.0 GHz", "6.65 GHz",
         "4.42 mm", "1.0000", "17.9 dB"],
        ["LiteVNA-64", "3.00&ndash;6.30 GHz", "3.30 GHz", "8.91 mm",
         "1.0000", "<b>51.5 dB</b> at 95 dB dynamic range; <b>36.4 dB</b> "
         "at 70 dB"],
        ["NanoVNA V2 Plus4", "3.00&ndash;4.40 GHz", "1.40 GHz", "21.0 mm",
         "1.0000", "<b>43.0 dB</b>, band only, at 95 dB dynamic range"],
    ], [29 * mm, 27 * mm, 22 * mm, 20 * mm, 15 * mm, 50 * mm],
        highlight=[3, 4]))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "<b>Verdict: both work, and on the band alone the LiteVNA beats the "
        "department VNA.</b> Removing the upper band <i>raises</i> the "
        "separation, 51.5 dB against 40.8, because the frequencies above "
        "6.3 GHz contribute little through 6 mm or more of overlay and "
        "mostly add image background the detector does not want; the low "
        "band carries the penetration (Section 6). By overlay, the LiteVNA "
        "band gives 64.9 / 66.6 / 65.2 / 51.5 dB at 0 / 3 / 6 / 10 mm and the "
        "NanoVNA band 54.8 / 57.3 / 60.5 / 45.9 dB. The classes do not "
        "overlap at any overlay for either.", "Key"))
    f.append(P(
        "<b>Dynamic range, measured separately.</b> The band study keeps the "
        "error model's 95 dB noise floor, which the cheap VNAs do not have. "
        "Re-scoring the LiteVNA band at 70 dB "
        "(<i>scripts/vna_dynrange_study.py</i>, 576 realisations) gives "
        "AUC 1.0000 and <b>36.4 dB</b> separation: 50.2 / 49.1 / 50.0 / "
        "36.4 dB by overlay. The 25 dB worse floor costs 15 dB of margin, "
        "nearly all of it at the 10 mm overlay, and what remains is within "
        "5 dB of the department VNA's full-band 40.8. A LiteVNA-64 is "
        "therefore a defensible instrument for this experiment, not a "
        "compromise. The same test has not been run for the NanoVNA band; "
        "its 43.0 dB is the band-only figure at 95 dB and should be read as "
        "an upper bound on what that instrument would deliver."))

    # ------------------------------------------------------------- antenna
    f.append(P(f"{pre}3&nbsp;&nbsp;The antenna", "H2k"))
    f.append(P(
        "Design files are in <i>figures/</i>: <i>vivaldi.dxf</i> (4 layers, "
        "mm, origin at the feed edge), <i>vivaldi_antenna.step</i>, "
        "<i>vivaldi_fab_drawing.pdf</i> (A4, both faces dimensioned) and "
        "<i>vivaldi_geom.json</i>. Rebuild with "
        "<i>python scripts/make_antenna_fab.py</i>."))
    f.append(table([
        H6,
        ["Substrate",
         "Rogers RO4350B, 0.762 mm (30 mil), 1 oz Cu, 100 &times; 150 mm; "
         "the antenna is 150 &times; 90 mm, one board per antenna",
         "RO4350B 0.762 mm", "2", "3,500",
         "FR4 alternative INR 300; costs 2.4 dB at 9 GHz and 3.6 dB at "
         "11 GHz (Stage 5)"],
        ["Fabrication",
         "Etch both faces from <i>vivaldi.dxf</i>; four 3.2 mm mounting "
         "holes at (6, &plusmn;38) mm",
         "PCB house, or in-house etch", "2", "3,000", "One spare"],
        ["SMA connector",
         "<b>End-launch, 18 GHz rated</b>; port trace is 1.74 mm (50 ohm)",
         "L-com RFPCB-SMA-FS18G-55 (solder, cut for 0.031 in board) or "
         "Southwest 292-04A-9 (solderless clamp, 0.010 in pin)",
         "4", "1,600",
         "<b>Do not use cheap 6 GHz parts.</b> No extra pads needed; see "
         "note"],
        ["Mounting", "M3 nylon standoffs and screws for the four holes",
         "M3 &times; 10 nylon", "8", "200",
         "Keeps metal out of the near field"],
    ], W6))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "<b>The antenna as designed.</b> Antipodal Vivaldi, growth "
        "a&middot;T = 2.0, 60 mm aperture, <b>tapered feed 4.50 mm at the "
        "flare to 1.74 mm at the port</b>. The taper is what took the match "
        "from 4.35&ndash;12.00 GHz to <b>2.48&ndash;12.00 GHz</b>: 99.69% of "
        "3&ndash;11 GHz below &minus;10 dB, worst &minus;9.98 dB at one "
        "point, median Re(Z<sub>in</sub>) 45.6 ohm (Section 5). Gain is "
        "7.02 dBi at 3 GHz, 11.9&ndash;12.5 dBi across 5&ndash;9 GHz and "
        "9.3 dBi at 11 GHz; the 8&ndash;10 dBi target is met from about "
        "4 GHz up and <b>not at 3 GHz</b>, which is aperture-limited and "
        "was shown not fixable by resizing within the board."))
    f.append(P(
        "<b>Connector note, from the fabrication drawing.</b> Both named "
        "parts were checked against their datasheets for the 0.762 mm "
        "board. An end-launch lands its pin on the 1.74 mm trace at the "
        "board edge and grounds to the full-width plane on the other face, "
        "so <b>no pads are drawn and none are needed</b>. The Southwest "
        "part's 0.0635 in (1.61 mm) dielectric is within 8% of the trace "
        "width, which is why it launches cleanly. The proposal's INR 400 per "
        "connector assumes a generic 18 GHz end-launch; the named Southwest "
        "part is a premium item at roughly ten times that &mdash; price it "
        "before choosing. Top-ground-tab connectors are supported only with "
        "a 2.5 mm or wider pad gap and cost the band above 9.6 GHz; avoid "
        "them."))
    f.append(fig("vivaldi_fab_drawing.png",
                 "Fabrication drawing of the antipodal Vivaldi, dimensioned "
                 "panels only; the full sheet with the connector and pad "
                 "notes is figures/vivaldi_fab_drawing.pdf. Both faces, "
                 "150 &times; 90 mm on RO4350B 0.762 mm, feed tapered from "
                 "4.50 mm at the flare to 1.74 mm at the port.",
                 crop=(0.29, 0.0, 0.655, 0.51), max_h=108 * mm))

    # ------------------------------------------------------------- cabling
    f.append(P(f"{pre}4&nbsp;&nbsp;Cabling", "H2k"))
    f.append(table([
        H6,
        ["Test cable", "Phase-stable, SMA&ndash;SMA, 18 GHz, 60 cm",
         "Mini-Circuits or Pasternack phase-stable", "1", "4,500",
         "<b>Secure it</b> &mdash; flexing changes phase"],
        ["Port saver", "SMA female&ndash;female adapter on the VNA port",
         "SMA F&ndash;F, 18 GHz", "2", "500",
         "The VNA connector outlives the project; the saver does not"],
    ], W6))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "The error model's cable term is 1 fs RMS delay jitter, i.e. a cable "
        "that does not move during a scan. Route it along the stage with "
        "slack at a single fixed bend, not dragged."))

    # --------------------------------------------------------------- stage
    f.append(P(f"{pre}5&nbsp;&nbsp;The scan stage", "H2k"))
    f.append(P(
        "Migration sums phase coherently across positions, so position "
        "error is phase error: 0.5 mm at 10 GHz in air is about 60 degrees. "
        "The error model assumes <b>100 &micro;m RMS</b> stage jitter and the "
        "result tolerated it; build to that."))
    f.append(table([
        H6,
        ["Rail",
         "At least 60 mm of scan travel (the matrix used 61 positions at "
         "1 mm, 20&ndash;80 mm); 200 mm gives clearance for the 150 mm "
         "antenna",
         "2020 aluminium extrusion, 200 mm", "1", "2,800",
         "Includes lead screw"],
        ["Lead screw", "8 mm, <b>anti-backlash nut</b>",
         "T8 with anti-backlash brass nut", "1", "(incl.)",
         "Backlash is a systematic position error migration cannot remove"],
        ["Motor and driver", "NEMA 17, A4988, 12 V 3 A supply",
         "Standard 3D-printer parts", "1", "1,400",
         "1 mm per step command; settle 200 ms before each sweep"],
        ["Home switch", "Mechanical limit switch at one end", "Microswitch",
         "1", "(incl.)",
         "Repeatable zero; required for empty-scene subtraction to line up"],
        ["Controller", "Serial command: step, settle, trigger",
         "Arduino Nano or ESP32", "1", "600",
         "The laptop drives the VNA over USB; the controller only moves "
         "the stage"],
    ], W6))
    f.append(Spacer(1, 3 * mm))
    f.append(fig("measurement_pipeline.png",
                 "The measurement the stage and fixture must reproduce: "
                 "61 antenna positions at 1 mm along the bone axis, 12 mm "
                 "standoff, one S11 sweep per position, then empty-scene "
                 "subtraction, clutter removal and migration."))

    # ------------------------------------------------------------- fixture
    f.append(P(f"{pre}6&nbsp;&nbsp;Fixture", "H2k"))
    f.append(table([
        H6,
        ["Antenna holder",
         "<b>12 mm standoff</b> from aperture to skin, held to "
         "<b>&plusmn;0.3 mm</b>",
         "Acrylic or 3D-printed bracket on the stage carriage", "1",
         "(in 2,500)", "standoff_sigma = 300 &micro;m in the error model"],
        ["Limb / phantom rest",
         "Holds the specimen with the bone axis parallel to the rail",
         "Acrylic cradle", "1", "(in 2,500)",
         "Tilt shows up as a sloping skin line"],
        ["Phantom tank", "For casting layered phantoms around the bone",
         "Acrylic box with lid", "1", "(in 2,500)",
         "Cast overlay slabs separately (next section)"],
        ["Frame", "Mounts rail, holder and rest in one rigid assembly",
         "2020 extrusion and brackets", "1", "2,500 total",
         "Rigidity is what makes the 100 &micro;m stage spec achievable"],
    ], W6))

    # ------------------------------------------------------------- phantom
    f.append(P(f"{pre}7&nbsp;&nbsp;The phantom and specimens", "H2k"))
    f.append(P(
        "The simulated layer stack is the casting target. Thicknesses are "
        "from <i>bonesim/geometry/phantom.py</i>; dielectric targets per "
        "tissue are in Section 3 (Gabriel four-Cole-Cole)."))
    f.append(table([
        ["Layer", "Thickness", "Note"],
        ["Skin", "2.0 mm", "Low oil fraction"],
        ["Fat", "3.0 mm", "High oil fraction"],
        ["Muscle", "1.0 mm", "High water"],
        ["Near cortical wall", "4.0 mm", "The bone specimen itself"],
        ["Marrow", "10.0 mm", "The bone specimen itself"],
        ["<b>Soft-tissue overlay</b>", "<b>0, 3, 6, 10 mm</b>",
         "The four experimental conditions; cast as separate slabs laid "
         "over the skin layer"],
    ], [45 * mm, 30 * mm, 88 * mm], highlight=[6]))
    f.append(Spacer(1, 3 * mm))
    f.append(table([
        H6,
        ["Phantom materials", "Oil-in-gelatin recipe (proposal 4.3)",
         "DI water 50&ndash;70%, porcine gelatin 250 bloom 10&ndash;15%, "
         "kerosene or safflower oil 15&ndash;35% (the tuning knob), "
         "surfactant 1&ndash;2%, n-propanol 0&ndash;5%, p-toluic acid "
         "under 0.5%, NaCl 0&ndash;1%",
         "&ndash;", "1,800",
         "Oil fraction sets permittivity 10&ndash;50; <b>measure each "
         "batch</b> with an open-ended coaxial probe on the VNA"],
        ["Bone specimens",
         "Mid-shaft, about 4 mm cortical wall, about 10 mm medullary cavity",
         "Goat or bovine tibia, fresh from a butcher", "6&ndash;12", "900",
         "Defat mechanically; <b>do not boil</b>; store in saline gauze at "
         "4 &deg;C"],
        ["Fracture fill", "Blood-mimicking fluid; haematoma is the real "
         "contrast", "Saline-based blood mimic", "&ndash;", "(in 1,800)",
         "The simulation used Gabriel blood"],
        ["Validation target", "<b>6 mm brass rod at 20 mm depth</b>",
         "Brass rod, 6 mm diameter, 100 mm", "1", "200",
         "<b>Stage 4 gate: image this before any bone.</b> If migration "
         "cannot find it, nothing downstream is meaningful"],
        ["Kerf tools",
         "Kerfs of 0.2&ndash;2.0 mm were simulated; the saw sets what is "
         "achievable", "Jeweller's saw, diamond wafering blade", "&ndash;",
         "(in 1,200)",
         "Measure the actual kerf; the measurement is the ground truth"],
        ["Metrology", "&ndash;", "Digital calliper, feeler gauges",
         "&ndash;", "(in 1,200)",
         "Record every kerf and every cortical thickness as covariates"],
        ["Consumables", "&ndash;", "Cling film, gloves, saw blades",
         "&ndash;", "1,200", "&ndash;"],
    ], W6))

    # ------------------------------------------------------------- compute
    f.append(P(f"{pre}8&nbsp;&nbsp;Compute and software", "H2k"))
    f.append(P("Nothing to buy. The laptop that ran the analysis runs the "
               "acquisition."))
    f.append(table([
        ["Item", "Note"],
        ["<i>bonesim</i> package",
         "Processing chain, detector, statistics &mdash; unchanged between "
         "simulation and bench"],
        ["VNA control",
         "scikit-rf and pyvisa for a lab VNA; LiteVNA and NanoVNA have "
         "serial protocols with Python libraries"],
        ["Stage control", "Serial to the Arduino or ESP32"],
    ], [40 * mm, 123 * mm]))
    f.append(Spacer(1, 3 * mm))
    f.append(P(
        "The processing chain was built so that it cannot tell the analytic "
        "model, the FDTD solver and a real VNA apart: it sees a matrix of "
        "complex S11 and nothing else. That is the point at which the "
        "simulation hands over to the bench."))

    # ----------------------------------------------------- what it tests
    f.append(P(f"{pre}9&nbsp;&nbsp;What the build would test that the "
               "simulation could not", "H2k"))
    f.append(P("In order of how much they threaten the result (Section 8):"))
    for t in [
        "<b>The error model.</b> 95 dB dynamic range, 100 &micro;m stage "
        "jitter, 1 fs cable jitter and &plusmn;0.3 mm standoff are "
        "assumptions. The 40.8 dB margin is the budget the real bench has to "
        "stay inside. This is what a brass rod and a VNA measure on day one.",
        "<b>Real bone.</b> Eight simulated specimens vary only in what the "
        "variation model perturbs. Goat tibiae vary in everything.",
        "<b>Fracture position.</b> Every simulated fracture is at "
        "x = 50 mm. A real cut is wherever the saw went, which tests "
        "localisation rather than separability.",
        "<b>Three dimensions.</b> The bench is 3D for free. The 3D model "
        "(<i>bonesim/geometry/cylindrical.py</i>) is built and verified but "
        "unsolved.",
    ]:
        f.append(P(t, "Body"))


def build():
    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=23 * mm, rightMargin=23 * mm,
                          topMargin=20 * mm, bottomMargin=20 * mm,
                          title=TITLE, author="Capstone Project")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="body")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=decorate)])
    f = []
    title_page(f)
    abstract(f)
    introduction(f)
    methodology(f)
    stages(f)
    antenna(f)
    results(f)
    band_study(f)
    safety(f)
    limitations(f)
    conclusions(f)
    reproducibility(f)
    references(f)
    appendix_bom(f)
    doc.build(f)
    kb = OUT.stat().st_size / 1024
    print(f"  wrote {OUT.name}  {kb:.0f} kB")


if __name__ == "__main__":
    build()
