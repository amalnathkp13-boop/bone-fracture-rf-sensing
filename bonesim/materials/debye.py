"""Fit multi-pole Debye models to Cole-Cole tissues, for gprMax.

FDTD cannot implement a Cole-Cole response directly: the fractional exponent
(j w tau)^(1-alpha) has no finite-order rational form, so there is no
recursive-convolution update for it. gprMax therefore offers multi-pole Debye,
and the standard practice is to fit a Debye sum to the Cole-Cole curve over the
band of interest only. Over 3-11 GHz - eight GHz, not eight decades - two or
three poles reproduce the response to well under a percent.

gprMax convention (docs/source/input.rst):

    #material: eps_inf sigma mu_r sigma_star name
    #add_dispersion_debye: N d_eps_1 tau_1 d_eps_2 tau_2 ... name

so the permittivity given to #material is the infinite-frequency value, the
poles supply the dispersion, and sigma is a separate frequency-independent
conductivity. gprMax additionally requires every tau to exceed the time step.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from .colecole import EPS0, ColeCole


@dataclass(frozen=True)
class DebyeFit:
    """A multi-pole Debye approximation valid over [f_lo, f_hi]."""
    name: str
    eps_inf: float
    sigma: float
    d_eps: tuple[float, ...]
    tau: tuple[float, ...]
    f_lo: float
    f_hi: float
    max_err_eps: float      # worst relative error in eps' over the band
    max_err_sigma: float    # worst relative error in sigma over the band
    source: str = ""

    @property
    def n_poles(self) -> int:
        return len(self.d_eps)

    def eps_complex(self, f):
        f = np.asarray(f, dtype=float)
        w = 2.0 * np.pi * f
        eps = np.full(f.shape, self.eps_inf, dtype=complex)
        for de, tau in zip(self.d_eps, self.tau):
            eps += de / (1.0 + 1j * w * tau)
        return eps - 1j * self.sigma / (w * EPS0)

    def eps_real(self, f):
        return self.eps_complex(f).real

    def sigma_eff(self, f):
        f = np.asarray(f, dtype=float)
        return 2.0 * np.pi * f * EPS0 * (-self.eps_complex(f).imag)

    def gprmax_cards(self, dt: float | None = None) -> str:
        """Emit the two gprMax commands defining this material."""
        if dt is not None:
            bad = [t for t in self.tau if t <= dt]
            if bad:
                raise ValueError(
                    f"{self.name}: relaxation times {bad} do not exceed the "
                    f"time step {dt:g} s; gprMax requires tau > dt")
        pairs = " ".join(f"{de:.6g} {tau:.6g}"
                         for de, tau in zip(self.d_eps, self.tau))
        return (f"#material: {self.eps_inf:.6g} {self.sigma:.6g} 1 0 {self.name}\n"
                f"#add_dispersion_debye: {self.n_poles} {pairs} {self.name}")

    def __str__(self) -> str:
        return (f"{self.name:<18} {self.n_poles} poles  "
                f"eps_inf {self.eps_inf:6.3f}  sigma {self.sigma:7.4f}  "
                f"max err: eps {self.max_err_eps:6.3%}  "
                f"sigma {self.max_err_sigma:6.3%}")


def fit_debye(material: ColeCole, f_lo: float, f_hi: float, n_poles: int = 3,
              tau_min: float = 1e-13, n_freq: int = 201,
              n_restarts: int = 12, seed: int = 0) -> DebyeFit:
    """Least-squares fit of an n-pole Debye model over [f_lo, f_hi].

    Residuals are *relative* in both eps' and sigma, so a low-permittivity
    tissue such as fat is fitted as tightly as muscle rather than being
    swamped by it.

    tau_min must exceed the FDTD time step. The default is permissive; pass the
    model's actual dt to keep the optimiser inside the stable region.
    """
    f = np.geomspace(f_lo, f_hi, n_freq)
    eps_t = material.eps_real(f)
    sig_t = material.sigma_eff(f)

    def unpack(x):
        eps_inf, sigma = x[0], x[1]
        de = x[2:2 + n_poles]
        tau = 10.0 ** x[2 + n_poles:]
        return eps_inf, sigma, de, tau

    def residual(x):
        eps_inf, sigma, de, tau = unpack(x)
        w = 2.0 * np.pi * f
        eps = np.full(f.shape, eps_inf, dtype=complex)
        for d, t in zip(de, tau):
            eps += d / (1.0 + 1j * w * t)
        eps_r = eps.real
        sig = w * EPS0 * (-eps.imag) + sigma
        return np.concatenate([(eps_r - eps_t) / eps_t, (sig - sig_t) / sig_t])

    # Relaxation times that matter in-band satisfy w tau ~ 1; seed there.
    lo, hi = np.log10(tau_min), np.log10(1.0 / (2 * np.pi * f_lo) * 100)
    centre = np.log10(1.0 / (2 * np.pi * np.sqrt(f_lo * f_hi)))
    bounds = ([1.0, 0.0] + [0.0] * n_poles + [lo] * n_poles,
              [200.0, 200.0] + [1e4] * n_poles + [hi] * n_poles)

    rng = np.random.default_rng(seed)
    best, best_cost = None, np.inf
    for k in range(n_restarts):
        if k == 0:
            taus = np.linspace(centre - 0.5, centre + 0.5, n_poles)
        else:
            taus = np.sort(rng.uniform(centre - 1.5, centre + 1.5, n_poles))
        x0 = np.concatenate([[max(material.eps_inf, 1.0), 0.0],
                             np.full(n_poles, eps_t.mean() / n_poles),
                             np.clip(taus, lo, hi)])
        try:
            r = least_squares(residual, x0, bounds=bounds, method="trf",
                              max_nfev=20000, ftol=1e-14, xtol=1e-14)
        except ValueError:
            continue
        if r.cost < best_cost:
            best, best_cost = r, r.cost

    if best is None:
        raise RuntimeError(f"Debye fit failed for {material.name}")

    eps_inf, sigma, de, tau = unpack(best.x)
    order = np.argsort(tau)
    de, tau = de[order], tau[order]

    fit = DebyeFit(name=material.name, eps_inf=float(eps_inf),
                   sigma=float(sigma), d_eps=tuple(map(float, de)),
                   tau=tuple(map(float, tau)), f_lo=f_lo, f_hi=f_hi,
                   max_err_eps=0.0, max_err_sigma=0.0, source=material.source)
    e_err = np.abs(fit.eps_real(f) - eps_t) / eps_t
    s_err = np.abs(fit.sigma_eff(f) - sig_t) / sig_t
    return DebyeFit(**{**fit.__dict__,
                       "max_err_eps": float(e_err.max()),
                       "max_err_sigma": float(s_err.max())})
