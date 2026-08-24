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
| S11 < -10 dB across 3-11 GHz (2.2) | **not met: best ~1.7 GHz of coverage** |
| model validated against a known-good design | **done** - openEMS patch tutorial reproduces at Zin 49.7+4.5j |
| 50 ohm median input impedance | **achieved** at a 1.8 mm feed (51 ohm) |

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
| -10 dB match | **4.35 - 12.00 GHz contiguous** |
| mean over 3-11 GHz | **-14.9 dB** |
| median Re(Zin) | 41 ohm |
| below -10 dB | everything from 5 to 11 GHz |
| board | 150 x 90 mm, fits the 100 x 150 mm stock already in the BOM |

Available as `bonesim.antenna.vivaldi.uwb_3_11()`.

## What is still short, and why corrugations did not fix it

3.0 to 4.35 GHz. Re(Zin) ripples there - 117 ohm at 3.0 GHz against 24.5 ohm at
4.0 GHz - which is edge-current resonance, and corrugated outer edges are the
standard remedy.

They were implemented and run, and they are impractical here, for a reason that
was not the expected one. **They cost nothing in mesh**: 7.40 M cells either
way, identical minimum cell and time step, because the slot edges fall inside
refinement the flare already required. What they cost is **convergence**. The
slots are resonant by design - that is how they lengthen the current path - so
they ring, and the energy will not decay to the -40 dB end criterion:

| | recorded steps | wall time |
|---|---|---|
| plain | 336, converged | 795 s |
| corrugated | 1,735 and rising | 70 min, abandoned |

Advancing 12 steps per 30 s against a 60,000-step cap, the extrapolated runtime
was about 40 hours. Revisiting them means shallower and fewer slots, and
relaxing EndCriteria: a design that rings by intent cannot be judged by a decay
criterion tuned for one that does not.

## Status

**Stage 5 delivers a working UWB antenna covering 4.35-12.00 GHz**, against a
3-11 GHz specification. 6.65 of the 8 GHz target band is matched, and the
shortfall is characterised rather than mysterious.

The stage began at 4.00-6.40 GHz with a mean of -10.9 dB and an input impedance
of 27 ohm. It ends at 7.65 GHz of contiguous match, -14.9 dB mean, 41 ohm - on a
board already in the bill of materials.

Not on the critical path either way: the imaging model excites with a hertzian
dipole in gprMax, not with this antenna.

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
