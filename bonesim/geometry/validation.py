"""Validation targets: the brass-rod gate of proposal section 9.

    "Verify with a known strong scatterer first: if you cannot image a 6 mm
    brass rod at 20 mm depth in phantom, you will never image a fracture."

The proposal lists attempting migration before this check as the first way
students fail on Path A, and makes it the week-6 go/no-go. It is a decisive
test because it removes every excuse: a metal rod in a uniform medium is an
enormously stronger and simpler target than a blood-filled kerf in layered
tissue. If the chain cannot image it, the fault is in the chain.

Modelled as PEC rather than as brass. At 3-11 GHz the skin depth in brass is
well under a micrometre, so it is a perfect reflector for this purpose, and PEC
avoids pretending to a precision the model does not have.

This class deliberately duck-types the same interface as Phantom, so the deck
builder, the pipeline and the detector all treat it identically. Running the
gate through different code from the experiment would defeat its purpose.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RodPhantom:
    """A uniform tissue-mimicking phantom containing a metal rod.

    background   material filling the tank. The proposal's Path A phantom is
                 oil-in-gelatin tuned across eps_r 10-50 (section 4.3); muscle
                 stands in for a high-water-content mix.
    rod_depth    depth of the rod *centre* below the phantom surface, m
    rod_diameter m
    present      False builds the identical phantom with no rod, which is the
                 control the rod scan is compared against
    """
    background: str = "muscle"
    rod_depth: float = 0.020
    rod_diameter: float = 0.006
    rod_x: float = 0.050
    depth: float = 0.040
    standoff: float = 0.012
    present: bool = True

    # --- interface shared with Phantom ------------------------------------

    fracture = None          # no fracture in this geometry

    @property
    def cortex(self) -> float:
        """Margin the deck builder reserves below the deepest structure."""
        return 0.0

    @property
    def z_far_cortex(self) -> float:
        return self.depth

    @property
    def overlay(self) -> float:
        """Material above the rod, the analogue of soft-tissue overlay."""
        return self.rod_depth - self.rod_diameter / 2

    def stack(self):
        return [(self.background, 0.0, self.depth)]

    def cylinders(self):
        """(x, z, radius, material) for the deck builder."""
        if not self.present:
            return []
        return [(self.rod_x, self.rod_depth, self.rod_diameter / 2, "pec")]

    def scatterers(self):
        if not self.present:
            return []
        return [(self.rod_x, self.rod_depth, 10.0)]

    def without_rod(self) -> "RodPhantom":
        return RodPhantom(**{**self.__dict__, "present": False})

    def describe(self) -> str:
        if not self.present:
            return (f"{self.background} phantom, {self.depth*1e3:.0f} mm deep, "
                    f"no rod (control)")
        return (f"{self.background} phantom, {self.rod_diameter*1e3:.0f} mm PEC "
                f"rod at {self.rod_depth*1e3:.0f} mm depth, "
                f"{self.overlay*1e3:.0f} mm of overlay above it")
