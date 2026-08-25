"""gprMax in three dimensions, for the cylindrical limb.

The 2D backend in `gprmax.py` writes a domain one cell deep and draws the
anatomy as boxes. This one writes a real volume and draws it as nested
cylinders running along the bone axis, which is what a forearm is.

Cost is the reason the rest of the project is 2D, and it is worth stating
plainly rather than discovering halfway through a run. The 2D matrix used
0.2 mm cells on a 500 x 275 grid: 138 k cells. The same resolution in 3D over
a 76 mm width would be 380 times larger.

The grid here is 0.4 mm and the centre frequency is lowered to 4 GHz. Both
1.0 mm and 0.5 mm were tried first and rejected by the mesh check below. Two
consequences follow and both are reported rather than hidden:

  - The band becomes roughly 2-6 GHz instead of 3-11 GHz. **The 2D data is
    band-limited to the same window before the two are compared**, using the
    same machinery as the bandwidth study, so the comparison isolates geometry
    rather than confounding it with bandwidth.
  - The 0.2 mm kerf cannot be represented at 0.4 mm cells, so this model runs
    the 1 and 2 mm cases.

That is the right trade. The question this model exists to answer is whether
curvature and out-of-plane scattering change the result, not whether a hairline
crack survives a coarser mesh.

Orientation. gprMax uses x, y, z with y upward. The phantom uses x along the
bone and z into the limb. There are TWO axes, because the bone is offset
toward the skin rather than centred: the soft-tissue shells are concentric
with the limb axis and the cortex and marrow with the bone axis. So:

    gprMax x  <-  bone axis
    gprMax y  <-  vertical, antenna above, y = y_skin - z_phantom
    gprMax z  <-  transverse width, bone axis centred at z = width / 2
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .gprmax import _materials_block

C0 = 299_792_458.0


@dataclass(frozen=True)
class GridSpec3D:
    """Discretisation and domain extent for the 3D model, metres."""
    dx: float = 0.0004          # 0.4 mm; 0.5 and 1.0 fail the mesh check
    length: float = 0.090       # along the bone axis
    width: float = 0.076        # transverse
    height: float = 0.090       # vertical, including standoff and margins
    margin: float = 0.008       # clearance between PML and anything of interest
    time_window: float = 3.5e-9
    centre_freq: float = 4e9    # NOT the 7 GHz of the 2D model. A 3D grid
                                # fine enough for 11 GHz is unaffordable, so
                                # the band is lowered to roughly 2-6 GHz and
                                # the 2D data is band-limited to match when
                                # the two are compared.

    @property
    def dt(self) -> float:
        """3D Courant limit, which is what gprMax will choose."""
        return self.dx / (C0 * np.sqrt(3))

    @property
    def cells(self) -> int:
        return int(round(self.length / self.dx)
                   * round(self.height / self.dx)
                   * round(self.width / self.dx))

    def y_antenna(self) -> float:
        return self.height - self.margin

    def y_skin(self, ph) -> float:
        return self.y_antenna() - ph.standoff

    def z_axis(self) -> float:
        return self.width / 2.0

    def check(self, ph) -> None:
        """Fail before the solver does, with a reason rather than a crash."""
        y_skin = self.y_skin(ph)
        y_bottom = y_skin - 2 * ph.r_limb
        if y_bottom < self.margin:
            raise ValueError(
                f"domain too short: the limb reaches y={y_bottom*1e3:.1f} mm, "
                f"needs {self.margin*1e3:.1f} mm of margin. Raise height.")
        if self.width < 2 * ph.r_limb + 2 * self.margin:
            raise ValueError(
                f"domain too narrow: limb is {2*ph.r_limb*1e3:.0f} mm across, "
                f"width is {self.width*1e3:.0f} mm. Raise width.")
        # Cells per wavelength in the highest-permittivity tissue.
        #
        # The band edge is 3x the centre frequency, not 2x. A first version
        # used 2x and passed a 0.5 mm grid at 6 GHz; gprMax then reported the
        # maximum significant frequency as 22 GHz and a -4.81% phase-velocity
        # error in muscle. A gaussiandot pulse carries usable energy well past
        # twice its centre, so the check has to as well or it certifies grids
        # the solver will not honour.
        f_edge = 3.0 * self.centre_freq
        lam = C0 / f_edge / np.sqrt(45.0)
        ppw = lam / self.dx
        if ppw < 8.0:
            raise ValueError(
                f"dx={self.dx*1e3:.2f} mm gives {ppw:.1f} cells per wavelength "
                f"in muscle at {f_edge/1e9:.0f} GHz (the gaussiandot band "
                f"edge); 8 is the minimum. Lower centre_freq or dx.")


def build_geometry(ph, grid: GridSpec3D) -> str:
    """Nested cylinders along the bone axis, then the fracture."""
    grid.check(ph)
    y_skin = grid.y_skin(ph)
    y_limb = y_skin - ph.r_limb              # soft tissue is about this axis
    y_bone = y_skin - ph.z_bone_axis         # cortex and marrow about this one
    z_c = grid.z_axis()
    L = grid.length
    lines = []

    # Outermost first: each shell overwrites the inside of the previous one,
    # which is how gprMax composes geometry - later commands win.
    for mat, r, about_bone in ph.shells():
        y_c = y_bone if about_bone else y_limb
        lines.append(f"#cylinder: 0 {y_c:.4f} {z_c:.4f} {L:.4f} "
                     f"{y_c:.4f} {z_c:.4f} {r:.4f} {mat}")

    fr = ph.fracture
    if fr is not None:
        # A transverse crack: a slab across the whole bone at x = fr.x,
        # restricted to the cortical tube by redrawing the marrow afterwards
        # so the gap does not spill into the medullary cavity.
        half = max(fr.kerf / 2, grid.dx / 2)
        x0, x1 = fr.x - half, fr.x + half
        if x1 - x0 < grid.dx - 1e-12:
            raise ValueError(
                f"kerf {fr.kerf*1e3:.2f} mm is under one {grid.dx*1e3:.2f} mm "
                f"cell and will vanish when the coordinates snap")
        lines.append(f"#cylinder: {x0:.4f} {y_bone:.4f} {z_c:.4f} {x1:.4f} "
                     f"{y_bone:.4f} {z_c:.4f} {ph.r_cortex:.4f} {fr.fill}")
        lines.append(f"#cylinder: {x0:.4f} {y_bone:.4f} {z_c:.4f} {x1:.4f} "
                     f"{y_bone:.4f} {z_c:.4f} {ph.r_marrow:.4f} marrow")
    return "\n".join(lines)


def build_input(ph, grid: GridSpec3D, materials, x_start: float,
                n_positions: int, step: float, title: str = "") -> str:
    """One 3D gprMax deck. Pass ph=None for the free-space reference."""
    y_ant = grid.y_antenna()
    z_c = grid.z_axis()
    head = [
        f"#title: {title or 'bonesim 3D B-scan'}",
        "##",
        "## Generated by bonesim/forward/gprmax3d.py - do not edit by hand.",
        "",
        f"#domain: {grid.length:.4f} {grid.height:.4f} {grid.width:.4f}",
        f"#dx_dy_dz: {grid.dx:.4f} {grid.dx:.4f} {grid.dx:.4f}",
        f"#time_window: {grid.time_window:g}",
        "",
        f"#waveform: gaussiandot 1 {grid.centre_freq:g} pulse",
        f"#hertzian_dipole: z {x_start:.4f} {y_ant:.4f} {z_c:.4f} pulse",
        f"#rx: {x_start:.4f} {y_ant:.4f} {z_c:.4f}",
    ]
    if n_positions > 1:
        head += [f"#src_steps: {step:.4f} 0 0", f"#rx_steps: {step:.4f} 0 0"]
    if ph is None:
        return "\n".join(head) + "\n"
    return ("\n".join(head) + "\n\n" + _materials_block(materials) + "\n\n"
            + build_geometry(ph, grid) + "\n")


def estimate(grid: GridSpec3D, n_models: int, mcells_per_s: float = 300.0):
    """Rough wall-clock estimate, so a run is sized before it is started.

    Measured on this project: 36.9 Mcell/s on 12 CPU threads locally, and
    roughly 300 on a Colab T4, which is why the matrix went to Colab. The 2D
    work taught this lesson expensively - an unmeasured extrapolation is how a
    ten-minute job was once recorded as forty hours - so both figures here are
    measured rather than assumed.
    """
    steps = int(grid.time_window / grid.dt)
    work = grid.cells * steps * n_models / 1e6
    return {"cells": grid.cells, "timesteps": steps, "models": n_models,
            "Mcell_steps": work, "hours": work / mcells_per_s / 3600}
