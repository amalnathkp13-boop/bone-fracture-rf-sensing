"""Four-Cole-Cole parameters for the tissues in the Path A forward model.

Provenance matters here and is recorded per tissue, because these numbers
propagate into every result the project produces.

GABRIEL96
    Gabriel S, Lau R W and Gabriel C 1996, Phys. Med. Biol. 41 2271-2293,
    table 1. Transcribed verbatim from the paper.

IFAC
    Andreuccetti D, Fossi R and Petrucci C, "An Internet resource for the
    calculation of the dielectric properties of body tissues", IFAC-CNR,
    Florence. Implements the wider Gabriel AFOSR-TR-96 compilation. Used only
    for bone marrow, which does not appear in table 1 of the paper above.

Units in the source tables are ps / ns / us / ms for tau1..tau4; everything
here is converted to seconds at the point of definition.
"""
from __future__ import annotations

from scipy.optimize import brentq

from .colecole import ColeCole, Pole

ps, ns, us, ms = 1e-12, 1e-9, 1e-6, 1e-3

# --------------------------------------------------------------------------
# Tissues of the forearm / lower leg relevant to a superficial long bone.
# --------------------------------------------------------------------------

CORTICAL_BONE = ColeCole(
    name="cortical_bone", eps_inf=2.5, sigma_i=0.0200, source="GABRIEL96",
    poles=(Pole(10.0, 13.26 * ps, 0.20),
           Pole(180.0, 79.58 * ns, 0.20),
           Pole(5.0e3, 159.15 * us, 0.20),
           Pole(1.0e5, 15.915 * ms, 0.00)))

CANCELLOUS_BONE = ColeCole(
    name="cancellous_bone", eps_inf=2.5, sigma_i=0.0700, source="GABRIEL96",
    poles=(Pole(18.0, 13.26 * ps, 0.22),
           Pole(300.0, 79.58 * ns, 0.25),
           Pole(2.0e4, 159.15 * us, 0.20),
           Pole(2.0e7, 15.915 * ms, 0.00)))

# Yellow (fatty) marrow. Not in Gabriel 1996 table 1; taken from IFAC.
MARROW = ColeCole(
    name="marrow", eps_inf=2.5, sigma_i=0.001, source="IFAC",
    poles=(Pole(3.0, 7.958 * ps, 0.20),
           Pole(25.0, 15.915 * ns, 0.10),
           Pole(5.0e3, 1591.549 * us, 0.10),
           Pole(2.0e6, 15.915 * ms, 0.10)))

MARROW_INFILTRATED = ColeCole(
    name="marrow_infiltrated", eps_inf=2.5, sigma_i=0.100, source="IFAC",
    poles=(Pole(9.0, 14.469 * ps, 0.20),
           Pole(80.0, 15.915 * ns, 0.10),
           Pole(1.0e4, 1591.549 * us, 0.10),
           Pole(2.0e6, 15.915 * ms, 0.10)))

# The fracture gap. Section 2.1 of the proposal is explicit that a fracture is
# not a void: within hours it fills with haematoma, and blood against cortical
# bone is the dielectric contrast the whole method depends on.
BLOOD = ColeCole(
    name="blood", eps_inf=4.0, sigma_i=0.7000, source="GABRIEL96",
    poles=(Pole(56.0, 8.38 * ps, 0.10),
           Pole(5200.0, 132.63 * ns, 0.10)))

MUSCLE = ColeCole(
    name="muscle", eps_inf=4.0, sigma_i=0.2000, source="GABRIEL96",
    poles=(Pole(50.0, 7.23 * ps, 0.10),
           Pole(7000.0, 353.68 * ns, 0.10),
           Pole(1.2e6, 318.31 * us, 0.10),
           Pole(2.5e7, 2.274 * ms, 0.00)))

SKIN_DRY = ColeCole(
    name="skin_dry", eps_inf=4.0, sigma_i=0.0002, source="GABRIEL96",
    poles=(Pole(32.0, 7.23 * ps, 0.00),
           Pole(1100.0, 32.48 * ns, 0.20)))

