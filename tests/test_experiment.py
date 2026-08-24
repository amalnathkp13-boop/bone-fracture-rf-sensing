"""Tests for the experiment matrix of proposal section 4.4."""
from __future__ import annotations

import numpy as np
import pytest

from bonesim.experiment import (DX, FRACTURE_STATES, KERF_CELLS, N_SPECIMENS,
                                OVERLAYS, build_matrix, matrix_summary)
from bonesim.forward.gprmax import GridSpec
from bonesim.geometry.phantom import Phantom


# --- shape of the design --------------------------------------------------

def test_matrix_is_the_full_factorial():
    cells = build_matrix()
    assert len(cells) == N_SPECIMENS * len(FRACTURE_STATES) * len(OVERLAYS)
    assert len(cells) == 192


def test_keys_are_unique_so_nothing_overwrites_anything():
    keys = [c.key for c in build_matrix()]
    assert len(set(keys)) == len(keys)


def test_every_specimen_appears_intact_at_every_overlay():
    """Proposal 4.4: each specimen is its own control, so pairs must exist."""
    cells = build_matrix()
    intact = {(c.specimen, c.overlay) for c in cells if not c.fractured}
    assert len(intact) == N_SPECIMENS * len(OVERLAYS)
    for c in cells:
        assert (c.specimen, c.overlay) in intact


def test_specimens_actually_differ():
    """Without variation, leave-one-specimen-out has nothing to leave out."""
    cells = build_matrix()
    cortices = {c.specimen: c.phantom.cortex for c in cells}
    assert len(set(cortices.values())) == N_SPECIMENS
    spread = max(cortices.values()) / min(cortices.values())
    assert spread > 1.1


def test_a_specimen_keeps_its_cortex_across_all_its_acquisitions():
    """Drawing per cell would make each acquisition a different animal."""
    cells = build_matrix()
    for s in range(N_SPECIMENS):
        widths = {c.phantom.cortex for c in cells if c.specimen == s}
        assert len(widths) == 1


def test_matrix_is_deterministic():
    a, b = build_matrix(), build_matrix()
    assert [c.key for c in a] == [c.key for c in b]
    assert [c.phantom.cortex for c in a] == [c.phantom.cortex for c in b]


# --- kerf must be exactly representable -----------------------------------

@pytest.mark.parametrize("name,cells", sorted(KERF_CELLS.items()))
def test_every_kerf_is_a_whole_number_of_cells(name, cells):
    """Proposal 4.2: ground truth is the measurement, not the intention.

    A 0.3 mm slot on a 0.2 mm grid is built 0.2 mm wide, so reporting a 0.3 mm
    detection threshold would be a fabricated number.
    """
    kerf = next(k for n, k, _, _ in FRACTURE_STATES if n == name)
    assert kerf == pytest.approx(cells * DX)
    assert abs(kerf / DX - round(kerf / DX)) < 1e-9


def test_kerf_levels_span_an_order_of_magnitude():
    kerfs = sorted(k for _, k, _, _ in FRACTURE_STATES if k is not None)
    assert kerfs[-1] / kerfs[0] >= 10


def test_oblique_shares_a_kerf_with_a_transverse_state():
    """So angle can be separated from width in the analysis."""
    by_name = {n: k for n, k, _, _ in FRACTURE_STATES}
    assert by_name["oblique"] == by_name["kerf10"]
    angles = {n: a for n, _, a, _ in FRACTURE_STATES}
    assert angles["oblique"] == 45.0
    assert angles["kerf10"] == 0.0


# --- overlays -------------------------------------------------------------

def test_bare_bone_is_included_and_really_bare():
    cells = build_matrix()
    bare = [c for c in cells if c.overlay == 0.0]
    assert bare
    for c in bare:
        assert c.phantom.is_bare
        assert c.phantom.overlay == 0.0
        assert c.phantom.z_cortex == 0.0


def test_overlay_sweep_matches_the_proposal():
    assert OVERLAYS == (0.000, 0.003, 0.006, 0.010)


def test_overlay_below_skin_scales_the_whole_stack():
    p = Phantom().with_overlay(0.001)
    assert p.overlay == pytest.approx(0.001)
    assert p.skin > 0 and p.fat > 0 and p.muscle > 0


def test_negative_overlay_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        Phantom().with_overlay(-0.001)


# --- solvability ----------------------------------------------------------

def test_every_cell_fits_the_production_domain():
    """Fail here, in milliseconds, rather than partway through 32 hours."""
    grid = GridSpec(depth=0.060, time_window=2.5e-9)
    for c in build_matrix():
        grid.check(c.phantom)


def test_deepest_cell_leaves_margin():
    grid = GridSpec(depth=0.060, time_window=2.5e-9)
    cells = build_matrix()
    deepest = max(cells,
                  key=lambda c: c.phantom.z_far_cortex + c.phantom.cortex)
    clearance = (grid.y_skin(deepest.phantom)
                 - (deepest.phantom.z_far_cortex + deepest.phantom.cortex))
    assert clearance >= grid.margin


def test_summary_reports_the_paired_design():
    text = matrix_summary(build_matrix())
    assert "192 acquisitions" in text
    assert "paired" in text


# --- bare bone must actually build ----------------------------------------

def test_bare_phantom_emits_no_zero_thickness_layers():
    """Regression: gprMax rejects a primitive with no volume.

    A bare specimen has skin, fat and muscle all at zero, and emitting them as
    degenerate boxes made the first cell of the matrix fail to build.
    """
    p = Phantom().with_overlay(0.0)
    layers = p.stack()
    assert layers, "bare bone still needs its cortex and marrow"
    for mat, a, b in layers:
        assert b > a, f"{mat} has zero thickness"
    assert {m for m, _, _ in layers} == {"cortical_bone", "marrow"}


def test_bare_phantom_produces_a_valid_deck():
    from bonesim.forward.gprmax import GridSpec, build_geometry
    text = build_geometry(Phantom().with_overlay(0.0),
                          GridSpec(depth=0.060, time_window=2.5e-9))
    boxes = [l for l in text.splitlines() if l.startswith("#box:")]
    assert boxes
    for line in boxes:
        p = line.split()
        assert float(p[4]) > float(p[2]), f"degenerate box: {line}"


def test_layered_phantom_still_has_all_six_layers():
    assert len(Phantom().stack()) == 6
