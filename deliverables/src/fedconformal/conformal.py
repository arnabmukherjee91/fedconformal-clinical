r"""
Split conformal prediction for binary / multiclass classifiers.

This module implements the core methods from Angelopoulos & Bates,
"A Gentle Introduction to Conformal Prediction and Distribution-Free
Uncertainty Quantification" (arXiv:2107.07511), specialized to the tabular
clinical setting used in the workshop:

    * `split_conformal_quantile`  -- the conformal quantile \hat q (Eq. 1-2)
    * `LACPredictor`  -- Least-Ambiguous set-valued classifier
                         (a.k.a. "softmax score", score s = 1 - f(x)_y)
    * `APSPredictor`  -- Adaptive Prediction Sets (Romano et al. 2020; Eq. 3)

Both predictors return *label sets* (subsets of {0, 1}) that are guaranteed to
contain the true label with probability >= 1 - alpha, *provided calibration and
test data are exchangeable*. The workshop's punchline is what happens to that
guarantee when they are NOT exchangeable -- i.e. when the calibration site and
the deployment site differ.

Everything here is plain NumPy so attendees can read every line.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ----------------------------------------------------------------------------
# The conformal quantile
# ----------------------------------------------------------------------------

def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    r"""Finite-sample-corrected (1 - alpha) quantile of calibration scores.

    Implements  \hat q = the  ceil((n+1)(1-alpha)) / n  empirical quantile
    of the calibration scores (Eq. 1 in the paper). Returns +inf when the
    correction level exceeds 1 (too few calibration points for the requested
    alpha), which correctly yields the full label set.
    """
    scores = np.asarray(scores, dtype=float)
    n = len(scores)
    if n == 0:
        return np.inf
    level = np.ceil((n + 1) * (1 - alpha)) / n
    if level >= 1.0:
        return np.inf
    return float(np.quantile(scores, level, method="higher"))


# ----------------------------------------------------------------------------
# Score functions
# ----------------------------------------------------------------------------

def lac_scores(probs: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """LAC / 'softmax' nonconformity score:  s_i = 1 - f(x_i)_{y_i}.

    High when the model puts low probability on the true class (Section 1).
    """
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels)
    n = len(labels)
    return 1.0 - probs[np.arange(n), labels]


def aps_scores(probs: np.ndarray, labels: np.ndarray, rng: np.random.Generator | None = None,
               randomize: bool = True) -> np.ndarray:
    """Adaptive Prediction Sets nonconformity score (Eq. 3 in the paper).

    For each row, sort classes from most to least probable and accumulate the
    softmax mass up to and including the true class. Optional randomized
    tie-breaking (Romano et al. 2020) gives exact coverage.
    """
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels)
    n, K = probs.shape
    order = np.argsort(-probs, axis=1)                 # most -> least likely
    sorted_p = np.take_along_axis(probs, order, axis=1)
    cum = np.cumsum(sorted_p, axis=1)
    # rank (0-based) of the true label within the sorted order
    rank_of_true = np.argmax(order == labels[:, None], axis=1)
    cum_incl = cum[np.arange(n), rank_of_true]         # mass up to & incl true class
    p_true = probs[np.arange(n), labels]
    if randomize:
        rng = rng or np.random.default_rng()
        u = rng.uniform(size=n)
        scores = cum_incl - u * p_true
    else:
        scores = cum_incl
    return scores


# ----------------------------------------------------------------------------
# Predictors
# ----------------------------------------------------------------------------

@dataclass
class LACPredictor:
    """Least-Ambiguous set-valued Classifier (split conformal, LAC score).

    Usage::

        cp = LACPredictor(alpha=0.1).calibrate(cal_probs, cal_labels)
        sets = cp.predict_set(test_probs)     # list of arrays of labels
    """

    alpha: float = 0.1
    qhat: float = np.nan

    def calibrate(self, cal_probs: np.ndarray, cal_labels: np.ndarray) -> "LACPredictor":
        scores = lac_scores(cal_probs, cal_labels)
        self.qhat = conformal_quantile(scores, self.alpha)
        return self

    def predict_set(self, probs: np.ndarray) -> list[np.ndarray]:
        probs = np.asarray(probs, dtype=float)
        include = (1.0 - probs) <= self.qhat           # class kept if 1-f(x)_y <= qhat
        return [np.flatnonzero(row) for row in include]


@dataclass
class APSPredictor:
    """Adaptive Prediction Sets predictor (split conformal, APS score)."""

    alpha: float = 0.1
    randomize: bool = True
    seed: int = 0
    qhat: float = np.nan

    def calibrate(self, cal_probs: np.ndarray, cal_labels: np.ndarray) -> "APSPredictor":
        rng = np.random.default_rng(self.seed)
        scores = aps_scores(cal_probs, cal_labels, rng=rng, randomize=self.randomize)
        self.qhat = conformal_quantile(scores, self.alpha)
        return self

    def predict_set(self, probs: np.ndarray) -> list[np.ndarray]:
        probs = np.asarray(probs, dtype=float)
        n, K = probs.shape
        rng = np.random.default_rng(self.seed + 1)
        order = np.argsort(-probs, axis=1)
        sorted_p = np.take_along_axis(probs, order, axis=1)
        cum = np.cumsum(sorted_p, axis=1)
        sets = []
        for i in range(n):
            if self.randomize:
                u = rng.uniform()
                # include classes until cumulative-minus-random-fraction exceeds qhat
                incl = cum[i] - u * sorted_p[i] <= self.qhat
            else:
                incl = cum[i] <= self.qhat
            # always keep at least the top class to avoid empty sets
            incl[0] = True
            sets.append(np.sort(order[i][incl]))
        return sets


def sets_to_indicator(sets: list[np.ndarray], K: int) -> np.ndarray:
    """Convert a list of label arrays into an (n, K) 0/1 membership matrix."""
    ind = np.zeros((len(sets), K), dtype=int)
    for i, s in enumerate(sets):
        ind[i, s] = 1
    return ind
