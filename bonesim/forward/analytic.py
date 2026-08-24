"""Fast analytic forward model: layered background plus Born scattering.

Purpose is development speed, not fidelity. It exists so the SVD, migration,
autofocus and detection code can be written, unit-tested and debugged in seconds
rather than in FDTD hours. Scientific results come from the gprMax backend,
which carries full-wave physics this model does not.

Three contributions are summed at each scan position:

  1. antenna self-reflection, identical at every scan position
  2. the layered stack - an exact normal-incidence transfer matrix through
     skin/fat/muscle/cortex/marrow, referenced to the antenna plane. Nearly
     constant along the scan, and therefore exactly the coherent clutter the
     SVD stage exists to remove
  3. discrete scatterers - straight-ray two-way propagation using the true
     dispersive complex wavenumber of every layer the ray crosses

Because this model uses straight rays and migration also uses straight rays,
it is an inverse crime by construction. That is intended: it is a test harness
for the pipeline, not a source of results. The countermeasures described in the
README apply to the gprMax backend.
"""
from __future__ import annotations

import numpy as np

from ..materials import tissues as T
from ..materials.colecole import C0
from .base import ScanData

ETA0 = 376.730313668      # free-space wave impedance, ohm


def _eta(mat: str, f: np.ndarray) -> np.ndarray:
    if mat == "free_space":
        return np.full(np.shape(f), ETA0 + 0j)
    return ETA0 / np.sqrt(T.get(mat).eps_complex(f))


def _k(mat: str, f: np.ndarray) -> np.ndarray:
    """Complex wavenumber, attenuation included."""
    w = 2 * np.pi * np.asarray(f, float)
    if mat == "free_space":
        return w / C0 + 0j
    return w * np.sqrt(T.get(mat).eps_complex(f)) / C0


def stack_reflection(phantom, f: np.ndarray) -> np.ndarray:
    """Normal-incidence reflection of the layered limb, at the skin surface.

    Recursive transfer-matrix solution: start at the semi-infinite innermost
    layer and work outward toward the skin.
    """
    layers = phantom.stack()
    z_in = _eta(layers[-1][0], f)
    for mat, z0, z1 in reversed(layers[:-1]):
        eta = _eta(mat, f)
        t = np.tan(_k(mat, f) * (z1 - z0))
        z_in = eta * (z_in + 1j * eta * t) / (eta + 1j * z_in * t)
    return (z_in - ETA0) / (z_in + ETA0)


def _ray(phantom, f, x_ant, z_ant, x_t, z_t):
    """Two-way complex phase and interface transmission along a straight ray."""
    dx, dz = x_t - x_ant, z_t - z_ant
    r = float(np.hypot(dx, dz))
    cos_th = abs(dz) / r if r > 0 else 1.0

    phase = 2 * _k("free_space", f) * (-z_ant) / cos_th      # air standoff
    trans = np.ones(np.shape(f), dtype=complex)
    prev = "free_space"
    for mat, z0, z1 in phantom.stack():
        if z0 >= z_t:
            break
        phase = phase + 2 * _k(mat, f) * ((min(z1, z_t) - z0) / cos_th)
        e0, e1 = _eta(prev, f), _eta(mat, f)
        trans = trans * (2 * e1 / (e0 + e1)) * (2 * e0 / (e0 + e1))
        prev = mat
    return r, phase, trans


def gap_reflection(host: str, fill: str, width: float,
                   f: np.ndarray) -> np.ndarray:
    """Reflection of a fluid-filled gap of given width inside a host material.

    Exact one-dimensional slab result, including the internal multiple
    reflections and the loss of the filling:

        Gamma_slab = G (1 - P^2) / (1 - G^2 P^2),   P = exp(-j k_fill w)

    This replaces what was a free amplitude constant. It matters because the
    response is *not* linear in width: blood in bone is a quarter-wave resonator
    near 1.1 mm at 10 GHz, so detectability rises and then falls with kerf at
    any single frequency. Integrating over 3-11 GHz smears that resonance, and
    how much it smears is a result rather than an assumption.
    """
    n_h = np.sqrt(T.get(host).eps_complex(f))
    n_f = np.sqrt(T.get(fill).eps_complex(f))
    g = (n_h - n_f) / (n_h + n_f)
    pp = np.exp(-2j * _k(fill, f) * width)
    return g * (1.0 - pp) / (1.0 - g ** 2 * pp)


class AnalyticForward:
    """Layered-background plus Born-scatterer B-scan generator."""

    def __init__(self, antenna_reflection: float = 0.25,
                 antenna_delay: float = 80e-12,
                 aperture: float = 0.010):
        self.antenna_reflection = antenna_reflection
        self.antenna_delay = antenna_delay
        # Effective aperture over which the gap intercepts the beam. Converts
        # the one-dimensional slab reflection into a finite scatterer.
        self.aperture = aperture

    def empty_scene(self, phantom, f, x,
                    standoff: float | None = None) -> ScanData:
        """The reference scan of proposal 2.5 step 3.

        Antenna and stage in place, no limb present. Subtracting it removes the
        antenna self-reflection, leaving the layered stack and the target.
        """
        f = np.asarray(f, float)
        x = np.asarray(x, float)
        z_ant = -(standoff if standoff is not None else phantom.standoff)
        s_ant = self.antenna_reflection * np.exp(
            -2j * np.pi * f * self.antenna_delay)
        return ScanData(f, x, np.repeat(s_ant[:, None], x.size, axis=1), z_ant,
                        meta={"model": "analytic", "empty_scene": True})

    def scan(self, phantom, f, x, standoff=None, x_nominal=None) -> ScanData:
        """Generate a B-scan.

        x          antenna positions actually visited (may carry stage jitter)
        standoff   scalar, or one value per position for a drifting standoff
        x_nominal  positions the instrument *believes* it visited. Defaults to
                   x. When they differ, the returned ScanData carries the
                   nominal ones - which is what a real instrument records, and
                   what migration will later assume.
        """
        f = np.asarray(f, float)
        x = np.asarray(x, float)
        x_rec = x if x_nominal is None else np.asarray(x_nominal, float)
        so = phantom.standoff if standoff is None else standoff
        so = np.broadcast_to(np.asarray(so, float), x.shape)

        s_ant = self.antenna_reflection * np.exp(
            -2j * np.pi * f * self.antenna_delay)
        gamma = stack_reflection(phantom, f)
        k_air = _k("free_space", f)

        s11 = np.empty((f.size, x.size), dtype=complex)
        for n in range(x.size):
            s11[:, n] = s_ant + gamma * np.exp(-2j * k_air * so[n])

        for x_t, z_t, width, fill, host in phantom.scatterers():
            amp = gap_reflection(host, fill, width, f) * self.aperture
            for n, x_n in enumerate(x):
                r, phase, trans = _ray(phantom, f, x_n, -so[n], x_t, z_t)
                # Two-way cylindrical spreading, matching a 2D solver.
                s11[:, n] += (amp * trans * np.exp(-1j * phase)
                              / max(r, 1e-6))

        return ScanData(f, x_rec, s11, -float(np.mean(so)),
                        meta={"model": "analytic",
                              "phantom": phantom.describe()})
