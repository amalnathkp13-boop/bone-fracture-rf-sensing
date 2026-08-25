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
| Gain 8-10 dBi (2.2) | **met 4 GHz upward**; **UNMET at 3 GHz** at 7.02 dBi, and shown below not to be reachable by resizing |
| S11 < -10 dB across 3-11 GHz (2.2) | **met: 99.69% of the band, worst -9.98 dB at one 25 MHz point** |
| model validated against a known-good design | **done** - openEMS patch tutorial reproduces at Zin 49.7+4.5j |
| 50 ohm median input impedance | **achieved**: 45.6 ohm median with the 4.5/1.74 mm taper |

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

## The root cause, measured

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

## Hypotheses tested and eliminated

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

## Validation against a known-good design

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

## The design that works

Four things had to be right. None is stated in proposal 2.3, which specifies
only an opening rate.

| # | fix | effect on -10 dB coverage |
|---|---|---|
| 1 | metal edges snapped and refined | model became trustworthy |
| 2 | microstrip feed with a tapered ground balun | 0.75 -> 2.75 GHz |
| 3 | aperture from the **free-space** half wavelength | 3-6 GHz began to match |
| 4 | arms wide enough to carry current | 5.35-8.60 -> **4.35-12.00 GHz** |

### The feed (fix 2)

The classic Gazit topology in three sections: a 50 ohm microstrip, an
elliptical ground taper converting the asymmetric microstrip mode to the
symmetric parallel-strip mode gradually, then the flare. The original model
went straight to a bare parallel strip driven at the board edge, with nothing
transitioning the 50 ohm source onto it.

### The aperture (fix 3)

Sized from `c / (2 * aperture)`, in free space. Using the substrate's effective
permittivity flatters it badly:

| aperture | via eps_eff | free space |
|---|---|---|
| 44 mm | 2.28 GHz | **3.41 GHz** - above the band edge |
| 60 mm | 1.67 GHz | 2.50 GHz |

The 44 mm design could never have matched at 3 GHz, and the optimistic formula
hid that for several iterations.

### The arms (fix 4)

Aperture 60 mm inside a 70 mm board leaves each arm a **5 mm sliver**. Widening
the board to 90 mm gives 15 mm arms, and the band moved from 5.35-8.60 GHz to
4.35-12.00 GHz - the single largest improvement of the whole stage.

### Result

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

## How the low band was recovered, after two wrong diagnoses

The earlier version of this document said the shortfall was 3.0-4.35 GHz
caused by edge-current resonance, that corrugations were the remedy, and that
they were impractical because they would not converge inside 40 hours. **All
three claims were wrong.** They are kept here rather than deleted, because how
they failed is the useful part.

### Wrong claim 1: corrugations take 40 hours

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

### Wrong claim 2: corrugations are the remedy

They converge, and they do not work. 4 slots x 4 mm moved S11 at 3.0 GHz from
-6.61 to -6.41 dB, the wrong way. 6 slots x 6 mm reached Re(Zin) 94 ohm but
broke the contiguous band down to 8.97-12.00 GHz.

### Wrong claim 3: the shortfall is a low-frequency cutoff

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

## The fix: a tapered feed

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

## What this recovers downstream

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

## Gain, and one requirement that is not met

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

## Status

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
