# Non-Invasive Bone Fracture Detection by UWB Microwave Imaging

## A consolidated project dossier

This single document gathers the complete documentation of a virtual study of ultra-wideband microwave imaging for long-bone fracture detection. Every section below is reproduced verbatim from the project repository, so nothing here is a summary written after the fact.

- **Repository:** https://github.com/amalnathkp13-boop/bone-fracture-rf-sensing
- **Full report:** `Bone_Fracture_RF_Sensing_Report.pdf` (20 pages, 12 figures)
- **Nature of the work:** purely computational. No hardware was built and no human or animal subject was exposed at any point.

---

## Key figures at a glance

| Quantity | Value |
|---|---|
| Scored acquisitions | 576 (192 full-wave cells x 3 error realisations) |
| Intact scores | n=96, min 8.8 dB, median 19.3 dB, max 27.7 dB |
| Fractured scores | n=480, min 68.5 dB, median 89.9 dB, max 104.8 dB |
| **Class separation** | **40.8 dB, with no overlap** |
| Primary AUC (6 mm overlay) | 1.0000, bootstrap CI 1.000-1.000, permutation p = 0.001 |
| Leave-one-specimen-out | sensitivity 0.9979, specificity 1.0000, accuracy 0.9983 |
| Repeatability | ICC(1,1) = 0.9979 |
| Intact score against overlay | 0 mm: 14.3 dB, 3 mm: 16.5 dB, 6 mm: 22.6 dB, 10 mm: 25.1 dB |
| Bandwidth study | 3.00-11.0 GHz: 40.8 dB separation; 4.35-11.0 GHz: 17.9 dB; 5.00-11.0 GHz: 16.0 dB. AUC = 1.0000 in all three |
| Antenna match | 2.48-12.00 GHz; 99.69% of 3-11 GHz below -10 dB; worst -9.98 dB |
| Antenna feed | tapered, 4.50 mm at the flare, 1.74 mm at the port; median Re(Zin) 45.6 ohm |
| Antenna gain | 3 GHz: 7.02 dBi, 5 GHz: 11.87 dBi, 7 GHz: 12.49 dBi, 9 GHz: 12.06 dBi, 11 GHz: 9.33 dBi (8-10 dBi required; unmet at 3 GHz) |
| RF exposure at 0 dBm | all ICNIRP/IEEE limits pass, tightest margin 18x |
| Test suite | 146 tests passing |

---

## What this document can answer

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

---

## Glossary

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

---

# Part I - Substantive documentation

## Project overview and headline results

*Source file: `README.md`*

