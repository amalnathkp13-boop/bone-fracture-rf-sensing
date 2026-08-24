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
