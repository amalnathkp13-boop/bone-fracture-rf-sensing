# RF exposure assessment

Proposal 2.2 points a 3-11 GHz antenna at a human forearm at 12 mm standoff.
This is the exposure assessment for that geometry.

**Operating point: 0 dBm (1 mW) transmit.** Adopted, not merely recommended -
see "Why 0 dBm" below. Every limit passes by at least 18x.

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
wrong quantity for most of the bandwidth**, so both are reported.

## Result at the adopted operating point

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

## Why 0 dBm

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

## Where the energy goes

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

## Method

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

## Limitations

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
