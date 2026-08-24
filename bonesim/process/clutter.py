"""Clutter removal: empty-scene subtraction and SVD skin-artifact rejection.

Steps 3 and 4 of the processing chain in proposal 2.5. Together these are what
make the fracture visible at all: in a typical scan the fracture response sits
40 dB or more below the skin reflection.
"""
from __future__ import annotations

import numpy as np

from ..forward.base import ScanData


def subtract_empty_scene(data: ScanData, reference: ScanData) -> ScanData:
    """Remove the antenna self-reflection and stage clutter.

    The reference is recorded with the antenna and stage in place but no target
    (proposal 2.5 step 3). Skipping this and then blaming the SVD for a poor
    image is listed in the proposal as a common failure.
    """
    if reference.s11.shape != data.s11.shape:
        raise ValueError("reference scan geometry does not match the data")
    return data.copy_with(data.s11 - reference.s11, empty_scene_subtracted=True)


def svd_spectrum(data: ScanData) -> np.ndarray:
    """Singular values of the [n_freq x n_scan] data matrix."""
    return np.linalg.svd(data.s11, compute_uv=False)


def remove_clutter_svd(data: ScanData, k: int = 2) -> ScanData:
    """Discard the k leading singular components.

    The skin reflection is nearly identical at every scan position, so it is
    highly coherent along the scan axis and concentrates in the first few
    singular components. The fracture response moves with position and survives
    in later ones.

        M = U S V^H,   M_clean = sum_{i=k}^{R} s_i u_i v_i^H

    k is a free parameter. The proposal requires that it be swept, that the
    chosen value be reported, and that sensitivity to it be reported too - so
    `sweep_k` exists alongside this.
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    u, s, vh = np.linalg.svd(data.s11, full_matrices=False)
    if k >= s.size:
        raise ValueError(f"k={k} discards all {s.size} components")
    s = s.copy()
    s[:k] = 0.0
    return data.copy_with((u * s) @ vh, svd_k=k)


def sweep_k(data: ScanData, k_values=(0, 1, 2, 3, 4, 5)):
    """Yield (k, cleaned) for a range of k, for the sensitivity report."""
    for k in k_values:
        yield k, remove_clutter_svd(data, k)


def clutter_energy_fraction(data: ScanData, k: int = 2) -> float:
    """Fraction of total energy carried by the k leading components."""
    s = svd_spectrum(data)
    return float((s[:k] ** 2).sum() / (s ** 2).sum())


def component_extents(data: ScanData, eps_avg: float, n_components: int = 8,
                      z_window=(0.005, 0.035), **migrate_kw):
    """Lateral extent of each singular component once migrated, in metres.

    A flat interface is invariant along the scan axis and migrates to a line
    spanning the whole aperture; a compact target migrates to a spot. Measuring
    that in the image is what separates them - it cannot be done on the raw
    singular vectors, because a target is *seen* from many scan positions even
    though it occupies one, so its right singular vector is not localised
    either. Measured participation ratios of the right singular vectors were
    0.70 of full for the target against 0.64 for an interface: no threshold
    exists there.
    """
    from .migrate import migrate

    u, s, vh = np.linalg.svd(data.s11, full_matrices=False)
    n = min(n_components, s.size)
    out = []
    for i in range(n):
        only = data.copy_with(s[i] * np.outer(u[:, i], vh[i]))
        img = migrate(only, eps_avg, **migrate_kw)
        rows = (img.z >= z_window[0]) & (img.z <= z_window[1])
        prof = img.envelope[rows].max(axis=0)
        if prof.max() <= 0:
            out.append(0.0)
            continue
        width = float((prof > 0.5 * prof.max()).sum() * (img.x[1] - img.x[0]))
        out.append(width)
    return np.array(out), s


def remove_clutter_selective(data: ScanData, eps_avg: float,
                             extent_fraction: float = 0.5,
                             n_components: int = 8, z_window=(0.005, 0.035),
                             **migrate_kw):
    """Discard singular components by character rather than by index.

    Proposal 2.5 says to discard the leading K components. That rule assumes
    clutter occupies the strongest components and signal everything after, and
    on this geometry it is false: the phantom tank has two flat interfaces, its
    surface and its floor, and the target sits *between* them in the spectrum.
    Measured component extents for the brass-rod scan, migrated individually:

        component 0   57 mm   tank surface
        component 1   13 mm   the rod
        component 3   39 mm   tank floor

    So k=1 leaves the floor in and k=2 removes the rod. No value of k works,
    which is why the control image never reached the noise floor.

    This instead migrates each component alone and discards those whose energy
    spans more than `extent_fraction` of the scanned aperture, keeping the
    compact ones whatever their index.

    Returns (cleaned, kept_indices, extents).
    """
    extents, s = component_extents(data, eps_avg, n_components, z_window,
                                   **migrate_kw)
    aperture = float(data.x[-1] - data.x[0])
    keep = [i for i, w in enumerate(extents) if w <= extent_fraction * aperture]

    u, sv, vh = np.linalg.svd(data.s11, full_matrices=False)
    cleaned = np.zeros_like(data.s11)
    for i in keep:
        cleaned += sv[i] * np.outer(u[:, i], vh[i])
    # Everything past the inspected range is kept untouched: it is too weak to
    # be clutter and discarding it would throw away signal.
    for i in range(len(extents), sv.size):
        cleaned += sv[i] * np.outer(u[:, i], vh[i])
    return (data.copy_with(cleaned, svd_selective=True, kept=tuple(keep)),
            keep, extents)
