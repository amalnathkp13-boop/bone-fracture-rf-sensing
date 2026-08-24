"""Tests for the antipodal Vivaldi geometry.

Solver-free: everything here checks the shape, so the design can be validated
without openEMS present.
"""
from __future__ import annotations

import numpy as np
import pytest

from bonesim.antenna.vivaldi import SUBSTRATES, Vivaldi

BAND = (3e9, 11e9)


# --- the taper ------------------------------------------------------------

def test_taper_meets_both_endpoints_exactly():
    v = Vivaldi()
    assert v.taper(v.taper_start) == pytest.approx(-v.feed_width / 2)
    assert v.taper(v.length) == pytest.approx(v.aperture / 2)


@pytest.mark.parametrize("rate", [0.05, 0.08, 0.10])
def test_endpoints_hold_across_the_proposals_rate_range(rate):
    """Proposal 2.3 specifies 0.05 to 0.10 per mm."""
    v = Vivaldi(rate=rate)
    assert v.taper(v.taper_start) == pytest.approx(-v.feed_width / 2)
    assert v.taper(v.length) == pytest.approx(v.aperture / 2)


def test_taper_flares_monotonically():
    v = Vivaldi()
    y = v.taper(np.linspace(v.taper_start, v.length, 200))
    assert np.all(np.diff(y) > 0)


def test_higher_rate_flares_later_and_harder():
    """A larger opening rate keeps the slot narrow for longer."""
    slow, fast = Vivaldi(rate=0.05), Vivaldi(rate=0.10)
    mid = slow.taper_start + slow.taper_length / 2
    assert fast.taper(mid) < slow.taper(mid)


def test_taper_sampling_is_denser_at_the_mouth():
    """The curve bends hardest at the mouth and must not be stepped there."""
    v = Vivaldi()
    x = v.taper_points(40)[:, 0]
    gaps = np.diff(x)
    assert gaps[-1] < gaps[0]


# --- arms -----------------------------------------------------------------

def test_lower_arm_is_the_mirror_of_the_upper():
    v = Vivaldi()
    up, lo = v.upper_arm(), v.lower_arm()
    assert np.allclose(lo[:, 0], up[:, 0])
    assert np.allclose(lo[:, 1], -up[:, 1])


def test_arms_overlap_at_the_feed():
    """The overlap forms the parallel-strip line, so no balun is needed."""
    v = Vivaldi()
    assert v.taper(v.taper_start) < 0          # upper arm reaches below y=0
    overlap = -2 * v.taper(v.taper_start)
    assert overlap == pytest.approx(v.feed_width)


def test_arm_stays_inside_the_substrate():
    v = Vivaldi()
    arm = v.upper_arm()
    assert arm[:, 0].min() >= 0.0
    assert arm[:, 0].max() <= v.length + 1e-9
    assert arm[:, 1].max() <= v.sub_width / 2 + 1e-9


def test_slot_at_the_mouth_equals_the_aperture():
    v = Vivaldi()
    assert 2 * v.taper(v.length) == pytest.approx(v.aperture)


# --- validation -----------------------------------------------------------

def test_rejects_an_implausible_opening_rate():
    with pytest.raises(ValueError, match="opening rate"):
        Vivaldi(rate=5.0)


def test_rejects_an_aperture_wider_than_the_board():
    with pytest.raises(ValueError, match="aperture must fit"):
        Vivaldi(aperture=60.0, sub_width=50.0)


def test_rejects_a_taper_starting_past_the_mouth():
    with pytest.raises(ValueError, match="taper must start before"):
        Vivaldi(taper_start=80.0, length=70.0)


# --- predicted behaviour --------------------------------------------------

def test_cutoff_sits_below_the_working_band():
    """The design must radiate at the bottom of the 3-11 GHz sweep."""
    for name in SUBSTRATES:
        v = Vivaldi(substrate=name)
        assert v.cutoff_frequency() < BAND[0], name


def test_a_smaller_aperture_raises_the_cutoff():
    assert (Vivaldi(aperture=20.0).cutoff_frequency()
            > Vivaldi(aperture=40.0).cutoff_frequency())


