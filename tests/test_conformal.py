"""
Correctness checks for the conformal machinery (Section 3.3 of the paper).

The central sanity check: on EXCHANGEABLE data, split-conformal coverage must be
>= 1 - alpha on average, and land inside the benign Beta fluctuation band. If
these fail, the implementation is wrong. Run with:  pytest -q
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import conformal, evaluate as ev


def _synthetic(n, K=3, seed=0):
    """Well-specified softmax data so coverage should be ~ exact."""
    rng = np.random.default_rng(seed)
    logits = rng.normal(size=(n, K))
    probs = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
    labels = np.array([rng.choice(K, p=p) for p in probs])
    return probs, labels


def test_quantile_inf_when_too_few():
    # alpha smaller than 1/(n+1) cannot be satisfied -> full set (inf quantile)
    assert conformal.conformal_quantile(np.array([0.2, 0.5]), alpha=0.01) == np.inf


def test_lac_marginal_coverage():
    probs, labels = _synthetic(4000, K=3, seed=1)
    cal_p, test_p = probs[:2000], probs[2000:]
    cal_y, test_y = labels[:2000], labels[2000:]
    alpha = 0.1
    cp = conformal.LACPredictor(alpha=alpha).calibrate(cal_p, cal_y)
    sets = cp.predict_set(test_p)
    cov = ev.coverage(sets, test_y)
    lo, hi = ev.coverage_beta_interval(len(cal_y), alpha, level=0.999)
    assert lo <= cov <= hi + 0.02, f"coverage {cov:.3f} outside [{lo:.3f},{hi:.3f}]"


def test_aps_marginal_coverage():
    probs, labels = _synthetic(4000, K=4, seed=2)
    cal_p, test_p = probs[:2000], probs[2000:]
    cal_y, test_y = labels[:2000], labels[2000:]
    alpha = 0.1
    cp = conformal.APSPredictor(alpha=alpha, seed=3).calibrate(cal_p, cal_y)
    sets = cp.predict_set(test_p)
    cov = ev.coverage(sets, test_y)
    assert cov >= 1 - alpha - 0.03, f"APS coverage too low: {cov:.3f}"


def test_average_coverage_over_trials():
    """Averaged over many splits, coverage should be very close to 1 - alpha."""
    alpha = 0.1
    covs = []
    for seed in range(50):
        probs, labels = _synthetic(1200, K=3, seed=seed)
        cp = conformal.LACPredictor(alpha=alpha).calibrate(probs[:600], labels[:600])
        sets = cp.predict_set(probs[600:])
        covs.append(ev.coverage(sets, labels[600:]))
    assert abs(np.mean(covs) - (1 - alpha)) < 0.02, np.mean(covs)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
