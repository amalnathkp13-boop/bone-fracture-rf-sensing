"""Shared plotting style, so every figure in the report looks like one set.

Deliberately plain: a capstone figure is read printed, in greyscale as often as
not, at a column width. So the palette is colour-blind safe and distinguishable
without colour, lines carry markers where they might overlap, and nothing
depends on a colour to be readable.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")                       # no display under WSL or on CI
import matplotlib.pyplot as plt

FIGDIR = Path(__file__).resolve().parent.parent / "figures"

# Okabe-Ito, which stays distinguishable for the common colour-vision
# deficiencies and survives being printed in grey.
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
RED = "#D55E00"
PURPLE = "#CC79A7"
SKY = "#56B4E9"
YELLOW = "#F0E442"
GREY = "#666666"
CYCLE = [BLUE, ORANGE, GREEN, RED, PURPLE, SKY]


def use_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": plt.cycler(color=CYCLE),
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 1.6,
        "figure.constrained_layout.use": True,
    })


def save(fig, name: str, caption: str = "") -> Path:
    """Write a figure and echo where it went, with its caption."""
    FIGDIR.mkdir(exist_ok=True)
    path = FIGDIR / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    size = path.stat().st_size / 1024
    print(f"  {path.name:<34} {size:5.0f} kB   {caption}")
    return path


def annotate(ax, text: str, loc: str = "upper right") -> None:
    """A boxed note inside the axes, for the one thing the reader must see."""
    pos = {"upper right": (0.98, 0.97, "right", "top"),
           "upper left": (0.02, 0.97, "left", "top"),
           "lower right": (0.98, 0.03, "right", "bottom"),
           "lower left": (0.02, 0.03, "left", "bottom")}[loc]
    ax.text(pos[0], pos[1], text, transform=ax.transAxes,
            ha=pos[2], va=pos[3], fontsize=8,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                      edgecolor=GREY, alpha=0.9, linewidth=0.6))


def image_axes(ax, img, db_floor: float = -25.0, cmap: str = "inferno",
               ref: float | None = None):
    """Show a migrated image in dB, with depth increasing downward.

    Depth downward matters: the reader is looking into a limb, and an image
    with z increasing upward reads as a mirror of the anatomy.

    `ref` sets the 0 dB level explicitly. Give the *same* ref to every panel
    that will be compared side by side. Without it each panel is normalised to
    its own maximum, which stretches a target-free image's noise floor across
    the full colour range and makes an empty scene look as busy as one holding
    a fracture - the two panels then cannot be read against each other at all.
    """
    env = np.abs(img.data)
    peak = env.max() if ref is None else ref
    with np.errstate(divide="ignore"):
        data = np.maximum(20 * np.log10(env / peak + 1e-30), db_floor)
    extent = [img.x[0] * 1e3, img.x[-1] * 1e3,
              img.z[-1] * 1e3, img.z[0] * 1e3]
    im = ax.imshow(data, aspect="auto", extent=extent, cmap=cmap,
                   vmin=db_floor, vmax=0.0, interpolation="bilinear")
    ax.set_xlabel("position along bone axis (mm)")
    ax.set_ylabel("depth (mm)")
    ax.grid(False)
    return im
