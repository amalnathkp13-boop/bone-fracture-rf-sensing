"""Tests for the gprMax deck builder and output assembler.

These deliberately do not invoke the solver: they cover the parts that are easy
to get silently wrong - the coordinate mapping, the guards, the output ordering
and the S11 normalisation.
"""
from __future__ import annotations

import numpy as np
import pytest

from bonesim.forward.bscan import BScanPlan
from bonesim.forward.gprmax import (GridSpec, assemble, build_geometry,
                                    build_input, sorted_outputs)
from bonesim.geometry.phantom import Fracture, Phantom

C0 = 299_792_458.0
MATS = "config/materials.in"


def parse_boxes(text):
    out = []
    for line in text.splitlines():
        if line.startswith("#box:"):
            p = line.split()[1:]
            out.append((p[-1], float(p[0]), float(p[1]), float(p[3]),
                        float(p[4])))
    return out


# --- grid -----------------------------------------------------------------

def test_timestep_is_the_2d_courant_limit():
    g = GridSpec(dx=0.0002)
    assert g.dt == pytest.approx(0.0002 / (C0 * np.sqrt(2)))


def test_guard_rejects_a_domain_that_truncates_anatomy():
    with pytest.raises(ValueError, match="too shallow"):
        GridSpec().check(Phantom(marrow=0.040))


def test_guard_rejects_a_time_window_shorter_than_the_round_trip():
    with pytest.raises(ValueError, match="shorter than"):
        GridSpec(time_window=2e-10).check(Phantom())


# --- coordinate mapping ---------------------------------------------------

def test_depth_maps_to_descending_y():
    """Phantom z runs into the limb; gprMax y runs up. Layers must invert."""
    g, p = GridSpec(), Phantom()
    boxes = parse_boxes(build_geometry(p, g))
    mats = [b[0] for b in boxes]
    assert mats[:3] == ["skin_dry", "fat", "muscle"]
    tops = [b[4] for b in boxes]           # y of each layer top
    assert tops == sorted(tops, reverse=True)


def test_skin_top_sits_one_standoff_below_the_antenna():
    g, p = GridSpec(), Phantom()
    boxes = parse_boxes(build_geometry(p, g))
    skin_top = next(b[4] for b in boxes if b[0] == "skin_dry")
    assert skin_top == pytest.approx(g.y_antenna() - p.standoff, abs=1e-9)


def test_layers_are_contiguous_with_no_gaps():
    boxes = parse_boxes(build_geometry(Phantom(), GridSpec()))
    for upper, lower in zip(boxes[:-1], boxes[1:]):
        assert upper[2] == pytest.approx(lower[4], abs=1e-9)


# --- fracture -------------------------------------------------------------

def test_fracture_overwrites_the_cortex_and_is_written_last():
    p = Phantom().with_fracture(Fracture(0.050, 0.001))
    boxes = parse_boxes(build_geometry(p, GridSpec()))
    assert boxes[-1][0] == "blood"
    _, x0, _, x1, _ = boxes[-1]
    assert x0 == pytest.approx(0.0495) and x1 == pytest.approx(0.0505)


def test_kerf_sets_the_gap_width():
    for kerf in (0.0003, 0.001, 0.002):
        p = Phantom().with_fracture(Fracture(0.050, kerf))
        _, x0, _, x1, _ = parse_boxes(build_geometry(p, GridSpec()))[-1]
        assert x1 - x0 == pytest.approx(kerf)


def test_partial_fracture_does_not_span_the_full_cortex():
    g = GridSpec()
    full = parse_boxes(build_geometry(
        Phantom().with_fracture(Fracture(0.05, 0.001)), g))[-1]
    half = parse_boxes(build_geometry(
        Phantom().with_fracture(Fracture(0.05, 0.001, depth_fraction=0.5)),
        g))[-1]
    assert (half[4] - half[2]) < (full[4] - full[2])


def test_oblique_fracture_is_stacked_and_offset():
    p = Phantom().with_fracture(Fracture(0.050, 0.001, angle_deg=45))
    blood = [b for b in parse_boxes(build_geometry(p, GridSpec()))
             if b[0] == "blood"]
    assert len(blood) > 1
    centres = [0.5 * (b[1] + b[3]) for b in blood]
    assert max(centres) - min(centres) > 0.001      # it actually leans


