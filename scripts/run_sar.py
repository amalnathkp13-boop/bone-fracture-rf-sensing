"""RF exposure assessment for the scanning geometry.

    python scripts/run_sar.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bonesim.antenna.vivaldi import uwb_3_11
from bonesim.geometry.phantom import Phantom
from bonesim.safety import sar as S

RULE = "=" * 78


def main() -> None:
    ph = Phantom()
    ant = uwb_3_11()

    # Illuminated area. The limb sits 12 mm from the mouth, deep in the near
    # field, so the aperture footprint is the sensible estimate rather than a
    # far-field beamwidth. The conservative case squeezes the same power into
    # a half-wavelength spot at the top of the band, which is about the
    # smallest area the physics allows and so the highest SAR.
    a_aperture = (ant.aperture * 1e-3) ** 2
    a_tight = (0.5 * 299_792_458.0 / 11e9) ** 2

    print(RULE)
    print("RF exposure assessment")
    print(RULE)
    print(f"  geometry     forearm stack, {ph.standoff*1e3:.0f} mm standoff")
    print(f"  aperture     {ant.aperture:.0f} mm mouth "
          f"-> {a_aperture*1e4:.1f} cm^2 footprint")
    print(f"  tight spot   half wavelength at 11 GHz "
          f"-> {a_tight*1e4:.2f} cm^2")
    print()
    print("  Guidelines split this band in two, so both quantities are needed:")
    print("    3.0-6.0 GHz    SAR, W/kg, averaged over 10 g")
    print("    6.0-11.0 GHz   absorbed power density, W/m^2, over 4 cm^2")

    # ---------------------------------------------------------------- SAR ---
    f_sar = np.linspace(3e9, S.SAR_MAX_F, 61)
    print()
    print(RULE)
    print("1. SAR, 3.0-6.0 GHz")
    print(RULE)
    print(f"  {'scenario':<20}{'P_tx':>9}{'bound':>10}{'aperture':>11}"
          f"{'tight':>10}")
    print(f"  {'':<20}{'dBm':>9}{'W/kg':>10}{'W/kg':>11}{'W/kg':>10}")
    rows = []
    for sc in S.SCENARIOS:
        # Only the part of the scenario's power that falls in the SAR band.
        frac = ((min(sc.f_hi, S.SAR_MAX_F) - max(sc.f_lo, 3e9))
                / (sc.f_hi - sc.f_lo))
        p_band = sc.p_tx_w * max(frac, 0.0)
        b = S.bound_10g(p_band)
        z, sar_a, _ = S.profile(ph, f_sar, p_band, a_aperture)
        _, sar_t, _ = S.profile(ph, f_sar, p_band, a_tight)
        ga = S.averaged_10g(z, sar_a)
        gt = S.averaged_10g(z, sar_t)
        o1 = S.averaged_1g(z, sar_t)          # for the 1 g limit only
        rows.append((sc, b, ga, gt, o1, z, sar_a))
        print(f"  {sc.name:<20}{sc.dbm:>9.1f}{b:>10.3f}{ga:>11.4f}"
              f"{gt:>10.3f}")

    print()
    print("  bound    = every watt into 10 g. No geometry, no tissue model.")
    print("             Nothing below it can be exceeded by the ones above.")
    print("  aperture = 10 g averaged, power spread over the antenna mouth.")
    print("  tight    = 10 g averaged, power squeezed into a half-wave spot.")

    print()
    worst10 = max(r[3] for r in rows)
    worst1 = max(r[4] for r in rows)
    print(f"  Each limit is checked against a value averaged over ITS OWN mass.")
    print(f"  worst 10 g {worst10:.3f} W/kg     worst 1 g {worst1:.3f} W/kg")
    print()
    print(f"  {'limit':<32}{'W/kg':>8}{'measured':>10}   verdict")
    for k, v in S.LIMITS.items():
        got = worst1 if "1g" in k else worst10
        margin = v / got if got > 0 else float("inf")
        verdict = "PASS" if got < v else "FAIL"
        print(f"  {k:<32}{v:>8.1f}{got:>10.3f}   {verdict}, "
              f"{margin:.1f}x margin")

    # ------------------------------------------- absorbed power density ---
    f_hi = np.linspace(S.SAR_MAX_F, 11e9, 51)
    print()
    print(RULE)
    print("2. Absorbed power density, 6.0-11.0 GHz")
    print(RULE)
    print(f"  {'scenario':<20}{'aperture':>12}{'tight':>12}")
    print(f"  {'':<20}{'W/m^2':>12}{'W/m^2':>12}")
    worst_sab = 0.0
    for sc in S.SCENARIOS:
        frac = ((sc.f_hi - max(sc.f_lo, S.SAR_MAX_F)) / (sc.f_hi - sc.f_lo))
        p_band = sc.p_tx_w * max(frac, 0.0)
        sa = S.absorbed_power_density(ph, f_hi, p_band, a_aperture)
        st = S.absorbed_power_density(ph, f_hi, p_band, a_tight)
        worst_sab = max(worst_sab, st)
        print(f"  {sc.name:<20}{sa:>12.3f}{st:>12.3f}")
    print()
    for k, v in S.SAB_LIMITS.items():
        verdict = "PASS" if worst_sab < v else "FAIL"
        print(f"  {k:<32}{v:>8.1f} W/m^2   {verdict}, "
              f"{v/worst_sab:.1f}x margin")

    # ------------------------------------------------------ where it lands --
    z, sar, _ = S.profile(ph, f_sar, S.SCENARIOS[-1].p_tx_w * 0.375, a_tight)
    print()
    print(RULE)
    print("3. Where the energy is absorbed (worst scenario, tight spot)")
    print(RULE)
    print(f"  {'layer':<16}{'depth':>14}{'peak SAR':>12}{'share':>9}")
    dz = z[1] - z[0]
    total = float((sar * dz).sum())
    for mat, z0, z1 in ph.stack():
        m = (z >= z0) & (z < z1)
        if not m.any():
            continue
        share = float((sar[m] * dz).sum()) / total * 100
        print(f"  {mat:<16}{z0*1e3:>6.1f}-{z1*1e3:<7.1f}{sar[m].max():>12.4f}"
              f"{share:>8.1f}%")
    print()
    print(f"  peak point SAR {sar.max():.4f} W/kg at "
          f"{z[int(np.argmax(sar))]*1e3:.1f} mm depth")
    print("  Point SAR always exceeds the 10 g average, so a point value under")
    print("  the limit means the averaged value is too.")


if __name__ == "__main__":
    main()
