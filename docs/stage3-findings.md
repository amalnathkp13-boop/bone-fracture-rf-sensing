# Stage 3: first full-wave result

Two 61-position gprMax B-scans, fractured and intact, 610 s each. This is the
first result in the project that is not an inverse crime: the data comes from a
full-wave solver with dispersive layered tissue, a curved wavefront, near-field
antenna coupling and multiple reflections, and the reconstructor is given a
single scalar permittivity and nothing else.

## The fracture is found

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

## The proposal's guidance on k is wrong here

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

## Two errors in the first pass, both now fixed

### The detector had no noise floor

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

### eps_avg was fixed by hand

The first pass set eps_avg = 9.0 rather than autofocusing, putting the
reconstructed depth at 12.8 mm against a true cortex at 6.0 mm. With autofocus
the peak moves to 8.8 mm - better, and still 2.8 mm deep.

## Autofocus was broken, and the fix is instructive

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

## Lateral localisation is remarkably robust

Across every eps_avg from 4 to 60 - a fifteen-fold span of assumed permittivity,
moving the reconstructed depth from 18.2 mm to 2.2 mm - the lateral position
stayed at 49.8 mm, a 0.2 mm error, in **20 out of 20** cases.

Along-track position is fixed by the aperture geometry and the shape of the
hyperbolic moveout, not by the assumed velocity. Velocity errors move a target
in depth, not sideways.

This matters clinically. Answering *is there a fracture, and where along the
bone* is robust to getting the tissue model wrong. Answering *how deep* is not.

## Cost

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

## Re-verified after Stages 4 and 5

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