SKIN_WET = ColeCole(
    name="skin_wet", eps_inf=4.0, sigma_i=0.0004, source="GABRIEL96",
    poles=(Pole(39.0, 7.96 * ps, 0.10),
           Pole(280.0, 79.58 * ns, 0.00),
           Pole(3.0e4, 1.59 * us, 0.16),
           Pole(3.0e4, 1.592 * ms, 0.20)))

# Subcutaneous fat over the tibia is low-water: "not infiltrated".
FAT = ColeCole(
    name="fat", eps_inf=2.5, sigma_i=0.0100, source="GABRIEL96",
    poles=(Pole(3.0, 7.96 * ps, 0.20),
           Pole(15.0, 15.92 * ns, 0.10),
           Pole(3.3e4, 159.15 * us, 0.05),
           Pole(1.0e7, 7.958 * ms, 0.01)))

FAT_INFILTRATED = ColeCole(
    name="fat_infiltrated", eps_inf=2.5, sigma_i=0.0350, source="GABRIEL96",
    poles=(Pole(9.0, 7.96 * ps, 0.20),
           Pole(35.0, 15.92 * ns, 0.10),
           Pole(3.3e4, 159.15 * us, 0.05),
           Pole(1.0e7, 15.915 * ms, 0.01)))


def hydrate(base: ColeCole, target_eps: float, f_ref: float,
            name: str | None = None) -> ColeCole:
    """Scale a material's water-relaxation pole to hit target_eps at f_ref.

    Gabriel's parametrisation describes bone of low water content - the paper
    itself notes water content below 20% for cortical bone. Fresh, fully
    hydrated bone has a markedly higher permittivity, and section 4.1 of the
    proposal insists specimens be kept hydrated for exactly this reason.

    This scales the first (picosecond, water) dispersion only, leaving the
    lower-frequency structural dispersions untouched, and solves for the scale
    factor that reproduces a measured permittivity. It is a calibrated stand-in,
    not an independently measured parametrisation, and must be reported as such.
    """
    p0 = base.poles[0]
    rest = base.poles[1:]

    def err(scale: float) -> float:
        trial = ColeCole(base.name, base.eps_inf, base.sigma_i,
                         (Pole(p0.d_eps * scale, p0.tau, p0.alpha),) + rest)
        return float(trial.eps_real(f_ref)) - target_eps

    scale = brentq(err, 0.1, 50.0)
    return ColeCole(name or f"{base.name}_wet", base.eps_inf, base.sigma_i,
                    (Pole(p0.d_eps * scale, p0.tau, p0.alpha),) + rest,
                    source=f"{base.source} + hydration scaling "
                           f"(x{scale:.2f} on pole 1 -> eps_r "
                           f"{target_eps:g} at {f_ref/1e9:g} GHz)")


# Section 2.1 of the proposal quotes cortical bone at eps_r 11-12 near 10 GHz.
# Gabriel's parametrisation gives 8.1. The gap is hydration, and it is a
# first-order sensitivity for this project: it sets the bone/blood contrast and
# the refraction of the imaging path. Both are carried, and Stage 7 reports the
# matrix under each.
CORTICAL_BONE_WET = hydrate(CORTICAL_BONE, target_eps=11.5, f_ref=10e9,
                            name="cortical_bone_wet")


TISSUES: dict[str, ColeCole] = {
    t.name: t for t in (
        CORTICAL_BONE, CORTICAL_BONE_WET, CANCELLOUS_BONE, MARROW, MARROW_INFILTRATED, BLOOD,
        MUSCLE, SKIN_DRY, SKIN_WET, FAT, FAT_INFILTRATED)
}

# Layers of the forward model, from the antenna inward (proposal section 4.3).
PHANTOM_STACK = ("skin_dry", "fat", "muscle", "cortical_bone", "marrow")


def get(name: str) -> ColeCole:
    try:
        return TISSUES[name]
    except KeyError:
        raise KeyError(f"unknown tissue {name!r}; "
                       f"available: {sorted(TISSUES)}") from None
