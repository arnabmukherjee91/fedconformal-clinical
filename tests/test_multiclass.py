"""
Correctness checks for the multiclass (chest-pain) task and the softmax FedAvg
model. Run with:  pytest -q
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, conformal, evaluate as ev, federated


def _synthetic_multiclass(n, K=4, d=6, seed=0):
    """Well-specified softmax data so conformal coverage is ~ exact."""
    rng = np.random.default_rng(seed)
    W = rng.normal(size=(d, K))
    X = rng.normal(size=(n, d))
    logits = X @ W
    P = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
    y = np.array([rng.choice(K, p=p) for p in P])
    return P, y


def test_softmax_model_learns():
    P, y = _synthetic_multiclass(1500, K=4, seed=1)
    # train a softmax model directly on features == the probabilities' logits proxy
    rng = np.random.default_rng(0)
    X = rng.normal(size=(len(y), 5))
    # make X predictive of y by embedding class means
    means = rng.normal(size=(4, 5))
    X = means[y] + 0.6 * rng.normal(size=X.shape)
    m = federated.make_model(5, 4)
    m = federated.local_train(m, X, y, epochs=300, lr=0.4)
    acc = (m.predict_proba(X).argmax(1) == y).mean()
    assert acc > 0.6, f"softmax model failed to learn: acc={acc:.2f}"
    assert m.predict_proba(X).shape == (len(y), 4)


def test_aps_multiclass_marginal_coverage():
    P, y = _synthetic_multiclass(4000, K=4, seed=2)
    calP, teP = P[:2000], P[2000:]
    calY, teY = y[:2000], y[2000:]
    alpha = 0.1
    cp = conformal.APSPredictor(alpha=alpha, seed=0).calibrate(calP, calY)
    cov = ev.coverage(cp.predict_set(teP), teY)
    assert cov >= 1 - alpha - 0.03, f"APS 4-class coverage too low: {cov:.3f}"


def test_lac_multiclass_average_coverage():
    alpha = 0.1
    covs = []
    for seed in range(40):
        P, y = _synthetic_multiclass(1200, K=4, seed=seed)
        cp = conformal.LACPredictor(alpha=alpha).calibrate(P[:600], y[:600])
        covs.append(ev.coverage(cp.predict_set(P[600:]), y[600:]))
    assert abs(np.mean(covs) - (1 - alpha)) < 0.02, np.mean(covs)


def test_disease_task_loads_five_classes():
    """The default task ("disease") is the original 0-4 UCI severity target,
    not a binary collapse -- and every site's features must be fully imputed
    (no NaN survives ca/thal's heavy missingness outside Cleveland)."""
    sites = data.load_sites(task="disease")
    for s, sd in sites.items():
        assert sd.n_classes == 5
        assert set(np.unique(sd.y)).issubset({0, 1, 2, 3, 4})
        assert sd.X.shape[1] == 13
        assert np.isfinite(sd.X).all()
    assert set(np.unique(sites["cleveland"].y)) == {0, 1, 2, 3, 4}


def test_cp_task_loads_four_classes():
    sites = data.load_sites(task="cp")
    for s, sd in sites.items():
        assert sd.n_classes == 4
        assert set(np.unique(sd.y)).issubset({0, 1, 2, 3})
        assert sd.X.shape[1] == 12   # 13 clinical features minus cp


def test_federated_cp_runs():
    sites = data.load_sites(task="cp")
    fed = federated.federated_averaging(sites, rounds=15, local_epochs=2,
                                        train_sites=["cleveland", "hungarian", "va"])
    assert isinstance(fed.global_model, federated.SoftmaxModel)
    P = fed.global_model.predict_proba(sites["switzerland"].X)
    assert P.shape[1] == 4
    assert np.allclose(P.sum(1), 1.0, atol=1e-6)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
