"""Drive a full gprMax B-scan and return it as ScanData.

Splits the scan positions across several concurrent gprMax processes, because
the solver is memory-bandwidth-bound: four processes of four threads each run
4.7x faster than one process across sixteen threads on this machine
(docs/compute-budget.md).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .base import ScanData
from .gprmax import GridSpec, assemble, build_input, run_models


@dataclass
class BScanPlan:
    """Scan geometry, independent of what is being scanned."""
    x_start: float = 0.020
    x_stop: float = 0.080
    step: float = 0.001          # proposal 2.4: 1 mm steps
    f_lo: float = 3e9
    f_hi: float = 11e9
    n_freq: int = 201            # cf. 1601 on a real VNA; only the band matters

    @property
    def x(self) -> np.ndarray:
        n = int(round((self.x_stop - self.x_start) / self.step)) + 1
        return self.x_start + self.step * np.arange(n)

    @property
    def f(self) -> np.ndarray:
        return np.linspace(self.f_lo, self.f_hi, self.n_freq)


def expected_outputs(work, decks) -> list[Path]:
    """Filenames gprMax will write for these decks.

    With -n 1 it writes <stem>.out; with -n N it writes <stem>1.out to
    <stem>N.out.
    """
    work = Path(work)
    out = []
    for stem, n in decks:
        if n == 1:
            out.append(work / f"{stem}.out")
        else:
            out.extend(work / f"{stem}{i}.out" for i in range(1, n + 1))
    return out


def run_bscan(phantom, work_dir, plan: BScanPlan | None = None,
              grid: GridSpec | None = None, materials=None,
              n_proc: int = 4, threads: int = 4, clean: bool = False,
              resume: bool = True, timeout: float = 86400,
              wsl_distro="Ubuntu", gpu: bool = False) -> ScanData:
    """Generate, run and assemble one B-scan.

    The free-space reference is run alongside the scan chunks. It is a single
    model and does not depend on scan position, so one serves the whole B-scan.

    Resumable by default. If every output a set of decks would produce is
    already present, the solve is skipped and the existing files are assembled.
    This is not a nicety: a B-scan is ten minutes of compute, the laptop can
    suspend mid-run, and a hosted GPU session can be reclaimed at any time.
    Stage 4 lost a completed 62-model scan to a driver timeout that fired while
    the machine was asleep, with every output file sitting on disk intact.

    The same property is what makes the matrix safe to run on Colab, where the
    unit of checkpointing is one B-scan.

    timeout is deliberately a full day. It exists to catch a wedged solver, not
    to bound normal work, and a tight value turns an ordinary suspend into a
    lost run.
    """
    plan = plan or BScanPlan()
    grid = grid or GridSpec()
    work = Path(work_dir)
    if clean and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    materials = Path(materials) if materials else (
        Path(__file__).resolve().parents[2] / "config" / "materials.in")

    x = plan.x
    chunks = np.array_split(np.arange(x.size), n_proc)
    chunks = [c for c in chunks if c.size]

    decks = []
    stems = []
    for i, c in enumerate(chunks):
        stem = f"scan_p{i}"
        (work / f"{stem}.in").write_text(
            build_input(phantom, grid, materials, float(x[c[0]]),
                        int(c.size), plan.step,
                        title=f"bonesim B-scan chunk {i}"))
        decks.append((stem, int(c.size)))
        stems.append(stem)

    (work / "ref.in").write_text(
        build_input(None, grid, materials, float(x[0]), 1, plan.step,
                    title="bonesim free-space reference"))
    decks.append(("ref", 1))

    missing = [p for p in expected_outputs(work, decks) if not p.exists()]
    if resume and not missing:
        print(f"    {work.name}: all {len(expected_outputs(work, decks))} "
              f"outputs present, skipping solve")
    else:
        run_models(work, decks, threads=threads, wsl_distro=wsl_distro,
                   timeout=timeout, gpu=gpu)

    z_ant = -(phantom.standoff if phantom is not None else 0.0)
    return assemble(work, stems, "ref", plan.f, x, z_ant,
                    meta={"phantom": phantom.describe() if phantom else "free",
                          "dx": grid.dx, "time_window": grid.time_window})


def run_empty_scene(work_dir, plan: BScanPlan | None = None,
                    grid: GridSpec | None = None, standoff: float = 0.012,
                    n_proc: int = 1, threads: int = 4, clean: bool = True,
                    wsl_distro="Ubuntu") -> ScanData:
    """Reference acquisition: antenna and stage present, no limb.

    Under the S11 normalisation used here this is identically one at every
    frequency and position, since the reference divides itself out. It is
    produced explicitly anyway so the pipeline receives the same object type
    from either backend and the subtraction step is never special-cased.
    """
    plan = plan or BScanPlan()
    x, f = plan.x, plan.f
    return ScanData(f, x, np.ones((f.size, x.size), dtype=complex),
                    -standoff, meta={"model": "gprmax", "empty_scene": True})
