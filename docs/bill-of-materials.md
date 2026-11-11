# Bill of materials: what it takes to build the instrument

The project is purely virtual by design, and nothing here has been bought.
This is the list of what a physical build would need, with each specification
traced to the simulation that fixed it rather than to a generic shopping list.
Cost figures are the proposal's own indicative Indian-supplier numbers
(Robu, Element14 India, Mouser India, Amazon.in) and **must be re-quoted before
purchase**; several are a year old.

Totals from the proposal, which this document does not change:

| configuration | approx. total |
|---|---|
| with a department VNA (recommended) | **INR 23,800** |
| with the LiteVNA-64 fallback | **INR 32,800** |

`docs/bill-of-materials.csv` is the same list as a spreadsheet. It carries all
three VNA options, so its column sum (INR 42,700) is not a configuration total;
pick one VNA row.

The one thing the proposal could only guess at - whether the cheap VNA
fallbacks actually work - is now measured. See section A.

## A. The measurement instrument

The VNA decides viability. The proposal's framing stands: *the single question
is whether the department owns a VNA reaching 8 GHz or above.*

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| VNA, preferred | 1-port S11; sweep 3-11 GHz (antenna is matched 2.48-12.00); >= 201 points; output 0 dBm; dynamic range >= 95 dB at ~1 kHz IFBW | department lab VNA, 8-20 GHz | 1 | 0 | check first; decides everything below |
| VNA, fallback 1 | 50 kHz - 6.3 GHz | LiteVNA-64 | 1 | 9,000 | **works: measured below** |
| VNA, fallback 2 | to 4.4 GHz | NanoVNA V2 Plus4 | 1 | 7,000 | **works on band; dynamic range untested** |
| calibration kit | SMA short/open/load, calibrated **at the antenna connector**, not the VNA port | SMA SOL kit (often bundled with LiteVNA) | 1 | 1,500-3,000 | everything downstream is referenced to the antenna feed |

**Where the numbers come from.** The matrix was solved over 3-11 GHz at 201
points (`ScanData` grid). The error model (`bonesim/perturb/errors.py`,
`Instrument`) assumes a **95 dB** noise floor below the strongest return, which
a lab VNA at 1 kHz IF bandwidth meets and a LiteVNA (roughly 70 dB at its top
end) does not. **0 dBm** is the adopted transmit power from the exposure
assessment: at +10 dBm the 6-11 GHz absorbed power density sat within 1.8x of
the ICNIRP public limit; at 0 dBm every limit clears by at least 18x, and the
detector has 40.8 dB of margin to spend (`docs/safety-sar.md`).

### Do the cheap VNAs work? Measured, not guessed

The proposal labelled the LiteVNA "band-limited; degrades resolution" and the
NanoVNA "minimum viable, marginal". Those were guesses made before the matrix
was solved. Every solved cell stores the full 3-11 GHz response, so each
fallback can be scored on exactly the data it could have acquired, with no new
simulation (`scripts/vna_fallback_study.py`, same pipeline and detector as
Stage 7).

| VNA option | usable band | bandwidth | range res. | AUC | class separation |
|---|---|---|---|---|---|
| department VNA | 3.00-11.0 GHz | 8.00 GHz | 3.67 mm | 1.0000 | **40.8 dB** |
| (first antenna, for scale) | 4.35-11.0 GHz | 6.65 GHz | 4.42 mm | 1.0000 | 17.9 dB |
| LiteVNA-64 | 3.00-6.30 GHz | 3.30 GHz | 8.91 mm | 1.0000 | **51.5 dB** at 95 dB dynamic range; **36.4 dB** at 70 dB |
| NanoVNA V2 Plus4 | 3.00-4.40 GHz | 1.40 GHz | 21.0 mm | 1.0000 | **43.0 dB** band only, at 95 dB dynamic range |

**Verdict: both work, and on the band alone the LiteVNA beats the department
VNA.** Removing the upper band *raises* the separation, 51.5 dB against 40.8,
because the frequencies above 6.3 GHz contribute little through 6 mm or more
of overlay and mostly add image background the detector does not want; the
low band carries the penetration (`docs/band-study.md`). By overlay, the
LiteVNA band gives 64.9 / 66.6 / 65.2 / 51.5 dB at 0 / 3 / 6 / 10 mm and the
NanoVNA band 54.8 / 57.3 / 60.5 / 45.9 dB. The classes do not overlap at any
overlay for either.

