"""
A tiny, transparent federated-learning simulator (FedAvg).

We deliberately avoid heavyweight FL frameworks. Everything is NumPy so
workshop attendees can watch every step of federated training and see exactly
how site heterogeneity enters:

    * `LogisticModel`      -- L2-regularized logistic regression, trained by
                              full-batch gradient descent (weights are just a
                              vector, so averaging them is meaningful).
    * `local_train`        -- train one site's model for E local epochs.
    * `federated_averaging` -- the FedAvg loop: broadcast global weights, each
                               site takes local steps, server averages the
                               updated weights (weighted by n_k).

The point is not state-of-the-art accuracy; it is a model good enough that
conformal prediction on top of it tells a clear story about cross-site
uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .data import SiteData


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


@dataclass
class LogisticModel:
    """Binary logistic regression with an explicit weight vector + bias."""

    w: np.ndarray = None
    b: float = 0.0
    l2: float = 1e-2

    def init(self, d: int) -> "LogisticModel":
        self.w = np.zeros(d)
        self.b = 0.0
        return self

    def logits(self, X: np.ndarray) -> np.ndarray:
        return X @ self.w + self.b

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return an (n, 2) softmax-style probability matrix [P(y=0), P(y=1)].

        Two columns so the same object plugs straight into the multiclass
        conformal machinery.
        """
        p1 = _sigmoid(self.logits(X))
        return np.column_stack([1 - p1, p1])

    def copy(self) -> "LogisticModel":
        m = LogisticModel(l2=self.l2)
        m.w = None if self.w is None else self.w.copy()
        m.b = self.b
        return m

    # ------- parameter (un)packing, used by FedAvg -------
    def get_params(self) -> np.ndarray:
        return np.concatenate([self.w, [self.b]])

    def set_params(self, theta: np.ndarray) -> "LogisticModel":
        self.w = theta[:-1].copy()
        self.b = float(theta[-1])
        return self


def _grads(model: LogisticModel, X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    n = len(y)
    p = _sigmoid(model.logits(X))
    err = p - y
    gw = X.T @ err / n + model.l2 * model.w
    gb = float(err.mean())
    return gw, gb


def local_train(
    model: LogisticModel,
    X: np.ndarray,
    y: np.ndarray,
    epochs: int = 25,
    lr: float = 0.3,
) -> LogisticModel:
    """Full-batch gradient-descent training of a copy of ``model`` on one site."""
    m = model.copy()
    if m.w is None:
        m.init(X.shape[1])
    for _ in range(epochs):
        gw, gb = _grads(m, X, y)
        m.w -= lr * gw
        m.b -= lr * gb
    return m


@dataclass
class FedResult:
    global_model: LogisticModel
    history: list = field(default_factory=list)     # per-round list of dicts


def federated_averaging(
    sites: dict[str, SiteData],
    rounds: int = 30,
    local_epochs: int = 3,
    lr: float = 0.3,
    l2: float = 1e-2,
    train_sites: list[str] | None = None,
    seed: int = 0,
) -> FedResult:
    """Run FedAvg across the given sites and return the global model.

    Parameters
    ----------
    train_sites:
        Which sites participate in training. Holding a site *out* here lets the
        workshop show what happens when the federation never saw a hospital
        (the classic external-validation / covariate-shift scenario).
    """
    rng = np.random.default_rng(seed)
    names = train_sites or list(sites.keys())
    d = sites[names[0]].X.shape[1]

    global_model = LogisticModel(l2=l2).init(d)
    sizes = np.array([sites[n].n for n in names], dtype=float)
    weights = sizes / sizes.sum()

    history = []
    for r in range(rounds):
        local_params = []
        for name in names:
            sd = sites[name]
            local = local_train(global_model, sd.X, sd.y, epochs=local_epochs, lr=lr)
            local_params.append(local.get_params())
        # weighted average of the local parameter vectors
        new_theta = np.average(np.vstack(local_params), axis=0, weights=weights)
        global_model.set_params(new_theta)

        # log train loss per site for a learning-curve plot
        round_log = {"round": r}
        for name in names:
            sd = sites[name]
            p = _sigmoid(global_model.logits(sd.X))
            eps = 1e-9
            loss = -np.mean(sd.y * np.log(p + eps) + (1 - sd.y) * np.log(1 - p + eps))
            round_log[f"loss_{name}"] = float(loss)
        history.append(round_log)

    return FedResult(global_model=global_model, history=history)


def train_centralized(
    sites: dict[str, SiteData],
    train_sites: list[str] | None = None,
    epochs: int = 300,
    lr: float = 0.3,
    l2: float = 1e-2,
) -> LogisticModel:
    """Pool the training sites and train one model (the non-federated baseline)."""
    names = train_sites or list(sites.keys())
    X = np.vstack([sites[n].X for n in names])
    y = np.concatenate([sites[n].y for n in names])
    model = LogisticModel(l2=l2).init(X.shape[1])
    return local_train(model, X, y, epochs=epochs, lr=lr)
