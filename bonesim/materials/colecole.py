"""Gabriel four-term Cole-Cole dielectric model.

Implements equation (4) of Gabriel S, Lau R W and Gabriel C 1996, "The
dielectric properties of biological tissues: III. Parametric models for the
dielectric spectrum of tissues", Phys. Med. Biol. 41 2271-2293:

    eps*(w) = eps_inf + sum_n  d_eps_n / (1 + (j w tau_n)^(1 - alpha_n))
                     + sigma_i / (j w eps_0)

with the engineering sign convention eps* = eps' - j eps''.

The proposal (section 2.1) is explicit that table values must not be used for
simulation and that this parametrisation is required instead, because tissue
permittivity is strongly dispersive across the 3-11 GHz working band.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

EPS0 = 8.8541878128e-12   # F/m, CODATA 2018
C0 = 299_792_458.0        # m/s


@dataclass(frozen=True)
class Pole:
    """One Cole-Cole dispersion term."""
    d_eps: float          # magnitude of the dispersion
    tau: float            # relaxation time, seconds
    alpha: float = 0.0    # broadening, 0 <= alpha < 1 (0 gives pure Debye)

    def __post_init__(self) -> None:
        if self.d_eps < 0:
            raise ValueError(f"d_eps must be non-negative, got {self.d_eps}")
        if self.tau <= 0:
            raise ValueError(f"tau must be positive, got {self.tau}")
        if not 0.0 <= self.alpha < 1.0:
            raise ValueError(f"alpha must be in [0, 1), got {self.alpha}")


@dataclass(frozen=True)
class ColeCole:
    """A dispersive material defined by up to four Cole-Cole terms."""
    name: str
    eps_inf: float
    sigma_i: float                       # static ionic conductivity, S/m
    poles: tuple[Pole, ...] = field(default_factory=tuple)
    source: str = ""                     # provenance, printed in reports

    def eps_complex(self, f):
        """Complex relative permittivity eps' - j eps'' at frequency f (Hz)."""
        f = np.asarray(f, dtype=float)
        w = 2.0 * np.pi * f
        eps = np.full(f.shape, self.eps_inf, dtype=complex)
        for p in self.poles:
            if p.d_eps == 0.0:
                continue
            # Principal branch is correct here: arg(j w tau) = +pi/2 for w > 0.
            eps += p.d_eps / (1.0 + (1j * w * p.tau) ** (1.0 - p.alpha))
        # Ionic term. 1/(j w eps0) = -j/(w eps0), so this adds to eps''.
        with np.errstate(divide="ignore", invalid="ignore"):
            eps = eps + self.sigma_i / (1j * w * EPS0)
        return eps

    def eps_real(self, f):
        """Real relative permittivity eps'."""
        return self.eps_complex(f).real

    def eps_imag(self, f):
        """Loss factor eps'' (positive)."""
        return -self.eps_complex(f).imag

    def sigma_eff(self, f):
        """Effective conductivity (S/m), sigma = w eps0 eps''.

        Includes both the ionic term and relaxation losses, which is what an
        open-ended coaxial probe or a VNA actually sees.
        """
        f = np.asarray(f, dtype=float)
        return 2.0 * np.pi * f * EPS0 * self.eps_imag(f)

    def loss_tangent(self, f):
        return self.eps_imag(f) / self.eps_real(f)

    def wavelength(self, f):
        """Wavelength (m) in the lossy medium."""
        return C0 / (np.asarray(f, dtype=float) * self.refractive_index(f))

    def refractive_index(self, f):
        """Real part of sqrt(eps*), i.e. the phase index."""
        return np.sqrt(self.eps_complex(f)).real

    def attenuation(self, f):
        """Field attenuation constant alpha (Np/m).

        With eps* = eps' - j eps'', sqrt(eps*) = n - j kappa, so the propagation
        constant is gamma = j w sqrt(eps*) / c = w kappa / c + j w n / c.
        """
        f = np.asarray(f, dtype=float)
        w = 2.0 * np.pi * f
        kappa = -np.sqrt(self.eps_complex(f)).imag
        return w * kappa / C0

    def penetration_depth(self, f):
        """Conventional penetration depth delta = 1 / alpha (m).

        The distance over which the *field* falls to 1/e. This is the standard
        definition in the EM literature and the one that reproduces the values
        tabulated in section 1.1 of the proposal.

        Note that the proposal labels that table "one-way 1/e power decay
        distance", which is a different quantity - see power_penetration_depth
        below, which is half this. The tabulated numbers are field depths, so
        the label is wrong by a factor of two. The conclusion drawn from the
        table is unaffected: 0.4 mm or 0.2 mm at 60 GHz is hopeless either way
        against 3-8 mm of overlay.
        """
        return 1.0 / self.attenuation(f)

    def power_penetration_depth(self, f):
        """Distance over which transmitted *power* falls to 1/e (m).

        Power goes as exp(-2 alpha z), so this is half penetration_depth.
        """
        return 1.0 / (2.0 * self.attenuation(f))

    def __str__(self) -> str:
        return (f"{self.name} (eps_inf={self.eps_inf:g}, "
                f"sigma_i={self.sigma_i:g} S/m, {len(self.poles)} poles)")
