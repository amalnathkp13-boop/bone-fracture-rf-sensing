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
    feed_width: float = 1.74      # 50 ohm microstrip on RO4350B
    feed_len: float = 8.0         # microstrip section before the ground taper
    feed_width_port: float | None = None   # None means no taper
    rate: float = 0.08
    substrate: str = "RO4350B"
    pad_gap: float | None = None  # coplanar ground pads at the feed; None = none
    pad_width: float = 5.0        # how far each pad extends outward, mm
    via_d: float = 0.6            # via diameter, mm
    via_pitch: float = 2.0        # via spacing along the pad, mm
    n_corrugations: int = 0       # slots in the outer edge; 0 disables
    corr_depth: float = 8.0       # mm, inward from the substrate edge
    corr_width: float = 4.0       # mm, along the antenna axis

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
        pts += [(self.length, self.sub_width / 2)]
        pts += self._outer_edge()
        pts += [(self.taper_start, self.sub_width / 2),
                (self.taper_start, half_feed),
                (0.0, half_port)]
        return np.array(pts, float)

    def _outer_edge(self) -> list:
        """Outer edge from the mouth back toward taper_start, with slots.

        Rectangular corrugations cut inward from the substrate edge. They
        lengthen the current path along the outer edge, which is the standard
        remedy when a tapered slot ripples at the bottom of its band: edge
        currents there are what make the input impedance oscillate. Measured
        before adding them, Re(Zin) was 117 ohm at 3.0 GHz against 24.5 ohm at
        4.0 GHz, with the match failing at both.

        Returns an empty list when n_corrugations is 0, leaving a plain edge.
        """
        if self.n_corrugations <= 0:
            return []
        half = self.sub_width / 2
        inner = half - self.corr_depth
        if inner <= self.aperture / 2:
            raise ValueError(
                f"corrugation depth {self.corr_depth} mm cuts past the "
                f"aperture edge; the arm is only "
                f"{half - self.aperture / 2:g} mm wide")
        # Spread over the outer part of the flare, where the arm is widest.
        x0 = self.taper_start + 0.3 * self.taper_length
        centres = np.linspace(x0, self.length - self.corr_width,
                              self.n_corrugations)
        pts = []
        for xc in centres[::-1]:            # walking back from the mouth
            a, b = xc + self.corr_width / 2, xc - self.corr_width / 2
            pts += [(float(a), half), (float(a), float(inner)),
                    (float(b), float(inner)), (float(b), half)]
        return pts

    def lower_arm(self, n: int = 60) -> np.ndarray:
        """The bottom-face arm as a plain mirror of the top.

        This is the *symmetric* form: both faces carry an identical strip that
        flares the opposite way, so the feed is a parallel-strip line driven
        directly at the board edge. It was the first topology modelled and it
        does not work - the input impedance swings from 18 to 133 ohm across
        3-11 GHz because nothing transitions the 50 ohm source onto the line.

        Kept for comparison. `ground_arm` is the topology actually used.
        """
        arm = self.upper_arm(n).copy()
        arm[:, 1] *= -1.0
        return arm

    # --- optional coplanar ground pads at the feed ------------------------

    def ground_pads(self):
        """Two top-face pads flanking the trace, for a top-ground-tab SMA.

        Some end-launch connectors ground through tabs that sit on the TOP
        face either side of the signal pin, so they need copper there. Adding
        it turns the feed from microstrip into grounded coplanar waveguide and
        pulls the impedance down, which is why the gap matters: coupling to the
        coplanar ground falls away once the gap exceeds roughly three substrate
        heights, here about 2.3 mm.

        Returns [] when pad_gap is None, which is the plain microstrip launch
        the antenna was validated with.
        """
        if self.pad_gap is None:
            return []
        inner = self.feed_width / 2 + self.pad_gap
        outer = inner + self.pad_width
        return [[(0.0, inner), (self.feed_len, inner),
                 (self.feed_len, outer), (0.0, outer)],
                [(0.0, -inner), (self.feed_len, -inner),
                 (self.feed_len, -outer), (0.0, -outer)]]

    def via_positions(self):
        """Stitching vias tying the top pads to the ground plane.

        Without them the pads are floating copper beside the feed, which is
        worse than no pads at all: an isolated conductor next to a transmission
        line is a resonator, not a ground.
        """
        if self.pad_gap is None:
            return []
        centre = self.feed_width / 2 + self.pad_gap + self.pad_width / 2
        n = max(2, int(self.feed_len // self.via_pitch))
        xs = np.linspace(self.via_pitch / 2,
                         self.feed_len - self.via_pitch / 2, n)
        return [(float(x), float(sy * centre))
                for x in xs for sy in (1.0, -1.0)]

    def ground_taper(self, x):
        """Upper edge of the ground plane through the balun section.

        Elliptical rather than linear: it leaves the full ground plane and
        meets the strip tangentially at both ends, so neither junction is a
        discontinuity. A linear taper corners at both joints and reflects.
        """
        x = np.asarray(x, float)
        t = np.clip((x - self.feed_len) / max(self.balun_length, 1e-12), 0, 1)
        # Quarter ellipse from (0, sub_width/2) to (1, feed_width/2).
        return (self.feed_width / 2
                + (self.sub_width / 2 - self.feed_width / 2)
                * np.sqrt(np.clip(1.0 - t * t, 0.0, None)))

    @property
    def balun_length(self) -> float:
        """Length of the microstrip-to-parallel-strip transition."""
        return self.taper_start - self.feed_len

    def ground_arm(self, n: int = 60) -> np.ndarray:
        """Bottom-face conductor: ground plane, balun taper, then the flare.

        The classic antipodal Vivaldi (Gazit) in three sections:

          x < feed_len              full ground plane under a narrow top strip,
                                    i.e. an ordinary 50 ohm microstrip
          feed_len .. taper_start   the ground's upper edge tapers in to meet
                                    the strip width - this is the balun, and it
                                    is what converts the asymmetric microstrip
                                    mode into the symmetric parallel-strip mode
                                    gradually rather than abruptly
          x > taper_start           flares downward, mirroring the top arm

        The lower edge stays at the board edge throughout: the ground is only
        reshaped from above. Omitting the balun entirely was the defect that
        left the input impedance swinging by an order of magnitude.
        """
        if self.balun_length <= 0:
            raise ValueError("feed_len must be shorter than taper_start")
        half = self.sub_width / 2
        xs = np.linspace(self.feed_len, self.taper_start, max(8, n // 3))
        pts = [(0.0, half), (self.feed_len, half)]
        pts += [(float(x), float(y)) for x, y in
                zip(xs, self.ground_taper(xs))]
        # Mirror of the top arm inner taper: flares downward.
        pts += [(float(x), float(-y)) for x, y in self.taper_points(n)]
        pts += [(self.length, -half)]
        pts += [(x, -y) for x, y in self._outer_edge()]
        pts += [(self.taper_start, -half), (0.0, -half)]
        return np.array(pts, float)

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


# --- the design that works -------------------------------------------------

def uwb_3_11(substrate: str = "RO4350B", corrugations: int = 0) -> Vivaldi:
    """Best design reached for the 3-11 GHz sweep of proposal 2.2.

    Measured (openEMS, metal edges refined, PML_8):

        -10 dB match   4.35 to 12.00 GHz, contiguous
        mean in band   -14.9 dB over 3-11 GHz
        median Re(Zin) 41 ohm

    Everything from 5 to 11 GHz is below -10 dB. The shortfall is 3.0 to
    4.35 GHz, where the input impedance still ripples: 117 ohm at 3.0 GHz
    against 24.5 ohm at 4.0 GHz.

    Four things had to be right, and each was found by measurement rather than
    from proposal 2.3, which specifies only the opening rate:

    1. a microstrip feed with a tapered ground balun, not a bare parallel-strip
       line driven at the board edge. This alone took the match from 0.75 GHz
       to 2.75 GHz of coverage
    2. an aperture set from the FREE-SPACE half wavelength at the lowest
       frequency, c/(2*ap). Using the substrate's effective permittivity
       flatters it: 44 mm looks like 2.28 GHz that way but is really 3.41 GHz,
       above the band edge
    3. arms wide enough to carry current. At aperture 60 mm in a 70 mm board
       each arm is a 5 mm sliver; widening the board to 90 mm gave 15 mm arms
       and moved the band from 5.35-8.60 GHz to 4.35-12.00 GHz
    4. the mesh snapped and refined at every metal edge

    150 x 90 mm fits the 100 x 150 mm boards already in the proposal's bill of
    materials, so this costs nothing extra to fabricate.

    corrugations > 0 adds slots to the outer edges, the standard remedy for the
    remaining low-frequency ripple. **Measured here to be impractical, and not
    for the reason expected.**

    They cost nothing in mesh: 7.40 M cells either way, identical minimum cell
    and time step, because the slot edges fall inside refinement the flare
    already required.

    **The 40-hour convergence claim made here was wrong, and both halves of it
    were wrong.** It read: the slots ring by design, stored energy will not
    decay to -40 dB, the corrugated run was still going after 70 minutes at
    1,735 timesteps advancing 12 per 30 s against a 60,000 cap, extrapolating
    to about 40 hours. Retried in scripts/retry_corrugations.py:

    | run | converged | wall time |
    |---|---|---|
    | plain, -30 dB | timestep 6,608 | 578 s |
    | 4 slots x 4 mm | timestep 6,972 | 601 s |
    | 6 slots x 6 mm | timestep 7,952 | 738 s |

    Corrugations converge in 4% more time than plain, not 40 hours. The
    original run advanced at 0.4 timesteps/s where this machine does 11 on the
    identical mesh, so it was starved of CPU, not ringing. A 28x speed anomaly
    should have been read as a broken run rather than a property of the
    geometry.

    They are still not the fix, but now for a measured reason rather than an
    abandoned one. 4 slots x 4 mm moves S11 at 3.0 GHz from -6.61 to -6.41 dB -
    the wrong way - and Re(Zin) from 113 to 111 ohm. 6 slots x 6 mm reaches
    94 ohm but breaks the contiguous band down to 8.97-12.00 GHz.

    The low-frequency shortfall is not edge-current resonance and not a cutoff.
    See docs/stage5-findings.md: there is a fully matched island at
    2.225-2.725 GHz reaching -33 dB, so the antenna radiates well below the
    stated band edge. What sits between is a mismatch, and the remedy is a feed
    transformer - scripts/tune_feed_taper.py.
    """
    w_feed = 1.74 if substrate == "RO4350B" else 3.08   # 50 ohm microstrip
    return Vivaldi(length=150.0, taper_start=20.0, feed_len=8.0,
                   aperture=60.0, sub_width=90.0, feed_width=w_feed,
                   rate=2.0 / 130.0, substrate=substrate,
                   n_corrugations=corrugations)
