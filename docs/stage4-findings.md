# Stage 4: the brass-rod gate

Proposal section 9 makes this the week-6 go/no-go, and section 2.5 lists skipping
it as the first way students fail on Path A:

    "Verify with a known strong scatterer first: if you cannot image a 6 mm
    brass rod at 20 mm depth in phantom, you will never image a fracture."

A 6 mm PEC rod in a uniform muscle-equivalent phantom, run through the identical
deck builder, pipeline and detector as the fracture study. `RodPhantom`
duck-types the same interface as `Phantom` precisely so that no separate code
path exists - a gate that runs different code from the experiment tests nothing.

## Gate cleared

| | value |
|---|---|
| true position | x 50.0 mm, z 20.0 mm |
| recovered | x 49.8 mm, z 20.8 mm |
| error | **0.2 mm lateral, 0.8 mm depth** |
| autofocused eps_avg | 30.3, an interior optimum |
| SNR, rod | 70.6 dB |
| SNR, no-rod control | 51.4 dB |
| separation | 19.2 dB |

## Depth recovery works here, and did not in Stage 3

The fracture study could not place a target in depth: autofocus railed against
its bound and the residual depth error was several millimetres. Here depth comes
out to 0.8 mm, and eps_avg = 30.3 is a genuine interior optimum rather than a
boundary.

The difference is the target. A single strong isolated scatterer in a uniform
medium gives the focus metric something to bite on. The fracture is weak, sits
in a layered medium whose interfaces the SVD has removed, and leaves the
velocity and depth nearly degenerate.

That is a useful diagnostic to carry into the report: **when depth estimates
degrade, suspect the target, not the code.** The chain is demonstrably capable
of 0.8 mm depth accuracy.

## Depth sweep

The proposal claims a 15-20 mm working range (section 2.7). Measured:

| true depth | recovered | depth error | lateral error | SNR | eps_avg |
|---|---|---|---|---|---|
| 12 mm | 8.6 mm | 3.4 mm | 0.2 mm | 82.4 dB | 45.0 (at bound) |
| 20 mm | 20.8 mm | 0.8 mm | 0.2 mm | 70.6 dB | 30.3 |
| 28 mm | 30.0 mm | 2.0 mm | 0.2 mm | 57.3 dB | 25.8 |

Two things worth reporting.

**The claimed range is conservative.** A rod at 28 mm is still found, with 2 mm
of depth error and 57 dB of SNR. The technique does not stop working at 20 mm;
it degrades gracefully.

**Shallow targets are harder to focus, not easier.** At 12 mm the autofocus
rails against its upper bound again and the depth error is the worst of the
three. A short path gives the phase ramp less leverage on velocity, so eps_avg
is weakly determined. This is counter-intuitive and worth stating plainly,
because the instinct is that closer means better.

SNR falls 82.4 to 57.3 dB across 12 to 28 mm - roughly 25 dB for 16 mm of extra
depth, which is the two-way attenuation of muscle-equivalent phantom at these
frequencies.

## k = 1, confirmed on a completely different target

Stage 3 found that the proposal's "typically K = 2 or 3" destroys the result and
that k must be 1. That could have been a quirk of the fracture geometry. It is
not:

| k | lateral error | depth error | SNR |
|---|---|---|---|
| 1 | 0.2 mm | 0.8 mm | 70.6 dB |
| 2 | 21.6 mm | 14.8 mm | 51.6 dB |
| 3 | 16.6 mm | 14.8 mm | 48.9 dB |

A PEC rod in uniform phantom and a blood-filled kerf in layered tissue are about
as different as two targets in this project can be, and both require k = 1. The
guidance in section 2.5 is wrong for this monostatic geometry, and the finding
now has two independent supports.

## Lateral localisation is 0.2 mm everywhere

At every depth, and in Stage 3 across a fifteen-fold span of assumed
permittivity, the lateral error is 0.2 mm - one imaging cell. Along-track
position is set by aperture geometry and the shape of the hyperbolic moveout,
not by the assumed velocity or the target depth.

This is the most robust result the project has produced, and it is the one worth
leading with: *is there a fracture, and where along the bone* is answerable
reliably. *How deep* is not, unless the target is strong.

## Caveat

The no-rod control scores 51.4 dB, not the noise floor. Residual clutter
survives the SVD - the phantom tank has a flat bottom at 36 mm as well as its
surface, and one rank does not remove both. The 19.2 dB separation is real and
the gate passes, but the control is not clean, and the same will be true of any
ROC analysis built on this detector. Worth revisiting before Stage 7.

## Operational note: the laptop slept

The first attempt at this stage crashed. Not a code fault and not a solver
fault: the machine suspended for three hours mid-run, and a two-hour subprocess
timeout fired. All 62 output files for the affected scan were sitting on disk,
complete and intact, and were thrown away by the driver.

Fixed properly rather than by raising the timeout alone:

- `run_bscan` is now **resumable**. If every output a set of decks would produce
  is already present, the solve is skipped and the existing files are assembled.
  Recovering that lost scan took 0.2 s instead of 12 minutes.
- the solver timeout is now 24 hours. It exists to catch a wedged solver, not to
  bound normal work; a tight value turns an ordinary suspend into a lost run.

This is the same checkpointing the matrix needs on Colab, where a session can be
reclaimed at any time, so it was worth building properly here.
