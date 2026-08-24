# Processing chain: findings against proposal 2.5

Stage 2 implements the chain of section 2.5 and validates it end to end on
analytic data. Four things had to change from the text as written, and one
piece of physics turned up that the proposal does not anticipate.

## 1. Migration must be done in the time domain

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

## 2. K = 2 is right, but only once instrument errors are present

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

## 3. There is no detectable bone line

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

## 4. Peak-to-background is the wrong detector

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

## 5. Fracture scattering is resonant, not linear in kerf

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

## What validated cleanly

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
