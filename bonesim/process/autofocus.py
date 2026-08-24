"""Autofocus on the effective tissue permittivity (proposal 2.5 step 6).

The proposal notes that image focus is extremely sensitive to eps_avg and that
choosing it by guesswork and never revisiting it is a common failure. It also
suggests reporting the autofocus step as a contribution, since the published
work it replicates does not do it.

Two focus metrics, both standard in synthetic-aperture imaging:

  entropy         minimise. Sensitive to how concentrated the image is, not
                  just its brightest point, so it is robust when the target is
                  weak. Default, and the only one of the two that works here.
  peak_to_average maximise. Cheaper and more intuitive, but on Stage 3 data it
                  rises monotonically to the bound even with a fixed window,
                  because the single brightest pixel keeps sharpening as the
                  image compresses. Kept for comparison, not for use.

Both metrics MUST be evaluated over a fixed depth window. Without one, raising
eps_avg compresses the image toward the surface, energy concentrates into fewer
pixels, and sharpness improves without limit - the optimiser then rails against
its upper bound and reports compression as focus. With the window, entropy has
a genuine interior minimum. See docs/stage3-findings.md.

The default bounds reach 45 rather than the 20 first tried, because the
recovered eps_avg is an *effective* value: migration assumes straight rays, so
it must absorb the refraction it does not model, and lands well above the
physical layer average of about 15.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from ..forward.base import ScanData
from .migrate import Image, migrate


@dataclass
class FocusResult:
    eps_avg: float
    image: Image
    metric: str
    eps_grid: np.ndarray
    scores: np.ndarray

    def sensitivity(self, tol: float = 0.02) -> tuple[float, float]:
        """Range of eps_avg whose score is within `tol` of the best.

        Reporting this matters more than reporting the optimum: a broad minimum
        means the result does not hinge on the exact value chosen.
        """
        best = self.scores.min()
        span = np.abs(self.scores - best) <= tol * abs(best)
        inside = self.eps_grid[span]
        return float(inside.min()), float(inside.max())


def _score(img: Image, metric: str, z_window=None) -> float:
    """Lower is always better, so both metrics can share one optimiser."""
    if metric == "entropy":
        return img.entropy(z_window)
    if metric == "peak_to_average":
        return -img.peak_to_average(z_window)
    raise ValueError(f"unknown focus metric {metric!r}")


def autofocus(data: ScanData, eps_lo: float = 4.0, eps_hi: float = 45.0,
              n_coarse: int = 33, metric: str = "entropy",
              refine: bool = True, z_window=(0.003, 0.020),
              **migrate_kw) -> FocusResult:
    """Coarse grid search over eps_avg, then a bounded refinement.

    A grid search first because the focus metric is not guaranteed unimodal;
    starting a local optimiser cold can settle into a sidelobe.
    """
    grid = np.linspace(eps_lo, eps_hi, n_coarse)
    scores = np.array([_score(migrate(data, e, **migrate_kw), metric,
                              z_window)
                       for e in grid])
    i = int(np.argmin(scores))
    best_eps = float(grid[i])

    if refine:
        lo = grid[max(i - 1, 0)]
        hi = grid[min(i + 1, grid.size - 1)]
        r = minimize_scalar(
            lambda e: _score(migrate(data, float(e), **migrate_kw), metric,
                             z_window),
            bounds=(lo, hi), method="bounded",
            options={"xatol": 1e-3})
        if r.fun <= scores[i]:
            best_eps = float(r.x)

    return FocusResult(best_eps, migrate(data, best_eps, **migrate_kw),
                       metric, grid, scores)
