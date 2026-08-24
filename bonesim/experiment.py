"""The experiment matrix of proposal section 4.4.

    | Factor              | Levels                                        | n |
    | Specimen            | individual bones (biological replicate)        | 8 |
    | Fracture state      | intact, hairline, 0.4, 1.0, 2.0 mm, oblique   | 6 |
    | Soft tissue overlay | 0 mm (bare), 3 mm, 6 mm, 10 mm                | 4 |
    | Repeat measurements | full teardown and remount between repeats     | 3 |

The proposal calls that 8 x 6 x 4 x 3 = 576 acquisitions. Here it is 192.

The difference is the repeats, and it is not a shortcut. A remount changes the
*instrument*, not the anatomy: the stage lands a fraction of a millimetre
elsewhere, the standoff differs, the cable has drifted. Those are exactly the
errors `bonesim.perturb.errors` injects after the forward solve, so three
repeats are three draws from the error model applied to one solved scan. Solving
the same geometry three times would produce three bit-identical results, which
is not a repeatability estimate at all - it would measure nothing and cost 21
hours.

Two design rules from 4.4 are preserved because they are what make the numbers
mean anything:

**Each specimen is its own control.** Every specimen appears intact as well as
fractured, at every overlay, so the paired comparison the proposal asks for is
available and inter-specimen variation does not swamp the effect.

**Specimens actually differ.** `SpecimenVariation` gives each one its own
cortical wall thickness and overlay. Without that the eight are identical and
the leave-one-specimen-out cross-validation of section 5 has nothing to leave
out.
"""
from __future__ import annotations

from dataclasses import dataclass

from .geometry.phantom import Fracture, Phantom
from .perturb.errors import SpecimenVariation

X_FRACTURE = 0.050          # m, mid-scan
DX = 0.0002                 # m, the FDTD cell size the matrix is solved on

# Kerf widths, defined as whole numbers of cells rather than as round numbers
# of millimetres.
#
# Proposal 4.2 lists 0.3, 0.5, 1.0 and 2.0 mm and then insists: "Measure every
# kerf with a digital calliper and record the actual value, not the nominal
# one. Your ground truth is the measurement, not the intention." In simulation
# the measured kerf is whatever the grid represents, and on a 0.2 mm grid a
# 0.3 mm slot is 1.5 cells - it becomes 0.2 mm, and a 0.5 mm slot becomes
# 0.4 mm. Reporting a detection threshold of "0.3 mm" for a slot the solver
# built 0.2 mm wide would be a fabricated number.
#
# So the levels below are exact on the grid and are reported as such. The
# alternative, a 0.1 mm grid, quadruples a 32-hour matrix to 128 hours to gain
# two intermediate kerf values.
KERF_CELLS = {"hairline": 1, "kerf04": 2, "kerf10": 5, "kerf20": 10}

# (name, kerf in m, angle in degrees, depth fraction). kerf None = intact.
FRACTURE_STATES: tuple[tuple[str, float | None, float, float], ...] = (
    ("intact", None, 0.0, 1.0),
    ("hairline", KERF_CELLS["hairline"] * DX, 0.0, 1.0),
    ("kerf04", KERF_CELLS["kerf04"] * DX, 0.0, 1.0),
    ("kerf10", KERF_CELLS["kerf10"] * DX, 0.0, 1.0),
    ("kerf20", KERF_CELLS["kerf20"] * DX, 0.0, 1.0),
    ("oblique", KERF_CELLS["kerf10"] * DX, 45.0, 1.0),
)

OVERLAYS: tuple[float, ...] = (0.000, 0.003, 0.006, 0.010)
N_SPECIMENS = 8
N_REPEATS = 3               # error realisations, not re-solves


@dataclass(frozen=True)
class Cell:
    """One acquisition in the matrix: a phantom to solve, and its labels."""
    specimen: int
    state: str
    overlay: float
    phantom: Phantom

    @property
    def key(self) -> str:
        """Stable filename stem. Used to skip work already done."""
        return f"s{self.specimen:02d}_{self.state}_ov{self.overlay*1e3:04.1f}"

    @property
    def fractured(self) -> bool:
        return self.phantom.fracture is not None

    @property
    def kerf(self) -> float:
        return 0.0 if not self.fractured else self.phantom.fracture.kerf

    def describe(self) -> str:
        return (f"specimen {self.specimen}, {self.state}, overlay "
                f"{self.overlay*1e3:.0f} mm | {self.phantom.describe()}")


def build_matrix(base: Phantom | None = None,
                 variation: SpecimenVariation | None = None,
                 n_specimens: int = N_SPECIMENS) -> list[Cell]:
    """Every cell of the matrix, in a deterministic order.

    Specimen variation is drawn once per specimen and applied at every state
    and overlay, so a given bone keeps its cortical thickness throughout - as
    it would in the laboratory. Drawing per cell would make each acquisition a
    different animal and destroy the paired design.
    """
    base = base or Phantom()
    variation = variation or SpecimenVariation()

    cells: list[Cell] = []
    for specimen in range(n_specimens):
        # One draw per specimen, reused across all its acquisitions.
        drawn = variation.draw(base, specimen)
        for state, kerf, angle, depth in FRACTURE_STATES:
            for overlay in OVERLAYS:
                ph = drawn.with_overlay(overlay)
                if kerf is not None:
                    ph = ph.with_fracture(
                        Fracture(X_FRACTURE, kerf, angle_deg=angle,
                                 depth_fraction=depth))
                else:
                    ph = ph.with_fracture(None)
                cells.append(Cell(specimen, state, overlay, ph))
    return cells


def matrix_summary(cells: list[Cell]) -> str:
    states = sorted({c.state for c in cells})
    overlays = sorted({c.overlay for c in cells})
    specimens = sorted({c.specimen for c in cells})
    cortices = sorted({round(c.phantom.cortex * 1e3, 2) for c in cells})
    return (
        f"{len(cells)} acquisitions = {len(specimens)} specimens x "
        f"{len(states)} states x {len(overlays)} overlays\n"
        f"  states   : {', '.join(states)}\n"
        f"  overlays : {', '.join(f'{o*1e3:g}' for o in overlays)} mm\n"
        f"  cortical wall across specimens: "
        f"{min(cortices):.2f} to {max(cortices):.2f} mm\n"
        f"  each specimen appears intact at every overlay, so every "
        f"comparison is paired")