**Dynamic range, measured separately.** The band study keeps the error
model's 95 dB noise floor, which the cheap VNAs do not have. Re-scoring the
LiteVNA band with `Instrument(dynamic_range_db=70)`
(`scripts/vna_dynrange_study.py`, 576 realisations) gives AUC 1.0000 and
**36.4 dB** separation: 50.2 / 49.1 / 50.0 / 36.4 dB by overlay. The 25 dB
worse floor costs 15 dB of margin, nearly all of it at the 10 mm overlay, and
what remains is within 5 dB of the department VNA's full-band 40.8. So a
LiteVNA-64 is a defensible instrument for this experiment, not a compromise.
The same test has not been run for the NanoVNA band; its 43.0 dB is the
band-only figure at 95 dB and should be read as an upper bound on what that
instrument would deliver.

## B. The antenna

Design files are in `figures/`: `vivaldi.dxf` (4 layers, mm, origin at the
feed edge), `vivaldi_antenna.step`, `vivaldi_fab_drawing.pdf` (A4, both faces
dimensioned), `vivaldi_geom.json`. Rebuild with
`python scripts/make_antenna_fab.py`.

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| substrate | Rogers RO4350B, 0.762 mm (30 mil), 1 oz Cu, 100 x 150 mm; antenna is 150 x 90 mm so one board per antenna | RO4350B 0.762 mm | 2 | 3,500 | FR4 alternative INR 300, costs 2.4 dB at 9 GHz and 3.6 dB at 11 (Stage 5) |
| fabrication | etch both faces from `vivaldi.dxf`; 4 x 3.2 mm mounting holes at (6, +/-38) mm | PCB house, or in-house etch | 2 | 3,000 | one spare |
| SMA connector | **end-launch, 18 GHz rated**; port trace is 1.74 mm (50 ohm) | L-com RFPCB-SMA-FS18G-55 (solder, cut for 0.031 in board) **or** Southwest 292-04A-9 (solderless clamp, 0.010 in pin) | 4 | 1,600 | **do not use cheap 6 GHz parts.** No extra pads needed; see note |
| mounting | M3 nylon standoffs + screws for the four holes | M3 x 10 nylon | 8 | 200 | keeps metal out of the near field |

**The antenna as designed.** Antipodal Vivaldi, growth a*T = 2.0, 60 mm
aperture, **tapered feed 4.50 mm at the flare to 1.74 mm at the port**. The
taper is what took the match from 4.35-12.00 GHz to **2.48-12.00 GHz**: 99.69%
of 3-11 GHz below -10 dB, worst -9.98 dB at one point, median Re(Zin) 45.6 ohm
(`docs/stage5-findings.md`). Gain is 7.02 dBi at 3 GHz, 11.9-12.5 dBi across
5-9 GHz, 9.3 dBi at 11 GHz; the 8-10 dBi target is met from about 4 GHz up and
**not at 3 GHz**, which is aperture-limited and was shown not fixable by
resizing within the board.

**Connector note, from the fab drawing.** Both named parts were checked
against their datasheets for the 0.762 mm board. An end-launch lands its pin on
the 1.74 mm trace at the board edge and grounds to the full-width plane on the
other face, so **no pads are drawn and none are needed**. The Southwest part's
0.0635 in (1.61 mm) dielectric is within 8% of the trace width, which is why
it launches cleanly. The proposal's INR 400 per connector assumes a generic
18 GHz end-launch; the named Southwest part is a premium item at roughly ten
times that - price it before choosing. Top-ground-tab connectors are supported
only with a >= 2.5 mm pad gap and cost the band above 9.6 GHz; avoid them.

## C. Cabling

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| test cable | phase-stable, SMA-SMA, 18 GHz, 60 cm | e.g. Mini-Circuits / Pasternack phase-stable | 1 | 4,500 | **secure it** - flexing changes phase |
| port saver | SMA female-female adapter on the VNA port | SMA F-F, 18 GHz | 2 | 500 | the VNA connector outlives the project; the saver does not |

The error model's cable term is 1 fs RMS delay jitter, i.e. a cable that does
not move during a scan. Route it along the stage with slack at a single fixed
bend, not dragged.

## D. The scan stage

Migration sums phase coherently across positions, so position error is phase
error: 0.5 mm at 10 GHz in air is about 60 degrees (proposal 2.4). The error
model assumes **100 um RMS** stage jitter and the result tolerated it; build to
that.

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| rail | >= 60 mm scan travel (matrix used 61 positions at 1 mm, 20-80 mm); 200 mm gives clearance for the 150 mm antenna | 2020 aluminium extrusion, 200 mm | 1 | 2,800 | includes lead screw |
| lead screw | 8 mm, **anti-backlash nut** | T8 + anti-backlash brass nut | 1 | (incl.) | backlash is a systematic position error migration cannot remove |
| motor + driver | NEMA 17, A4988, 12 V 3 A PSU | standard 3D-printer parts | 1 | 1,400 | 1 mm per step command; settle 200 ms before each sweep |
| home switch | mechanical limit switch at one end | microswitch | 1 | (incl.) | repeatable zero; required for empty-scene subtraction to line up |
| controller | serial command "step, settle, trigger" | Arduino Nano or ESP32 | 1 | 600 | the laptop drives the VNA over USB; the controller only moves the stage |

