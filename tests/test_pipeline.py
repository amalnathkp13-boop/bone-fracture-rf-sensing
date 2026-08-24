"""Regression tests for the Stage 2 forward model and processing chain."""
from __future__ import annotations

import numpy as np
import pytest

from bonesim.detect.metrics import detect_snr, estimate_sample_noise
from bonesim.forward.analytic import AnalyticForward, gap_reflection
from bonesim.forward.base import ScanData
from bonesim.geometry.phantom import Fracture, Phantom
from bonesim.perturb.errors import Instrument
from bonesim.process.clutter import remove_clutter_svd, subtract_empty_scene
from bonesim.process.migrate import migrate
from bonesim.process.pipeline import process

C0 = 299_792_458.0
F = np.linspace(3e9, 11e9, 101)
X = np.arange(0.025, 0.0751, 0.002)
FWD = AnalyticForward()


def acquire(phantom, inst=None):
    inst = inst or Instrument(seed=7)
    xa = inst.actual_positions(X)
    so = inst.actual_standoff(phantom.standoff, X.size)
    return (inst.apply_post(FWD.scan(phantom, F, xa, standoff=so, x_nominal=X)),
            inst.apply_post(FWD.empty_scene(phantom, F, X)))


# --- geometry -------------------------------------------------------------

def test_overlay_rescaling_preserves_skin():
    p = Phantom().with_overlay(0.010)
    assert p.overlay == pytest.approx(0.010)
    assert p.skin == Phantom().skin       # skin is physiological, not padding


def test_overlay_below_skin_scales_the_whole_stack():
    """Thinner than skin used to raise. It now scales all three layers down.

    The change was needed for the experiment matrix: proposal 4.4 makes bare
    bone, overlay zero, the first of its four overlay levels, and refusing
    anything below skin thickness made that level impossible to express.
    """
    p = Phantom().with_overlay(0.001)
    assert p.overlay == pytest.approx(0.001)
    assert p.skin > 0 and p.fat > 0 and p.muscle > 0
    # Proportions preserved.
    base = Phantom()
    assert p.skin / p.overlay == pytest.approx(base.skin / base.overlay)


def test_overlay_zero_gives_bare_bone():
    p = Phantom().with_overlay(0.0)
    assert p.is_bare
    assert p.skin == 0.0 and p.fat == 0.0 and p.muscle == 0.0
    assert p.z_cortex == 0.0


def test_negative_overlay_still_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        Phantom().with_overlay(-0.001)


def test_fracture_sits_on_the_cortex():
    p = Phantom().with_fracture(Fracture(0.05, 0.001))
    (_, z, kerf, fill, host), = p.scatterers()
    assert p.z_cortex < z < p.z_marrow
    assert kerf == 0.001 and fill == "blood" and host == "cortical_bone"
    assert p.material_at(0.05, z) == "blood"
    assert p.material_at(0.02, z) == "cortical_bone"


# --- forward model --------------------------------------------------------

def test_scandata_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="does not match"):
        ScanData(F, X, np.zeros((3, 4), complex), -0.012)


def test_gap_reflection_is_resonant_not_linear():
    """A blood-filled gap is a quarter-wave resonator, so response is not
    monotone in width at a single frequency."""
    f = np.array([10e9])
    g = [abs(complex(gap_reflection("cortical_bone", "blood", w, f)[0]))
         for w in (0.0003, 0.001, 0.002)]
    assert g[1] > g[0] and g[1] > g[2]


def test_intact_scan_is_constant_along_the_scan():
    d = FWD.scan(Phantom(), F, X)
    assert np.allclose(d.s11, d.s11[:, :1])


def test_fracture_adds_position_dependence():
    a = FWD.scan(Phantom(), F, X).s11
    b = FWD.scan(Phantom().with_fracture(Fracture(0.05, 0.001)), F, X).s11
    assert not np.allclose(a, b)
    var = np.abs(b - b.mean(axis=1, keepdims=True)).max()
    assert var > 0


def test_fracture_response_grows_with_kerf():
    base = FWD.scan(Phantom(), F, X).s11
    peaks = []
    for kerf in (0.0003, 0.0005, 0.001):
        d = FWD.scan(Phantom().with_fracture(Fracture(0.05, kerf)), F, X)
        peaks.append(np.abs(d.s11 - base).max())
    assert peaks == sorted(peaks)


