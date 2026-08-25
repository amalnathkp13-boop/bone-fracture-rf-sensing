# RF exposure assessment

Proposal 2.2 points a 3-11 GHz antenna at a human forearm at 12 mm standoff.
This is the exposure assessment for that geometry.

    python scripts/run_sar.py

## The band straddles a boundary in the guidelines

ICNIRP 2020 and IEEE C95.1-2019 do not use one quantity across this band:

| range | quantity | averaging |
|---|---|---|
| 100 kHz - 6 GHz | SAR, W/kg | 10 g, 6 min |
| 6 GHz - 300 GHz | absorbed power density, W/m^2 | 4 cm^2, 6 min |

Above 6 GHz the penetration depth is small enough that a volume-averaged dose
rate stops being the right description, and the guidelines switch to a surface
quantity. **A single "the SAR is X" figure for a 3-11 GHz system quotes the
wrong quantity for most of the bandwidth**, so both are reported here.

## Scenarios

| scenario | P_tx | why it matters |
|---|---|---|
| FCC Part 15 UWB | -2.5 dBm (0.56 mW) | -41.3 dBm/MHz EIRP over 7.5 GHz: what a fielded device may emit |
| VNA at 0 dBm | 0 dBm (1 mW) | typical bench setting |
| VNA at +10 dBm | +10 dBm (10 mW) | worst case bench setting |

The bench figures are **higher than the regulatory device limit**, which is the
point of including them: the experiment is not automatically covered by the
UWB emission mask just because the system is a UWB system.

Two illumination areas are carried through, because the answer depends on how
tightly the power is concentrated and that is the least certain input:

- **aperture**, 36.0 cm^2, the 60 mm mouth footprint at 12 mm standoff
- **tight**, 1.86 cm^2, a half wavelength at 11 GHz - about the smallest area
  the physics allows, and therefore the highest SAR

## Result: SAR, 3.0-6.0 GHz

| scenario | bound | aperture | tight |
|---|---|---|---|
| FCC Part 15 UWB | 0.021 | 0.0008 | 0.016 |
| VNA at 0 dBm | 0.037 | 0.0015 | 0.028 |
| VNA at +10 dBm | 0.375 | 0.0146 | **0.283** |

All W/kg, 10 g averaged. `bound` is assumption-free: every transmitted watt
deposited in 10 g, no geometry and no tissue model. Nothing the simulation
produces can exceed it, which makes it the number to check first.

Each limit is checked against a value averaged over **its own** mass. A 10 g
average must not be compared against a 1 g limit - the smaller the averaging
mass the higher the number, so doing so understates exposure against the
strictest limit in use.

Worst case: **0.283 W/kg** over 10 g, **0.494 W/kg** over 1 g.

| limit | W/kg | measured | verdict |
|---|---|---|---|
| ICNIRP public, limbs (10 g) | 4.0 | 0.283 | **PASS**, 14.1x |
| ICNIRP public, head/torso (10 g) | 2.0 | 0.283 | **PASS**, 7.1x |
| ICNIRP occupational, limbs (10 g) | 20.0 | 0.283 | **PASS**, 70.7x |
| FCC / IEEE public, partial body (1 g) | 1.6 | 0.494 | **PASS**, 3.2x |

## Result: absorbed power density, 6.0-11.0 GHz

| scenario | aperture | tight |
|---|---|---|
| FCC Part 15 UWB | 0.031 | 0.605 |
| VNA at 0 dBm | 0.057 | 1.109 |
| VNA at +10 dBm | 0.572 | **11.092** |

All W/m^2 over 4 cm^2.

| limit | W/m^2 | verdict |
|---|---|---|
| ICNIRP public | 20.0 | **PASS, 1.8x** |
| ICNIRP occupational | 100.0 | PASS, 9.0x |

**This is the binding case in the whole assessment.** At +10 dBm with tightly
focused power the 6-11 GHz exposure sits within a factor of 1.8 of the general
public limit. Everything else clears by 3x or more.

## Recommendation

**Run the VNA at 0 dBm or below.** That is the difference between a 1.8x margin
and an 18x margin, it costs nothing - the detector has 40.8 dB of separation to
spend and needs none of it - and it removes the only case in this assessment
that is not comfortable.

At 0 dBm every quantity clears every limit by at least 18x, including the
strictest 1 g figure.

## Where the energy goes

Worst scenario, tight spot, 3-6 GHz:

| layer | depth | peak SAR | share of absorbed power |
|---|---|---|---|
| skin | 0.0-2.0 mm | 1.3915 | 38.1% |
| fat | 2.0-5.0 mm | 0.2546 | 11.7% |
| muscle | 5.0-6.0 mm | 1.0041 | 14.7% |
| cortical bone | 6.0-10.0 mm | 0.2509 | 13.4% |
| marrow | 10.0-20.0 mm | 0.1113 | 15.3% |
| far cortex | 20.0-24.0 mm | 0.1254 | 6.8% |

Peak point SAR **1.39 W/kg at the skin surface**. Roughly 38% of the absorbed
power stops in the first 2 mm, which is the same physics that makes the imaging
problem hard: what reaches the bone is what is left after the skin has taken
its share.

Point SAR always exceeds any mass average, so a point value under the limit
guarantees the averaged value is too.

## Limitations

Stated because a safety number nobody can check is worthless.

1. **Plane wave at normal incidence.** At 12 mm the limb is deep in the
   antenna's reactive near field - far field begins near 1.3 m at 7 GHz - where
   the field is not a plane wave. This is the standard engineering
   approximation, and it is why the assumption-free bound is reported next to
   it.
2. **1D layered model.** Lateral spreading is ignored, which can only dilute a
   spatial average, so the reported figures err high.
3. **10 g and 1 g averaging are done in depth only**, for the same reason and
   in the same direction.
4. **Multiple internal reflections** are folded into the stack reflection but
   not re-applied layer by layer, which slightly overstates deep absorption.
5. **No thermal model.** SAR is a dose rate, not a temperature rise. The 6 min
   averaging in the guidelines is a thermal-time-constant argument this
   analysis does not reproduce.
6. **Simulation, not measurement.** No regulatory submission is based on a
   calculation of this kind; a compliance test uses a measured phantom to
   IEC 62209. This assessment establishes that the design is nowhere near a
   limit, not that it is certified.

Densities are IT'IS Foundation tissue property database v4.1. Dielectric
properties are the same Gabriel four-Cole-Cole models used everywhere else in
this project, and the layered reflection is `stack_reflection` from the
analytic forward solver rather than a second implementation that could drift
from it.
