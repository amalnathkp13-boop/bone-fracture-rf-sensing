"""The complete Path A processing chain, in the order of proposal 2.5.

Encapsulated here so that every script - development, validation, the full
experiment matrix - runs literally the same code, and so the one subtlety below
is stated once rather than rediscovered.

**There is no detectable bone line, and the detector must not need one.**
Section 2.5 step 8 asks for a region of interest "along the detected bone line".
That cannot be done as written: SVD removes the bone reflection along with the
skin, because coherence along the scan axis is exactly what it rejects; and
before SVD the skin is some 20 dB stronger and its point-spread function smears
over the cortex, so a search for the brightest continuous structure returns the
skin. The detector therefore uses a fixed anatomical depth window, identical for
every acquisition, which leaks no ground truth. See bonesim/detect/metrics.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..detect.metrics import Detection, detect_snr
from ..forward.base import ScanData
from .autofocus import FocusResult, autofocus
from .clutter import remove_clutter_svd, subtract_empty_scene
from .migrate import Image, migrate


@dataclass
class Result:
    image: Image                 # migrated, clutter-removed
    detection: Detection
    z_bone: float                # located pre-SVD
    eps_avg: float
    focus: FocusResult | None = None


def process(data: ScanData, reference: ScanData | None = None,
            k: int = 2, eps_avg: float | None = None,
            eps_bounds: tuple[float, float] = (4.0, 20.0),
            **migrate_kw) -> Result:
    """Run the chain. Pass eps_avg to fix it, or leave it None to autofocus."""
    d = subtract_empty_scene(data, reference) if reference is not None else data
    clean = remove_clutter_svd(d, k=k)

    focus = None
    if eps_avg is None:
        focus = autofocus(clean, *eps_bounds, **migrate_kw)
        img, eps_avg = focus.image, focus.eps_avg
    else:
        img = migrate(clean, eps_avg, **migrate_kw)

    det = detect_snr(img, clean)
    return Result(img, det, det.z_peak, eps_avg, focus)


def estimate_clutter_rank(data: ScanData, threshold: float = 1e-9) -> int:
    """Number of singular components above a relative threshold.

    Useful for choosing k honestly. Idealised analytic data has exactly rank-1
    clutter, so k=1 is correct there and k=2 destroys signal.

    Full-wave data was expected to have higher-rank clutter - standoff drift,
    surface curvature, near-field structure - and so to need the "typically
    K = 2 or 3" of proposal 2.5. Measurement contradicted that. On the Stage 3
    gprMax scans the singular spectrum falls away as

        1.00, 1.49e-2, 1.27e-3, 1.41e-4, ...

    and the fracture lives in the *second* component. k=1 localises it to
    0.2 mm; k=2 removes it along with the clutter and the peak jumps 11.7 mm
    off target. The proposal's guidance is wrong for this geometry, and k must
    be chosen from the spectrum rather than from a rule of thumb.
    """
    s = np.linalg.svd(data.s11, compute_uv=False)
    return int(np.sum(s / s[0] > threshold))
