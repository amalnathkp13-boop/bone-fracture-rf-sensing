"""Shared container for B-scan data, and the forward-model interface.

The point of this abstraction is that the processing chain cannot tell which
forward model produced its input. The analytic model runs in seconds and is used
to develop and unit-test the pipeline; gprMax runs in hours and produces the
results. Both emit a ScanData, so no processing code changes between them.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass
class ScanData:
    """One monostatic B-scan: complex S11 over frequency and scan position."""
    f: np.ndarray                      # (n_freq,) Hz
    x: np.ndarray                      # (n_scan,) m, positions along bone axis
    s11: np.ndarray                    # (n_freq, n_scan) complex
    z_antenna: float                   # m, negative (above the skin surface)
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.s11.shape != (self.f.size, self.x.size):
            raise ValueError(
                f"s11 shape {self.s11.shape} does not match "
                f"(n_freq, n_scan) = ({self.f.size}, {self.x.size})")

    @property
    def n_freq(self) -> int:
        return self.f.size

    @property
    def n_scan(self) -> int:
        return self.x.size

    @property
    def bandwidth(self) -> float:
        return float(self.f[-1] - self.f[0])

    def range_resolution(self, eps_r: float) -> float:
        """Nominal resolution dR = c / (2 B sqrt(eps_r)), proposal 2.1.

        Reported to preserve the distinction the proposal insists on: a 1 mm
        kerf is far below this, and is *detected* as a scattering centre rather
        than *resolved* as two separated targets.
        """
        return 299_792_458.0 / (2 * self.bandwidth * np.sqrt(eps_r))

    def copy_with(self, s11: np.ndarray, **meta) -> "ScanData":
        return ScanData(self.f, self.x, s11, self.z_antenna,
                        {**self.meta, **meta})

    def save(self, path: str | Path) -> None:
        np.savez_compressed(path, f=self.f, x=self.x, s11=self.s11,
                            z_antenna=self.z_antenna,
                            meta=np.array(repr(self.meta), dtype=object))

    @classmethod
    def load(cls, path: str | Path) -> "ScanData":
        d = np.load(path, allow_pickle=True)
        return cls(d["f"], d["x"], d["s11"], float(d["z_antenna"]),
                   ast.literal_eval(str(d["meta"])))

    def __str__(self) -> str:
        return (f"ScanData: {self.n_freq} freqs "
                f"({self.f[0]/1e9:.1f}-{self.f[-1]/1e9:.1f} GHz), "
                f"{self.n_scan} positions "
                f"({self.x[0]*1e3:.0f}-{self.x[-1]*1e3:.0f} mm)")


class ForwardModel(Protocol):
    """Anything that can produce a B-scan from a phantom."""

    def scan(self, phantom, f, x) -> ScanData: ...