## E. Fixture

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| antenna holder | **12 mm standoff** aperture to skin, held to **+/- 0.3 mm** | acrylic or 3D-printed bracket on the stage carriage | 1 | (in 2,500) | standoff_sigma = 300 um in the error model |
| limb / phantom rest | holds the specimen with the bone axis parallel to the rail | acrylic cradle | 1 | (in 2,500) | tilt shows up as a sloping skin line |
| phantom tank | for casting layered phantoms around the bone | acrylic box, lid | 1 | (in 2,500) | cast overlay slabs separately (next section) |
| frame | mounts rail, holder, rest in one rigid assembly | 2020 extrusion + brackets | 1 | 2,500 total | rigidity is what makes the 100 um stage spec achievable |

## F. The phantom and specimens

The simulated layer stack is the casting target. Thicknesses from
`bonesim/geometry/phantom.py`; dielectric targets per tissue in
`docs/tissue-model.md` (Gabriel four-Cole-Cole).

| layer | thickness | note |
|---|---|---|
| skin | 2.0 mm | low oil fraction |
| fat | 3.0 mm | high oil fraction |
| muscle | 1.0 mm | high water |
| near cortical wall | 4.0 mm | the bone specimen itself |
| marrow | 10.0 mm | the bone specimen itself |
| **soft-tissue overlay** | **0, 3, 6, 10 mm** | the four experimental conditions; cast as separate slabs laid over the skin layer |

| item | spec the simulation fixed | suggested | qty | INR | note |
|---|---|---|---|---|---|
| phantom materials | oil-in-gelatin recipe, proposal 4.3 | DI water 50-70%, porcine gelatin 250 bloom 10-15%, kerosene or safflower oil 15-35% (the tuning knob), surfactant 1-2%, n-propanol 0-5%, p-toluic acid < 0.5%, NaCl 0-1% | - | 1,800 | oil fraction sets eps_r 10-50; **measure each batch** with an open-ended coax probe on the VNA |
| bone specimens | mid-shaft, ~4 mm cortical wall, ~10 mm medullary cavity | goat or bovine tibia, fresh from a butcher | 6-12 | 900 | defat mechanically; **do not boil**; store in saline gauze at 4 C |
| fracture fill | blood-mimicking fluid; haematoma is the real contrast | saline-based blood mimic | - | (in 1,800) | the simulation used Gabriel blood |
| validation target | **6 mm brass rod at 20 mm depth** | brass rod, 6 mm dia, 100 mm | 1 | 200 | **Stage 4 gate: image this before any bone.** If migration cannot find it, nothing downstream is meaningful |
| kerf tools | kerfs 0.2-2.0 mm were simulated; the saw sets what is achievable | jeweller's saw, diamond wafering blade | - | (in 1,200) | measure the actual kerf; the measurement is the ground truth |
| metrology | | digital calliper, feeler gauges | - | (in 1,200) | record every kerf and every cortical thickness as covariates |
| consumables | | cling film, gloves, saw blades | - | 1,200 | |

## G. Compute and software

Nothing to buy. The laptop that ran the analysis runs the acquisition.

| item | note |
|---|---|
| `bonesim` package | processing chain, detector, statistics - unchanged between simulation and bench |
| VNA control | `scikit-rf` + `pyvisa` for a lab VNA; LiteVNA/NanoVNA have serial protocols with Python libraries |
| stage control | serial to the Arduino/ESP32 |

The processing chain was built so that it cannot tell the analytic model, the
FDTD solver and a real VNA apart: it sees a matrix of complex S11 and nothing
else. That is the point at which the simulation hands over to the bench.

## What the build would test that the simulation could not

In order of how much they threaten the result (`docs/stage7-findings.md`,
limitations):

1. **The error model.** 95 dB dynamic range, 100 um stage jitter, 1 fs cable
   jitter, +/-0.3 mm standoff are assumptions. The 40.8 dB margin is the budget
   the real bench has to stay inside. This is what a brass rod and a VNA measure
   on day one.
2. **Real bone.** Eight simulated specimens vary only in what the variation
   model perturbs. Goat tibiae vary in everything.
3. **Fracture position.** Every simulated fracture is at x = 50 mm. A real cut
   is wherever the saw went, which tests localisation rather than separability.
4. **Three dimensions.** The bench is 3D for free. The 3D model
   (`bonesim/geometry/cylindrical.py`) is built and verified but unsolved.
