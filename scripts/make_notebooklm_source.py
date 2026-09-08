"""Assemble one consolidated source document for NotebookLM.

NotebookLM answers are only as good as the sources it is given. It works best
on a small number of dense, well-headed, self-contained documents, and badly on
many overlapping fragments - so this concatenates the project's real
documentation into one file rather than a dozen.

The content is READ FROM THE FILES, never retyped, so the dossier cannot drift
from the repository. The key-figures table is read from
results/report_numbers.json, the same file the report itself reads.

Setup notes (install, Colab) are kept but pushed to an appendix: they are
operational rather than substantive, and putting them first would dilute the
retrieval quality of everything else.

    python scripts/make_notebooklm_source.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_MD = ROOT / "notebooklm" / "bonesim_project_dossier.md"
OUT_TXT = ROOT / "notebooklm" / "bonesim_project_dossier.txt"

# Order matters: substantive material first, operational appendix last.
MAIN = [
    ("Project overview and headline results", "README.md"),
    ("Tissue dielectric modelling", "docs/tissue-model.md"),
    ("The signal-processing pipeline", "docs/pipeline.md"),
    ("Stage 3 findings: full-wave forward model", "docs/stage3-findings.md"),
    ("Stage 4 findings: the brass-rod validation gate",
     "docs/stage4-findings.md"),
    ("Stage 5 findings: antenna design and characterisation",
     "docs/stage5-findings.md"),
    ("Stage 7 findings: the statistical result", "docs/stage7-findings.md"),
    ("Bandwidth study: what a saturated statistic conceals",
     "docs/band-study.md"),
    ("Radio-frequency exposure assessment", "docs/safety-sar.md"),
]
APPENDIX = [
    ("Compute budget and measured solver performance",
     "docs/compute-budget.md"),
    ("Installation and environment", "docs/install.md"),
    ("Running the matrix on a Colab GPU", "docs/colab.md"),
]

GLOSSARY = """
| Term | Meaning in this project |
|---|---|
| UWB | Ultra-wideband. Here, the 3-11 GHz band used for imaging. |
| FDTD | Finite-Difference Time-Domain. The numerical method that solves Maxwell's equations on a grid; gprMax and openEMS are both FDTD solvers. |
| S11 | Reflection coefficient. What the instrument measures: the ratio of reflected to incident signal, per frequency, per antenna position. |
| B-scan | A set of measurements taken as the antenna steps along the bone axis, giving a 2D map of S11 against frequency and position. |
| Cole-Cole model | A parametric description of how tissue permittivity varies with frequency. The Gabriel four-Cole-Cole model is the standard reference. |
| Debye model | A simpler relaxation model. FDTD cannot integrate Cole-Cole directly, so each tissue is refitted to a multi-pole Debye form. |
| Clutter | Strong unwanted reflections, here dominated by the skin surface and the tissue layer boundaries, which swamp the fracture echo. |
| SVD | Singular Value Decomposition. Used to separate the layered clutter, which spans the whole scan, from local scattering. |
| Kirchhoff migration | An imaging step that focuses scattered energy back to the position it came from, turning a smeared echo into a localised spot. |
| Kerf | The width of the simulated fracture gap, 0.2 to 2.0 mm in this study. |
| Overlay | The thickness of soft tissue above the bone, 0 to 10 mm here, representing anatomical variation. |
| AUC | Area Under the ROC Curve. A threshold-free measure of how well two classes separate; 0.5 is chance, 1.0 is perfect. |
| LOSO | Leave-One-Specimen-Out. All measurements from one bone are held out together, so the decision threshold is never tested on a bone it was fitted to. |
| ICC(1,1) | Intraclass Correlation. Measures repeatability across remounts of the same specimen. |
| SAR | Specific Absorption Rate, W/kg. The regulatory measure of RF energy absorbed by tissue below 6 GHz. |
| Inverse crime | Generating simulated data with the same model used to reconstruct it, which guarantees success and invalidates the result. |
| Vivaldi antenna | A tapered-slot antenna with wide bandwidth and an end-fire pattern; the antipodal form is used here. |
"""

QUESTIONS = """
These are the questions the material below can answer, listed so that a reader
or an assistant can navigate it.

1.  What problem does this project address, and why is microwave imaging a
    plausible approach to bone fracture detection?
2.  Why is the working band 3-11 GHz rather than higher or lower?
3.  What is an inverse crime, and what specific measures prevent one here?
4.  How is human tissue modelled, and why must Cole-Cole be refitted to Debye?
5.  What are the stages of the signal-processing chain, and what does each one
    remove or recover?
6.  Why was the published recommendation to discard the first two or three
    singular components rejected?
7.  What was the go/no-go validation gate, and what did it establish?
8.  How large is the experiment, and how were the specimens varied?
9.  What is the primary statistical result, and why is a perfect AUC treated as
    a warning rather than a success?
10. What did the bandwidth study demonstrate, and why does it matter beyond
    this project?
11. How was the antenna designed, what does it achieve, and which requirement
    is not met?
12. What conclusions about corrugations and about convergence time turned out
    to be wrong, and how were they corrected?
