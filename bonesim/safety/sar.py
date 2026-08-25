"""Specific absorption rate for the limb-scanning geometry.

Proposal 2.2 points a 3-11 GHz antenna at a human forearm at 12 mm standoff.
That needs an exposure assessment, and the assessment has to respect a split
the guidelines make and this project's band straddles:

    100 kHz - 6 GHz     SAR, W/kg, averaged over 10 g       (ICNIRP 2020)
    6 GHz - 300 GHz     absorbed power density, W/m^2,
                        averaged over 4 cm^2

So the lower half of the band is an SAR problem and the upper half is not. A
single "the SAR is X" number for a 3-11 GHz system would be quoting the wrong
quantity for most of the bandwidth.

Method. The limb is a plane-layered lossy stack under normal incidence, which
is the same model the analytic forward solver already uses, so the reflection
comes from `stack_reflection` rather than a second implementation that could
disagree with it. Power crossing into the skin is

    S_in(f) = S0(f) * (1 - |Gamma(f)|^2)

and inside the tissue it decays as exp(-2 alpha z) with the Gabriel four-Cole-
Cole attenuation. The volumetric absorption is the derivative of that,

    p(z) = 2 alpha(z) S(z)        [W/m^3]
    SAR(z) = p(z) / rho(z)        [W/kg]

Limitations, because a safety number nobody can check is worthless:

  - Plane wave at normal incidence. The limb is deep in the antenna's reactive
    near field at 12 mm (far field starts near 1.3 m at 7 GHz), where the field
    is not a plane wave. This is the standard engineering approximation and it
    is the reason the assumption-free bound below is reported alongside.
  - Multiple internal reflections are folded into Gamma but not re-applied
    layer by layer, which slightly overstates deep absorption.
  - No thermal model. SAR is a dose rate, not a temperature.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..forward.analytic import stack_reflection
from ..materials import tissues as T

# Mass density, kg/m^3, IT'IS Foundation tissue property database v4.1.
# Keyed by the material names the phantom emits.
DENSITY = {
    "skin_dry": 1109.0,
    "skin_wet": 1109.0,
    "fat": 911.0,
    "fat_infiltrated": 911.0,
    "muscle": 1090.0,
    "cortical_bone": 1908.0,
    "cortical_bone_wet": 1908.0,
    "cancellous_bone": 1178.0,
    "marrow": 1029.0,
    "marrow_infiltrated": 1029.0,
    "blood": 1050.0,
}

# ICNIRP 2020 and IEEE C95.1-2019. W/kg unless noted.
LIMITS = {
    "icnirp_public_limbs": 4.0,        # local, 10 g, 6 min
    "icnirp_public_head_torso": 2.0,   # local, 10 g, 6 min
    "icnirp_occupational_limbs": 20.0,
    "fcc_ieee_public_1g": 1.6,         # partial body, 1 g - the strictest
}
# Absorbed power density, W/m^2, 4 cm^2, for 6-300 GHz.
SAB_LIMITS = {"icnirp_public": 20.0, "icnirp_occupational": 100.0}

SAR_MAX_F = 6e9        # above this the guidelines stop using SAR
TEN_GRAM_SIDE = 0.0209  # cube of 10 g of muscle at 1090 kg/m^3, metres
ONE_GRAM_SIDE = 0.0097  # cube of 1 g of muscle, for the FCC/IEEE limit


@dataclass
class Exposure:
    """One transmit scenario."""
    name: str
    p_tx_w: float
    f_lo: float
    f_hi: float
    note: str = ""
    adopted: bool = False

    @property
    def dbm(self) -> float:
        return 10 * np.log10(self.p_tx_w * 1e3)


# The three that matter here. FCC Part 15 is what a fielded UWB device may
# emit; the VNA figures are what this experiment would actually use on a bench,
# and they are HIGHER than the regulatory device limit, which is the point.
SCENARIOS = [
    Exposure("FCC Part 15 UWB", 5.56e-4, 3.1e9, 10.6e9,
             "-41.3 dBm/MHz EIRP over 7.5 GHz"),
    Exposure("VNA at 0 dBm", 1.0e-3, 3e9, 11e9,
             "ADOPTED operating point", adopted=True),
    Exposure("VNA at +10 dBm", 1.0e-2, 3e9, 11e9,
             "rejected: only 1.8x on absorbed power density"),
]


def operating_point() -> Exposure:
    """The transmit power this experiment is specified to run at.

    0 dBm rather than the +10 dBm a VNA will happily give you. The first
    assessment showed +10 dBm sitting within 1.8x of the ICNIRP public limit
    on absorbed power density above 6 GHz - the only quantity in the whole
    study that was not comfortable. Dropping 10 dB costs nothing that matters:
    the detector has 40.8 dB of separation and spends none of it here.
    """
    return next(s for s in SCENARIOS if s.adopted)


def _layers(phantom):
    """(material, z0, z1) for the stack, with densities attached."""
    out = []
    for mat, z0, z1 in phantom.stack():
        rho = DENSITY.get(mat)
        if rho is None:
            raise KeyError(f"no density for tissue {mat!r}; add it to DENSITY "
                           f"with a citation rather than guessing")
        out.append((mat, z0, z1, rho))
    return out


def profile(phantom, f: np.ndarray, p_tx_w: float, area_m2: float,
            n_z: int = 2000):
    """SAR against depth, summed over the band.

    f is the frequency grid the transmit power is spread across, flat in power
    spectral density, which is what a UWB emission mask specifies.

    Returns (z, sar, s_in_total) with z in metres, sar in W/kg, and s_in the
    band-summed power density crossing into the skin in W/m^2.
    """
    f = np.atleast_1d(np.asarray(f, float))
    layers = _layers(phantom)
    z_end = layers[-1][2]
    z = np.linspace(0.0, z_end, n_z)
    dz = z[1] - z[0]

    # Per-frequency share of the transmit power, flat PSD.
    s0 = p_tx_w / area_m2 / f.size

    gamma = stack_reflection(phantom, f)
    s_in = s0 * (1.0 - np.abs(gamma) ** 2)          # W/m^2 per frequency

    # alpha and rho as functions of depth, per frequency.
    alpha = np.zeros((f.size, n_z))
    rho = np.zeros(n_z)
    for mat, z0, z1, r in layers:
        m = (z >= z0) & (z < z1)
        if not m.any():
            continue
        alpha[:, m] = T.get(mat).attenuation(f)[:, None]
        rho[m] = r
    rho[rho == 0] = layers[-1][3]

    # Optical depth, then Beer-Lambert decay and its derivative.
    tau = 2.0 * np.cumsum(alpha, axis=1) * dz
    s_z = s_in[:, None] * np.exp(-tau)               # W/m^2 at depth z
    p_vol = 2.0 * alpha * s_z                        # W/m^3
    sar = p_vol.sum(axis=0) / rho                    # summed over the band
    return z, sar, float(s_in.sum())


def averaged_10g(z, sar, side: float = TEN_GRAM_SIDE):
    """Peak SAR averaged over a 10 g cube, approximated in depth only.

    A true 10 g average is a volume average over a cube. Averaging in depth
    alone ignores lateral spreading, which can only DILUTE the average, so this
    is an upper bound on the real 10 g figure - the safe direction to err.
    """
    dz = z[1] - z[0]
    n = max(1, int(round(side / dz)))
    if n >= z.size:
        return float(sar.mean())
    k = np.ones(n) / n
    return float(np.convolve(sar, k, mode="valid").max())


def averaged_1g(z, sar):
    """Peak SAR averaged over 1 g, for the FCC/IEEE limit.

    A 10 g average must NOT be compared against a 1 g limit: the smaller the
    averaging mass the higher the number, so doing so understates exposure
    against the strictest limit in use.
    """
    return averaged_10g(z, sar, side=ONE_GRAM_SIDE)


def bound_10g(p_tx_w: float) -> float:
    """Assumption-free upper bound: ALL transmitted power into 10 g.

    No geometry, no tissue model, no near-field argument - if every watt
    leaving the antenna were deposited in the smallest mass the guideline
    averages over, this is the answer. Nothing the simulation says can exceed
    it, so it is the number to check first.
    """
    return p_tx_w / 0.010


def absorbed_power_density(phantom, f: np.ndarray, p_tx_w: float,
                           area_m2: float) -> float:
    """S_ab in W/m^2, the quantity the guidelines use above 6 GHz."""
    f = np.atleast_1d(np.asarray(f, float))
    s0 = p_tx_w / area_m2 / f.size
    gamma = stack_reflection(phantom, f)
    return float((s0 * (1.0 - np.abs(gamma) ** 2)).sum())