# --- decks ----------------------------------------------------------------

def test_reference_deck_has_no_materials_or_geometry():
    deck = build_input(None, GridSpec(), MATS, 0.02, 1, 0.001)
    assert "#box:" not in deck and "#material:" not in deck
    assert "#src_steps" not in deck                 # single position


def test_scan_deck_steps_only_when_multiple_positions():
    g = GridSpec()
    assert "#src_steps" in build_input(Phantom(), g, MATS, 0.02, 61, 0.001)
    assert "#src_steps" not in build_input(Phantom(), g, MATS, 0.02, 1, 0.001)


def test_deck_rejects_a_materials_file_without_debye_cards(tmp_path):
    bad = tmp_path / "bad.in"
    bad.write_text("#material: 4 0 1 0 nope\n")
    with pytest.raises(ValueError, match="no Debye cards"):
        build_input(Phantom(), GridSpec(), bad, 0.02, 1, 0.001)


def test_source_and_receiver_are_colocated():
    deck = build_input(Phantom(), GridSpec(), MATS, 0.02, 1, 0.001)
    src = [l for l in deck.splitlines() if l.startswith("#hertzian_dipole")][0]
    rx = [l for l in deck.splitlines() if l.startswith("#rx:")][0]
    assert src.split()[2:4] == rx.split()[1:3]


# --- output handling ------------------------------------------------------

def _write_out(path, trace, dt):
    import h5py
    with h5py.File(path, "w") as h:
        h.attrs["dt"] = dt
        h.attrs["Iterations"] = trace.size
        h.create_dataset("/rxs/rx1/Ez", data=trace)


def test_outputs_sort_numerically_not_lexically(tmp_path):
    """scan2 must come before scan10, which string sorting gets wrong."""
    for i in (1, 2, 10, 11):
        _write_out(tmp_path / f"scan{i}.out", np.zeros(4), 1e-12)
    got = [p.name for p in sorted_outputs(tmp_path, "scan")]
    assert got == ["scan1.out", "scan2.out", "scan10.out", "scan11.out"]


def test_assemble_normalises_to_the_reference(tmp_path):
    """A scene identical to the reference must give S11 = 1 exactly."""
    dt = 5e-13
    t = np.arange(512) * dt
    inc = np.exp(-((t - 1e-10) / 3e-11) ** 2) * np.sin(2 * np.pi * 7e9 * t)
    _write_out(tmp_path / "ref.out", inc, dt)
    for i in (1, 2):
        _write_out(tmp_path / f"scan{i}.out", inc, dt)

    f = np.linspace(3e9, 11e9, 41)
    d = assemble(tmp_path, ["scan"], "ref", f, np.array([0.02, 0.021]), -0.012)
    assert np.allclose(d.s11, 1.0, atol=1e-6)


def test_assemble_rejects_a_trace_count_mismatch(tmp_path):
    dt = 5e-13
    tr = np.random.default_rng(0).normal(size=256)
    _write_out(tmp_path / "ref.out", tr, dt)
    _write_out(tmp_path / "scan1.out", tr, dt)
    with pytest.raises(ValueError, match="got 1 traces for 3"):
        assemble(tmp_path, ["scan"], "ref", np.linspace(3e9, 11e9, 9),
                 np.array([0.0, 0.001, 0.002]), -0.012)


def test_assemble_rejects_mismatched_timesteps(tmp_path):
    tr = np.random.default_rng(0).normal(size=256)
    _write_out(tmp_path / "ref.out", tr, 5e-13)
    _write_out(tmp_path / "scan1.out", tr, 6e-13)
    with pytest.raises(ValueError, match="different time step"):
        assemble(tmp_path, ["scan"], "ref", np.linspace(3e9, 11e9, 9),
                 np.array([0.0]), -0.012)


# --- plan -----------------------------------------------------------------

def test_plan_covers_the_requested_span_inclusively():
    p = BScanPlan(x_start=0.020, x_stop=0.080, step=0.001)
    assert p.x.size == 61
    assert p.x[0] == pytest.approx(0.020) and p.x[-1] == pytest.approx(0.080)