def test_both_substrates_from_the_proposal_are_present():
    assert set(SUBSTRATES) == {"RO4350B", "FR4"}
    assert SUBSTRATES["RO4350B"]["eps_r"] == 3.48
    assert SUBSTRATES["FR4"]["eps_r"] == 4.4
    assert SUBSTRATES["RO4350B"]["tan_d"] < SUBSTRATES["FR4"]["tan_d"]


def test_loss_conductivity_ordering():
    """FR4 must come out lossier than RO4350B at the same frequency."""
    from bonesim.antenna.model import _kappa
    ro = SUBSTRATES["RO4350B"]
    fr = SUBSTRATES["FR4"]
    assert (_kappa(fr["eps_r"], fr["tan_d"], 7e9)
            > _kappa(ro["eps_r"], ro["tan_d"], 7e9))


def test_bandwidth_finds_a_contiguous_band():
    from bonesim.antenna.model import bandwidth
    f = np.linspace(1e9, 12e9, 111)
    # A dip below -10 dB between 3 and 11 GHz, plus an isolated spike that
    # must not be counted as part of the band.
    s = np.full(f.size, 10 ** (-2 / 20))
    s[(f >= 3e9) & (f <= 11e9)] = 10 ** (-15 / 20)
    s[5] = 10 ** (-20 / 20)
    lo, hi, _ = bandwidth(f, s)
    assert lo == pytest.approx(3e9, rel=0.02)
    assert hi == pytest.approx(11e9, rel=0.02)


def test_bandwidth_returns_none_when_never_matched():
    from bonesim.antenna.model import bandwidth
    f = np.linspace(1e9, 12e9, 50)
    lo, hi, db = bandwidth(f, np.ones(50))
    assert lo is None and hi is None
    assert np.allclose(db, 0.0)


# --- the feed section (regression) ----------------------------------------

def test_arm_is_only_feed_width_tall_at_the_feed_edge():
    """Regression: the outer edge must step out at taper_start, not at x=0.

    Running it back to the feed edge made each arm 26.5 mm tall where the port
    drives it, so the port saw two large overlapping plates rather than a
    parallel-strip line. The antenna then resonated instead of behaving as a
    travelling-wave taper.
    """
    for v in (Vivaldi(), Vivaldi(length=110, aperture=55, sub_width=65)):
        arm = v.upper_arm()
        ys = arm[np.isclose(arm[:, 0], 0.0)][:, 1]
        assert ys.size >= 2
        assert ys.max() - ys.min() == pytest.approx(v.feed_width)


def test_feed_strip_is_centred_on_the_axis():
    v = Vivaldi()
    ys = v.upper_arm()[np.isclose(v.upper_arm()[:, 0], 0.0)][:, 1]
    assert ys.min() == pytest.approx(-v.feed_width / 2)
    assert ys.max() == pytest.approx(v.feed_width / 2)


def test_both_arms_coincide_in_the_feed_region():
    """Face-to-face identical strips are what make it a parallel-strip line."""
    v = Vivaldi()
    up = v.upper_arm()
    lo = v.lower_arm()
    up_feed = np.sort(up[np.isclose(up[:, 0], 0.0)][:, 1])
    lo_feed = np.sort(lo[np.isclose(lo[:, 0], 0.0)][:, 1])
    assert np.allclose(up_feed, lo_feed)


def test_arm_widens_only_after_the_taper_starts():
    v = Vivaldi()
    arm = v.upper_arm()
    before = arm[arm[:, 0] < v.taper_start - 1e-9]
    assert np.all(np.abs(before[:, 1]) <= v.feed_width / 2 + 1e-9)


def test_polygon_does_not_self_intersect():
    """A self-intersecting outline would be meshed unpredictably."""
    def seg_cross(p, q, r, s):
        d1, d2 = q - p, s - r
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12:
            return False
        t = ((r[0] - p[0]) * d2[1] - (r[1] - p[1]) * d2[0]) / den
        u = ((r[0] - p[0]) * d1[1] - (r[1] - p[1]) * d1[0]) / den
        return 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9

    pts = Vivaldi().upper_arm(20)
    n = len(pts)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            assert not seg_cross(pts[i], pts[(i + 1) % n],
                                 pts[j], pts[(j + 1) % n]), (i, j)
