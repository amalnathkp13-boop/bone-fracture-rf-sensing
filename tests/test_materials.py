"""Regression tests for the Stage 1 tissue and Debye machinery."""
from __future__ import annotations

import numpy as np
import pytest

from bonesim.materials import tissues as T
from bonesim.materials.colecole import ColeCole, Pole
from bonesim.materials.debye import fit_debye

GHZ = 1e9
BAND = (3 * GHZ, 11 * GHZ)


# --- Cole-Cole model ------------------------------------------------------

@pytest.mark.parametrize("name,eps,sigma", [
    ("blood", 45.1, 13.1),
    ("muscle", 42.8, 10.6),
    ("skin_dry", 31.3, 8.0),
    ("fat", 4.6, 0.59),
])
def test_matches_published_values_at_10ghz(name, eps, sigma):
    """Section 2.1 of the proposal, which these reproduce to a few percent."""
    t = T.get(name)
    assert float(t.eps_real(10 * GHZ)) == pytest.approx(eps, rel=0.03)
    assert float(t.sigma_eff(10 * GHZ)) == pytest.approx(sigma, rel=0.05)


def test_penetration_depth_at_60ghz_kills_bone_imaging():
    """The load-bearing claim of section 1: 60 GHz cannot reach bone."""
    d = float(T.MUSCLE.penetration_depth(60 * GHZ))
    assert d < 1e-3, "60 GHz should penetrate well under a millimetre"
    # Round trip through even 3 mm of overlay, in field amplitude.
    assert 20 * np.log10(np.exp(-2 * 3e-3 / d)) < -50


def test_power_depth_is_half_field_depth():
    f = np.array([3e9, 10e9])
    assert np.allclose(T.MUSCLE.power_penetration_depth(f),
                       T.MUSCLE.penetration_depth(f) / 2)


def test_permittivity_decreases_with_frequency():
    """Normal dispersion: eps' must fall monotonically across the band."""
    f = np.linspace(*BAND, 50)
    for t in (T.MUSCLE, T.BLOOD, T.CORTICAL_BONE, T.FAT):
        assert np.all(np.diff(t.eps_real(f)) < 0), t.name


def test_blood_bone_contrast_is_large():
    """The detection mechanism (section 2.1)."""
    f = 8.3 * GHZ
    ratio = float(T.BLOOD.eps_real(f)) / float(T.CORTICAL_BONE.eps_real(f))
    assert ratio > 4.0


def test_hydration_scaling_hits_its_target():
    assert float(T.CORTICAL_BONE_WET.eps_real(10 * GHZ)) == pytest.approx(11.5,
                                                                          rel=1e-3)
    assert (float(T.CORTICAL_BONE_WET.eps_real(10 * GHZ))
            > float(T.CORTICAL_BONE.eps_real(10 * GHZ)))


def test_pole_validation():
    with pytest.raises(ValueError):
        Pole(-1.0, 1e-12, 0.0)
    with pytest.raises(ValueError):
        Pole(1.0, -1e-12, 0.0)
    with pytest.raises(ValueError):
        Pole(1.0, 1e-12, 1.0)


def test_zero_alpha_reduces_to_debye():
    """A Cole-Cole pole with alpha = 0 is exactly Debye."""
    cc = ColeCole("x", 2.0, 0.0, (Pole(10.0, 1e-11, 0.0),))
    f = np.linspace(*BAND, 20)
    w = 2 * np.pi * f
    expect = 2.0 + 10.0 / (1 + 1j * w * 1e-11)
    assert np.allclose(cc.eps_complex(f), expect)


# --- Debye fitting --------------------------------------------------------

@pytest.mark.parametrize("name", ["muscle", "fat", "cortical_bone", "blood"])
def test_two_pole_fit_is_accurate(name):
    fit = fit_debye(T.get(name), *BAND, n_poles=2)
    assert fit.max_err_eps < 0.005
    assert fit.max_err_sigma < 0.005


def test_more_poles_never_worse():
    m = T.MUSCLE
    errs = [max(fit_debye(m, *BAND, n_poles=n).max_err_eps for _ in (0,))
            for n in (1, 2, 3)]
    assert errs[1] < errs[0] and errs[2] < errs[1]


def test_gprmax_card_format():
    fit = fit_debye(T.MUSCLE, *BAND, n_poles=2)
    card = fit.gprmax_cards()
    lines = card.splitlines()
    assert lines[0].startswith("#material: ")
    assert lines[0].endswith(" 1 0 muscle")
    assert lines[1].startswith("#add_dispersion_debye: 2 ")
    assert lines[1].endswith(" muscle")
    # eps_inf, sigma, mu_r, sigma_star, name
    assert len(lines[0].split()) == 6
    # N, then (d_eps, tau) per pole, then name
    assert len(lines[1].split()) == 2 + 2 * 2 + 1


def test_card_rejects_tau_below_timestep():
    """gprMax requires tau > dt; the card writer must enforce it."""
    fit = fit_debye(T.MUSCLE, *BAND, n_poles=2)
    assert fit.gprmax_cards(dt=1e-15)
    with pytest.raises(ValueError, match="do not exceed the time step"):
        fit.gprmax_cards(dt=1e-9)


def test_fit_reproduces_colecole_over_band():
    f = np.geomspace(*BAND, 100)
    for name in ("muscle", "cortical_bone", "blood"):
        m = T.get(name)
        fit = fit_debye(m, *BAND, n_poles=2)
        assert np.allclose(fit.eps_real(f), m.eps_real(f), rtol=0.005)
        assert np.allclose(fit.sigma_eff(f), m.sigma_eff(f), rtol=0.005)


def test_all_tissues_have_provenance():
    for name, t in T.TISSUES.items():
        assert t.source, f"{name} has no recorded source"