### bonesim — Virtual UWB Microwave Imaging for Long-Bone Fracture Detection

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](environment.yml)
[![Tests](https://img.shields.io/badge/tests-146%20passing-brightgreen.svg)](tests/)

A fully in-silico study of monostatic ultra-wideband microwave imaging at 3–11 GHz for
detecting fractures in long bones, with SVD clutter removal and Kirchhoff migration.

**No hardware was built.** Every number below is produced by the code in this repository.

📄 **[Full report (20 pages, 12 figures)](Bone_Fracture_RF_Sensing_Report.pdf)**

---

#### Headline results

| | |
|---|---|
| **Class separation** | **40.8 dB**, no overlap, across 192 full-wave acquisitions |
| Area under ROC curve | 1.0000 (bootstrap CI 1.000–1.000, permutation *p* = 0.001) |
| Leave-one-specimen-out | sensitivity 0.998, specificity 1.000 |
| Repeatability | ICC(1,1) = 0.998 |
| Antenna match | 2.48–12.00 GHz, 99.69% of the design band |
| RF exposure | all ICNIRP/IEEE limits pass, minimum margin 18× |

Design space covered: 8 simulated specimens × 4 soft-tissue overlays (0–10 mm) ×
6 fracture states (0.2–2.0 mm kerf, plus oblique and intact).

##### How a measurement is taken and processed

![Acquisition and processing](figures/measurement_pipeline.png)

Every panel except the schematic is real solver output from one matrix cell — a 1 mm
fracture under 6 mm of overlay. The fracture is genuinely invisible in the raw data,
still buried after empty-scene subtraction, and only emerges after clutter removal.

---

#### The finding worth reading, which is not the AUC

An AUC of 1.0000 is normally a sign of a data leak, and it was treated as one. It
survives inspection — the two classes are separated by a real 40.8 dB gap with no
overlap, and the weakest fractured cases are exactly the physically hardest ones. But a
perfect score is **saturated**, and a saturated statistic cannot measure margin.

That is demonstrated rather than asserted. Re-scoring the whole matrix over a restricted
band, with no new simulation:

| band | bandwidth | AUC | separation |
|---|---|---|---|
| 3.00–11.0 GHz (design target) | 8.00 GHz | 1.0000 | **40.8 dB** |
| 4.35–11.0 GHz (initial antenna) | 6.65 GHz | 1.0000 | **17.9 dB** |
| 5.00–11.0 GHz (deliberately worse) | 6.00 GHz | 1.0000 | 16.0 dB |

**Removing 3.00–4.35 GHz costs more than half the separation. The AUC registers none of
it.** Reporting that statistic alone would have supported the incorrect conclusion that
the antenna's shortfall was inconsequential — and it is what motivated the antenna
redesign that recovered the band. See [`docs/band-study.md`](docs/band-study.md).

![Statistical result](figures/stage7_statistics.png)

---

#### What this is, and what it is not

This is a **simulation study**. It answers *"if you built this instrument, what would it
be able to detect?"* — it is not a measurement of a real bone.

That distinction matters because simulated imaging studies have a specific, well-known
failure mode, and this repository is organised around avoiding it.

##### The inverse-crime problem

If the model that **generates** the data and the model that **reconstructs** the image
share their assumptions, reconstruction always succeeds and the result is circular. This
is an *inverse crime*, and it is the first thing a competent reviewer looks for.

The countermeasures are structural, not cosmetic:

| | Forward model (data) | Inverse model (image) |
|---|---|---|
| Physics | Full-wave FDTD, dispersive tissue | Migration in a homogeneous medium |
| Tissue | 4-Cole-Cole → multi-pole Debye, 6 layers | One scalar `eps_avg`, found by autofocus |
| Geometry | Layered cortex, marrow cavity, real kerf | Unknown; never supplied to the reconstructor |
| Grid | FDTD cells, 0.2 mm | Independent imaging grid |
| Instrument | Noise, cable drift, stage jitter injected | Blind to all injected error |

The reconstructor is never given the permittivity profile, the bone geometry, the
fracture position, or the noise realisation. It sees a matrix of complex S11 values,
exactly as it would from a VNA.

##### What simulation cannot supply

Hardware gives you certain error sources for free. In simulation they must be modelled
explicitly, and the study's credibility rests on how honestly that is done:

- VNA receiver noise at finite IF bandwidth
- Cable phase drift between scan positions
- Linear-stage position jitter and backlash
- Standoff (antenna-to-skin) variation
- Specimen-to-specimen variation in tissue properties and bone geometry

These live in `bonesim/perturb/` and are applied **after** the forward solve, so one FDTD
result generates several independent "remounts" — cheaper, and physically correct, since
a remount changes the instrument rather than the anatomy.

---

#### Honest limitations

Stated here rather than buried, because a result whose limits are not stated cannot be
assessed. Full discussion in [the report](Bone_Fracture_RF_Sensing_Report.pdf), §8.

1. **The injected error model is the binding assumption.** A real bench adds cable flex,
   connector repeatability, operator variation and genuine inter-bone heterogeneity. The
   40.8 dB margin is the budget those unmodelled terms must consume.
2. **Every fracture is at a known position.** This measures separability, not
   localisation.
3. **Propagation is 2D TMz.** A 3D cylindrical model has been built and verified
   (`bonesim/geometry/cylindrical.py`) but the comparison has not yet been run.
4. **Eight simulated specimens are not eight cadaveric bones.**
5. **The imaging model excites with an elementary dipole**, not the Vivaldi of Stage 5.
6. **Antenna gain is unmet at 3 GHz** — 7.02 dBi against an 8–10 dBi requirement, shown
   not to be reachable by resizing within the specified board.
7. **Exposure is assessed by simulation**, not by IEC 62209 measurement.

---

#### Repository layout

```
bonesim/
  materials/   Gabriel 4-Cole-Cole tissue models -> multi-pole Debye fits for FDTD
  geometry/    Layered phantom, and the 3D cylindrical limb
  forward/     Data generation. Interchangeable backends:
                 analytic.py   fast layered Green's function (seconds, for development)
                 gprmax.py     full-wave 2D FDTD B-scan (hours, for the real dataset)
                 gprmax3d.py   full-wave 3D, cylindrical limb
  antenna/     Antipodal Vivaldi geometry and the openEMS model
  vna/         Instrument emulation: time domain -> S11(f), IF bandwidth, noise floor
  perturb/     Injected instrument and specimen error models
  process/     Empty-scene subtraction, SVD clutter removal, time gating, migration
  detect/      Scalar detection metric (peak-to-background ratio)
  stats/       ROC/AUC, leave-one-specimen-out CV, permutation test, bootstrap CIs
  safety/      SAR and absorbed power density against ICNIRP 2020 / IEEE C95.1
scripts/       Entry points; every figure and number in the report comes from one
config/        Experiment matrix definitions and solver settings
tests/         146 unit tests, including the analytic-vs-FDTD cross-check
docs/          Install notes, per-stage findings, and the statistical analysis plan
notebooks/     Colab notebooks for the GPU runs
figures/       Committed, because they cannot be rebuilt without the 127 MB of runs/
```

The forward backends share one interface. The processing chain cannot tell them apart,
which is what makes it possible to develop and unit-test the whole pipeline in seconds
and only then spend FDTD hours on it.

---

#### Status

| Stage | Description | State |
|---|---|---|
| 0 | WSL2 environment, gprMax, compute benchmark | **complete** |
| 1 | Cole-Cole → Debye fitting, validated against published curves | **complete** |
| 2 | Analytic forward model + full processing chain | **complete** |
| 3 | gprMax geometry builder and B-scan driver | **complete** |
| 4 | Brass-rod validation gate | **complete** |
| 5 | Antipodal Vivaldi in openEMS | **complete** — 2.48–12.00 GHz; gain unmet at 3 GHz, see [`docs/stage5-findings.md`](docs/stage5-findings.md) |
| 6 | Full 192-cell experiment matrix (8 specimens) | **complete** — 192/192 on a Colab T4 |
| 7 | Statistical analysis plan | **complete** — see [`docs/stage7-findings.md`](docs/stage7-findings.md) |
| 8 | 3D cylindrical limb | **model built and verified; run pending** |
| — | RF exposure assessment | **complete** — 0 dBm adopted, all limits pass by ≥18×, see [`docs/safety-sar.md`](docs/safety-sar.md) |

Stage 4 was the go/no-go gate: if migration could not image a 6 mm conducting rod at
20 mm depth in phantom, nothing downstream would be meaningful.

---

#### Reproducing

Reading the results needs nothing but Python. Regenerating the *data* needs gprMax and
openEMS, both built from source — see [`docs/install.md`](docs/install.md).

```bash
conda env create -f environment.yml && conda activate bonesim   # or: pip install -r requirements.txt
python -m pytest tests/ -q          # 146 tests, no solver required
python scripts/run_sar.py           # exposure assessment, no solver required
python scripts/make_report.py       # rebuild the PDF from committed figures
```

With solver output present in `runs/` (127 MB, not hosted here):

```bash
python scripts/make_figures.py      # every figure in the report
python scripts/run_stage7.py        # the statistical analysis
python scripts/run_band_study.py    # the bandwidth study
```

Source lives on the Windows filesystem; simulation output is written to WSL-native
storage, because gprMax produces many small HDF5 files and cross-filesystem I/O under
WSL2 is roughly an order of magnitude slower.

##### A note on measured timings

Every runtime figure in this repository is measured, not extrapolated. That rule exists
because an early convergence estimate of "about 40 hours" turned out to be the laptop
entering Modern Standby and suspending the solver while gprMax kept counting wall-clock
time; the real figure was 10 minutes. openEMS's Mcell/s reading is the honest one,
because it excludes suspended time.

---

#### Third-party software

| Tool | Role | Licence |
|---|---|---|
| [gprMax](https://github.com/gprMax/gprMax) 3.1.7 | 2D/3D FDTD forward solver | GPLv3 |
| [openEMS](https://github.com/thliebig/openEMS-Project) v0.37.0-rc1 | Antenna FDTD, S-parameters, far fields | GPLv3 |

Neither is vendored here; both are built from source per `docs/install.md`. Tissue
dielectric parameters are the Gabriel four-Cole-Cole models; densities are from the
IT'IS Foundation database v4.1.

#### Licence and citation

MIT — see [LICENSE](LICENSE). If you use this work, please cite it; metadata is in
[CITATION.cff](CITATION.cff).


---

## Tissue dielectric modelling

*Source file: `docs/tissue-model.md`*

### Tissue model: findings against the proposal

Stage 1 implements the Gabriel four-Cole-Cole parametrisation and fits Debye
models to it for FDTD. Validating that implementation against the proposal's own
tables surfaced three discrepancies. All three are documented here because each
one changes something a reviewer might check.

#### 1. Section 1.1 is labelled with the wrong quantity

The table is captioned "one-way 1/e power decay distance". The numbers in it are
the conventional field penetration depth, delta = 1/alpha, which is twice the
power depth. Reproducing the table from Gabriel's model gives ratios of 0.73 to
1.12 against the quoted values across 1-77 GHz when compared as field depth, and
a uniform factor of roughly 2 when compared as power depth.

| f (GHz) | field depth, muscle (mm) | quoted (mm) | power depth (mm) |
|---|---|---|---|
| 1 | 40.7 | 40 | 20.3 |
| 5 | 9.3 | 10 | 4.7 |
| 11 | 2.9 | 4.0 | 1.5 |
| 60 | 0.41 | 0.5 | 0.20 |
| 77 | 0.34 | 0.4 | 0.17 |

**The conclusion of section 1 is unaffected.** Whether 60 GHz reaches 0.41 mm or
0.20 mm, it is hopeless against 3-8 mm of overlay. Only the caption needs fixing,
and it should be fixed before a jury sees it, because a reviewer who recomputes
the table will find the factor of two and will not assume it was the caption.

Both quantities are available: `penetration_depth()` and
`power_penetration_depth()`.

#### 2. Cortical bone permittivity — a first-order sensitivity

| Source | eps_r at 10 GHz |
|---|---|
| Gabriel 1996 parametrisation | 8.12 |
| Proposal section 2.1 | 11-12 |

This is not an error in either. Gabriel's paper states the water content of
cortical bone is below 20%, and permittivity in this band is dominated by water
relaxation. Fresh, fully hydrated bone sits higher. Section 4.1 of the proposal
makes the same point from the other direction when it insists specimens be kept
in saline-soaked gauze because "dried bone has very different dielectric
properties from living bone and will invalidate your results."

It matters here because bone permittivity sets both the bone/blood contrast that
makes a fracture visible and the refraction of the imaging path, which
migration must compensate.

Both variants are therefore carried:

- `CORTICAL_BONE` — Gabriel verbatim, eps_r 8.12 at 10 GHz
- `CORTICAL_BONE_WET` — the first (water) dispersion scaled by 1.61 to reach
  eps_r 11.5 at 10 GHz, giving 12.4 at 8.3 GHz, inside the proposal's range

The scaling is a calibrated stand-in, not an independently measured
parametrisation, and is labelled as such in the material's `source` field.
Stage 7 reports the experiment matrix under both.

#### 3. Quoted conductivities are low-frequency values

Section 2.1 is headed "near 10 GHz", but the conductivity column for bone and
marrow is roughly the 1 GHz value:

| tissue | sigma at 10 GHz | sigma at 1 GHz | quoted |
|---|---|---|---|
| cortical bone | 2.14 | 0.16 | 0.15-0.5 |
| marrow | 0.58 | 0.04 | 0.1 |
| blood | 13.13 | 1.58 | 13 |
| muscle | 10.62 | 0.98 | 11 |

Blood, muscle, skin and fat are correct at 10 GHz; bone and marrow are not.
Low impact, since the model uses the parametrisation rather than the table, but
worth knowing before quoting the table in a report.

#### What validated cleanly

Blood, muscle, dry skin and fat reproduce the section 2.1 permittivities to
within 3% and conductivities to within 5%. The penetration-depth table
reproduces across nearly two decades of frequency. These are strong checks: the
implementation is not tuned to them.

#### Debye fits

Two poles per tissue, fitted over 3-11 GHz only, worst-case error 0.233%
(cortical bone). One pole would meet a 2% target but leaves cortical bone at
1.9%, and cortical bone is the material being imaged — that error is a
systematic bias on the target itself, not noise. All relaxation times land
between 7.4 and 80 ps, comfortably above the 0.47 ps time step gprMax requires
them to exceed.

Cards are generated into `config/materials.in`; never edit that file by hand.


---

## The signal-processing pipeline

*Source file: `docs/pipeline.md`*

### Processing chain: findings against proposal 2.5

Stage 2 implements the chain of section 2.5 and validates it end to end on
analytic data. Four things had to change from the text as written, and one
piece of physics turned up that the proposal does not anticipate.

#### 1. Migration must be done in the time domain

Written literally, step 6 costs one complex exponential per (pixel, scan
position, frequency): about 240 million per image at working resolution. A
single image took roughly 20 s and autofocus, which migrates 30-odd times,
never finished.

Because the frequency samples are uniform, the inner sum is a DFT evaluated at
an arbitrary delay:

    sum_m M[m,n] exp(j 2 pi (f0 + m df) tau)
        = exp(j 2 pi f0 tau) sum_m M[m,n] exp(j 2 pi m df tau)

so each scan position is inverse-transformed once onto a padded time grid and
sampled at the delay each pixel needs. **0.068 s per image, a 300x speedup**,
verified against the literal double sum to a relative error of 2e-4 with
correlation 0.99999999 and the same peak pixel. This is what makes autofocus and
a 192-scan matrix affordable.

#### 2. K = 2 is right, but only once instrument errors are present

With no errors the clutter is *exactly* rank 1 - the second singular value is
7e-15, machine epsilon - because an intact limb gives an identical column at
every scan position. In that idealised case K = 2 destroys about half the
fracture signal.

Adding the error model changes the answer, and the proposal's guidance is
vindicated. Turning error sources on one at a time, against a fracture signal of
2.65e-2:

| error source | residual at K=1 | K=2 | K=3 |
|---|---|---|---|
| none | 8.5e-15 | 8.5e-15 | 8.4e-15 |
| receiver noise | 2.0e-5 | 1.9e-5 | 1.9e-5 |
| cable drift | 3.4e-4 | 3.4e-8 | 2.2e-12 |
| stage jitter | 8.5e-15 | 8.5e-15 | 8.4e-15 |
| **standoff drift** | **5.0e-2** | 6.2e-4 | 7.3e-6 |

Standoff drift dominates everything else, and at K=1 it leaves a residual twice
the fracture signal. At K=2 it is 42x below it. So **K=2, and the binding
constraint on the instrument is standoff stability, not stage repeatability** -
stage jitter at 100 um contributes nothing measurable.

#### 3. There is no detectable bone line

Step 8 asks for a region of interest "along the detected bone line". This cannot
be done as written:

* **After SVD there is no bone line.** Coherence along the scan axis is the
  definition of what SVD removes, and a specular reflection from the bone
  surface is coherent along the scan axis. It goes with the skin.
* **Before SVD the bone line cannot be found.** The skin reflection is about
  20 dB stronger and its point-spread function, roughly 5 mm at this bandwidth,
  smears over the cortex. Searching for the brightest laterally-continuous
  structure returns the skin every time - in testing it returned 2.0 mm against
  a true cortex at 6.0 mm, and the resulting region of interest then excluded
  the fracture at 8.0 mm entirely.

The detector uses a **fixed anatomical depth window** (3-20 mm) instead,
identical for every acquisition, so it leaks no ground truth. Taking the depth
from the phantom would have inflated every result in the study.

Worth noting that the post-SVD image locates the fracture in depth correctly
without any help: its median depth profile peaks at 8.0 mm against a true
fracture centre of 8.0 mm.

#### 4. Peak-to-background is the wrong detector

Step 8 proposes "the peak-to-background ratio within a region of interest". On
these images it inverts. Migrating a single point scatterer across a finite
aperture smears energy over the whole image, so a stronger target raises its own
background nearly as fast as it raises its peak, and the ratio compresses.

Measured at 6 mm overlay, the absolute peak orders the kerfs correctly while the
ratio reverses them:

| kerf | absolute peak | peak-to-background |
|---|---|---|
| 0.3 mm | 39.5 | 16.7 dB |
| 0.5 mm | 58.5 | 15.9 dB |
| 1.0 mm | 84.8 | 14.4 dB |
| 2.0 mm | 89.1 | 12.2 dB |
| intact | 0.60 | 15.4 dB |

Note the intact limb scoring *above* a 1 mm fracture. Widening the exclusion
zone from 8 to 25 mm did not fix it, because the smear is global.

The detector therefore references the peak to the **receiver noise floor**,
which does not scale with the target - an ordinary radar SNR. This is legitimate
here because a SOL-calibrated S11 is an absolute reflection coefficient, not an
arbitrary-gain quantity. The noise level is estimated from the singular-value
tail of the data matrix, so no separate noise acquisition is needed.

With that change the ordering is correct and the separation is large: 95.3,
98.7, 101.8, 102.3 dB across the four kerfs against 59.3 dB intact.

#### 5. Fracture scattering is resonant, not linear in kerf

The proposal treats kerf as a simple sensitivity axis - section 9 anticipates
"detection works only at 2 mm kerf". The physics is not monotone. A blood-filled
gap in cortical bone is a **quarter-wave resonator**: lambda/4 in blood is about
1.1 mm at 10 GHz, so at a single frequency the reflection peaks near 1 mm kerf
and falls again by 2 mm.

Band-averaged over 3-11 GHz the resonance partly smears, leaving a residual
1 dB dip at 2 mm kerf at 3 mm overlay. Two consequences:

* a wider fracture is not necessarily easier to see, and reporting "minimum
  detectable kerf" as a single monotone threshold would be wrong
* the effect is a prediction of this model and must be checked against full-wave
  FDTD in Stage 4 before it is reported as a finding

#### What validated cleanly

* localisation to **0.2 mm** against a true fracture at 50.0 mm, with the
  reconstructor blind to the layer structure, the bone depth and the fracture
  position
* **43.8 dB** separation between fractured and intact at 6 mm overlay
* the overlay envelope, which is the proposal's headline result (4.3): lift over
  intact falls **40.3 -> 37.2 -> 31.1 dB** as overlay goes 3 -> 6 -> 10 mm

None of this is evidence that the method works. The analytic forward model uses
straight rays and so does migration, so it is an inverse crime by construction
and detection is guaranteed. It validates the *pipeline*. The physics test is
Stage 4, against gprMax.


---

## Stage 3 findings: full-wave forward model

*Source file: `docs/stage3-findings.md`*

### Stage 3: first full-wave result

Two 61-position gprMax B-scans, fractured and intact, 610 s each. This is the
first result in the project that is not an inverse crime: the data comes from a
full-wave solver with dispersive layered tissue, a curved wavefront, near-field
antenna coupling and multiple reflections, and the reconstructor is given a
single scalar permittivity and nothing else.

#### The fracture is found

| quantity | value |
|---|---|
| true fracture position | 50.0 mm |
| recovered position, k=1 | **49.8 mm** |
| error | 0.2 mm, under one 0.5 mm imaging cell |
| fracture response vs skin clutter | -21.1 dB |
| peak amplitude, fractured vs intact | 370x |

Confirmed independently. Migrating the pure difference of the two scans
(fractured minus intact, no SVD at all) also peaks at 49.8 mm, so the SVD
pipeline and a direct subtraction agree on where the scatterer is.

The singular spectra separate cleanly:

| | s1/s0 | s2/s0 | s3/s0 |
|---|---|---|---|
| fractured | 1.49e-2 | 1.27e-3 | 1.41e-4 |
| intact | 1.61e-5 | 6.90e-6 | 3.80e-6 |

About a thousand times more energy in the second component when a fracture is
present. That component *is* the fracture.

#### The proposal's guidance on k is wrong here

Section 2.5 says "typically K = 2 or 3". On this geometry that destroys the
result, because the fracture lives in the second singular component:

| k | recovered x | error | interpretation |
|---|---|---|---|
| 1 | 49.8 mm | 0.2 mm | correct |
| 2 | 38.3 mm | 11.7 mm | fracture removed with the clutter |
| 3 | 70.6 mm | 20.6 mm | noise |
| 4 | 32.4 mm | 17.6 mm | noise |

k must be chosen from the singular spectrum, not from a rule of thumb. The
proposal is right that k should be swept and its sensitivity reported; it is
wrong about which value to expect.

This is worth stating plainly in the report. It is a concrete, defensible
finding that came out of doing the work.

#### Two errors in the first pass, both now fixed

##### The detector had no noise floor

The first run reported a peak-to-noise ratio near 300 dB. That is not a result.
FDTD output is deterministic, so the noise estimated from the singular tail came
out at 5.95e-17, or 5.4e-16 of the signal peak - machine epsilon. The detector
divided by it.

With the instrument model applied, the floor is real:

| | sigma | vs signal peak |
|---|---|---|
| noiseless solver output | 5.95e-17 | 5.4e-16 |
| with instrument errors | 1.95e-06 | 1.75e-05 |

The second line corresponds to the stated 95 dB dynamic range. Every SNR figure
from the first pass should be discarded; none was quoted in any deliverable.

**A simulation-only study must inject the instrument.** Without it, ratio
detectors are scale-invariant and report nonsense with complete confidence.

##### eps_avg was fixed by hand

The first pass set eps_avg = 9.0 rather than autofocusing, putting the
reconstructed depth at 12.8 mm against a true cortex at 6.0 mm. With autofocus
the peak moves to 8.8 mm - better, and still 2.8 mm deep.

#### Autofocus was broken, and the fix is instructive

Autofocus returned eps_avg = 20.0, the upper bound of its search. Widening the
sweep to 60 showed why: **both focus metrics improved monotonically across the
whole range, with no turning point at all.**

| eps_avg | 4 | 12 | 20 | 32 | 48 | 60 |
|---|---|---|---|---|---|---|
| entropy (whole image) | 9.735 | 9.328 | 9.064 | 8.945 | 8.849 | 8.776 |
| peak-to-average | 1.50 | 2.82 | 3.62 | 4.07 | 4.37 | 4.84 |
| depth (mm) | 18.2 | 11.4 | 8.8 | 6.6 | 5.2 | 2.2 |

The cause is geometric, not physical. Raising eps_avg lowers the assumed
velocity, which compresses the entire image toward the surface. Energy then
concentrates into fewer pixels, so any whole-image sharpness metric improves
without limit. **The optimiser was rewarding compression and calling it focus.**

The fix is to evaluate the metric over a *fixed physical depth window* so the
pixel count contributing to it cannot change. With a 3-20 mm window, entropy
develops a genuine interior minimum:

| eps_avg | 16 | 20 | 24 | **28** | 32 | 40 | 60 |
|---|---|---|---|---|---|---|---|
| entropy (windowed) | 8.582 | 8.510 | 8.484 | **8.482** | 8.490 | 8.510 | 8.507 |

The optimum at eps_avg = 28 places the scatterer at z = 7.2 mm, inside the
6-10 mm gap. Peak-to-average still rails to the bound even with the window,
because the single brightest pixel keeps sharpening as the image compresses, so
entropy is the metric to use and peak-to-average is kept only for comparison.

Two things worth carrying into the report:

**eps_avg is effective, not physical.** The layer stack averages to eps_r 15.2
at 7 GHz, but the best-focusing value is 28. Migration assumes straight rays, so
the recovered permittivity has to absorb the refraction the model omits. The
proposal already calls it "an effective permittivity for the layered path";
this quantifies how far from physical that can be.

**The first depth error was partly a mis-comparison.** A transverse fracture is
a blood-filled gap spanning the whole cortical wall, 6 to 10 mm, so its
scattering centroid is mid-wall at 8 mm - not the 6 mm cortex surface the first
pass compared against.

#### Lateral localisation is remarkably robust

Across every eps_avg from 4 to 60 - a fifteen-fold span of assumed permittivity,
moving the reconstructed depth from 18.2 mm to 2.2 mm - the lateral position
stayed at 49.8 mm, a 0.2 mm error, in **20 out of 20** cases.

Along-track position is fixed by the aperture geometry and the shape of the
hyperbolic moveout, not by the assumed velocity. Velocity errors move a target
in depth, not sideways.

This matters clinically. Answering *is there a fracture, and where along the
bone* is robust to getting the tissue model wrong. Answering *how deep* is not.

#### Cost

Measured, and it revises the earlier estimate upward:

| | value |
|---|---|
| throughput, dispersive production model | 74 M cell-updates/s |
| throughput, non-dispersive benchmark | 178 M cell-updates/s |
| cost of dispersion | **2.4x** |
| one B-scan, 61 positions plus reference | 610 s |
| full matrix, 192 B-scans | **32.5 h** |

See `docs/colab.md` for whether to move that to a hosted GPU.


---

#### Re-verified after Stages 4 and 5

The numbers above were recorded before three later improvements. Re-running
`scripts/analyse_stage3.py` against the same saved scans with the current
pipeline changes the result materially, and in every case for the better.

**Autofocus now finds a real optimum.** With the focus metric restricted to a
fixed depth window and the search widened to 45, it returns eps_avg = 26.4 as an
interior minimum rather than railing against a bound at 20.0.

**Depth is now inside the fracture.** The recovered depth is 7.4 mm. The gap
spans the whole cortical wall from 6.0 to 10.0 mm, so its scattering centroid is
at 8.0 mm - the first pass compared against the 6.0 mm cortex *surface*, which
was the wrong reference and made the error look worse than it was.

**Selective clutter removal helps here too**, and by more than the edge margin:

| method | fractured | intact | separation | x error | depth |
|---|---|---|---|---|---|
| k=1, no margin | 89.7 dB | 37.5 | 52.2 dB | 0.2 mm | 7.4 mm |
| k=1, 10 mm margin | 89.7 | 37.4 | 52.3 | 0.2 | 7.4 |
| **selective, 10 mm margin** | **90.4** | **20.7** | **69.7 dB** | **0.2** | **7.4** |

The intact control falls from 37.5 dB to 20.7 dB. Unlike the Stage 4 phantom
tank, the edge margin barely matters for the limb geometry - it has no flat
floor generating a strong edge artefact - so essentially all of the gain here
comes from selecting components by character rather than by index.

**Everything else stands.** k = 1 is still required; k = 2 mislocalises by
10.7 mm, k = 3 by 15.1 mm. Lateral error is still 0.2 mm. The detector still
responds to target strength, with a fractured-to-intact peak ratio of 356x.

Current headline for Stage 3: a 1 mm fracture under 6 mm of overlay, localised
to **0.2 mm laterally and inside the 4 mm gap in depth**, with **69.7 dB** of
separation from an intact limb, on full-wave data the reconstructor knows
nothing about.


---

## Stage 4 findings: the brass-rod validation gate

*Source file: `docs/stage4-findings.md`*

### Stage 4: the brass-rod gate

Proposal section 9 makes this the week-6 go/no-go, and section 2.5 lists skipping
it as the first way students fail on Path A:

    "Verify with a known strong scatterer first: if you cannot image a 6 mm
    brass rod at 20 mm depth in phantom, you will never image a fracture."

A 6 mm PEC rod in a uniform muscle-equivalent phantom, run through the identical
deck builder, pipeline and detector as the fracture study. `RodPhantom`
duck-types the same interface as `Phantom` precisely so that no separate code
path exists - a gate that runs different code from the experiment tests nothing.

#### Gate cleared

| | value |
|---|---|
| true position | x 50.0 mm, z 20.0 mm |
| recovered | x 49.8 mm, z 20.8 mm |
| error | **0.2 mm lateral, 0.8 mm depth** |
| autofocused eps_avg | 30.3, an interior optimum |
| SNR, rod | 70.6 dB |
| SNR, no-rod control | 51.4 dB |
| separation | 19.2 dB |

#### Depth recovery works here, and did not in Stage 3

The fracture study could not place a target in depth: autofocus railed against
its bound and the residual depth error was several millimetres. Here depth comes
out to 0.8 mm, and eps_avg = 30.3 is a genuine interior optimum rather than a
boundary.

The difference is the target. A single strong isolated scatterer in a uniform
medium gives the focus metric something to bite on. The fracture is weak, sits
in a layered medium whose interfaces the SVD has removed, and leaves the
velocity and depth nearly degenerate.

That is a useful diagnostic to carry into the report: **when depth estimates
degrade, suspect the target, not the code.** The chain is demonstrably capable
of 0.8 mm depth accuracy.

#### Depth sweep

The proposal claims a 15-20 mm working range (section 2.7). Measured:

| true depth | recovered | depth error | lateral error | SNR | eps_avg |
|---|---|---|---|---|---|
| 12 mm | 8.6 mm | 3.4 mm | 0.2 mm | 82.4 dB | 45.0 (at bound) |
| 20 mm | 20.8 mm | 0.8 mm | 0.2 mm | 70.6 dB | 30.3 |
| 28 mm | 30.0 mm | 2.0 mm | 0.2 mm | 57.3 dB | 25.8 |

Two things worth reporting.

**The claimed range is conservative.** A rod at 28 mm is still found, with 2 mm
of depth error and 57 dB of SNR. The technique does not stop working at 20 mm;
it degrades gracefully.

**Shallow targets are harder to focus, not easier.** At 12 mm the autofocus
rails against its upper bound again and the depth error is the worst of the
three. A short path gives the phase ramp less leverage on velocity, so eps_avg
is weakly determined. This is counter-intuitive and worth stating plainly,
because the instinct is that closer means better.

SNR falls 82.4 to 57.3 dB across 12 to 28 mm - roughly 25 dB for 16 mm of extra
depth, which is the two-way attenuation of muscle-equivalent phantom at these
frequencies.

#### k = 1, confirmed on a completely different target

Stage 3 found that the proposal's "typically K = 2 or 3" destroys the result and
that k must be 1. That could have been a quirk of the fracture geometry. It is
not:

| k | lateral error | depth error | SNR |
|---|---|---|---|
| 1 | 0.2 mm | 0.8 mm | 70.6 dB |
| 2 | 21.6 mm | 14.8 mm | 51.6 dB |
| 3 | 16.6 mm | 14.8 mm | 48.9 dB |

A PEC rod in uniform phantom and a blood-filled kerf in layered tissue are about
as different as two targets in this project can be, and both require k = 1. The
guidance in section 2.5 is wrong for this monostatic geometry, and the finding
now has two independent supports.

#### Lateral localisation is 0.2 mm everywhere

At every depth, and in Stage 3 across a fifteen-fold span of assumed
permittivity, the lateral error is 0.2 mm - one imaging cell. Along-track
position is set by aperture geometry and the shape of the hyperbolic moveout,
not by the assumed velocity or the target depth.

This is the most robust result the project has produced, and it is the one worth
leading with: *is there a fracture, and where along the bone* is answerable
reliably. *How deep* is not, unless the target is strong.

#### The dirty control, and what it turned out to be

The first pass left this open: the no-rod control scored 51.4 dB rather than
the noise floor, so the detector had a dirty reference and any ROC analysis
would inherit it. Two separate causes, both now fixed.

##### Cause 1: clutter and signal are interleaved in the singular spectrum

Proposal 2.5 says to discard the leading K components. That rule assumes
clutter occupies the strongest components and signal everything after. Migrating
each component alone shows it is false here:

| component | lateral extent | what it is |
|---|---|---|
| 0 | 57 mm | tank surface |
| **1** | **13 mm** | **the rod** |
| 2 | 22 mm | mixed |
| 3 | 39 mm | tank floor |

The phantom tank has two flat interfaces and **the target sits between them**.
So k=1 leaves the floor in, and k=2 removes the rod. No value of k works, which
is why the control never reached the floor and why the earlier k sweeps all
looked bad.

`remove_clutter_selective` migrates each component alone and discards those
spanning more than half the aperture, keeping compact ones whatever their
index. Separation improves from 15.7 dB to 18.1 dB with localisation unchanged.

Note what does *not* work: discriminating on the raw right singular vectors.
A target is *seen* from many scan positions even though it occupies one, so its
singular vector is not localised either - measured participation ratios were
0.70 of full for the target against 0.64 for an interface. The discrimination
has to happen in the image, after migration.

##### Cause 2: the residual was a migration edge artefact

What remained in the control was not clutter at all. It peaked at exactly
x = 20.0 mm - the first scan position - with a U-shaped lateral profile:

| x (mm) | 20.0 | 34.9 | 49.8 | 64.6 | 79.5 |
|---|---|---|---|---|---|
| level | **0.0 dB** | -14.3 | -13.2 | -18.5 | **-0.2 dB** |

Migration can only focus a pixel with scan positions on both sides of it. At
the ends of the aperture the sum is one-sided and unfocused energy piles up. No
amount of SVD filtering removes this; excluding a margin does.

`detect_snr` now takes `x_margin`, default 10 mm:

| margin | rod SNR | control SNR | separation |
|---|---|---|---|
| 0 mm | 72.7 | 54.6 | 18.1 dB |
| 5 mm | 72.7 | 49.3 | 23.4 |
| **10 mm** | **72.7** | **49.0** | **23.6** |
| 15 mm | 72.7 | 42.9 | 29.7 |

The rod score is identical at every margin - it sits at mid-aperture - so this
is pure artefact removal, not a trade against signal. It does cost usable scan
length: a 10 mm margin leaves 40 of 60 mm. A wider margin keeps improving the
separation, and is worth taking if the scan can afford the length.

##### Result

Both fixes together: **separation 19.2 dB to 22.6 dB**, control 51.4 dB to
48.8 dB, localisation unchanged at 0.2 mm lateral and 1.0 mm in depth.

The control still sits above the noise floor. What is left is genuine residual
structure, not artefact, and it matters less than it appears: ROC needs the two
classes to separate, which they do by 22.6 dB, and a systematic offset common to
all acquisitions moves the threshold rather than degrading the curve. It should
still be watched in Stage 7, because an offset that *varies* between specimens
would add variance to the AUC.

#### Operational note: the laptop slept

The first attempt at this stage crashed. Not a code fault and not a solver
fault: the machine suspended for three hours mid-run, and a two-hour subprocess
timeout fired. All 62 output files for the affected scan were sitting on disk,
complete and intact, and were thrown away by the driver.

Fixed properly rather than by raising the timeout alone:

- `run_bscan` is now **resumable**. If every output a set of decks would produce
  is already present, the solve is skipped and the existing files are assembled.
  Recovering that lost scan took 0.2 s instead of 12 minutes.
- the solver timeout is now 24 hours. It exists to catch a wedged solver, not to
  bound normal work; a tight value turns an ordinary suspend into a lost run.

This is the same checkpointing the matrix needs on Colab, where a session can be
reclaimed at any time, so it was worth building properly here.


---

## Stage 5 findings: antenna design and characterisation

*Source file: `docs/stage5-findings.md`*

### Stage 5: the antipodal Vivaldi in openEMS

Proposal 2.3 asks for the antenna to be simulated before it is etched. It was,
and the honest outcome is mixed: two of the three claims tested are confirmed,
two real defects were found and fixed, and **the design does not meet the
3-11 GHz match specification.** That last point is unresolved and is stated as
such rather than papered over.

#### Status

| item | outcome |
|---|---|
| openEMS v0.37.0-rc1 built, Python bindings working | done |
| FR4 costs "a few dB above 8 GHz" (2.3) | **confirmed: 2.4 dB at 9 GHz, 3.6 at 11** |
| Gain 8-10 dBi (2.2) | **met 4 GHz upward**; **UNMET at 3 GHz** at 7.02 dBi, and shown below not to be reachable by resizing |
| S11 < -10 dB across 3-11 GHz (2.2) | **met: 99.69% of the band, worst -9.98 dB at one 25 MHz point** |
| model validated against a known-good design | **done** - openEMS patch tutorial reproduces at Zin 49.7+4.5j |
| 50 ohm median input impedance | **achieved**: 45.6 ohm median with the 4.5/1.74 mm taper |

**Stage 5 is not on the critical path.** The imaging model excites with a
hertzian dipole in gprMax, not with this antenna, so Stages 6 and 7 are not
blocked by it.

#### The substrate decision, and a trap in it

Judged on S11 alone, FR4 looks *better* than RO4350B - mean -15.1 dB against
-10.2 dB below 8 GHz, and better at every probe frequency. That conclusion is
wrong, and the reason is worth stating in the report: **a lossy substrate
absorbs rather than reflects, so loss flatters return loss.**

Gain is the honest measure:

| f (GHz) | RO4350B | FR4 | FR4 penalty |
|---|---|---|---|
| 3 | 3.7 dBi | 3.2 | -0.5 |
| 5 | 5.9 | 6.5 | +0.6 |
| 7 | 8.1 | 8.8 | +0.7 |
| 9 | 8.7 | 6.3 | **-2.4** |
| 11 | 8.8 | 5.2 | **-3.6** |

Comparable up to about 8 GHz, then FR4 falls away. Proposal 2.3 says FR4 is
"acceptable up to about 8 GHz and will cost you a few dB above that". Measured:
2.4 dB at 9 GHz and 3.6 dB at 11 GHz. The recommendation to spend on RO4350B
stands - but buy it on the gain argument, not the return loss.

#### Defect 1: the feed was two plates, not a transmission line

The first geometry ran the outer edge of each arm straight from the aperture
mouth back to x = 0. Each arm was therefore **26.5 mm tall at the feed edge**
instead of 3 mm, and the lumped port drove two large overlapping conductors - a
capacitor - rather than a parallel-strip line.

Three symptoms, none of which fitted an aperture-too-small explanation:

- matched bands about 1 GHz wide instead of an octave
- bands that wandered erratically: the same nominal geometry gave 4.00-6.40 GHz
  in one run and 9.60-11.10 GHz in another, differing only in `taper_start`
  by 2.5 mm
- **the match got worse as aperture and length were increased**, which is
  backwards

Fixed by stepping the outer edge out at `taper_start`, leaving a
constant-width strip for the feed section. Five regression tests pin it.

Improvement: worst-in-band -2.9 dB to -5.3 dB, mean -9.9 dB to -13.3 dB. Real,
but not sufficient.

#### Defect 2: the absorbing boundary was too close, and too simple

Every run hit the 60000-timestep ceiling without reaching the -40 dB end
criterion, with residual energy stuck at -37.9 dB and not decaying. The cause
was MUR (a first-order absorbing boundary) placed 20 mm from the antenna, which
is 0.2 wavelengths at 3 GHz - inside the near field.

Switching to PML_8 with 50 mm of air converged properly and **halved the run
time, 105 s to 52 s**, because the solver could terminate on the energy
criterion instead of running to the ceiling.

It did **not** change the answer: 4.75-6.45 GHz against 4.80-6.50 GHz, mean
-12.9 dB either way. A real fix to convergence and cost, and a disproved
hypothesis about the bandwidth. Both are worth recording.

#### Dead end: curving the outer edge

The remaining suspect was the hard step where the outer edge jumps from 3 mm to
65 mm exactly where the taper begins. Curving it at the same opening rate as
the inner edge made things dramatically worse - the band collapsed from 1.7 GHz
to 0.25 GHz and the mean went from -12.9 dB to -5.8 dB.

At equal rates the two edges stay roughly parallel, so the arm becomes a thin
curved strip about 3 mm wide instead of a broad flare. In an antipodal Vivaldi
the arm is a broad conductor and it is the *slot between* the inner edges that
tapers. Reverted; the reasoning is kept in `Vivaldi.outer` so it is not retried.

#### The root cause, measured

After four geometry hypotheses had been tried and disproved, the input
impedance was measured instead of inferred - which should have been the first
move, not the fifth:

| f (GHz) | Re(Zin) | Im(Zin) | S11 |
|---|---|---|---|
| 3 | 13 | -16 | -4.2 dB |
| 5 | 19 | +13 | -6.2 |
| 7 | 56 | -7 | **-21.7** |
| 9 | 13 | +13 | -4.3 |
| 11 | 21 | -3 | -7.9 |

Median Re(Zin) across the band is **27 ohm against a 50 ohm port**, swinging
from 12 to 116 ohm. Where it happens to land near 50 + j0, at 7 GHz, the match
is excellent at -21.7 dB. The antenna radiates perfectly well; it is the feed
impedance that is wrong, and worse, unstable with frequency.

**Feed width controls the median predictably**, exactly as parallel-strip
theory says (Z0 proportional to h/w):

| feed width | median Re(Zin) |
|---|---|
| 1.5 mm | 43 ohm |
| 3.0 mm | 29 ohm |
| 5.0 mm | 19 ohm |

but fixing the median does not fix the swing, and the swing is what destroys
the bandwidth: at 1.5 mm the median is a respectable 43 ohm and the matched
band is still only 0.55 GHz.

#### Hypotheses tested and eliminated

Recorded so none of them is retried.

| # | hypothesis | outcome |
|---|---|---|
| 1 | aperture and length too small for 3 GHz | disproved: bigger was *worse* |
| 2 | absorbing boundary inside the near field | real fix (2x faster, converges) but **no change to S11** |
| 3 | outer edge should be curved, not stepped | much worse: band 1.7 -> 0.25 GHz |
| 4 | flare too abrupt (the a*T growth parameter) | disproved: flare/aperture 1.46 -> 2.01 changed nothing |
| 5 | feed width sets the impedance | **confirmed for the median**, does not fix the swing |
| 6 | tapered feed width (impedance transition) | no improvement; spread widened to 19-283 ohm |
| 7 | feed line run into the PML | pathological: PEC in PML never decays, 45 s became >10 min |
| 8 | the swing is a meshing artefact (substrate cells) | disproved: 3 to 10 cells through the substrate moved the median 27 to 28 ohm |
| 9 | the metal edges are not snapped or refined | **confirmed** - found by comparing against the openEMS patch tutorial. Spread 12-116 -> 14-77 ohm |
| 10 | feed width can reach 50 ohm | **confirmed** - 1.8 mm gives 51 ohm median, but the swing persists |

Hypothesis 8 matters most, because it closes the last modelling doubt. The
impedance behaviour is physical for this geometry, not an artefact of an
under-resolved port.

#### Validation against a known-good design

Stop sweeping parameters, validate the model. That was decisive.

**The toolchain is correct.** openEMS ships `Simple_Patch_Antenna.py`, whose
documented result is a resonance near 2.4 GHz. Run here it gives 2.430 GHz,
S11 -26.9 dB, and **Zin = 49.7 + 4.5j ohm** at resonance. A properly modelled
antenna returns 50 ohm.

**Comparing it to this model found the defect.** The tutorial calls
`FDTD.AddEdges2Grid(..., metal_edge_res=mesh_res/2)` on every metal; this model
never did. A patch has straight axis-aligned edges and tolerates a hand-placed
grid. A Vivaldi is defined by two curved exponential edges, and near the feed
the gap between them passes through zero over a few millimetres - staircased
onto a uniform 1.2 mm grid, that launch was two or three cells wide.

Mesh 0.33 M to 4.8 M cells; impedance spread 12-116 ohm to 14-77 ohm.

#### The design that works

Four things had to be right. None is stated in proposal 2.3, which specifies
only an opening rate.

| # | fix | effect on -10 dB coverage |
|---|---|---|
| 1 | metal edges snapped and refined | model became trustworthy |
| 2 | microstrip feed with a tapered ground balun | 0.75 -> 2.75 GHz |
| 3 | aperture from the **free-space** half wavelength | 3-6 GHz began to match |
| 4 | arms wide enough to carry current | 5.35-8.60 -> **4.35-12.00 GHz** |

##### The feed (fix 2)

The classic Gazit topology in three sections: a 50 ohm microstrip, an
elliptical ground taper converting the asymmetric microstrip mode to the
symmetric parallel-strip mode gradually, then the flare. The original model
went straight to a bare parallel strip driven at the board edge, with nothing
transitioning the 50 ohm source onto it.

##### The aperture (fix 3)

Sized from `c / (2 * aperture)`, in free space. Using the substrate's effective
permittivity flatters it badly:

| aperture | via eps_eff | free space |
|---|---|---|
| 44 mm | 2.28 GHz | **3.41 GHz** - above the band edge |
| 60 mm | 1.67 GHz | 2.50 GHz |

The 44 mm design could never have matched at 3 GHz, and the optimistic formula
hid that for several iterations.

##### The arms (fix 4)

Aperture 60 mm inside a 70 mm board leaves each arm a **5 mm sliver**. Widening
the board to 90 mm gives 15 mm arms, and the band moved from 5.35-8.60 GHz to
4.35-12.00 GHz - the single largest improvement of the whole stage.

##### Result

| | value |
|---|---|
| -10 dB match | **2.48 - 12.00 GHz** |
| covered in 3-11 GHz | **99.69%** of points below -10 dB |
| worst in band | **-9.98 dB**, one 25 MHz point at 4.775 GHz |
| mean over 3-11 GHz | **-16.8 dB** |
| median Re(Zin) | 45.6 ohm |
| board | 150 x 90 mm, fits the stock already in the BOM |

Available as `bonesim.antenna.vivaldi.uwb_3_11()`.

The single point at -9.98 dB misses -10 dB by 0.02 dB. That is smaller than
the difference between the -30 and -40 dB end criteria, so it is reported
rather than rounded away: the design **substantially meets** the 3-11 GHz
specification, and the 0.02 dB is stated so nobody has to take "meets spec"
on trust.

#### How the low band was recovered, after two wrong diagnoses

The earlier version of this document said the shortfall was 3.0-4.35 GHz
caused by edge-current resonance, that corrugations were the remedy, and that
they were impractical because they would not converge inside 40 hours. **All
three claims were wrong.** They are kept here rather than deleted, because how
they failed is the useful part.

##### Wrong claim 1: corrugations take 40 hours

Retried in `scripts/retry_corrugations.py` at a -30 dB end criterion, with a
plain run at the SAME criterion as a control - without it, any improvement
could have been the relaxed criterion rather than the slots:

| run | converged | wall time |
|---|---|---|
| plain, control | timestep 6,608 | 578 s |
| 4 slots x 4 mm | timestep 6,972 | 601 s |
| 6 slots x 6 mm | timestep 7,952 | 738 s |

Corrugations converge in **4% more time than plain**, not 40 hours. The
control also validated the relaxed criterion: -30 dB moved the band edge by
one 25 MHz grid point against the -40 dB reference, so nothing downstream
rests on it.

The original anomaly was caught in the act during the later feed sweep. The
machine enters **Modern Standby and suspends the solver** while openEMS keeps
counting wall-clock time. One run logged 39m25s elapsed for 4,564 timesteps -
an apparent 1.0 timesteps/s - and the Windows event log showed 33 of those
minutes as standby (Kernel-Power 506/507). The give-away was in the same log
line all along: openEMS reported 86.1 MC/s and 0.086 s per timestep
throughout. The solver was never slow. It was asleep.

Two lessons worth keeping. openEMS's MC/s figure is the honest one because it
excludes suspended time, and an elapsed-time extrapolation on a laptop is
worthless without `powercfg /change standby-timeout-ac 0`.

##### Wrong claim 2: corrugations are the remedy

They converge, and they do not work. 4 slots x 4 mm moved S11 at 3.0 GHz from
-6.61 to -6.41 dB, the wrong way. 6 slots x 6 mm reached Re(Zin) 94 ohm but
broke the contiguous band down to 8.97-12.00 GHz.

##### Wrong claim 3: the shortfall is a low-frequency cutoff

It never was. The 4.35 GHz design is **matched at 2.225-2.725 GHz, reaching
-33 dB** - two GHz below its own stated band edge - so the aperture was never
the limit. An independent check agrees: solving for the effective permittivity
implied by a 4.35 GHz cutoff and a 60 mm aperture gives 0.33, which is
impossible, and so falsifies the premise rather than sizing the antenna.

What sat between the matched island and the main band was a mismatch, in two
separate defects:

| band | Re(Zin) | Im(Zin) | nature |
|---|---|---|---|
| 3.25-4.40 GHz | 24-37 ohm | small | resistive plateau |
| ~3.0 GHz | passes through 50 | +37 to -56 ohm | reactive resonance |

The plateau is arithmetic, not physics: 24.4 ohm into 50 ohm predicts -9.3 dB
and -9.14 dB was measured. A transformer fixes that. It cannot cancel
reactance, so the 3.0 GHz resonance was expected to survive - and did not, as
a side effect of the geometry change.

#### The fix: a tapered feed

Widen the flare end of the feed while pinning the port at 1.74 mm, which is
50 ohm microstrip and what the SMA has to see:

| flare end | worst in 3-11 GHz | covered | Re(Zin) at 4 GHz |
|---|---|---|---|
| 1.74 mm (uniform, as built) | -6.61 dB | 84% | 24.4 ohm |
| 2.75 mm, 8 mm feed | -8.44 dB | 80% | 24.5 ohm |
| 2.75 mm, 12 mm feed | -8.50 dB | 79% | 25.9 ohm |
| 3.50 mm | -8.14 dB | 94% | 29.1 ohm |
| 4.00 mm | -9.80 dB | 98.1% | 36.7 ohm |
| **4.50 mm** | **-9.98 dB** | **99.69%** | **39.0 ohm** |

The first two rows looked like a failure and the direction was called wrong on
that partial evidence, before the third landed and reversed it. Worth
recording: two points of a monotonic trend are not a trend.

This runs OPPOSITE to the calibration in `vivaldi.py` (median Re(Zin) 43 / 29 /
19 ohm for feed widths 1.5 / 3.0 / 5.0 mm), and that is not a contradiction.
The calibration describes a **uniform** line, where widening lowers the line
impedance everywhere. Pinning the port turns width into taper **steepness**,
and a taper transforms upward.

#### What this recovers downstream

`docs/band-study.md` measured what the 4.35 GHz floor cost: separation fell
from 40.8 dB to 17.9 dB when 3.00-4.35 GHz was removed, while AUC stayed at
1.0000 and could not see it.

The antenna now covers 2.48-12.00 GHz, which fully contains the 3-11 GHz band
the matrix was solved over. The design-target row of that study therefore
applies directly and **the full 40.8 dB separation is recovered** - no
re-scoring needed, because the band study already computed that row.

One caveat on that claim. The band study crops with a brick wall, whereas a
real antenna rolls off, and its gain and phase vary across the band. A brick
wall is the pessimistic case for a band that is MISSING, which is why it was
the right tool there. It is the optimistic case for a band that is merely
poorly matched at the edges. Treating -9.98 dB at 4.775 GHz as equivalent to
-16.8 dB is an approximation, though a 0.02 dB one.

#### Gain, and one requirement that is not met

Measured on the tapered design, peak of the endfire pattern:

| frequency | peak gain | S11 |
|---|---|---|
| 3 GHz | **7.02 dBi** | -15.53 dB |
| 5 GHz | 11.87 dBi | -13.07 dB |
| 7 GHz | 12.49 dBi | -18.27 dB |
| 9 GHz | 12.06 dBi | -14.63 dB |
| 11 GHz | 9.33 dBi | -16.39 dB |

Proposal 2.2 asks for 8-10 dBi. It is met from about 4 GHz upward and **unmet
at 3 GHz, by 1.0 dB**.

The taper already did most of the work here for free: the uniform-feed design
gave 3.7 dBi at 3 GHz and this gives 7.02, because an antenna that reflects
less radiates more. The remaining decibel was then chased down both available
levers, and both made it worse:

| design | 3 GHz gain | covered in 3-11 GHz | worst in band |
|---|---|---|---|
| **150 x 90, aperture 60 (adopted)** | **7.02 dBi** | **99.69%** | **-9.98 dB** |
| 150 x 100, aperture 70 | 7.74 dBi | 93.46% | -9.54 dB |
| 170 x 90, aperture 60 | 6.09 dBi | 91.90% | -6.92 dB |

Widening the aperture bought +0.72 dB and cost 6% of the match - the same trade
the Stage 5 sweep found with a uniform feed, now confirmed with a tapered one.
Lengthening to 170 mm was predicted to help by reading the measured gain as a
function of L/lambda, and instead made both worse: it collapsed the 3 GHz match
to -6.96 dB, and gain follows the match down. That prediction conflated length
with aperture, since both change with frequency on a fixed antenna, and it was
wrong.

Acceptance criteria for both tests were written into the scripts before the
runs, so neither result could be rationalised afterwards. Both were rejected by
their own criteria.

**So the requirement is reported as unmet rather than engineered at.** The
design is co-optimised for the match across 3-11 GHz, and at 3 GHz it is
1.5 wavelengths long with a 0.6-wavelength mouth. Scaling either dimension
breaks the match, and lost match costs gain directly. 8-10 dBi across the whole
of 3-11 GHz is over-specified for a board this size; it is achievable at the
top of the band and not at the bottom.

This does not block anything. The imaging model excites with a hertzian dipole
in gprMax, so the 40.8 dB separation of Stage 7 does not depend on antenna
gain, and the band study's conclusion rests on the MATCH, which is met.

#### Status

**Stage 5 is complete.** The antenna meets the 3-11 GHz MATCH specification
of proposal 2.2 to within 0.02 dB at a single frequency point, on a board
already in the bill of materials. The GAIN specification is met from about
4 GHz upward and is unmet at 3 GHz by 1.0 dB, which was measured, chased down
both available levers, and reported rather than engineered at.

The stage began at 4.00-6.40 GHz with a mean of -10.9 dB and an input impedance
of 27 ohm. It passed through 4.35-12.00 GHz. It ends at 2.48-12.00 GHz,
-16.8 dB mean, 45.6 ohm median - and with three published claims of its own
corrected along the way.

Fabrication artefacts in `figures/`: `vivaldi.dxf`, `vivaldi_fab_drawing.pdf`,
`vivaldi_antenna.step`, `vivaldi_geom.json`. All regenerated for the tapered
design; the drawing now reports the width at the PORT where the SMA lands, not
at the flare, which were the same number until this design and are not now.

#### Reproducing

```bash
bash scripts/setup_openems.sh        # in WSL; ~45 min, mostly VTK/Qt/Boost
python scripts/run_stage5.py         # both substrates, S11 + gain
python scripts/sweep_vivaldi.py      # geometry sweep, S11 only
```

Two install traps, both handled in `setup_openems.sh`:

- `update_openEMS.sh --python` installs the bindings into an **isolated venv**
  under the prefix, not the active environment. They are built by hand here so
  they land in the `bonesim` conda environment alongside numpy and h5py.
- CSXCAD and openEMS both refuse to configure unless `CSXCAD_INSTALL_PATH` is
  set, failing with a `metadata-generation-failed` error that does not name the
  missing variable unless pip is run verbosely.

One solver trap, handled in `model.py`: `CreateNF2FFBox()` without a frequency
list records the **time-domain** field on six surfaces at every timestep, about
1.8 GB of HDF5 per run. Passing `frequency=` switches it to frequency-domain
accumulation - 576 kB, and CPU utilisation rose from 21% to 139% once the run
was no longer I/O bound. Solver scratch also belongs on WSL-native storage, not
`/mnt/c`.


---

## Stage 7 findings: the statistical result

*Source file: `docs/stage7-findings.md`*

### Stage 7 findings: the statistical result

Full matrix, 192/192 cells, 8 specimens. Every acquisition scored through the
same pipeline (empty-scene subtraction, instrument errors, selective SVD
clutter removal, Kirchhoff migration, peak-over-noise detector), three remount
realisations each: 576 scores.

#### The headline, and why it needs a caveat

Primary endpoint (AUC, intact vs fractured, 6 mm overlay): **1.0000**,
bootstrap CI over specimens 1.000-1.000, permutation p = 0.0010 (the floor for
1000 shuffles). AUC is 1.0000 at every overlay and every kerf.

A perfect AUC is the kind of number that usually means a leak, so the
distributions come first:

| class | n | min | median | max |
|---|---|---|---|---|
| intact | 96 | 8.8 | 19.3 | **27.7 dB** |
| fractured | 480 | **68.5** | 89.9 | 104.8 dB |

**Gap 40.8 dB, no overlap.** So it is not a leak and not a fitting artefact:
the two classes really are separated by a factor of 110 in amplitude under this
error model.

But it does mean the AUC is **saturated**, and a saturated statistic is a lower
bound, not a measurement. The honest claim is:

> Under the modelled error budget, fractured and intact limbs separate by
> 40.8 dB with no overlap across 8 specimens, 4 overlays and 4 fracture widths.

not "the method detects fractures perfectly". The binding assumption here is
the **error model**, not the physics. `bonesim/perturb/errors.py` models finite
dynamic range, additive noise and remount jitter. A real bench also has cable
flex, connector repeatability, operator variation, specimen preparation
differences and tissue heterogeneity between real bones, none of which are in
the simulation. The 40.8 dB margin is the budget those unmodelled terms would
have to consume before the result changes.

#### What the structure of the result does tell us

The margin behaves the way physics predicts, which is the real evidence that
the pipeline is working rather than leaking:

- **The weakest fractured cases are the physically hardest ones**: every score
  near 68.5 dB is a 0.2 mm kerf under 10 mm of overlay. Thinner gap, more
  attenuating path.
- **The strongest intact cases are also at 10 mm overlay.** The intact control
  score rises monotonically with overlay: 14.3, 16.5, 22.6, 25.1 dB at 0, 3, 6
  and 10 mm. This is the Stage 4 residual, showing up exactly where it was
  predicted to. It is a layered-interface artefact that migration does not fully
  collapse, and thicker overlay gives it more to work with.
- So the margin **narrows at thick overlay from both ends** - 68.5 vs 27.7
  rather than 68.5 vs 14.3 - and still never closes.

#### Leave-one-specimen-out

The detector has no fitted parameters; the decision **threshold** is the only
trained quantity, so that is what LOSO is applied to. Threshold picked on seven
specimens by Youden, applied to the eighth:

- sensitivity 0.9979 (Wilson 0.988-1.000)
- specificity 1.0000 (Wilson 0.962-1.000)
- accuracy 0.9983

One miss in 576, on specimen 5, at that specimen's weakest condition. The
threshold is stable at 68.5 dB for seven of the eight folds.

#### Repeatability

ICC(1,1) = 0.9979. Within-measurement sd 0.468 dB (median 0.169) against
between-measurement sd 26.8 dB. Remount jitter is negligible next to the signal
it has to compete with.

#### Limitations, stated plainly

1. **The error model is the binding assumption**, as above.
2. **Every fracture is at x = 50 mm.** The study never tests detection at an
   unknown position, so it measures separability, not localisation.
3. **The specimens vary only in the parameters `SpecimenVariation` perturbs.**
   Eight simulated bones are not eight cadaveric tibiae.
4. **2D TMz.** Out-of-plane scattering is absent.
5. **The antenna is a hertzian dipole**, not the Vivaldi of Stage 5. The
   antenna characterisation and the imaging matrix are separate results.

#### To measure the limit instead of a bound

The experiment currently stops before the method does. Three ways to push it
until it fails, cheapest first:

1. **Harsher error model** - one constructor call in `experiment.py`.
2. **Thicker overlay** beyond 10 mm - one line, but needs a deeper domain.
3. **Thinner kerf** than 0.2 mm - needs a finer grid, so cost scales as dx^-3.

Reproduce: `python scripts/run_stage7.py`, figure via
`python scripts/make_figures.py 7`.


---

## Bandwidth study: what a saturated statistic conceals

*Source file: `docs/band-study.md`*

### What the Stage 5 antenna shortfall costs

The Vivaldi of Stage 5 matches 4.35-12.00 GHz against a 3-11 GHz target. This
asks whether the detection result depends on the 3.00-4.35 GHz it cannot
deliver. Every solved cell stores full-band S11, so the whole 192-cell matrix
was re-scored over restricted windows with no new FDTD - the same pipeline,
a different slice of data already in hand.

    python scripts/run_band_study.py        # the three-band comparison
    python scripts/diagnose_band_loss.py    # which cells bind, and why

#### Result

| band | BW | range res | AUC | p | separation |
|---|---|---|---|---|---|
| 3.00-11.0 GHz, design target | 8.00 GHz | 3.67 mm | 1.0000 | 0.0010 | **40.8 dB** |
| 4.35-11.0 GHz, antenna as built | 6.65 GHz | 4.42 mm | 1.0000 | 0.0010 | **17.9 dB** |
| 5.00-11.0 GHz, deliberately worse | 6.00 GHz | 4.90 mm | 1.0000 | 0.0010 | **16.0 dB** |
| 3.00-6.30 GHz, upper band removed (LiteVNA-64 range) | 3.30 GHz | 8.91 mm | 1.0000 | - | **51.5 dB** |
| 3.00-4.40 GHz, upper band removed (NanoVNA V2 Plus4 range) | 1.40 GHz | 21.0 mm | 1.0000 | - | **43.0 dB** |
| 3.00-6.30 GHz at **70 dB** dynamic range (LiteVNA-64 as it is) | 3.30 GHz | 8.91 mm | 1.0000 | - | **36.4 dB** |

Losing 3.00-4.35 GHz costs **22.9 dB, more than half the total separation**.

#### The methodological point

**AUC is 1.0000 in all three bands.** It cannot see this degradation, because
it is saturated - it already reported perfect separation at 40.8 dB and has
nowhere left to go at 17.9 dB. Reporting the AUC alone would have concealed the
loss of over half the margin.

This is the Stage 7 caveat made concrete rather than hypothetical. Once a
threshold-free statistic pins at its ceiling, the margin is the only quantity
still carrying information. Both belong in the report.

#### Which cells bind, and the mechanism

Band-limiting damages both classes, and the intact side is the more dangerous:

| | full band | 4.35-11.0 | change |
|---|---|---|---|
| weakest fractured (hairline, 10 mm overlay) | 68.5 | 55.7 dB | **-12.8** |
| strongest intact (specimen 3, 6 mm overlay) | 27.7 | **37.8 dB** | **+10.1** |

The fractured loss is unsurprising: a narrower band penetrates 10 mm of overlay
less well and resolves a 0.2 mm kerf less sharply.

The intact rise is the finding. 37.8 dB is **specimen 3 at 6 mm overlay against
a group mean of 23.7** - an outlier, a **false alarm** rather than a missed
detection, and sitting exactly on the primary endpoint condition.

**The first explanation written here was wrong, and is kept, in italics, so
the correction is visible.** It read: *bandwidth buys range resolution, 3.67 mm
against 4.42 mm; at full band migration resolves specimen 3's layered-interface
reflection and collapses it; band-limited, it smears into the detection window.*

That was refuted by removing the *other* end of the band
(`scripts/vna_fallback_study.py`). Keeping only **3.0-6.3 GHz** - the range of a
LiteVNA-64, with a range resolution of **8.91 mm**, more than twice as coarse -
gives a separation of **51.5 dB, higher than the full band's 40.8**, and the
same specimen-3 cell that reached 37.8 dB at 4.35-11 GHz reads 10.2 dB there.
Even 3.0-4.4 GHz, a 1.4 GHz window with 21 mm resolution, keeps 43.0 dB.
Resolution is not the driver. The two restricted windows differ in which end
of the band was removed, and that is what matters.

The low band carries the penetration. The deep layered reflection that
migration has to collapse is returned almost entirely by the frequencies that
reach it. Remove them and that reflection is undersampled; its residue lands in
the detection window and reads as a target. The upper band contributes little
to it through 6 mm or more of overlay - on the hardest fractured cell
(hairline, 10 mm) the fracture peak moves by about 1 dB when 6.3-11 GHz is
removed, while the image background drops by 10 dB - so dropping it costs
resolution the detector does not need and removes noise it does not want. The
low band's job is letting migration separate the interface artefact from the
fracture, and this is the same Stage 4 residual appearing for the third time -
after Stage 4 itself and the overlay drift in Stage 7.

#### Why this changes the recommendation

The concerning part is not the mean shift but the **variance**. One specimen in
eight spikes to 37.8 dB while its peers sit near 23.7. That is a
specimen-dependent margin, and with thirty specimens rather than eight the
expectation is a worse outlier, not a better one. A safety factor that depends
on which bone was drawn is not one to rely on.

So the antenna as built remains **usable** - 17.9 dB of clear air is real
separation, and detection survives - but recovering the low band moves from
optional to worthwhile. It is over half the buffer protecting the result
against everything the error model omits: cable flex, connector repeatability,
operator variation, genuine inter-bone heterogeneity.

#### Caveat on the method

`crop()` is a brick-wall cut, not an antenna. A real antenna rolls off, and its
gain and phase vary across the band it does cover. A hard cut is the right first
question - it is the pessimistic case, so if it barely moved the result a gentle
roll-off certainly would not - but it is an upper bound on the damage, not a
prediction. Modelling the measured S11 as a frequency weighting would refine it.

The restricted-window rows also keep the error model's 95 dB dynamic range,
which a LiteVNA does not have. Re-scoring the 3.0-6.3 GHz window with
`Instrument(dynamic_range_db=70)` (`scripts/vna_dynrange_study.py`, 576
realisations) gives AUC 1.0000 and 36.4 dB - 50.2 / 49.1 / 50.0 / 36.4 dB by
overlay. The worse floor costs 15 dB, nearly all of it at 10 mm overlay, and
the window still separates cleanly. See `docs/bill-of-materials.md`.

Also, the antenna reaches 12 GHz while the matrix stops at 11, so the 4.35-11.0
row **understates it**. True bandwidth is 7.65 GHz against the target's 8.0, a
4% loss rather than the 17% the low-end figure alone suggests.

#### Routes to recovering the low band

Ruled out first: **enlarging the antenna will not work.** Stage 5's sweep found
the match got *worse* as aperture and length grew, and an independent check
confirms it - solving for the effective permittivity implied by the measured
4.35 GHz cutoff and the 60 mm aperture gives 0.33, which is impossible and so
falsifies the premise that the aperture is what limits the low end. The cause is
edge-current resonance: Re(Zin) ripples to 117 ohm at 3.0 GHz against 24.5 ohm
at 4.0 GHz.

1. **Corrugations, retried with a suitable end criterion.** Slots ring by
   design, and Stage 5 judged them against a -40 dB decay criterion written for
   a structure that does not ring, giving a 40-hour extrapolated runtime. Mesh
   cost was nil - 7.40 M cells either way, identical time step. Fewer and
   shallower slots with EndCriteria relaxed is the first thing to try.
2. **Resistive edge loading.** Damps the resonance directly and converges
   normally. Costs efficiency; the fallback if the slots still will not settle.

#### Resolved

The shortfall this document measures no longer exists. A tapered feed took the
antenna from 4.35-12.00 GHz to **2.48-12.00 GHz**, which fully contains the
3-11 GHz band the matrix was solved over, so the design-target row above is
now the operating row and **the full 40.8 dB separation is recovered**.

The measurement retains its value for two reasons that outlive the defect. It
is the concrete demonstration that AUC = 1.0000 concealed the loss of more
than half the margin - the Stage 7 saturation caveat, shown rather than
asserted. And it is what made recovering the low band a priority instead of a
documented footnote: without the 22.9 dB figure, 4.35 GHz would have looked
like an acceptable compromise.

See `docs/stage5-findings.md`.


---

## Radio-frequency exposure assessment

*Source file: `docs/safety-sar.md`*

### RF exposure assessment

Proposal 2.2 points a 3-11 GHz antenna at a human forearm at 12 mm standoff.
This is the exposure assessment for that geometry.

**Operating point: 0 dBm (1 mW) transmit.** Adopted, not merely recommended -
see "Why 0 dBm" below. Every limit passes by at least 18x.

    python scripts/run_sar.py

#### The band straddles a boundary in the guidelines

ICNIRP 2020 and IEEE C95.1-2019 do not use one quantity across this band:

| range | quantity | averaging |
|---|---|---|
| 100 kHz - 6 GHz | SAR, W/kg | 10 g, 6 min |
| 6 GHz - 300 GHz | absorbed power density, W/m^2 | 4 cm^2, 6 min |

Above 6 GHz the penetration depth is small enough that a volume-averaged dose
rate stops being the right description, and the guidelines switch to a surface
quantity. **A single "the SAR is X" figure for a 3-11 GHz system quotes the
wrong quantity for most of the bandwidth**, so both are reported.

#### Result at the adopted operating point

0 dBm, and worst-case illumination throughout: the power squeezed into a
half-wavelength spot at 11 GHz, 1.86 cm^2, about the smallest area the physics
allows and therefore the highest exposure.

| limit | limit value | measured | verdict |
|---|---|---|---|
| ICNIRP public, limbs (10 g) | 4.0 W/kg | 0.0283 | **PASS, 141x** |
| ICNIRP public, head/torso (10 g) | 2.0 W/kg | 0.0283 | **PASS, 71x** |
| ICNIRP occupational, limbs (10 g) | 20.0 W/kg | 0.0283 | **PASS, 707x** |
| FCC / IEEE public, partial body (1 g) | 1.6 W/kg | 0.0494 | **PASS, 32x** |
| ICNIRP public, 6-11 GHz (4 cm^2) | 20.0 W/m^2 | 1.109 | **PASS, 18x** |

Tightest margin **18x**, on absorbed power density above 6 GHz.

Each limit is checked against a value averaged over **its own** mass. A 10 g
average must not be compared against a 1 g limit - the smaller the averaging
mass the higher the number, so doing so understates exposure against the
strictest limit in use. That error was made in the first version of this
assessment and is the reason the 1 g row is computed separately.

#### Why 0 dBm

A VNA will happily deliver +10 dBm, and the first assessment ran all three
plausible settings:

| scenario | P_tx | SAR 3-6 GHz, 10 g | S_ab 6-11 GHz | tightest margin |
|---|---|---|---|---|
| FCC Part 15 UWB | -2.5 dBm | 0.016 W/kg | 0.605 W/m^2 | 33x |
| **VNA at 0 dBm (adopted)** | **0 dBm** | **0.028 W/kg** | **1.109 W/m^2** | **18x** |
| VNA at +10 dBm (rejected) | +10 dBm | 0.283 W/kg | 11.092 W/m^2 | **1.8x** |

At +10 dBm the 6-11 GHz exposure sits within a factor of 1.8 of the general
public limit - the only quantity in the whole study that was not comfortable.
Dropping 10 dB takes that to 18x.

**It costs nothing that matters.** The detector has 40.8 dB of separation
between fractured and intact and spends none of it here; a 10 dB reduction in
transmit power does not approach the point where detection is at risk. Trading
an unused 10 dB for a 10x safety margin is not a trade-off, it is free.

Note that the bench settings are **higher than the regulatory device limit**:
FCC Part 15 UWB is -2.5 dBm EIRP total, below even 0 dBm. An experiment is not
automatically covered by the UWB emission mask just because the system is a
UWB system.

#### Where the energy goes

0 dBm, tight spot, 3-6 GHz:

| layer | depth | peak SAR (W/kg) | share of absorbed power |
|---|---|---|---|
| skin | 0.0-2.0 mm | 0.1392 | 38.1% |
| fat | 2.0-5.0 mm | 0.0255 | 11.7% |
| muscle | 5.0-6.0 mm | 0.1004 | 14.7% |
| cortical bone | 6.0-10.0 mm | 0.0251 | 13.4% |
| marrow | 10.0-20.0 mm | 0.0111 | 15.3% |
| far cortex | 20.0-24.0 mm | 0.0125 | 6.8% |

Peak point SAR **0.139 W/kg at the skin surface**, 11x under the strictest
limit before any averaging is applied at all.

Roughly 38% of the absorbed power stops in the first 2 mm. That is the same
physics that makes the imaging problem hard: what reaches the bone is what is
left after the skin has taken its share.

Point SAR always exceeds any mass average, so a point value under the limit
guarantees the averaged value is too.

#### Method

The limb is a plane-layered lossy stack at normal incidence. Power crossing
into the skin is

    S_in(f) = S0(f) * (1 - |Gamma(f)|^2)

and inside the tissue it decays as exp(-2 alpha z), giving

    p(z) = 2 alpha(z) S(z)      [W/m^3]
    SAR(z) = p(z) / rho(z)      [W/kg]

Gamma comes from `stack_reflection` in the analytic forward solver rather than
a second layered model that could drift from it. Dielectric properties are the
same Gabriel four-Cole-Cole models used everywhere else in this project.
Densities are IT'IS Foundation tissue property database v4.1.

An assumption-free bound is reported alongside: every transmitted watt
deposited in 10 g, with no geometry and no tissue model. At 0 dBm that is
0.037 W/kg, and nothing the simulation produces can exceed it.

#### Limitations

Stated because a safety number nobody can check is worthless.

1. **Plane wave at normal incidence.** At 12 mm the limb is deep in the
   antenna's reactive near field - far field begins near 1.3 m at 7 GHz - where
   the field is not a plane wave. This is the standard engineering
   approximation, and it is why the assumption-free bound is reported too.
2. **1D layered model.** Lateral spreading is ignored, which can only dilute a
   spatial average, so the figures err high.
3. **10 g and 1 g averaging are done in depth only**, same reason, same
   direction.
4. **Multiple internal reflections** are folded into the stack reflection but
   not re-applied layer by layer, slightly overstating deep absorption.
5. **No thermal model.** SAR is a dose rate, not a temperature rise. The 6 min
   averaging in the guidelines is a thermal-time-constant argument this
   analysis does not reproduce.
6. **Simulation, not measurement.** No regulatory submission rests on a
   calculation of this kind; compliance testing uses a measured phantom to
   IEC 62209. This establishes that the design is nowhere near a limit. It
   does not certify it.


---

## Bill of materials for a physical build

*Source file: `docs/bill-of-materials.md`*

### Bill of materials: what it takes to build the instrument

The project is purely virtual by design, and nothing here has been bought.
This is the list of what a physical build would need, with each specification
traced to the simulation that fixed it rather than to a generic shopping list.
Cost figures are the proposal's own indicative Indian-supplier numbers
(Robu, Element14 India, Mouser India, Amazon.in) and **must be re-quoted before
purchase**; several are a year old.

Totals from the proposal, which this document does not change:

| configuration | approx. total |
|---|---|
| with a department VNA (recommended) | **INR 23,800** |
| with the LiteVNA-64 fallback | **INR 32,800** |

`docs/bill-of-materials.csv` is the same list as a spreadsheet. It carries all
three VNA options, so its column sum (INR 42,700) is not a configuration total;
pick one VNA row.

The one thing the proposal could only guess at - whether the cheap VNA
fallbacks actually work - is now measured. See section A.

#### A. The measurement instrument

The VNA decides viability. The proposal's framing stands: *the single question
is whether the department owns a VNA reaching 8 GHz or above.*

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| VNA, preferred | 1-port S11; sweep 3-11 GHz (antenna is matched 2.48-12.00); >= 201 points; output 0 dBm; dynamic range >= 95 dB at ~1 kHz IFBW | department lab VNA, 8-20 GHz | 1 | 0 | check first; decides everything below |
| VNA, fallback 1 | 50 kHz - 6.3 GHz | LiteVNA-64 | 1 | 9,000 | **works: measured below** |
| VNA, fallback 2 | to 4.4 GHz | NanoVNA V2 Plus4 | 1 | 7,000 | **works on band; dynamic range untested** |
| calibration kit | SMA short/open/load, calibrated **at the antenna connector**, not the VNA port | SMA SOL kit (often bundled with LiteVNA) | 1 | 1,500-3,000 | everything downstream is referenced to the antenna feed |

**Where the numbers come from.** The matrix was solved over 3-11 GHz at 201
points (`ScanData` grid). The error model (`bonesim/perturb/errors.py`,
`Instrument`) assumes a **95 dB** noise floor below the strongest return, which
a lab VNA at 1 kHz IF bandwidth meets and a LiteVNA (roughly 70 dB at its top
end) does not. **0 dBm** is the adopted transmit power from the exposure
assessment: at +10 dBm the 6-11 GHz absorbed power density sat within 1.8x of
the ICNIRP public limit; at 0 dBm every limit clears by at least 18x, and the
detector has 40.8 dB of margin to spend (`docs/safety-sar.md`).

##### Do the cheap VNAs work? Measured, not guessed

The proposal labelled the LiteVNA "band-limited; degrades resolution" and the
NanoVNA "minimum viable, marginal". Those were guesses made before the matrix
was solved. Every solved cell stores the full 3-11 GHz response, so each
fallback can be scored on exactly the data it could have acquired, with no new
simulation (`scripts/vna_fallback_study.py`, same pipeline and detector as
Stage 7).

| VNA option | usable band | bandwidth | range res. | AUC | class separation |
|---|---|---|---|---|---|
| department VNA | 3.00-11.0 GHz | 8.00 GHz | 3.67 mm | 1.0000 | **40.8 dB** |
| (first antenna, for scale) | 4.35-11.0 GHz | 6.65 GHz | 4.42 mm | 1.0000 | 17.9 dB |
| LiteVNA-64 | 3.00-6.30 GHz | 3.30 GHz | 8.91 mm | 1.0000 | **51.5 dB** at 95 dB dynamic range; **36.4 dB** at 70 dB |
| NanoVNA V2 Plus4 | 3.00-4.40 GHz | 1.40 GHz | 21.0 mm | 1.0000 | **43.0 dB** band only, at 95 dB dynamic range |

**Verdict: both work, and on the band alone the LiteVNA beats the department
VNA.** Removing the upper band *raises* the separation, 51.5 dB against 40.8,
because the frequencies above 6.3 GHz contribute little through 6 mm or more
of overlay and mostly add image background the detector does not want; the
low band carries the penetration (`docs/band-study.md`). By overlay, the
LiteVNA band gives 64.9 / 66.6 / 65.2 / 51.5 dB at 0 / 3 / 6 / 10 mm and the
NanoVNA band 54.8 / 57.3 / 60.5 / 45.9 dB. The classes do not overlap at any
overlay for either.

**Dynamic range, measured separately.** The band study keeps the error
model's 95 dB noise floor, which the cheap VNAs do not have. Re-scoring the
LiteVNA band with `Instrument(dynamic_range_db=70)`
(`scripts/vna_dynrange_study.py`, 576 realisations) gives AUC 1.0000 and
**36.4 dB** separation: 50.2 / 49.1 / 50.0 / 36.4 dB by overlay. The 25 dB
worse floor costs 15 dB of margin, nearly all of it at the 10 mm overlay, and
what remains is within 5 dB of the department VNA's full-band 40.8. So a
LiteVNA-64 is a defensible instrument for this experiment, not a compromise.
The same test has not been run for the NanoVNA band; its 43.0 dB is the
band-only figure at 95 dB and should be read as an upper bound on what that
instrument would deliver.

#### B. The antenna

Design files are in `figures/`: `vivaldi.dxf` (4 layers, mm, origin at the
feed edge), `vivaldi_antenna.step`, `vivaldi_fab_drawing.pdf` (A4, both faces
dimensioned), `vivaldi_geom.json`. Rebuild with
`python scripts/make_antenna_fab.py`.

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| substrate | Rogers RO4350B, 0.762 mm (30 mil), 1 oz Cu, 100 x 150 mm; antenna is 150 x 90 mm so one board per antenna | RO4350B 0.762 mm | 2 | 3,500 | FR4 alternative INR 300, costs 2.4 dB at 9 GHz and 3.6 dB at 11 (Stage 5) |
| fabrication | etch both faces from `vivaldi.dxf`; 4 x 3.2 mm mounting holes at (6, +/-38) mm | PCB house, or in-house etch | 2 | 3,000 | one spare |
| SMA connector | **end-launch, 18 GHz rated**; port trace is 1.74 mm (50 ohm) | L-com RFPCB-SMA-FS18G-55 (solder, cut for 0.031 in board) **or** Southwest 292-04A-9 (solderless clamp, 0.010 in pin) | 4 | 1,600 | **do not use cheap 6 GHz parts.** No extra pads needed; see note |
| mounting | M3 nylon standoffs + screws for the four holes | M3 x 10 nylon | 8 | 200 | keeps metal out of the near field |

**The antenna as designed.** Antipodal Vivaldi, growth a*T = 2.0, 60 mm
aperture, **tapered feed 4.50 mm at the flare to 1.74 mm at the port**. The
taper is what took the match from 4.35-12.00 GHz to **2.48-12.00 GHz**: 99.69%
of 3-11 GHz below -10 dB, worst -9.98 dB at one point, median Re(Zin) 45.6 ohm
(`docs/stage5-findings.md`). Gain is 7.02 dBi at 3 GHz, 11.9-12.5 dBi across
5-9 GHz, 9.3 dBi at 11 GHz; the 8-10 dBi target is met from about 4 GHz up and
**not at 3 GHz**, which is aperture-limited and was shown not fixable by
resizing within the board.

**Connector note, from the fab drawing.** Both named parts were checked
against their datasheets for the 0.762 mm board. An end-launch lands its pin on
the 1.74 mm trace at the board edge and grounds to the full-width plane on the
other face, so **no pads are drawn and none are needed**. The Southwest part's
0.0635 in (1.61 mm) dielectric is within 8% of the trace width, which is why
it launches cleanly. The proposal's INR 400 per connector assumes a generic
18 GHz end-launch; the named Southwest part is a premium item at roughly ten
times that - price it before choosing. Top-ground-tab connectors are supported
only with a >= 2.5 mm pad gap and cost the band above 9.6 GHz; avoid them.

#### C. Cabling

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| test cable | phase-stable, SMA-SMA, 18 GHz, 60 cm | e.g. Mini-Circuits / Pasternack phase-stable | 1 | 4,500 | **secure it** - flexing changes phase |
| port saver | SMA female-female adapter on the VNA port | SMA F-F, 18 GHz | 2 | 500 | the VNA connector outlives the project; the saver does not |

The error model's cable term is 1 fs RMS delay jitter, i.e. a cable that does
not move during a scan. Route it along the stage with slack at a single fixed
bend, not dragged.

#### D. The scan stage

Migration sums phase coherently across positions, so position error is phase
error: 0.5 mm at 10 GHz in air is about 60 degrees (proposal 2.4). The error
model assumes **100 um RMS** stage jitter and the result tolerated it; build to
that.

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| rail | >= 60 mm scan travel (matrix used 61 positions at 1 mm, 20-80 mm); 200 mm gives clearance for the 150 mm antenna | 2020 aluminium extrusion, 200 mm | 1 | 2,800 | includes lead screw |
| lead screw | 8 mm, **anti-backlash nut** | T8 + anti-backlash brass nut | 1 | (incl.) | backlash is a systematic position error migration cannot remove |
| motor + driver | NEMA 17, A4988, 12 V 3 A PSU | standard 3D-printer parts | 1 | 1,400 | 1 mm per step command; settle 200 ms before each sweep |
| home switch | mechanical limit switch at one end | microswitch | 1 | (incl.) | repeatable zero; required for empty-scene subtraction to line up |
| controller | serial command "step, settle, trigger" | Arduino Nano or ESP32 | 1 | 600 | the laptop drives the VNA over USB; the controller only moves the stage |

#### E. Fixture

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| antenna holder | **12 mm standoff** aperture to skin, held to **+/- 0.3 mm** | acrylic or 3D-printed bracket on the stage carriage | 1 | (in 2,500) | standoff_sigma = 300 um in the error model |
| limb / phantom rest | holds the specimen with the bone axis parallel to the rail | acrylic cradle | 1 | (in 2,500) | tilt shows up as a sloping skin line |
| phantom tank | for casting layered phantoms around the bone | acrylic box, lid | 1 | (in 2,500) | cast overlay slabs separately (next section) |
| frame | mounts rail, holder, rest in one rigid assembly | 2020 extrusion + brackets | 1 | 2,500 total | rigidity is what makes the 100 um stage spec achievable |

#### F. The phantom and specimens

The simulated layer stack is the casting target. Thicknesses from
`bonesim/geometry/phantom.py`; dielectric targets per tissue in
`docs/tissue-model.md` (Gabriel four-Cole-Cole).

| layer | thickness | note |
|---|---|---|
| skin | 2.0 mm | low oil fraction |
| fat | 3.0 mm | high oil fraction |
| muscle | 1.0 mm | high water |
| near cortical wall | 4.0 mm | the bone specimen itself |
| marrow | 10.0 mm | the bone specimen itself |
| **soft-tissue overlay** | **0, 3, 6, 10 mm** | the four experimental conditions; cast as separate slabs laid over the skin layer |

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| phantom materials | oil-in-gelatin recipe, proposal 4.3 | DI water 50-70%, porcine gelatin 250 bloom 10-15%, kerosene or safflower oil 15-35% (the tuning knob), surfactant 1-2%, n-propanol 0-5%, p-toluic acid < 0.5%, NaCl 0-1% | - | 1,800 | oil fraction sets eps_r 10-50; **measure each batch** with an open-ended coax probe on the VNA |
| bone specimens | mid-shaft, ~4 mm cortical wall, ~10 mm medullary cavity | goat or bovine tibia, fresh from a butcher | 6-12 | 900 | defat mechanically; **do not boil**; store in saline gauze at 4 C |
| fracture fill | blood-mimicking fluid; haematoma is the real contrast | saline-based blood mimic | - | (in 1,800) | the simulation used Gabriel blood |
| validation target | **6 mm brass rod at 20 mm depth** | brass rod, 6 mm dia, 100 mm | 1 | 200 | **Stage 4 gate: image this before any bone.** If migration cannot find it, nothing downstream is meaningful |
| kerf tools | kerfs 0.2-2.0 mm were simulated; the saw sets what is achievable | jeweller's saw, diamond wafering blade | - | (in 1,200) | measure the actual kerf; the measurement is the ground truth |
| metrology | | digital calliper, feeler gauges | - | (in 1,200) | record every kerf and every cortical thickness as covariates |
| consumables | | cling film, gloves, saw blades | - | 1,200 | |

#### G. Compute and software

Nothing to buy. The laptop that ran the analysis runs the acquisition.

| item | note |
|---|---|
| `bonesim` package | processing chain, detector, statistics - unchanged between simulation and bench |
| VNA control | `scikit-rf` + `pyvisa` for a lab VNA; LiteVNA/NanoVNA have serial protocols with Python libraries |
| stage control | serial to the Arduino/ESP32 |

The processing chain was built so that it cannot tell the analytic model, the
FDTD solver and a real VNA apart: it sees a matrix of complex S11 and nothing
else. That is the point at which the simulation hands over to the bench.

#### What the build would test that the simulation could not

In order of how much they threaten the result (`docs/stage7-findings.md`,
limitations):

1. **The error model.** 95 dB dynamic range, 100 um stage jitter, 1 fs cable
   jitter, +/-0.3 mm standoff are assumptions. The 40.8 dB margin is the budget
   the real bench has to stay inside. This is what a brass rod and a VNA measure
   on day one.
2. **Real bone.** Eight simulated specimens vary only in what the variation
   model perturbs. Goat tibiae vary in everything.
3. **Fracture position.** Every simulated fracture is at x = 50 mm. A real cut
   is wherever the saw went, which tests localisation rather than separability.
4. **Three dimensions.** The bench is 3D for free. The 3D model
   (`bonesim/geometry/cylindrical.py`) is built and verified but unsolved.


---

# Part II - Appendix: operational notes

## Compute budget and measured solver performance

*Source file: `docs/compute-budget.md`*

### Compute budget

Measured on the target machine (Ryzen 9 5900HX, 8C/16T, 10 GB allocated to WSL2,
Ubuntu 24.04, gprMax 3.1.7 built with `-O3 -fopenmp -march=native`).

All figures are measurements, not estimates. Reproduce with
`config/benchmark_2d.in`.

#### Benchmark model

Sized to the real Path A problem rather than a toy:

| Parameter | Value |
|---|---|
| Cell size | 0.2 mm (resolves a 0.3 mm kerf) |
| Domain | 140 x 100 mm, 2D (one cell in z) |
| Grid | 700 x 500 = 350,000 cells |
| Time window | 3 ns |
| Time step | 0.472 ps (2D Courant limit) |
| Iterations | 6,361 |
| Work | 2.23 x 10^9 cell-updates |
| Memory | 135 MB |

#### Parallel scaling — the important result

| Configuration | Wall clock per model | Aggregate throughput | Speedup |
|---|---|---|---|
| 1 process x 16 threads | 57.7 s | 38.6 M cell-updates/s | 1.00x |
| 4 processes x 4 threads | 12.5 s | 178 M cell-updates/s | 4.61x |
| 8 processes x 2 threads | 12.5 s | 178 M cell-updates/s | 4.61x |
| 16 processes x 1 thread | 12.1 s | 184 M cell-updates/s | 4.76x |

**Intra-model OpenMP reaches only ~21% of the machine's achievable throughput.**
The FDTD update is memory-bandwidth-bound, so threads within a single model
contend for the same memory traffic while independent models do not. Aggregate
throughput saturates near 180 M cell-updates/s regardless of how threads are
divided, so the split is a scheduling choice rather than a performance one.

**Use 4 processes x 4 threads.** All three configurations deliver the same
throughput; four processes gives the lowest batch latency and the smallest
memory footprint, and it leaves headroom if a 3D hero case has to run alongside.

A B-scan is an embarrassingly parallel sweep over scan positions, so this
speedup applies to the entire experiment matrix with no algorithmic change.

#### Budget for the experiment matrix

Proposal 4.4 specifies 8 specimens x 6 fracture states x 4 overlays x 3 repeats
= 576 acquisitions. The 3 repeats are *remounts*: they change the instrument, not
the anatomy. They are therefore generated by re-injecting position jitter and
cable drift onto the frequency-domain data (`bonesim/perturb/`), not by
re-solving. That leaves 8 x 6 x 4 = **192 B-scans** to solve.

| | Per scan position | Per B-scan (61 positions) | Full matrix (192) |
|---|---|---|---|
| Naive (1 x 16 threads) | 57.7 s | 59 min | 188 h |
| Measured (4 x 4) | 12.3 s | 12.5 min | **40 h** |
| With domain + window trim | ~6 s | ~6 min | **~20 h** |

The trim reduces the domain to 100 x 70 mm and the window to 2.2 ns; the round
trip to 40 mm depth in muscle (eps_r 42) is 1.7 ns, so 3 ns was generous. Both
must be re-validated against the Stage 4 brass-rod gate before being adopted for
the matrix.

Twenty to forty hours is three to four unattended overnight runs. This is
feasible, and it is the number that made the project viable — at 188 h it was
not.

#### Why the smoke test is not a benchmark

`config/smoketest_*.in` runs 24 M cell-updates in 13 s, an apparent 1.9 M
cell-updates/s. That figure is meaningless: at 14,400 cells each iteration is
too small to amortise per-iteration overhead, so the run is overhead-bound
rather than compute-bound. Never size the project from the smoke test.

#### 3D

3D hero cases are memory-limited, not time-limited. At 0.2 mm over
150 x 80 x 60 mm the grid is ~45 M cells, which exceeds the 10 GB WSL allocation
once field and coefficient arrays are counted. 3D is therefore reserved for one
or two figures at coarser resolution, and the matrix is 2D. This is a stated
methodological limitation, not a silent one.

#### GPU

gprMax ships a CUDA solver. The RX 6800M is AMD, so it is unavailable and every
figure above is CPU-only.

---

#### Measured on the real model (Stage 3), not the benchmark

The benchmark above used non-dispersive materials. The production model carries
seven two-pole Debye materials, and each pole adds auxiliary field arrays and
per-cell work. Measured on a full 61-position B-scan:

| | value |
|---|---|
| Grid | 500 x 275 = 137,500 cells |
| Iterations | 5,299 (2.5 ns at the 0.472 ps Courant limit) |
| Work per position | 7.29 x 10^8 cell-updates |
| Wall clock, 61 positions + reference, 4x4 | **610 s** |
| Amortised per position | 9.84 s |
| Aggregate throughput | 74 M cell-updates/s |

**Dispersive materials cost 2.4x**: 74 M cell-updates/s against 178 M/s for the
non-dispersive benchmark. That is the price of representing tissue properly and
is not negotiable.

Revised budget for the matrix:

| | per B-scan | full matrix (192) |
|---|---|---|
| Earlier estimate (non-dispersive) | 12.5 min | 40 h |
| **Measured (dispersive)** | **10.2 min** | **32.5 h** |

Roughly four unattended overnight runs. Still feasible on this laptop.

#### The GPU option

gprMax ships a CUDA solver behind the `-gpu` flag, requiring an NVIDIA card and
pycuda. The RX 6800M is AMD, so this is unavailable locally and every figure
above is CPU-only.

It is available on a hosted NVIDIA GPU. Measured on a Colab Tesla T4:

| model | local | Colab CPU | Colab GPU | GPU vs local |
|---|---|---|---|---|
| non-dispersive benchmark | 178 M | 64 M | 1467 M | 8.24x |
| production model, Debye | 74 M | 14 M | 532 M | **7.18x** |

**The matrix moves to Colab: 32.5 h locally, 4.5 h on a T4.**

Colab's CPU is five times *slower* than this laptop on the production model
(14 M against 74 M) - two vCPUs against sixteen threads. The GPU is the entire
reason to go there, and a run where `-gpu` fails to engage is a significant
downgrade rather than a fallback. See `docs/colab.md`.


---

## Installation and environment

*Source file: `docs/install.md`*

### Installation

Target machine for this build: Windows 11 host, AMD Ryzen 9 5900HX (8C/16T), 16 GB RAM,
Radeon RX 6800M, Ubuntu 24.04 LTS under WSL2.

#### Why WSL2

gprMax and openEMS build cleanly on Linux and painfully on native Windows. WSL2 gives a
real Linux toolchain with no dual-boot.

**Note on the GPU.** gprMax ships a CUDA solver. The RX 6800M is AMD, so CUDA is
unavailable and all FDTD runs use the OpenMP CPU solver across 16 threads. This is a
hardware constraint, not a configuration choice, and it sets the compute budget in
`docs/methods.md`.

#### 1. WSL memory limit

WSL2 defaults to 50% of host RAM (7.5 GB here), which throttles FDTD. Create
`C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=10GB
processors=16
swap=4GB
localhostForwarding=true
```

Then `wsl --shutdown` and reopen. Verify with `free -h` — should read ~9.7 Gi.

Revert by deleting the file and running `wsl --shutdown` again.

#### 2. Build toolchain

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake pkg-config python3-dev python3-venv libhdf5-dev bzip2
```

If apt reports a held dpkg lock immediately after a WSL restart, `unattended-upgrades` is
running. Wait for it rather than forcing the lock:

```bash
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done
```

#### 3. Miniforge

Miniforge rather than Anaconda: conda-forge only, no commercial terms-of-service
constraints on institutional use.

```bash
wget -O /tmp/miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash /tmp/miniforge.sh -b -p ~/miniforge3
~/miniforge3/bin/conda init bash && exec bash
```

#### 4. Environment

```bash
conda env create -f environment.yml
conda activate bonesim
```

#### 5. gprMax from source

gprMax `master` (post-3.1.7) supports NumPy 2.x and Cython 3, so it builds against the
environment above without pinning. It compiles with `-O3 -fopenmp -march=native`.

```bash
git clone https://github.com/gprMax/gprMax.git ~/src/gprMax
cd ~/src/gprMax
conda activate bonesim
python setup.py build
python setup.py install
```

Verify:

```bash
python -c "import gprMax; print(gprMax.__version__)"
python -m gprMax --help
```

#### 6. openEMS (Stage 5 only)

Needed only for the antipodal Vivaldi antenna characterisation. It pulls Boost, VTK, CGAL
and Qt5 and takes roughly 45 minutes to build, so it is deliberately deferred until
Stage 5 rather than installed up front.

```bash
sudo apt-get install -y libhdf5-dev libvtk9-dev libboost-all-dev libcgal-dev \
                        libtinyxml-dev qtbase5-dev libvtk9-qt-dev
git clone --recursive https://github.com/thliebig/openEMS-Project.git ~/src/openEMS-Project
cd ~/src/openEMS-Project && ./update_openEMS.sh ~/opt/openEMS --python
```

#### Filesystem layout

| Path | Contents | Why |
|---|---|---|
| `C:\Users\<you>\bonesim` | Source, git repo | Editable from Windows, survives WSL reset |
| `/mnt/c/Users/<you>/bonesim` | Same, seen from WSL | Few small files; the I/O penalty does not matter |
| `~/bonesim-runs` | FDTD output (HDF5) | WSL-native; cross-filesystem I/O is ~10x slower |

Simulation output is never committed. Every artefact is regenerated by a script in
`scripts/`.

#### Disk

The full experiment matrix stores only receiver traces, roughly 2.5 MB per B-scan and
under 1 GB for the whole matrix. Field snapshots are large and are written only for the
one or two figures that need them. Do not enable `#snapshot` across the matrix.


---

## Running the matrix on a Colab GPU

*Source file: `docs/colab.md`*

### Running the experiment matrix on Colab

#### Verdict: yes, move it

Measured on a Colab Tesla T4 with `notebooks/colab_gpu_benchmark.ipynb`, against
the local numbers from `docs/compute-budget.md`:

| model | local (16 threads) | Colab CPU (2 vCPU) | Colab GPU (T4) | GPU vs local |
|---|---|---|---|---|
| non-dispersive benchmark | 178 M | 64 M | 1467 M | **8.24x** |
| production model, 6 Debye tissues | 74 M | 14 M | 532 M | **7.18x** |

(cell-updates per second)

**Full matrix: 32.5 h locally, 4.5 h on a T4.**

Two things in that table are worth reading carefully.

**Colab's CPU is much slower than the laptop** - 14 M against 74 M on the
production model, a factor of five the wrong way. Two vCPUs against sixteen
threads. If the GPU ever fails to engage, running here is a serious downgrade,
not a fallback. Check that `-gpu` actually took effect before trusting a
timing.

**Dispersion costs more on the GPU than on the CPU.** The speedup drops from
8.24x to 7.18x once the Debye materials are present, because the auxiliary
field updates for each pole are less GPU-friendly than the plain Yee update.
Still an enormous win, but it is the 7.18x that applies to real work, not the
8.24x from the simpler benchmark.

#### Why the GPU is the whole argument

gprMax ships a CUDA solver behind a `-gpu` flag. The development laptop has an
AMD RX 6800M, so that solver is unreachable there and every local figure is
CPU-only.

Checked before spending any time on this: the CUDA kernels do handle multi-pole
dispersive materials (`update_e_dispersive_A`, with a `MAXPOLES` argument). Had
they not, the GPU would have been useless here, since every tissue in the model
is a two-pole Debye material.

#### How the matrix has to run

At 4.5 hours the matrix now fits inside a single free session, which caps near
12 hours. That removes the need to split the work across sessions, but not the
need for resumability: free sessions can be reclaimed at any time, and losing
four hours of compute to a disconnect at hour four is avoidable.

The design that follows:

- **one B-scan per checkpoint.** Self-contained, about 165 kB compressed, and
  roughly 85 s on the GPU. Write each to Drive as it completes.
- **skip work already present.** The driver checks Drive before running, so a
  reconnect resumes rather than restarts.
- **idle timeout is not a concern while computing.** The roughly 90-minute idle
  disconnect applies to an idle runtime; a session actively running gprMax is
  not idle. The risk being managed is arbitrary reclamation, not idleness.

#### Running the matrix

`notebooks/colab_matrix.ipynb`, generated by
`scripts/make_colab_matrix_notebook.py`.

    laptop:  python scripts/package_for_colab.py     ->  bonesim_colab.zip
    Drive:   upload to MyDrive/bonesim/bonesim_colab.zip
    Colab:   Runtime > Change runtime type > T4 GPU, then Run all

The zip is 108 kB and holds only the package, the scripts, `config/`, and the
tests - not `runs/`, which is where results come *back* from. It is verified
self-sufficient: unpacked fresh on Linux it builds the matrix and passes its
tests with nothing else present.

| | value |
|---|---|
| measured, laptop | 17 min per cell |
| full matrix, laptop | ~54 h |
| full matrix, T4 | **~7.6 h** |
| result size | ~140 kB per cell, ~27 MB total |

Results go to `MyDrive/bonesim/matrix/`, one `.npz` per acquisition. Scratch
stays on local Colab disk: gprMax writes many small files per cell and Drive is
far slower for that, and only the finished `.npz` needs to survive the session.
The cost is that an interrupted cell restarts rather than resuming mid-scan -
about two minutes on a GPU.

`--max-hours` stops cleanly before a session is reclaimed rather than being
killed part-way through a cell. At 7.6 h of solve on a free tier, expect at
least one interruption; reopening and running again continues from the first
unsolved acquisition.

On the GPU the decks run sequentially rather than concurrently. There is one
device, and the four-process trick that wins on CPU is a memory-bandwidth
argument that does not carry over.

#### What stays local

Only the FDTD solve moves. Geometry construction, Cole-Cole fitting, the
processing chain, and the statistics all stay on the laptop, where iteration is
fast, there are no session limits, and all sixteen threads are available.

Colab is a compute backend for one stage, not a development environment. This is
the hybrid arrangement: develop locally, solve remotely, analyse locally.

#### Reproducing the benchmark

`notebooks/colab_gpu_benchmark.ipynb`, regenerated by
`scripts/make_colab_notebook.py`. Upload, set Runtime > Change runtime type >
T4 GPU, Run all. About 15 minutes, most of it building gprMax from source, which
is necessary because the Cython extensions must match the runtime's Python and
NumPy. It built cleanly against Python 3.13.

The generator is the source of truth; do not edit the notebook by hand, because
the local reference numbers it compares against live in the generator.


---
