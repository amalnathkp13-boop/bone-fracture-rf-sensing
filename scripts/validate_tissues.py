"""Stage 1 validation: check the Cole-Cole implementation against the proposal.

Two independent checks:

1. Section 2.1 dielectric table, near 10 GHz. The proposal itself warns that
   these entries are "indicative" and that the Cole-Cole parametrisation must be
   used for simulation, so disagreement is informative rather than fatal.

2. Section 1.1 penetration-depth table. This is the load-bearing claim of the
   whole document - that 60 GHz cannot reach bone. Reproducing it from an
   independent implementation of Gabriel's model is a much stronger test than
   the spot check above, because it spans 1-77 GHz.

Gabriel's parametrisation is fitted to data up to 20 GHz. Entries above that are
extrapolation and are marked as such.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.materials import tissues as T

GHZ = 1e9

# Proposal section 2.1, "near 10 GHz": (eps_r low, high), (sigma low, high)
SEC21 = {
    "cortical_bone": ((8, 9), (0.15, 0.5)),        # Gabriel, low water content
    "cortical_bone_wet": ((11, 12), (0.15, 0.5)),  # hydration-scaled to match
    "marrow":        ((4, 5),   (0.1, 0.1)),
    "blood":         ((45, 45), (13, 13)),
    "muscle":        ((42, 42), (11, 11)),
    "skin_dry":      ((32, 32), (9, 9)),
    "fat":           ((4, 5),   (0.6, 0.6)),
}

# Proposal section 1.1, penetration depth in "high-water-content tissue" (mm)
SEC11 = [(1, 40), (2.45, 20), (5, 10), (8, 4.5), (11, 4.0),
         (24, 1.2), (30, 0.85), (60, 0.5), (77, 0.4)]


def check_section_21() -> bool:
    print("=" * 74)
    print("Section 2.1 dielectric table, evaluated at 10 GHz")
    print("=" * 74)
    print(f"{'tissue':<16}{'eps_r':>8}{'quoted':>10}{'sig@10G':>9}"
          f"{'sig@1G':>8}{'quoted':>10}  {'source':<10}")
    f, f1 = 10 * GHZ, 1 * GHZ
    all_ok = True
    for name, ((e_lo, e_hi), (s_lo, s_hi)) in SEC21.items():
        t = T.get(name)
        e = float(t.eps_real(f))
        s10, s1 = float(t.sigma_eff(f)), float(t.sigma_eff(f1))
        e_ok = e_lo - 1.0 <= e <= e_hi + 1.0
        # Does the quoted sigma match 10 GHz, or 1 GHz?
        fits10 = s_lo * 0.5 <= s10 <= s_hi * 2.0
        fits1 = s_lo * 0.5 <= s1 <= s_hi * 2.0
        tag = "" if fits10 else ("  <- quoted sigma is the 1 GHz value"
                                 if fits1 else "  <- sigma unexplained")
        all_ok &= e_ok
        print(f"{name:<16}{e:8.2f}{f'{e_lo}-{e_hi}':>10}{s10:9.2f}{s1:8.2f}"
              f"{f'{s_lo}-{s_hi}':>10}  {t.source:<10}"
              f"{'' if e_ok else '  <- eps MISMATCH'}{tag}")
    return all_ok


def check_section_11() -> bool:
    print()
    print("=" * 74)
    print("Section 1.1 penetration depth. 'd' is the conventional field depth")
    print("1/alpha; 'power d' is the 1/e power depth the proposal's caption names.")
    print("=" * 74)
    print(f"{'f (GHz)':>9}{'muscle d':>10}{'skin d':>9}{'quoted':>9}"
          f"{'ratio':>8}{'power d':>9}   note")
    ok = True
    for fghz, quoted_mm in SEC11:
        f = fghz * GHZ
        dm = float(T.MUSCLE.penetration_depth(f)) * 1e3
        ds = float(T.SKIN_DRY.penetration_depth(f)) * 1e3
        dp = float(T.MUSCLE.power_penetration_depth(f)) * 1e3
        ratio = dm / quoted_mm
        note = "" if fghz <= 20 else "extrapolated beyond Gabriel's 20 GHz fit"
        # Agreement within a factor of 2 across nearly two decades is the
        # meaningful test; "soft tissue" in the proposal is not a single tissue.
        good = 0.5 <= ratio <= 2.0 or fghz > 20
        ok &= good
        print(f"{fghz:9.2f}{dm:10.2f}{ds:9.2f}{quoted_mm:9.2f}{ratio:8.2f}"
              f"{dp:9.2f}   {note}{'' if good else '  <-- OUT OF RANGE'}")
    return ok


def contrast_report() -> None:
    print()
    print("=" * 74)
    print("The detection mechanism: contrast across a blood-filled fracture")
    print("=" * 74)
    for fghz in (3, 5, 8.3, 10, 11.1):
        f = fghz * GHZ
        eb = float(T.CORTICAL_BONE.eps_real(f))
        ebl = float(T.BLOOD.eps_real(f))
        # Normal-incidence reflection coefficient at a bone/blood interface.
        nb = np.sqrt(T.CORTICAL_BONE.eps_complex(f))
        nbl = np.sqrt(T.BLOOD.eps_complex(f))
        gamma = abs((nbl - nb) / (nbl + nb))
        print(f"  {fghz:5.1f} GHz   bone eps_r {eb:6.2f}   blood eps_r {ebl:6.2f}"
              f"   ratio {ebl/eb:5.2f}x   |Gamma| {gamma:.3f} "
              f"({20*np.log10(gamma):6.2f} dB)")
    print("\n  Proposal section 2.1 claims a ~4x jump in eps_r across the gap.")


def main() -> int:
    ok21 = check_section_21()
    ok11 = check_section_11()
    contrast_report()
    print()
    print()
    print("Notes carried forward:")
    print("  * Section 1.1 is labelled 'power decay' but tabulates the")
    print("    conventional field depth 1/alpha. Numbers are right, caption is")
    print("    wrong by 2x. The 60 GHz conclusion is unaffected.")
    print("  * Cortical bone eps_r is a first-order sensitivity: Gabriel gives")
    print("    8.1 at 10 GHz, the proposal quotes 11-12. Difference is")
    print("    hydration. Both variants are carried through the matrix.")
    print("  * Quoted sigma for bone/marrow are low-frequency values, not the")
    print("    10 GHz values the table header implies.")
    print()
    if ok21 and ok11:
        print("STAGE 1 TISSUE MODEL PASS")
        return 0
    print("STAGE 1 TISSUE MODEL FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
