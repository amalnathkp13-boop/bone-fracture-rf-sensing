# Stage 7 findings: the statistical result

Full matrix, 192/192 cells, 8 specimens. Every acquisition scored through the
same pipeline (empty-scene subtraction, instrument errors, selective SVD
clutter removal, Kirchhoff migration, peak-over-noise detector), three remount
realisations each: 576 scores.

## The headline, and why it needs a caveat

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

## What the structure of the result does tell us

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

## Leave-one-specimen-out

The detector has no fitted parameters; the decision **threshold** is the only
trained quantity, so that is what LOSO is applied to. Threshold picked on seven
specimens by Youden, applied to the eighth:

- sensitivity 0.9979 (Wilson 0.988-1.000)
- specificity 1.0000 (Wilson 0.962-1.000)
- accuracy 0.9983

One miss in 576, on specimen 5, at that specimen's weakest condition. The
threshold is stable at 68.5 dB for seven of the eight folds.

## Repeatability

ICC(1,1) = 0.9979. Within-measurement sd 0.468 dB (median 0.169) against
between-measurement sd 26.8 dB. Remount jitter is negligible next to the signal
it has to compete with.

## Limitations, stated plainly

1. **The error model is the binding assumption**, as above.
2. **Every fracture is at x = 50 mm.** The study never tests detection at an
   unknown position, so it measures separability, not localisation.
3. **The specimens vary only in the parameters `SpecimenVariation` perturbs.**
   Eight simulated bones are not eight cadaveric tibiae.
4. **2D TMz.** Out-of-plane scattering is absent.
5. **The antenna is a hertzian dipole**, not the Vivaldi of Stage 5. The
   antenna characterisation and the imaging matrix are separate results.

## To measure the limit instead of a bound

The experiment currently stops before the method does. Three ways to push it
until it fails, cheapest first:

1. **Harsher error model** - one constructor call in `experiment.py`.
2. **Thicker overlay** beyond 10 mm - one line, but needs a deeper domain.
3. **Thinner kerf** than 0.2 mm - needs a finer grid, so cost scales as dx^-3.

Reproduce: `python scripts/run_stage7.py`, figure via
`python scripts/make_figures.py 7`.
