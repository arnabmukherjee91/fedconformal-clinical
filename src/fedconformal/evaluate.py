"""
Evaluation metrics for conformal prediction (Section 3 of the paper).

    * empirical marginal coverage
    * average prediction-set size
    * size-stratified coverage (SSC)  -- a conditional-coverage diagnostic
    * feature-stratified coverage (FSC) -- coverage within groups (here: site)
    * the analytic Beta distribution of coverage (Vovk), used to draw the
      "is my observed coverage within normal fluctuation?" band.

These let attendees *check* that an implementation is correct and, crucially,
*detect* when coverage silently breaks under site shift.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import beta as beta_dist


def coverage(sets: list[np.ndarray], labels: np.ndarray) -> float:
    """Fraction of test points whose true label is in the prediction set."""
    labels = np.asarray(labels)
    hits = [int(labels[i] in s) for i, s in enumerate(sets)]
    return float(np.mean(hits)) if hits else float("nan")


def per_point_covered(sets: list[np.ndarray], labels: np.ndarray) -> np.ndarray:
    labels = np.asarray(labels)
    return np.array([int(labels[i] in s) for i, s in enumerate(sets)], dtype=int)


def set_sizes(sets: list[np.ndarray]) -> np.ndarray:
    return np.array([len(s) for s in sets], dtype=int)


def average_set_size(sets: list[np.ndarray]) -> float:
    s = set_sizes(sets)
    return float(s.mean()) if len(s) else float("nan")


def size_stratified_coverage(sets: list[np.ndarray], labels: np.ndarray) -> dict[int, dict]:
    """Coverage stratified by prediction-set size (SSC metric, Section 3.1).

    Returns a dict {set_size: {"n":, "coverage":}}. A well-calibrated *adaptive*
    procedure keeps coverage ~ 1-alpha within every size bin.
    """
    sizes = set_sizes(sets)
    covered = per_point_covered(sets, labels)
    out = {}
    for k in sorted(set(sizes.tolist())):
        mask = sizes == k
        out[int(k)] = {
            "n": int(mask.sum()),
            "coverage": float(covered[mask].mean()) if mask.any() else float("nan"),
        }
    return out


def feature_stratified_coverage(
    sets: list[np.ndarray], labels: np.ndarray, groups: np.ndarray
) -> dict:
    """Coverage within each group (FSC metric, Section 3.1 / Eq. 8).

    In the workshop ``groups`` is the site id, so this directly measures whether
    a globally-calibrated conformal predictor covers *each hospital* at the
    target rate -- the group-balanced coverage property.
    """
    groups = np.asarray(groups)
    covered = per_point_covered(sets, labels)
    out = {}
    for g in np.unique(groups):
        mask = groups == g
        out[g] = {
            "n": int(mask.sum()),
            "coverage": float(covered[mask].mean()) if mask.any() else float("nan"),
        }
    return out


def class_conditional_coverage(sets: list[np.ndarray], labels: np.ndarray,
                               n_classes: int | None = None) -> dict:
    """Coverage within each true class (Section 4.2, class-balanced coverage).

    Returns {class_index: {"n":, "coverage":}}. For a good multiclass conformal
    procedure this should be >= 1-alpha for every class; rare classes are where
    it tends to break.
    """
    labels = np.asarray(labels)
    covered = per_point_covered(sets, labels)
    K = n_classes or int(labels.max() + 1)
    out = {}
    for c in range(K):
        mask = labels == c
        out[c] = {
            "n": int(mask.sum()),
            "coverage": float(covered[mask].mean()) if mask.any() else float("nan"),
        }
    return out


def coverage_beta_interval(n_cal: int, alpha: float, level: float = 0.95) -> tuple[float, float]:
    """Central `level` interval of the coverage distribution for a given n_cal.

    Conditional on the calibration set, coverage ~ Beta(n+1-l, l) with
    l = floor((n+1) * alpha)  (Vovk; Section 3.2). Useful to draw a
    'benign fluctuation' band around 1-alpha so attendees can judge whether an
    observed coverage drop is real or noise.
    """
    l = int(np.floor((n_cal + 1) * alpha))
    a = n_cal + 1 - l
    b = max(l, 1)
    lo = beta_dist.ppf((1 - level) / 2, a, b)
    hi = beta_dist.ppf(1 - (1 - level) / 2, a, b)
    return float(lo), float(hi)


def evaluate_all(
    sets: list[np.ndarray],
    labels: np.ndarray,
    groups: np.ndarray | None = None,
) -> dict:
    """Convenience bundle of the key metrics."""
    res = {
        "coverage": coverage(sets, labels),
        "avg_set_size": average_set_size(sets),
        "ssc": size_stratified_coverage(sets, labels),
    }
    if groups is not None:
        res["fsc"] = feature_stratified_coverage(sets, labels, groups)
    return res
