"""Scalar detection metric (proposal 2.5 step 8).

"Do not eyeball it. Define a scalar detector, for example the peak-to-background
ratio within a region of interest along the detected bone line, and threshold
it. This gives you an ROC curve."

The ROI is a horizontal band around the cortical surface. Its depth is *not*
taken from the phantom: doing so would leak ground truth into the detector and
inflate every result. It is found from the image itself, from the brightest
continuous horizontal structure, exactly as an operator would.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..process.migrate import Image


@dataclass
class Detection:
    """Result of applying a scalar detector to a migrated image."""
    ratio_db: float          # the detector statistic
    x_peak: float            # m, along the bone axis
    z_peak: float            # m, depth
    z_bone: float            # m, depth of the detected bone line
    background_db: float


def find_bone_line(img: Image, z_min: float = 0.002) -> float:
    """Depth of the brightest laterally-continuous structure.

    A fracture is a localised bright spot; the bone surface is a line extended
    along x. Using the median across x rather than the mean rejects the
    fracture itself from the estimate of where the bone is.
    """
    env = img.envelope
    valid = img.z >= z_min
    profile = np.median(env[valid], axis=1)
    return float(img.z[valid][int(np.argmax(profile))])


def peak_to_background(img: Image, z_window: tuple[float, float] = (0.003, 0.020),
                       exclude: float = 0.008,
                       z_bone: float | None = None) -> Detection:
    """Peak-to-background ratio within an anatomical depth window.

    Section 2.5 step 8 asks for a region of interest "along the detected bone
    line". That cannot be done as written, for a reason worth stating:

      * after SVD there is no bone line. Being coherent along the scan axis is
        the definition of what SVD removes, and a specular reflection from the
        bone surface is coherent along the scan axis, so it goes with the skin.
      * before SVD the bone line cannot be found either. The skin reflection is
        roughly 20 dB stronger and its point-spread function, about 5 mm wide at
        this bandwidth, smears straight over the cortex. Searching for the
        brightest laterally-continuous structure returns the skin every time.

    So the region of interest is a fixed anatomical depth window instead. It is
    identical for every specimen and every acquisition, and therefore leaks no
    ground truth into the detector - which taking the depth from the phantom
    would have done, inflating every result in the study.

    z_window  depth range searched, m. Default 3-20 mm covers the plausible
              cortex depth of a superficial long bone under 3-10 mm of overlay.
    exclude   half-width around the peak excluded from the background estimate,
              m. Without it the peak contaminates its own reference.
    """
    env = img.envelope
    if z_bone is not None:      # explicit override, for sensitivity studies
        z_window = (z_bone - 0.004, z_bone + 0.004)

    rows = (img.z >= z_window[0]) & (img.z <= z_window[1])
    if not rows.any():
        raise ValueError(f"depth window {z_window} is empty for this grid")
    roi = env[rows]

    iz, ix = np.unravel_index(int(np.argmax(roi)), roi.shape)
    x_peak = float(img.x[ix])
    z_peak = float(img.z[rows][iz])
    peak = float(roi[iz, ix])

    far = np.abs(img.x - x_peak) > exclude
    if not far.any():
        raise ValueError("no background region left after exclusion")
    # Median, not mean: robust to any second scatterer inside the window.
    background = float(np.median(roi[:, far]))

    ratio = (20 * np.log10(peak / background) if background > 0 else np.inf)
    return Detection(ratio, x_peak, z_peak, z_peak,
                     20 * np.log10(background) if background > 0 else -np.inf)


def estimate_sample_noise(data) -> float:
    """Per-sample receiver noise std, estimated from the singular-value tail.

    For an m x n matrix of iid complex noise with standard deviation sigma, the
    singular values follow the Marchenko-Pastur law and the bulk sits near
    sigma * (sqrt(m) + sqrt(n)) / 2. The trailing half of the spectrum of a
    measured matrix is noise-dominated, because the physical content is
    concentrated in the leading components, so its median gives sigma without
    needing a separate noise-only acquisition.
    """
    s = np.linalg.svd(data.s11, compute_uv=False)
    m, n = data.s11.shape
    bulk = float(np.median(s[s.size // 2:]))
    return bulk / ((np.sqrt(m) + np.sqrt(n)) / 2)


def detect_snr(img: Image, data, z_window: tuple[float, float] = (0.003, 0.020)
               ) -> Detection:
    """Peak-to-noise ratio: the detector this project actually uses.

    Peak-to-background *within one image* was tried first, following section 2.5
    step 8, and it does not work here. Migration of a single point scatterer
    across a finite aperture smears energy over the whole image, so a stronger
    target raises its own background almost as fast as it raises its peak. The
    statistic then compresses, and in testing it inverted: a 0.3 mm kerf scored
    higher than a 2.0 mm one, while the absolute peak correctly ordered them
    39.5 / 58.5 / 84.8 / 89.1 against 0.60 for an intact limb. Widening the
    exclusion zone did not fix it, because the smear is global.

    The peak is therefore referenced to the receiver noise floor instead, which
    does not scale with the target. Migration coherently sums n_freq * n_scan
    samples, so unit-modulus weighting grows the noise amplitude as the square
    root of that count. This is an ordinary radar SNR, and it is valid here
    because a SOL-calibrated S11 is an absolute reflection coefficient, not an
    arbitrary-gain quantity.
    """
    env = img.envelope
    rows = (img.z >= z_window[0]) & (img.z <= z_window[1])
    if not rows.any():
        raise ValueError(f"depth window {z_window} is empty for this grid")
    roi = env[rows]
    iz, ix = np.unravel_index(int(np.argmax(roi)), roi.shape)
    peak = float(roi[iz, ix])

    sigma = estimate_sample_noise(data)
    floor = sigma * np.sqrt(data.n_freq * data.n_scan)
    ratio = 20 * np.log10(peak / floor) if floor > 0 else np.inf
    return Detection(ratio, float(img.x[ix]), float(img.z[rows][iz]),
                     float(img.z[rows][iz]),
                     20 * np.log10(floor) if floor > 0 else -np.inf)
