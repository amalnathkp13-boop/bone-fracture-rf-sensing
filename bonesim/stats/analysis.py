"""Statistical analysis plan of proposal section 5.

Section 5 asks for these and says to write them down before looking at the data:

  1. primary endpoint: AUC for intact vs fractured, pooled across fracture
     types, at 6 mm overlay, with a bootstrap 95% interval
  2. secondary: AUC by kerf, AUC by overlay, smallest kerf detected at 80%
     sensitivity
  3. leave-one-specimen-out, every measurement from a bone entirely in one fold
  4. permutation test, 1000 label shuffles, empirical p-value
  5. repeatability across remounts
  6. Benjamini-Hochberg if more than one primary hypothesis
  7. negative results are reportable

One point needs care, because getting it wrong is the classic way to inflate a
result. **The detector is not trained.** It is a single scalar - peak over noise
floor - with no fitted parameters, so there is nothing for a training fold to
learn and a pooled leave-one-out AUC would equal the plain AUC.

What *is* chosen from data is the decision threshold. So the split here is
honest about which quantity each method applies to:

  AUC        threshold-free and untrained, so computed directly. No leakage
             exists to protect against.
  LOSO       applied to the threshold, which is the only trained quantity:
             pick it on five specimens, apply it to the sixth, pool the
             held-out decisions.
  bootstrap  resamples SPECIMENS, not measurements. Twenty-four acquisitions
             from one bone are not twenty-four independent samples, and
             resampling them would give a confidence interval several times
             too narrow.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Sample:
    """One detector score with everything needed to group it."""
    specimen: int
    state: str
    overlay: float
    kerf: float
    fractured: bool
    repeat: int
    score: float


def auc(scores, labels) -> float:
    """Area under the ROC curve, by the Mann-Whitney identity.

    Ties are counted as half, which matters here: a quantised detector can
    produce them and ignoring that biases the result upward.
    """
    scores = np.asarray(scores, float)
    labels = np.asarray(labels, bool)
    pos, neg = scores[labels], scores[~labels]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    diff = pos[:, None] - neg[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum())
                 / (pos.size * neg.size))


def roc_curve(scores, labels):
    """(fpr, tpr, thresholds), ordered by decreasing threshold."""
    scores = np.asarray(scores, float)
    labels = np.asarray(labels, bool)
    order = np.argsort(-scores)
    s, l = scores[order], labels[order]
    tp = np.cumsum(l)
    fp = np.cumsum(~l)
    tpr = tp / max(l.sum(), 1)
    fpr = fp / max((~l).sum(), 1)
    return (np.concatenate([[0], fpr]), np.concatenate([[0], tpr]),
            np.concatenate([[np.inf], s]))


def youden_threshold(scores, labels) -> float:
    """Threshold maximising sensitivity + specificity - 1."""
    fpr, tpr, thr = roc_curve(scores, labels)
    return float(thr[int(np.argmax(tpr - fpr))])


def bootstrap_auc_ci(samples, n_boot: int = 2000, alpha: float = 0.05,
                     seed: int = 0):
    """Percentile interval, resampling SPECIMENS.

    Resampling individual acquisitions would treat twenty-four measurements of
    one bone as twenty-four independent observations and return an interval
    several times too narrow. The specimen is the unit of replication, so the
    specimen is what gets resampled.
    """
    rng = np.random.default_rng(seed)
    by_spec: dict[int, list[Sample]] = {}
    for s in samples:
        by_spec.setdefault(s.specimen, []).append(s)
    ids = sorted(by_spec)
    out = []
    for _ in range(n_boot):
        drawn = rng.choice(ids, size=len(ids), replace=True)
        pool = [s for i in drawn for s in by_spec[i]]
        a = auc([s.score for s in pool], [s.fractured for s in pool])
        if np.isfinite(a):
            out.append(a)
    if not out:
        return float("nan"), float("nan")
    return (float(np.percentile(out, 100 * alpha / 2)),
            float(np.percentile(out, 100 * (1 - alpha / 2))))


def permutation_p(samples, n_perm: int = 1000, seed: int = 0):
    """Empirical p-value against a null built by shuffling labels.

    Labels are shuffled WITHIN each specimen. Shuffling globally would let a
    specimen whose scores happen to run high supply mostly positive labels,
    which breaks the pairing the design was built around and makes the null
    easier to beat than it should be.
    """
    rng = np.random.default_rng(seed)
    observed = auc([s.score for s in samples], [s.fractured for s in samples])
    by_spec: dict[int, list[Sample]] = {}
    for s in samples:
        by_spec.setdefault(s.specimen, []).append(s)

    null = []
    for _ in range(n_perm):
        sc, lb = [], []
        for group in by_spec.values():
            labels = np.array([g.fractured for g in group])
            rng.shuffle(labels)
            sc.extend(g.score for g in group)
            lb.extend(labels)
        null.append(auc(sc, lb))
    null = np.asarray(null)
    # +1 in numerator and denominator: an empirical p can never be exactly 0
    # with a finite number of shuffles, and reporting p = 0 would overstate it.
    p = (1 + int((null >= observed).sum())) / (1 + n_perm)
    return float(observed), float(p), null


def loso_decisions(samples):
    """Leave-one-specimen-out on the threshold, the only trained quantity.

    Returns (sensitivity, specificity, accuracy, per-specimen rows).
    """
    by_spec: dict[int, list[Sample]] = {}
    for s in samples:
        by_spec.setdefault(s.specimen, []).append(s)

    rows, tp = [], 0
    fp = fn = tn = 0
    for held in sorted(by_spec):
        train = [s for i, g in by_spec.items() if i != held for s in g]
        test = by_spec[held]
        thr = youden_threshold([s.score for s in train],
                               [s.fractured for s in train])
        a = b = c = d = 0
        for s in test:
            pred = s.score >= thr
            if s.fractured and pred: a += 1
            elif s.fractured: b += 1
            elif pred: c += 1
            else: d += 1
        tp += a; fn += b; fp += c; tn += d
        rows.append((held, thr, a, b, c, d))
    sens = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    acc = (tp + tn) / max(tp + tn + fp + fn, 1)
    return sens, spec, acc, rows


def wilson_interval(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a proportion.

    Proposal 5 asks for it by name, and rightly: the textbook normal interval
    misbehaves badly near 0 and 1, which is exactly where a good detector's
    sensitivity sits.
    """
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return float(centre - half), float(centre + half)


