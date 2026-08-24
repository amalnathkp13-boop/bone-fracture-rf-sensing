"""Antipodal Vivaldi antenna geometry (proposal section 2.3).

    "Antipodal Vivaldi is the right choice: inherently ultra-wideband, endfire
    radiation, compact, and etchable on a single double-sided board. An
    exponentially tapered slot with opening rate 0.05-0.10 per mm gives a clean
    3-11 GHz match."

Construction. Two identical flared conductors on opposite faces of the
substrate, one the mirror image of the other in y. Each arm occupies roughly
half the board beyond the feed and is bounded on its inner side by an
exponential taper. The two tapers diverge, and the slot between them is the
radiating aperture.

Near the feed the arms overlap, which forms a parallel-strip (twin) line - this
overlap is what distinguishes the antipodal form from a conventional Vivaldi and
is why it needs no separate microstrip-to-slotline balun.

    y(x) = A exp(a (x - x_t)) + B

fitted so the taper starts at the feed-strip edge and ends at the aperture
mouth, with `a` the opening rate the proposal specifies.

Geometry is pure and unit-tested here; the openEMS model is built from it in
model.py, so the shape can be checked without a solver.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Substrates named in proposal 2.3. Loss tangents at 10 GHz.
SUBSTRATES = {
    "RO4350B": {"eps_r": 3.48, "tan_d": 0.0037, "h": 0.762,
                "note": "markedly better across the full band; the one "
                        "premium item worth buying"},
    "FR4": {"eps_r": 4.4, "tan_d": 0.02, "h": 1.6,
            "note": "acceptable to about 8 GHz, costs a few dB above that"},
}


@dataclass(frozen=True)
class Vivaldi:
    """Antipodal Vivaldi, dimensions in millimetres.

    length       total, feed end to aperture mouth
    taper_start  where the flare begins; before this is the parallel-strip feed
    sub_width    substrate width, which also bounds the outer edge of each arm
    aperture     slot opening at the mouth, which sets the low-frequency limit
    feed_width   width of the parallel-strip conductors where the taper starts
    feed_width_port
                 width at the port. Different from feed_width makes the feed a
                 linear impedance taper rather than a uniform line, which is
                 the standard remedy when the antenna impedance and the 50 ohm
                 source cannot be matched by a single line width. Measured
                 here: median Re(Zin) is 43 / 29 / 19 ohm for feed widths of
                 1.5 / 3.0 / 5.0 mm, so width buys impedance predictably
    rate         exponential opening rate per mm (proposal: 0.05 to 0.10)
    """
    length: float = 70.0
    taper_start: float = 20.0
    sub_width: float = 50.0
    aperture: float = 40.0
    feed_width: float = 3.0
    feed_width_port: float | None = None   # None means no taper
    rate: float = 0.08
    substrate: str = "RO4350B"

    def __post_init__(self) -> None:
        if not 0.01 <= self.rate <= 0.5:
            raise ValueError(f"opening rate {self.rate} is outside any "
                             f"plausible range")
        if self.aperture >= self.sub_width:
            raise ValueError("aperture must fit inside the substrate width")
        if self.taper_start >= self.length:
            raise ValueError("taper must start before the aperture mouth")
        if self.feed_width_port is not None and self.feed_width_port <= 0:
            raise ValueError("feed_width_port must be positive")

    @property
    def w_port(self) -> float:
        """Strip width at the port; equals feed_width when untapered."""
        if self.feed_width_port is None:
            return self.feed_width
        return self.feed_width_port

    @property
    def sub(self) -> dict:
        return SUBSTRATES[self.substrate]

    @property
    def height(self) -> float:
        return self.sub["h"]

    @property
    def taper_length(self) -> float:
        return self.length - self.taper_start

    # --- the exponential taper -------------------------------------------

    @property
    def _coeffs(self) -> tuple[float, float]:
        """A and B such that the taper meets both endpoints.

        y(taper_start) = -feed_width/2   (inner edge of the overlapping feed)
        y(length)      = +aperture/2     (mouth)
        """
        e = np.exp(self.rate * self.taper_length)
        a_coef = (self.aperture / 2 + self.feed_width / 2) / (e - 1.0)
        b_coef = -self.feed_width / 2 - a_coef
        return float(a_coef), float(b_coef)

    def taper(self, x):
        """Inner edge of the upper arm at position x along the antenna."""
        x = np.asarray(x, float)
        a_coef, b_coef = self._coeffs
        return a_coef * np.exp(self.rate * (x - self.taper_start)) + b_coef

    # --- what actually governs the match ---------------------------------

    @property
    def growth(self) -> float:
        """The dimensionless opening parameter, rate x taper_length.

        This, not the rate alone, is what sets the shape of the flare. An
        exponential taper of a given total growth has the same profile however
        long it is stretched, so quoting an opening rate without a taper length
        - as proposal 2.3 does - does not specify the antenna.
        """
        return self.rate * self.taper_length

    @property
    def slot_start(self) -> float:
        """Distance past taper_start at which the two inner edges cross y = 0.

        Before this the arms still overlap and there is no slot at all; the
        radiating flare only begins here.
        """
        a_coef, b_coef = self._coeffs
        return float(np.log(-b_coef / a_coef) / self.rate)

    @property
    def flare_length(self) -> float:
        """Length over which the slot actually opens, mm."""
        return self.taper_length - self.slot_start

    @property
    def flare_ratio(self) -> float:
        """Flare length divided by aperture: the design number that matters.

        Below about 1 the slot opens over a distance shorter than its own
        mouth, an opening angle above sixty degrees, and the wave reflects at
        the mouth instead of radiating - the antenna becomes a resonator.
        Well-behaved tapered slots sit near 1.5 to 2.
        """
        return self.flare_length / self.aperture

    def taper_points(self, n: int = 60) -> np.ndarray:
        """(n, 2) polyline along the inner taper, mouth-dense for smoothness."""
        # Cluster samples where the curve bends hardest, at the mouth.
        t = np.linspace(0.0, 1.0, n) ** 0.7
        x = self.taper_start + t * self.taper_length
        return np.column_stack([x, self.taper(x)])

    @property
    def _outer_coeffs(self) -> tuple[float, float]:
        """A and B for the outer edge of the arm.

        y(taper_start) = +feed_width/2   (edge of the feed strip)
        y(length)      = +sub_width/2    (substrate edge at the mouth)
        """
        e = np.exp(self.rate * self.taper_length)
        a_coef = (self.sub_width / 2 - self.feed_width / 2) / (e - 1.0)
        b_coef = self.feed_width / 2 - a_coef
        return float(a_coef), float(b_coef)

    def outer(self, x):
        """Outer edge of the arm, if it were curved rather than stepped.

        Retained for reference, and NOT used by upper_arm. Curving the outer
        edge at the same opening rate as the inner one was tried and made
        matters much worse - the matched band collapsed from about 1.7 GHz to
        0.25 GHz and the mean in-band return loss went from -12.9 dB to
        -5.8 dB.

        The reason is that at equal rates the two edges stay roughly parallel,
        so the arm becomes a thin curved strip about 3 mm wide rather than a
        broad flare. In an antipodal Vivaldi the arm is a broad conductor; it
        is the *slot between* the two inner edges that tapers. Taking the outer
        edge out to the substrate edge is what makes the arm broad, and is what
        published designs do.
        """
        x = np.asarray(x, float)
        a_coef, b_coef = self._outer_coeffs
        return a_coef * np.exp(self.rate * (x - self.taper_start)) + b_coef

    def outer_points(self, n: int = 60) -> np.ndarray:
        """(n, 2) polyline along the outer edge, mouth-dense."""
        t = np.linspace(0.0, 1.0, n) ** 0.7
        x = self.taper_start + t * self.taper_length
        return np.column_stack([x, self.outer(x)])

    # --- conductor outlines ----------------------------------------------

    def upper_arm(self, n: int = 60) -> np.ndarray:
        """Closed polygon for the arm on the top face, in (x, y) mm.

        Two distinct sections, and keeping them distinct is the whole point:

          x < taper_start   a strip of exactly feed_width, centred on y = 0.
                            Both arms are identical here and sit face to face
                            across the substrate, forming the parallel-strip
                            line that feeds the antenna.
          x > taper_start   the arm flares. Its inner edge follows the
                            exponential taper; its outer edge steps out to the
                            substrate edge.

        The outer edge must step out **at taper_start, not at x = 0**. Running
        it back to the feed edge makes each arm as tall as half the board where
        the port drives it, so the port sees two large overlapping plates
        instead of a transmission line. The antenna then behaves as a resonant
        structure rather than a travelling-wave taper: measured symptoms were a
        matched band of about 1 GHz instead of an octave, a band that wandered
        erratically with geometry, and - decisively - a match that got *worse*
        as the aperture and length were increased.
        """
        half_feed = self.feed_width / 2
        half_port = self.w_port / 2
        pts = [(0.0, -half_port)]
        pts += [tuple(p) for p in self.taper_points(n)]
        pts += [(self.length, self.sub_width / 2),
                (self.taper_start, self.sub_width / 2),
                (self.taper_start, half_feed),
                (0.0, half_port)]
        return np.array(pts, float)

    def lower_arm(self, n: int = 60) -> np.ndarray:
        """The bottom-face arm: the upper arm mirrored in y."""
        arm = self.upper_arm(n).copy()
        arm[:, 1] *= -1.0
        return arm

    # --- predicted behaviour ---------------------------------------------

    def cutoff_frequency(self) -> float:
        """Low-frequency limit, Hz.

        A tapered-slot antenna stops radiating efficiently when the aperture
        falls below about half a wavelength in the effective medium.
        """
        eps_eff = (self.sub["eps_r"] + 1.0) / 2.0
        return 299_792_458.0 / (2 * self.aperture * 1e-3 * np.sqrt(eps_eff))

    def summary(self) -> str:
        a_coef, b_coef = self._coeffs
        return (f"{self.substrate} (eps_r {self.sub['eps_r']}, "
                f"tan_d {self.sub['tan_d']}, h {self.height} mm)\n"
                f"  {self.length:g} x {self.sub_width:g} mm, aperture "
                f"{self.aperture:g} mm, rate {self.rate:g}/mm\n"
                f"  taper y = {a_coef:.4f} exp({self.rate:g} x') "
                f"{b_coef:+.4f}\n"
                f"  predicted low cutoff {self.cutoff_frequency()/1e9:.2f} GHz")
