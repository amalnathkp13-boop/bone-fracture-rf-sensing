"""Kirchhoff migration / delay-and-sum focusing (proposal 2.5 step 6).

For every pixel in the imaging plane, coherently sum the contribution from every
scan position and every frequency, compensating the round-trip phase:

    I(x, z) = sum_n sum_f  M(f, x_n) exp( +j 2 k(f) R_n(x, z) )

The proposal writes this with a single effective permittivity for the whole
path. Here the known air standoff is separated from the unknown tissue path,
because the standoff is a mechanical quantity the instrument controls to better
than 0.5 mm (proposal 2.2) - there is no reason to make the autofocus solve for
something already known, and folding it in biases eps_avg.

The reconstruction is deliberately blind: it receives a permittivity scalar and
nothing else. It is never told the layer structure, the bone depth, or where the
fracture is. That is what keeps the gprMax results free of inverse crime.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..forward.base import ScanData

C0 = 299_792_458.0


@dataclass
class Image:
    """A migrated image on a regular grid."""
    x: np.ndarray            # (nx,) m
    z: np.ndarray            # (nz,) m
    data: np.ndarray         # (nz, nx) complex
    eps_avg: float

    @property
    def envelope(self) -> np.ndarray:
        return np.abs(self.data)

    def normalised_db(self, floor: float = -40.0) -> np.ndarray:
        env = self.envelope
        peak = env.max()
        if peak <= 0:
            return np.full(env.shape, floor)
        with np.errstate(divide="ignore"):
            db = 20 * np.log10(env / peak)
        return np.maximum(db, floor)

    def _window(self, z_window):
        """Rows inside a fixed depth window, or all rows if none is given.

        Focus metrics MUST be restricted to a fixed physical window. Raising
        eps_avg lowers the assumed velocity, which compresses the whole image
        toward the surface; energy then concentrates into fewer pixels and any
        whole-image sharpness metric improves monotonically. The optimiser then
        rails against its upper bound and reports compression as focus. This
        was observed directly: entropy fell and peak-to-average rose without a
        turning point across eps_avg 4 to 60. See docs/stage3-findings.md.
        """
        if z_window is None:
            return slice(None)
        rows = (self.z >= z_window[0]) & (self.z <= z_window[1])
        if not rows.any():
            raise ValueError(f"depth window {z_window} is empty for this grid")
        return rows

    def entropy(self, z_window=None) -> float:
        """Image entropy of the normalised intensity; lower is better focused."""
        p = self.envelope[self._window(z_window)] ** 2
        total = p.sum()
        if total <= 0:
            return np.inf
        p = (p / total).ravel()
        p = p[p > 0]
        return float(-(p * np.log(p)).sum())

    def peak_to_average(self, z_window=None) -> float:
        env = self.envelope[self._window(z_window)]
        return float(env.max() / env.mean()) if env.mean() > 0 else 0.0


def migrate(data: ScanData, eps_avg: float,
            x_grid: np.ndarray | None = None,
            z_grid: np.ndarray | None = None,
            n_fft: int = 16384) -> Image:
    """Focus a B-scan into an image assuming a homogeneous tissue permittivity.

    Implemented in the time domain. The direct double sum over frequency and
    scan position costs one complex exponential per (pixel, position,
    frequency) - hundreds of millions per image, which makes autofocus
    unaffordable. Because the frequency samples are uniform, the inner sum over
    frequency is a DFT evaluated at an arbitrary delay:

        sum_m M[m,n] exp(j 2 pi (f0 + m df) tau)
            = exp(j 2 pi f0 tau) * sum_m M[m,n] exp(j 2 pi m df tau)

    so each scan position is inverse-transformed once onto a finely padded time
    grid and then sampled at the delay each pixel requires. This turns an
    O(pixels x positions x frequencies) exponential evaluation into an
    O(positions) FFT plus O(pixels x positions) interpolation, and is how
    delay-and-sum is done in practice.

    The imaging grid is independent of the FDTD grid that generated the data,
    which is one of the deliberate mismatches between forward and inverse model.
    """
    if eps_avg <= 0:
        raise ValueError("eps_avg must be positive")
    if x_grid is None:
        x_grid = np.linspace(data.x[0], data.x[-1], 2 * data.n_scan)
    if z_grid is None:
        z_grid = np.linspace(0.0, 0.030, 151)

    f = data.f
    df = float(f[1] - f[0])
    if not np.allclose(np.diff(f), df, rtol=1e-6):
        raise ValueError("time-domain migration requires uniform frequency "
                         "spacing")
    f0 = float(f[0])
    z_ant = data.z_antenna
    n_t = np.sqrt(eps_avg)

    # Fine time grid on which every trace is resampled.
    dt = 1.0 / (n_fft * df)
    traces = np.fft.ifft(data.s11, n=n_fft, axis=0) * n_fft   # (n_fft, n_scan)

    ZZ = z_grid[:, None]
    XX = x_grid[None, :]
    img = np.zeros((z_grid.size, x_grid.size), dtype=complex)

    dz = ZZ - z_ant                                   # antenna to pixel
    frac_air = np.clip((-z_ant) / dz, 0.0, 1.0)

    for n, x_n in enumerate(data.x):
        r = np.sqrt((XX - x_n) ** 2 + dz ** 2)
        r_air = r * frac_air
        tau = 2.0 * (r_air + n_t * (r - r_air)) / C0

        idx = tau / dt
        i0 = np.floor(idx).astype(np.intp)
        w = idx - i0
        np.clip(i0, 0, n_fft - 2, out=i0)
        col = traces[:, n]
        g = col[i0] * (1.0 - w) + col[i0 + 1] * w      # linear interpolation
        img += g * np.exp(2j * np.pi * f0 * tau)

    return Image(x_grid, z_grid, img, eps_avg)
