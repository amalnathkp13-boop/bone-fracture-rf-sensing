"""A genuinely three-dimensional limb: nested cylinders, not stacked slabs.

Everything else in this project solves a 2D TMz plane. That was the right
first model - it is the plane the antenna scans, and it made a 192-cell matrix
affordable - but it carries an assumption that has been listed as a limitation
throughout: the bone is represented as a pair of flat layers rather than a
tube, so out-of-plane scattering and surface curvature are absent.

This module removes that assumption. The forearm becomes what it anatomically
is: concentric cylinders of skin, fat and muscle around a cortical tube with a
marrow cavity, running along x. A transverse fracture is a slab-shaped gap cut
through the cortical wall and filled with haematoma.

Two effects appear here that the 2D model cannot produce, and they work in
opposite directions, which is exactly why the comparison is worth running
rather than assuming:

  - **Curvature defocuses.** A cylindrical surface spreads the reflected
    wavefront in the transverse plane. A flat interface does not. This costs
    signal.
  - **Out-of-plane scattering leaks.** Energy that a 2D model traps in the
    plane can leave it. This also costs signal.
  - **But the cortex is a tube.** A transverse crack severs a curved wall, so
    the scattering edge is longer than the flat model represents, and it is
    illuminated over a range of incidence angles rather than one. This can
    return signal the flat model misses.

Coordinates match `Phantom`: x along the bone axis, z into the limb with z = 0
at the skin surface directly beneath the antenna, which sits at negative z.
The cylinder axis therefore lies at z = r_limb below the skin apex.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .phantom import Fracture


@dataclass(frozen=True)
class CylindricalPhantom:
    """Concentric tissue cylinders around a cortical tube.

    The bone is OFFSET toward the skin, not centred. A centred 10 mm bone in a
    30 mm limb would put the near cortical wall 20 mm deep, against 6 mm in the
    layered phantom, and the two models would then differ in depth as well as
    in geometry - so any difference in the result could not be attributed to
    curvature. It is also wrong anatomically: the tibial and radial shafts are
    subcutaneous over part of their circumference, which is precisely why they
    are the candidate sites.

    `bone_offset` therefore raises the bone axis toward the skin until the near
    cortical wall sits at the same depth the layered model uses.
    """
    r_limb: float = 0.030          # skin outer radius, m
    skin: float = 0.002            # wall thicknesses, m
    fat: float = 0.003
    muscle: float = 0.015          # fills to the cortex
    r_cortex: float = 0.010        # outer radius of the cortical tube
    bone_offset: float = 0.014     # bone axis raised toward the skin, m
    cortex: float = 0.004          # cortical wall thickness
    standoff: float = 0.012        # antenna aperture to the skin apex
    length: float = 0.090          # extent along the bone axis, m
    fracture: Fracture | None = None
    bone_material: str = "cortical_bone"
    _tissue_overrides: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.r_cortex >= self.r_limb:
            raise ValueError("the bone cannot be wider than the limb")
        if self.cortex >= self.r_cortex:
            raise ValueError("the cortical wall cannot exceed its own radius")
        soft = self.skin + self.fat
        if self.z_cortex <= soft:
            raise ValueError(
                f"the bone is offset so far that the cortex at "
                f"{self.z_cortex*1e3:.1f} mm sits inside skin and fat "
                f"({soft*1e3:.1f} mm)")
        if self.bone_offset + self.r_cortex >= self.r_limb:
            raise ValueError("the bone breaks the skin surface")

    # --- radii, outermost first -------------------------------------------

    @property
    def r_fat(self) -> float:
        return self.r_limb - self.skin

    @property
    def r_muscle(self) -> float:
        """Muscle fills everything inside the fat down to the bone."""
        return self.r_fat - self.fat

    @property
    def r_marrow(self) -> float:
        return self.r_cortex - self.cortex

    @property
    def z_bone_axis(self) -> float:
        """Depth of the bone axis below the skin apex."""
        return self.r_limb - self.bone_offset

    @property
    def z_cortex(self) -> float:
        """Depth below the skin apex at which the near cortical wall starts."""
        return self.z_bone_axis - self.r_cortex

    @property
    def z_far_cortex(self) -> float:
        """Depth at which the far cortical wall starts, for time-window sizing."""
        return self.z_bone_axis + self.r_marrow

    def soft_shells(self):
        """(material, radius) about the LIMB axis, outermost first."""
        return [("skin_dry", self.r_limb), ("fat", self.r_fat),
                ("muscle", self.r_muscle)]

    def bone_shells(self):
        """(material, radius) about the BONE axis, outermost first."""
        return [(self.bone_material, self.r_cortex), ("marrow", self.r_marrow)]

    def shells(self):
        """Every shell in draw order, as (material, radius, about_bone)."""
        return ([(m, r, False) for m, r in self.soft_shells()]
                + [(m, r, True) for m, r in self.bone_shells()])

    def with_fracture(self, fr: Fracture | None) -> "CylindricalPhantom":
        return CylindricalPhantom(**{**self.__dict__, "fracture": fr})

    def summary(self) -> str:
        return (f"cylindrical limb r={self.r_limb*1e3:.0f} mm, bone axis "
                f"{self.z_bone_axis*1e3:.0f} mm deep, cortex "
                f"{self.r_marrow*1e3:.0f}-{self.r_cortex*1e3:.0f} mm, "
                f"near wall at {self.z_cortex*1e3:.1f} mm")
