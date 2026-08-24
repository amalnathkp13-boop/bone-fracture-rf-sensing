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
