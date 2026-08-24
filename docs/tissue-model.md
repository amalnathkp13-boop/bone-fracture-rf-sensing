# Tissue model: findings against the proposal

Stage 1 implements the Gabriel four-Cole-Cole parametrisation and fits Debye
models to it for FDTD. Validating that implementation against the proposal's own
tables surfaced three discrepancies. All three are documented here because each
one changes something a reviewer might check.

## 1. Section 1.1 is labelled with the wrong quantity

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

## 2. Cortical bone permittivity — a first-order sensitivity

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

## 3. Quoted conductivities are low-frequency values

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

## What validated cleanly

Blood, muscle, dry skin and fat reproduce the section 2.1 permittivities to
within 3% and conductivities to within 5%. The penetration-depth table
reproduces across nearly two decades of frequency. These are strong checks: the
implementation is not tuned to them.

## Debye fits

Two poles per tissue, fitted over 3-11 GHz only, worst-case error 0.233%
(cortical bone). One pole would meet a 2% target but leaves cortical bone at
1.9%, and cortical bone is the material being imaged — that error is a
systematic bias on the target itself, not noise. All relaxation times land
between 7.4 and 80 ps, comfortably above the 0.47 ps time step gprMax requires
them to exceed.

Cards are generated into `config/materials.in`; never edit that file by hand.
