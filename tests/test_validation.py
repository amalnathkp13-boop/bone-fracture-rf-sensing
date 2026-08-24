"""Tests for the brass-rod validation geometry (proposal section 9)."""
from __future__ import annotations

import pytest

from bonesim.forward.gprmax import GridSpec, build_geometry
from bonesim.geometry.validation import RodPhantom

GRID = GridSpec(depth=0.062, time_window=3.0e-9)
TANK = 0.036


def parse(text):
    boxes, cyls = [], []
    for line in text.splitlines():
        p = line.split()
        if line.startswith("#box:"):
            boxes.append((p[-1], float(p[2]), float(p[5])))       # mat, y0, y1
        elif line.startswith("#cylinder:"):
            cyls.append((p[-1], float(p[1]), float(p[2]), float(p[7])))
    return boxes, cyls


def test_phantom_is_a_single_uniform_layer():
    boxes, _ = parse(build_geometry(RodPhantom(depth=TANK), GRID))
    assert len(boxes) == 1
    assert boxes[0][0] == "muscle"


def test_rod_is_pec_of_the_right_radius():
    _, cyls = parse(build_geometry(RodPhantom(depth=TANK), GRID))
    assert len(cyls) == 1
    mat, _, _, r = cyls[0]
    assert mat == "pec"
    assert r == pytest.approx(0.003)      # 6 mm diameter


def test_rod_depth_maps_to_the_right_gprmax_y():
    """Depth is measured from the phantom surface, not the domain floor."""
    ph = RodPhantom(depth=TANK, rod_depth=0.020)
    _, cyls = parse(build_geometry(ph, GRID))
    y_skin = GRID.y_skin(ph)
    assert cyls[0][2] == pytest.approx(y_skin - 0.020, abs=1e-9)


@pytest.mark.parametrize("z", [0.012, 0.020, 0.028])
def test_rod_sits_inside_the_phantom(z):
    ph = RodPhantom(depth=TANK, rod_depth=z)
    boxes, cyls = parse(build_geometry(ph, GRID))
    _, y0, y1 = boxes[0]
    _, _, y_rod, r = cyls[0]
    assert y0 + r <= y_rod <= y1 - r


def test_control_has_no_rod():
    ctrl = RodPhantom(depth=TANK).without_rod()
    boxes, cyls = parse(build_geometry(ctrl, GRID))
    assert cyls == []
    assert len(boxes) == 1                # phantom otherwise identical


def test_control_is_identical_apart_from_the_rod():
    rod = RodPhantom(depth=TANK)
    a, _ = parse(build_geometry(rod, GRID))
    b, _ = parse(build_geometry(rod.without_rod(), GRID))
    assert a == b


def test_overlay_is_measured_to_the_top_of_the_rod():
    ph = RodPhantom(rod_depth=0.020, rod_diameter=0.006)
    assert ph.overlay == pytest.approx(0.017)


def test_guard_rejects_a_domain_too_shallow_for_the_tank():
    with pytest.raises(ValueError, match="too shallow"):
        GridSpec(depth=0.040, time_window=3.0e-9).check(
            RodPhantom(depth=TANK, rod_depth=0.028))


def test_guard_rejects_a_time_window_too_short_for_the_tank():
    with pytest.raises(ValueError, match="shorter than"):
        GridSpec(depth=0.062, time_window=1.0e-9).check(RodPhantom(depth=TANK))


def test_rod_phantom_satisfies_the_phantom_interface():
    """The gate must run through the same code as the experiment."""
    ph = RodPhantom(depth=TANK)
    for attr in ("standoff", "cortex", "z_far_cortex", "fracture"):
        assert hasattr(ph, attr)
    for meth in ("stack", "scatterers", "cylinders", "describe"):
        assert callable(getattr(ph, meth))
    assert ph.fracture is None


def test_layered_phantom_still_emits_no_cylinders():
    """The cylinders hook must not disturb the limb geometry."""
    from bonesim.geometry.phantom import Fracture, Phantom
    text = build_geometry(Phantom().with_fracture(Fracture(0.05, 0.001)),
                          GridSpec())
    assert "#cylinder:" not in text


# --- clutter removal by character, not index -------------------------------