def icc(values_by_group) -> float:
    """Intraclass correlation, ICC(1,1): repeatability across remounts.

    1 means the repeats of a measurement agree perfectly and all the variance
    is between measurements; 0 means the repeats scatter as much as the
    measurements differ, so the method is not repeatable.
    """
    groups = [np.asarray(v, float) for v in values_by_group if len(v) > 1]
    if len(groups) < 2:
        return float("nan")
    k = min(len(g) for g in groups)
    m = np.array([g[:k] for g in groups])
    n = m.shape[0]
    grand = m.mean()
    ms_between = k * ((m.mean(axis=1) - grand) ** 2).sum() / (n - 1)
    ms_within = ((m - m.mean(axis=1, keepdims=True)) ** 2).sum() / (n * (k - 1))
    denom = ms_between + (k - 1) * ms_within
    return float((ms_between - ms_within) / denom) if denom > 0 else float("nan")


def benjamini_hochberg(pvalues, alpha: float = 0.05):
    """Return the boolean reject vector under BH control of the FDR."""
    p = np.asarray(pvalues, float)
    n = p.size
    order = np.argsort(p)
    thresh = alpha * (np.arange(1, n + 1) / n)
    passed = p[order] <= thresh
    reject = np.zeros(n, bool)
    if passed.any():
        cut = np.max(np.flatnonzero(passed))
        reject[order[:cut + 1]] = True
    return reject