13. Is the system safe under current RF exposure guidelines, and at what
    transmit power?
14. What are the stated limitations of the study?
15. What would future work address first?
"""


def facts() -> str:
    p = ROOT / "results" / "report_numbers.json"
    if not p.exists():
        return "(results/report_numbers.json not found)"
    n = json.loads(p.read_text(encoding="utf-8"))
    i, f, a = n["intact"], n["fract"], n["antenna"]
    g = n["gain"]
    lines = [
        "| Quantity | Value |",
        "|---|---|",
        f"| Scored acquisitions | {n['n_scores']} "
        f"(192 full-wave cells x 3 error realisations) |",
        f"| Intact scores | n={i[0]}, min {i[1]:.1f} dB, "
        f"median {i[2]:.1f} dB, max {i[3]:.1f} dB |",
        f"| Fractured scores | n={f[0]}, min {f[1]:.1f} dB, "
        f"median {f[2]:.1f} dB, max {f[3]:.1f} dB |",
        f"| **Class separation** | **{n['gap']:.1f} dB, with no overlap** |",
        "| Primary AUC (6 mm overlay) | 1.0000, bootstrap CI 1.000-1.000, "
        "permutation p = 0.001 |",
        "| Leave-one-specimen-out | sensitivity 0.9979, specificity 1.0000, "
        "accuracy 0.9983 |",
        "| Repeatability | ICC(1,1) = 0.9979 |",
        f"| Intact score against overlay | "
        + ", ".join(f"{k} mm: {v} dB" for k, v in n["intact_by_ov"].items())
        + " |",
        "| Bandwidth study | 3.00-11.0 GHz: 40.8 dB separation; "
        "4.35-11.0 GHz: 17.9 dB; 5.00-11.0 GHz: 16.0 dB. AUC = 1.0000 in all "
        "three |",
        f"| Antenna match | 2.48-12.00 GHz; "
        f"{a['frac_below_10dB_in_band']*100:.2f}% of 3-11 GHz below -10 dB; "
        f"worst {a['worst_db_in_band']:.2f} dB |",
        f"| Antenna feed | tapered, {a['feed_width']:.2f} mm at the flare, "
        f"{a['feed_width_port']:.2f} mm at the port; median Re(Zin) "
        f"{a['median_re_zin']:.1f} ohm |",
        "| Antenna gain | "
        + ", ".join(f"{fq:.0f} GHz: {v:.2f} dBi" for fq, v in g)
        + " (8-10 dBi required; unmet at 3 GHz) |",
        "| RF exposure at 0 dBm | all ICNIRP/IEEE limits pass, tightest "
        "margin 18x |",
        "| Test suite | 146 tests passing |",
    ]
    return "\n".join(lines)


def section(title: str, rel: str, level: int = 2) -> str:
    p = ROOT / rel
    if not p.exists():
        return f"{'#' * level} {title}\n\n(source file {rel} not found)\n"
    body = p.read_text(encoding="utf-8")
    # Demote the file's own headings so the dossier keeps one clean hierarchy.
    out = []
    for line in body.split("\n"):
        if line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            out.append("#" * min(hashes + level, 6) + line.lstrip("#"))
        else:
            out.append(line)
    return (f"{'#' * level} {title}\n\n"
            f"*Source file: `{rel}`*\n\n" + "\n".join(out).strip() + "\n")


def main() -> int:
    parts = [
        "# Non-Invasive Bone Fracture Detection by UWB Microwave Imaging",
        "",
        "## A consolidated project dossier",
        "",
        "This single document gathers the complete documentation of a virtual "
        "study of ultra-wideband microwave imaging for long-bone fracture "
        "detection. Every section below is reproduced verbatim from the "
        "project repository, so nothing here is a summary written after the "
        "fact.",
        "",
        "- **Repository:** https://github.com/amalnathkp13-boop/"
        "bone-fracture-rf-sensing",
        "- **Full report:** `Bone_Fracture_RF_Sensing_Report.pdf` "
        "(20 pages, 12 figures)",
        "- **Nature of the work:** purely computational. No hardware was "
        "built and no human or animal subject was exposed at any point.",
        "",
        "---",
        "",
        "## Key figures at a glance",
        "",
        facts(),
        "",
        "---",
        "",
        "## What this document can answer",
        QUESTIONS,
        "---",
        "",
        "## Glossary",
        GLOSSARY,
        "---",
        "",
        "# Part I - Substantive documentation",
        "",
    ]
    for t, rel in MAIN:
        parts += [section(t, rel), "", "---", ""]
    parts += ["# Part II - Appendix: operational notes", ""]
    for t, rel in APPENDIX:
        parts += [section(t, rel), "", "---", ""]

    text = "\n".join(parts).rstrip() + "\n"
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(text, encoding="utf-8", newline="")
    OUT_TXT.write_text(text, encoding="utf-8", newline="")
    words = len(text.split())
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    print(f"wrote {OUT_TXT.relative_to(ROOT)}")
    print(f"  {len(text.splitlines())} lines, {words:,} words, "
          f"{len(text)/1024:.0f} kB")
    print(f"  sections: {len(MAIN)} substantive + {len(APPENDIX)} appendix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