def _synthetic_scan(n_freq=64, n_scan=41, eps=12.0):
    """A flat interface, a point scatterer, and a second flat interface.

    Deliberately ordered so the target sits *between* the two interfaces in
    singular value, which is the situation the index rule cannot handle and
    which the Stage 4 phantom tank actually produced.

    The target must carry proper hyperbolic moveout - its delay varying with
    scan position - because that is what migration collapses to a point. An
    earlier version of this helper used a constant delay under a Gaussian
    amplitude envelope; that never focuses, so every component looked extended
    and the test failed on the fixture rather than on the code.
    """
    import numpy as np

    from bonesim.forward.base import ScanData
    C0 = 299_792_458.0
    f = np.linspace(3e9, 11e9, n_freq)
    x = np.linspace(0.020, 0.080, n_scan)
    z_ant = -0.012
    rng = np.random.default_rng(0)

    def flat(amp, delay):
        return amp * np.exp(-2j * np.pi * np.outer(f, np.full(n_scan, delay)))

    # Point scatterer at (50 mm, 20 mm), with the air/tissue path split the
    # reconstructor also assumes.
    x0, z0, n = 0.050, 0.020, np.sqrt(eps)
    r = np.hypot(x - x0, z0 - z_ant)
    r_air = r * ((-z_ant) / (z0 - z_ant))
    delay = 2.0 * (r_air + n * (r - r_air)) / C0
    tgt = 0.05 * np.exp(-2j * np.pi * np.outer(f, delay))

    s11 = flat(1.0, 1e-10) + tgt + flat(0.2, 8e-10)
    s11 = s11 + 1e-6 * (rng.normal(size=s11.shape)
                        + 1j * rng.normal(size=s11.shape))
    return ScanData(f, x, s11, z_ant, {})


def test_component_extents_separates_flat_from_compact():
    import numpy as np

    from bonesim.process.clutter import component_extents
    data = _synthetic_scan()
    ext, s = component_extents(data, 12.0, n_components=4)
    aperture = float(data.x[-1] - data.x[0])
    # At least one component spans most of the aperture and at least one does
    # not; that separation is the whole basis of the method.
    assert ext.max() > 0.5 * aperture
    assert ext.min() < 0.5 * aperture


def test_selective_removal_keeps_the_compact_component():
    from bonesim.process.clutter import remove_clutter_selective
    data = _synthetic_scan()
    cleaned, keep, ext = remove_clutter_selective(data, 12.0, n_components=4)
    assert keep, "everything was discarded"
    aperture = float(data.x[-1] - data.x[0])
    for i in keep:
        assert ext[i] <= 0.5 * aperture


def test_selective_removal_preserves_matrix_shape():
    from bonesim.process.clutter import remove_clutter_selective
    data = _synthetic_scan()
    cleaned, _, _ = remove_clutter_selective(data, 12.0, n_components=4)
    assert cleaned.s11.shape == data.s11.shape
    assert cleaned.meta["svd_selective"] is True


# --- migration edge artefact ----------------------------------------------

def test_detect_snr_excludes_the_aperture_edges():
    """Regression: the Stage 4 control residual was a migration edge artefact.

    It peaked at exactly the first scan position, with a U-shaped lateral
    profile - 0 dB at both ends against -18.5 dB in the middle - because
    migration cannot focus where the aperture is one-sided. No SVD filtering
    removes it; excluding a margin does.
    """
    import numpy as np
    import pytest as _pytest

    from bonesim.detect.metrics import detect_snr
    from bonesim.forward.base import ScanData
    from bonesim.process.migrate import Image

    x = np.linspace(0.020, 0.080, 61)
    z = np.linspace(0.0, 0.030, 31)
    env = np.full((z.size, x.size), 0.01)
    env[:, 0] = 1.0                      # artefact hard against the left edge
    env[15, 30] = 0.5                    # a genuine target mid-aperture
    img = Image(x, z, env.astype(complex), 12.0)
    rng = np.random.default_rng(1)
    data = ScanData(np.linspace(3e9, 11e9, 32), x,
                    1e-6 * (rng.normal(size=(32, 61))
                            + 1j * rng.normal(size=(32, 61))), -0.012, {})

    edge = detect_snr(img, data, z_window=(0.005, 0.025), x_margin=0.0)
    inner = detect_snr(img, data, z_window=(0.005, 0.025), x_margin=0.010)
    assert edge.x_peak == _pytest.approx(0.020)      # finds the artefact
    assert inner.x_peak == _pytest.approx(0.050, abs=1e-3)   # finds the target
    assert inner.ratio_db < edge.ratio_db


def test_detect_snr_rejects_a_margin_that_consumes_the_image():
    import numpy as np
    import pytest as _pytest

    from bonesim.detect.metrics import detect_snr
    from bonesim.forward.base import ScanData
    from bonesim.process.migrate import Image

    x = np.linspace(0.020, 0.080, 61)
    z = np.linspace(0.0, 0.030, 31)
    img = Image(x, z, np.ones((31, 61), complex), 12.0)
    rng = np.random.default_rng(1)
    data = ScanData(np.linspace(3e9, 11e9, 32), x,
                    1e-6 * (rng.normal(size=(32, 61))
                            + 1j * rng.normal(size=(32, 61))), -0.012, {})
    with _pytest.raises(ValueError, match="leaves no image"):
        detect_snr(img, data, z_window=(0.005, 0.025), x_margin=0.050)
