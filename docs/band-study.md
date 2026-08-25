# What the Stage 5 antenna shortfall costs

The Vivaldi of Stage 5 matches 4.35-12.00 GHz against a 3-11 GHz target. This
asks whether the detection result depends on the 3.00-4.35 GHz it cannot
deliver. Every solved cell stores full-band S11, so the whole 192-cell matrix
was re-scored over restricted windows with no new FDTD - the same pipeline,
a different slice of data already in hand.

    python scripts/run_band_study.py        # the three-band comparison
    python scripts/diagnose_band_loss.py    # which cells bind, and why

## Result

| band | BW | range res | AUC | p | separation |
|---|---|---|---|---|---|
| 3.00-11.0 GHz, design target | 8.00 GHz | 3.67 mm | 1.0000 | 0.0010 | **40.8 dB** |
| 4.35-11.0 GHz, antenna as built | 6.65 GHz | 4.42 mm | 1.0000 | 0.0010 | **17.9 dB** |
| 5.00-11.0 GHz, deliberately worse | 6.00 GHz | 4.90 mm | 1.0000 | 0.0010 | **16.0 dB** |

Losing 3.00-4.35 GHz costs **22.9 dB, more than half the total separation**.

## The methodological point

**AUC is 1.0000 in all three bands.** It cannot see this degradation, because
it is saturated - it already reported perfect separation at 40.8 dB and has
nowhere left to go at 17.9 dB. Reporting the AUC alone would have concealed the
loss of over half the margin.

This is the Stage 7 caveat made concrete rather than hypothetical. Once a
threshold-free statistic pins at its ceiling, the margin is the only quantity
still carrying information. Both belong in the report.

## Which cells bind, and the mechanism

Band-limiting damages both classes, and the intact side is the more dangerous:

| | full band | 4.35-11.0 | change |
|---|---|---|---|
| weakest fractured (hairline, 10 mm overlay) | 68.5 | 55.7 dB | **-12.8** |
| strongest intact (specimen 3, 6 mm overlay) | 27.7 | **37.8 dB** | **+10.1** |

The fractured loss is unsurprising: a narrower band penetrates 10 mm of overlay
less well and resolves a 0.2 mm kerf less sharply.

The intact rise is the finding. 37.8 dB is **specimen 3 at 6 mm overlay against
a group mean of 23.7** - an outlier, a **false alarm** rather than a missed
detection, and sitting exactly on the primary endpoint condition.

The mechanism follows from the resolution column. Bandwidth buys range
resolution, 3.67 mm against 4.42 mm. At full band, migration resolves specimen
3's layered-interface reflection and collapses it. Band-limited, it smears into
the detection window and reads as a target. The low band's real job is letting
migration separate the interface artefact from the fracture, and this is the
same Stage 4 residual appearing for the third time - after Stage 4 itself and
the overlay drift in Stage 7.

## Why this changes the recommendation

The concerning part is not the mean shift but the **variance**. One specimen in
eight spikes to 37.8 dB while its peers sit near 23.7. That is a
specimen-dependent margin, and with thirty specimens rather than eight the
expectation is a worse outlier, not a better one. A safety factor that depends
on which bone was drawn is not one to rely on.

So the antenna as built remains **usable** - 17.9 dB of clear air is real
separation, and detection survives - but recovering the low band moves from
optional to worthwhile. It is over half the buffer protecting the result
against everything the error model omits: cable flex, connector repeatability,
operator variation, genuine inter-bone heterogeneity.

## Caveat on the method

`crop()` is a brick-wall cut, not an antenna. A real antenna rolls off, and its
gain and phase vary across the band it does cover. A hard cut is the right first
question - it is the pessimistic case, so if it barely moved the result a gentle
roll-off certainly would not - but it is an upper bound on the damage, not a
prediction. Modelling the measured S11 as a frequency weighting would refine it.

Also, the antenna reaches 12 GHz while the matrix stops at 11, so the 4.35-11.0
row **understates it**. True bandwidth is 7.65 GHz against the target's 8.0, a
4% loss rather than the 17% the low-end figure alone suggests.

## Routes to recovering the low band

Ruled out first: **enlarging the antenna will not work.** Stage 5's sweep found
the match got *worse* as aperture and length grew, and an independent check
confirms it - solving for the effective permittivity implied by the measured
4.35 GHz cutoff and the 60 mm aperture gives 0.33, which is impossible and so
falsifies the premise that the aperture is what limits the low end. The cause is
edge-current resonance: Re(Zin) ripples to 117 ohm at 3.0 GHz against 24.5 ohm
at 4.0 GHz.

1. **Corrugations, retried with a suitable end criterion.** Slots ring by
   design, and Stage 5 judged them against a -40 dB decay criterion written for
   a structure that does not ring, giving a 40-hour extrapolated runtime. Mesh
   cost was nil - 7.40 M cells either way, identical time step. Fewer and
   shallower slots with EndCriteria relaxed is the first thing to try.
2. **Resistive edge loading.** Damps the resonance directly and converges
   normally. Costs efficiency; the fallback if the slots still will not settle.

## Resolved

The shortfall this document measures no longer exists. A tapered feed took the
antenna from 4.35-12.00 GHz to **2.48-12.00 GHz**, which fully contains the
3-11 GHz band the matrix was solved over, so the design-target row above is
now the operating row and **the full 40.8 dB separation is recovered**.

The measurement retains its value for two reasons that outlive the defect. It
is the concrete demonstration that AUC = 1.0000 concealed the loss of more
than half the margin - the Stage 7 saturation caveat, shown rather than
asserted. And it is what made recovering the low band a priority instead of a
documented footnote: without the 22.9 dB figure, 4.35 GHz would have looked
like an acceptable compromise.

See `docs/stage5-findings.md`.
