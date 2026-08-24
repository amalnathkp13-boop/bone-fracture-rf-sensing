# Stage 5: the antipodal Vivaldi in openEMS

Proposal 2.3 asks for the antenna to be simulated before it is etched. It was,
and the honest outcome is mixed: two of the three claims tested are confirmed,
two real defects were found and fixed, and **the design does not meet the
3-11 GHz match specification.** That last point is unresolved and is stated as
such rather than papered over.

## Status

| item | outcome |
|---|---|
| openEMS v0.37.0-rc1 built, Python bindings working | done |
| FR4 costs "a few dB above 8 GHz" (2.3) | **confirmed: 2.4 dB at 9 GHz, 3.6 at 11** |
| Gain 8-10 dBi (2.2) | met above ~7 GHz only; 3.7 dBi at 3 GHz |
| S11 < -10 dB across 3-11 GHz (2.2) | **not met: best is ~1.7 GHz of coverage** |

**Stage 5 is not on the critical path.** The imaging model excites with a
hertzian dipole in gprMax, not with this antenna, so Stages 6 and 7 are not
blocked by it.

## The substrate decision, and a trap in it

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

## Defect 1: the feed was two plates, not a transmission line

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

## Defect 2: the absorbing boundary was too close, and too simple

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

## Dead end: curving the outer edge

The remaining suspect was the hard step where the outer edge jumps from 3 mm to
65 mm exactly where the taper begins. Curving it at the same opening rate as
the inner edge made things dramatically worse - the band collapsed from 1.7 GHz
to 0.25 GHz and the mean went from -12.9 dB to -5.8 dB.

At equal rates the two edges stay roughly parallel, so the arm becomes a thin
curved strip about 3 mm wide instead of a broad flare. In an antipodal Vivaldi
the arm is a broad conductor and it is the *slot between* the inner edges that
tapers. Reverted; the reasoning is kept in `Vivaldi.outer` so it is not retried.

## What is actually unresolved

Best achieved: about 1.7 GHz of contiguous -10 dB match, against a required
8 GHz. The structure still behaves resonantly - band centre tracks
L/lambda_g of roughly 4.5 to 5.1 across configurations, which is a standing
wave along the taper rather than a travelling wave leaving the mouth.

**Proposal 2.3 under-specifies the antenna.** It gives one parameter, the
opening rate, and asserts that 0.05-0.10 per mm "gives a clean 3-11 GHz match".
Six geometries inside that range, spanning 70-110 mm length and 40-60 mm
aperture, produced nothing close. The rate is not the governing parameter.

Plausible next steps, in the order worth trying:

1. **Soften the outer-edge step without thinning the arm** - curve it out to
   the substrate edge over the first 20-30% of the taper, then hold it there.
   This is the middle ground between the two versions tried.
2. **Check the feed impedance directly** rather than inferring it. A
   parallel-strip line of 3 mm on 0.762 mm RO4350B computes to roughly 40 ohm
   against the 50 ohm port; a short line of the correct width, or a tapered
   section, would remove that.
3. **Add corrugations or a slot-edge termination** at the mouth, the standard
   remedy when a tapered slot reflects instead of radiating.
4. Compare against a published antipodal Vivaldi with stated dimensions before
   optimising further, so the model is validated against a known-good design.

That is a genuine antenna-design exercise. It is worth doing if the antenna is
a report deliverable in its own right; it is not worth blocking Stages 6-7 for,
since the imaging model does not use it.

## Reproducing

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
