# bonesim — Virtual UWB Microwave Imaging for Long-Bone Fracture Detection

A fully in-silico replication of **Path A** of *Contactless RF Detection of Long-Bone
Fractures* (v1.0, 5 Aug 2026): monostatic ultra-wideband microwave imaging at 3–11 GHz,
with SVD skin-artifact removal and Kirchhoff migration.

No hardware. Every number in the report is produced by the code in this repository.

---

## What this is, and what it is not

This is a **simulation study**. It answers the question *"if you built the Path A
instrument described in the proposal, what would it be able to detect?"* — it does not
constitute measurement of a real bone.

The distinction matters because a simulated imaging study has a specific and well-known
failure mode, and the design of this repository is organised around avoiding it.

### The inverse-crime problem

If the model that **generates** the data and the model that **reconstructs** the image
share their assumptions, the reconstruction will always succeed, and the result is
circular. This is called an *inverse crime*. It is the first thing a competent reviewer
will look for in a simulation-only study.

The countermeasures used here are structural, not cosmetic:

| | Forward model (data) | Inverse model (image) |
|---|---|---|
| Physics | Full-wave FDTD, dispersive tissue | Migration in a homogeneous medium |
| Tissue | 4-Cole-Cole → multi-pole Debye, 6 layers | One scalar `eps_avg`, found by autofocus |
| Geometry | Curved cortex, marrow cavity, real kerf | Unknown; not supplied to the reconstructor |
| Grid | FDTD cells, 0.2 mm | Independent imaging grid |
| Instrument | Noise, cable drift, stage jitter injected | Blind to all injected error |

The reconstructor is never given the permittivity profile, the bone radius, the fracture
position, or the noise realisation. It sees only a matrix of complex S11 values, exactly
as it would from a VNA.

### What simulation cannot supply

Hardware gives you certain error sources for free. In simulation they must be modelled
explicitly, and the credibility of the study rests on how honestly that is done:

- VNA receiver noise at finite IF bandwidth
- Cable phase drift between scan positions
- Linear-stage position jitter and backlash
- Standoff (antenna-to-skin) variation
- Specimen-to-specimen variation in tissue properties and bone geometry

These live in `bonesim/perturb/` and are applied **after** the forward solve, so a single
FDTD result can generate multiple independent "remounts" — which is both cheaper and
physically correct, since a remount changes the instrument, not the anatomy.

---

## Repository layout

```
bonesim/
  materials/   Gabriel 4-Cole-Cole tissue models -> multi-pole Debye fits for FDTD
  geometry/    Layered phantom + bone + fracture geometry builders
  forward/     Data generation. Two interchangeable backends:
                 analytic.py  fast layered Green's function (seconds, for development)
                 gprmax.py    full-wave FDTD B-scan (hours, for the real dataset)
  vna/         Instrument emulation: time domain -> S11(f), IF bandwidth, noise floor
  perturb/     Injected instrument and specimen error models
  process/     Empty-scene subtraction, SVD clutter removal, time gating, migration
  detect/      Scalar detection metric (peak-to-background ratio)
  stats/       ROC/AUC, leave-one-specimen-out CV, permutation test, bootstrap CIs
scripts/       Entry points; every figure in the report is produced by one of these
config/        Experiment matrix definitions and solver settings
tests/         Unit tests, including the analytic-vs-FDTD cross-check
docs/          Install notes, methods, and the statistical analysis plan
```

The two forward backends share one interface. The processing chain cannot tell them
apart, which is what makes it possible to develop and unit-test the whole pipeline in
seconds and only then spend FDTD hours on it.

---

## Status

| Stage | Description | State |
|---|---|---|
| 0 | WSL2 environment, gprMax, compute benchmark | **complete** |
| 1 | Cole-Cole → Debye fitting, validated against published curves | **complete** |
| 2 | Analytic forward model + full processing chain | **complete** |
| 3 | gprMax geometry builder and B-scan driver | **complete** |
| 4 | Brass-rod validation gate (proposal §9) | **complete** |
| 5 | Antipodal Vivaldi characterisation in openEMS | **complete** — match 2.48-12.00 GHz; gain unmet at 3 GHz, see `docs/stage5-findings.md` |
| 6 | Full 192-cell experiment matrix (8 specimens) | **complete** — 192/192 on Colab T4 |
| 7 | Statistical analysis plan (proposal §5) | **complete** — see `docs/stage7-findings.md` |
| - | RF exposure assessment (ICNIRP 2020 / IEEE C95.1) | **complete** — 0 dBm adopted, all limits pass by 18x or more, see `docs/safety-sar.md` |

Stage 4 is the go/no-go. If migration cannot image a 6 mm PEC rod at 20 mm depth in
phantom, nothing downstream is meaningful — this mirrors the week-6 gate in §9 of the
proposal.

---

## Reproducing

See `docs/install.md`. In brief: Ubuntu under WSL2, Miniforge, `conda env create -f
environment.yml`, then build gprMax from source with OpenMP.

Source lives on the Windows filesystem; simulation output is written to WSL-native
storage, because gprMax produces many small HDF5 files and cross-filesystem I/O under
WSL2 is roughly an order of magnitude slower.