def test_deeper_overlay_attenuates_the_fracture():
    peaks = []
    for ov in (0.003, 0.006, 0.010):
        p = Phantom().with_overlay(ov)
        d = FWD.scan(p.with_fracture(Fracture(0.05, 0.001)), F, X).s11
        peaks.append(np.abs(d - FWD.scan(p, F, X).s11).max())
    assert peaks == sorted(peaks, reverse=True)


# --- migration ------------------------------------------------------------

def test_fast_migration_matches_direct_double_sum():
    """The time-domain implementation must reproduce proposal 2.5 step 6."""
    d = FWD.scan(Phantom().with_fracture(Fracture(0.05, 0.001)), F, X)
    xg = np.linspace(0.04, 0.06, 11)
    zg = np.linspace(0.002, 0.016, 8)
    fast = migrate(d, 9.0, x_grid=xg, z_grid=zg)

    n_t, z_ant = 3.0, d.z_antenna
    slow = np.zeros((zg.size, xg.size), complex)
    for iz, z in enumerate(zg):
        for ix, x in enumerate(xg):
            dz = z - z_ant
            r = np.hypot(x - d.x, dz)
            r_air = r * min(max((-z_ant) / dz, 0.0), 1.0)
            path = 2.0 * (r_air + n_t * (r - r_air))
            slow[iz, ix] = np.sum(
                d.s11 * np.exp(2j * np.pi * np.outer(F, path / C0)))
    rel = np.abs(fast.data - slow).max() / np.abs(slow).max()
    assert rel < 1e-3


def test_migration_rejects_nonuniform_frequency():
    d = FWD.scan(Phantom(), np.geomspace(3e9, 11e9, 64), X)
    with pytest.raises(ValueError, match="uniform frequency"):
        migrate(d, 9.0)


def test_migration_rejects_bad_permittivity():
    with pytest.raises(ValueError, match="must be positive"):
        migrate(FWD.scan(Phantom(), F, X), -1.0)


# --- clutter removal ------------------------------------------------------

def test_svd_removes_rank_one_clutter_exactly():
    d = FWD.scan(Phantom(), F, X)
    assert np.abs(remove_clutter_svd(d, 1).s11).max() < 1e-12


def test_svd_rejects_removing_everything():
    d = FWD.scan(Phantom(), F, X)
    with pytest.raises(ValueError, match="discards all"):
        remove_clutter_svd(d, min(d.n_freq, d.n_scan))


def test_empty_scene_requires_matching_geometry():
    d = FWD.scan(Phantom(), F, X)
    other = FWD.scan(Phantom(), F, X[:5])
    with pytest.raises(ValueError, match="does not match"):
        subtract_empty_scene(d, other)


# --- instrument errors ----------------------------------------------------

def test_standoff_drift_is_smooth_and_scaled():
    """Smooth drift stays low-rank, so the SVD stage can reject it."""
    inst = Instrument(standoff_sigma=300e-6, seed=3)
    so = inst.actual_standoff(0.012, 61)
    assert so.std() == pytest.approx(300e-6, rel=0.05)
    # A smooth curve has far fewer sign changes in its derivative than noise.
    assert np.sum(np.diff(np.sign(np.diff(so))) != 0) < 10


def test_noise_estimator_recovers_injected_sigma():
    d = FWD.scan(Phantom(), F, X)
    inst = Instrument(dynamic_range_db=80, cable_delay_rms=0, seed=5)
    noisy = inst.add_receiver_noise(d)
    expected = np.abs(d.s11).max() * 10 ** (-80 / 20)
    assert estimate_sample_noise(noisy) == pytest.approx(expected, rel=0.35)


# --- end to end -----------------------------------------------------------

def test_pipeline_localises_the_fracture():
    p = Phantom().with_fracture(Fracture(0.050, 0.001))
    r = process(*acquire(p), k=2, eps_avg=9.0)
    assert abs(r.detection.x_peak - 0.050) < 0.003


def test_pipeline_separates_fractured_from_intact():
    frac = process(*acquire(Phantom().with_fracture(Fracture(0.05, 0.001))),
                   k=2, eps_avg=9.0)
    intact = process(*acquire(Phantom()), k=2, eps_avg=9.0)
    assert frac.detection.ratio_db - intact.detection.ratio_db > 10.0


def test_detectability_degrades_with_overlay():
    snr = []
    for ov in (0.003, 0.006, 0.010):
        p = Phantom().with_overlay(ov).with_fracture(Fracture(0.05, 0.001))
        snr.append(process(*acquire(p), k=2, eps_avg=9.0).detection.ratio_db)
    assert snr == sorted(snr, reverse=True)
