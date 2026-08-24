"""Geometry of the scanned limb, shared by both forward models.

The imaging plane contains the bone axis, because the antenna scans along it
(proposal 2.4). In that plane the cortex is not a circle but a pair of
horizontal layers - near cortex, marrow, far cortex - and a transverse fracture
is a vertical gap crossing them. This is why the proposal describes a fracture
as "a localised bright spot on the bone surface line, offset from the continuous
skin line above it".

Coordinates: x runs along the bone axis, z runs into the limb with z = 0 at the
skin surface. The antenna sits at negative z, at the standoff distance.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Fracture:
    """A transverse or oblique gap, filled with haematoma.

    Section 2.1 is emphatic that a fracture is not a void: within hours it fills
    with blood, and blood against cortical bone is the contrast being imaged.
    """
    x: float                    # centre position along the bone axis, m
    kerf: float                 # gap width, m (proposal 4.2: 0.3-2.0 mm)
    angle_deg: float = 0.0      # 0 = transverse; 30/45 = oblique
    depth_fraction: float = 1.0  # 1.0 = complete, 0.5 = partial (50% cut)
    fill: str = "blood"

    @property
    def is_partial(self) -> bool:
        return self.depth_fraction < 1.0


@dataclass(frozen=True)
class Phantom:
    """A layered limb model with a cortical bone and an optional fracture."""
    skin: float = 0.002          # m
    fat: float = 0.003
    muscle: float = 0.001
    cortex: float = 0.004        # near cortical wall thickness
    marrow: float = 0.010
    standoff: float = 0.012      # antenna aperture to skin (proposal 2.2)
    fracture: Fracture | None = None
    bone_material: str = "cortical_bone"
    length: float = 0.100        # extent along x
    _tissue_overrides: dict = field(default_factory=dict)

    # --- layer boundaries, all measured from the skin surface -------------

    @property
    def z_skin(self) -> float:
        return 0.0

    @property
    def z_fat(self) -> float:
        return self.skin

    @property
    def z_muscle(self) -> float:
        return self.z_fat + self.fat

    @property
    def z_cortex(self) -> float:
        """Depth of the near cortical surface - the line a fracture sits on."""
        return self.z_muscle + self.muscle

    @property
    def z_marrow(self) -> float:
        return self.z_cortex + self.cortex

    @property
    def z_far_cortex(self) -> float:
        return self.z_marrow + self.marrow

    @property
    def overlay(self) -> float:
        """Total soft tissue above the bone.

        The proposal's headline sweep (4.3) is over this quantity: 3, 6 and
        10 mm, characterising how fast soft tissue masks the bone.
        """
        return self.skin + self.fat + self.muscle

    def with_overlay(self, total: float) -> "Phantom":
        """Rescale the soft-tissue layers to a given total overlay thickness.

        Above skin thickness, skin is held at its physiological value and the
        remainder is split between fat and muscle in their existing proportion,
        because it is subcutaneous fat that actually varies between sites and
        subjects.

        At or below skin thickness the whole stack is scaled down together.
        total = 0 gives bare bone, which the experiment matrix of proposal 4.4
        requires as its first overlay level: specimens are scanned defleshed
        before any phantom is cast around them.
        """
        if total < 0:
            raise ValueError(f"overlay cannot be negative, got {total}")
        if total == 0.0:
            return Phantom(**{**self.__dict__,
                              "skin": 0.0, "fat": 0.0, "muscle": 0.0})
        if total < self.skin:
            # Thinner than skin alone: shrink all three in proportion.
            scale = total / self.overlay
            return Phantom(**{**self.__dict__,
                              "skin": self.skin * scale,
                              "fat": self.fat * scale,
                              "muscle": self.muscle * scale})
        rest = total - self.skin
        frac = self.fat / (self.fat + self.muscle)
        return Phantom(**{**self.__dict__,
                          "fat": rest * frac, "muscle": rest * (1 - frac)})

    @property
    def is_bare(self) -> bool:
        return self.overlay == 0.0

    def with_fracture(self, fracture: Fracture | None) -> "Phantom":
        return Phantom(**{**self.__dict__, "fracture": fracture})

    # --- description of the stack -----------------------------------------

    def stack(self) -> list[tuple[str, float, float]]:
        """(material, z_top, z_bottom) from the skin surface inward.

        Layers of zero thickness are omitted. A layer that is not there should
        not be emitted, and a degenerate box is not merely redundant: gprMax
        rejects a primitive with no volume, so a bare-bone specimen - overlay
        zero, the first level of the matrix in proposal 4.4 - would otherwise
        fail to build at all.
        """
        layers = [
            ("skin_dry", self.z_skin, self.z_fat),
            ("fat", self.z_fat, self.z_muscle),
            ("muscle", self.z_muscle, self.z_cortex),
            (self.bone_material, self.z_cortex, self.z_marrow),
            ("marrow", self.z_marrow, self.z_far_cortex),
            (self.bone_material, self.z_far_cortex,
             self.z_far_cortex + self.cortex),
        ]
        return [(m, a, b) for m, a, b in layers if b > a]

    def material_at(self, x: float, z: float) -> str:
        """Material at a point, accounting for the fracture gap."""
        if z < self.z_skin:
            return "free_space"
        fr = self.fracture
        if fr is not None and self.z_cortex <= z:
            # Oblique cuts lean with depth.
            shift = (z - self.z_cortex) * np.tan(np.radians(fr.angle_deg))
            if abs(x - (fr.x + shift)) <= fr.kerf / 2:
                z_end = self.z_cortex + fr.depth_fraction * self.cortex
                if z <= z_end:
                    return fr.fill
        for mat, z0, z1 in self.stack():
            if z0 <= z < z1:
                return mat
        return "free_space"

    def scatterers(self):
        """Discrete scattering centres as (x, z, kerf, fill, host).

        The fracture is deliberately returned as a *point* scatterer with a
        width, not as a resolved pair of edges. Section 2.1 is explicit that at
        2.8 GHz of bandwidth the range resolution in bone is about 15 mm, so a
        1 mm kerf is far below it and is detected as an isolated scattering
        centre rather than resolved as two targets.

        The width is carried through rather than collapsed into a strength,
        because the scattering amplitude of a fluid-filled gap is a resonant
        function of width and frequency, not a linear one - the forward model
        computes it.
        """
        if self.fracture is None:
            return []
        fr = self.fracture
        z = self.z_cortex + 0.5 * fr.depth_fraction * self.cortex
        return [(fr.x, z, fr.kerf, fr.fill, self.bone_material)]

    def describe(self) -> str:
        fr = self.fracture
        f = ("intact" if fr is None else
             f"kerf {fr.kerf*1e3:.2f} mm, {fr.angle_deg:g} deg, "
             f"{fr.depth_fraction*100:.0f}% depth")
        return (f"overlay {self.overlay*1e3:.1f} mm "
                f"(skin {self.skin*1e3:.1f} / fat {self.fat*1e3:.1f} / "
                f"muscle {self.muscle*1e3:.1f}), cortex "
                f"{self.cortex*1e3:.1f} mm at z={self.z_cortex*1e3:.1f} mm, {f}")
