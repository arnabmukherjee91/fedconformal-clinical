"""
A tiny, transparent federated-learning simulator (FedAvg).

We deliberately avoid heavyweight FL frameworks. Everything is NumPy so
workshop attendees can watch every step of federated training and see exactly
how site heterogeneity enters:

    * `LogisticModel` -- L2-regularized *binary* logistic regression.
    * `SoftmaxModel`  -- L2-regularized *multinomial* (softmax) logistic
                         regression, for K > 2 classes (e.g. the chest-pain task).
    * `local_train`   -- train one site's model for E local epochs (works with
                         either model via a common `grad` / param interface).
    * `federated_averaging` -- the FedAvg loop: broadcast global weights, each
                               site takes local steps, the server averages the
                               updated weights (weighted by n_k). Picks the right
                               model automatically from the number of classes.

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


def _softmax(Z: np.ndarray) -> np.ndarray:
    Z = Z - Z.max(axis=1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(axis=1, keepdims=True)


# ----------------------------------------------------------------------------
# Binary logistic model
# ----------------------------------------------------------------------------

@dataclass
class LogisticModel:
    """Binary logistic regression with an explicit weight vector + bias."""

    w: np.ndarray = None
    b: float = 0.0
    l2: float = 1e-2

    n_classes = 2

    def init(self, d: int) -> "LogisticModel":
        self.w = np.zeros(d)
        self.b = 0.0
        return self

    def logits(self, X: np.ndarray) -> np.ndarray:
        return X @ self.w + self.b

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """(n, 2) probability matrix [P(y=0), P(y=1)]."""
        p1 = _sigmoid(self.logits(X))
        return np.column_stack([1 - p1, p1])

    def grad(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        n = len(y)
        p = _sigmoid(self.logits(X))
        err = p - y
        gw = X.T @ err / n + self.l2 * self.w
        gb = float(err.mean())
        return np.concatenate([gw, [gb]])

    def get_params(self) -> np.ndarray:
        return np.concatenate([self.w, [self.b]])

    def set_params(self, theta: np.ndarray) -> "LogisticModel":
        self.w = theta[:-1].copy()
        self.b = float(theta[-1])
        return self

    def copy(self) -> "LogisticModel":
        m = LogisticModel(l2=self.l2)
        m.w = None if self.w is None else self.w.copy()
        m.b = self.b
        return m


# ----------------------------------------------------------------------------
# Multinomial (softmax) logistic model
# ----------------------------------------------------------------------------

@dataclass
class SoftmaxModel:
    """Multinomial logistic regression: weight matrix (d, K) + bias (K,)."""

    W: np.ndarray = None
    b: np.ndarray = None
    l2: float = 1e-2
    K: int = 2

    def init(self, d: int, K: int | None = None) -> "SoftmaxModel":
        if K is not None:
            self.K = K
        self.W = np.zeros((d, self.K))
        self.b = np.zeros(self.K)
        return self

    @property
    def n_classes(self) -> int:
        return self.K

    def logits(self, X: np.ndarray) -> np.ndarray:
        return X @ self.W + self.b

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """(n, K) softmax probability matrix."""
        return _softmax(self.logits(X))

    def grad(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        n = len(y)
        P = self.predict_proba(X)
        Y = np.zeros_like(P)
        Y[np.arange(n), y] = 1.0
        err = P - Y                                  # (n, K)
        gW = X.T @ err / n + self.l2 * self.W        # (d, K)
        gb = err.mean(axis=0)                        # (K,)
        return np.concatenate([gW.ravel(), gb])

    def get_params(self) -> np.ndarray:
        return np.concatenate([self.W.ravel(), self.b])

    def set_params(self, theta: np.ndarray) -> "SoftmaxModel":
        d = self.W.shape[0]
        self.W = theta[: d * self.K].reshape(d, self.K).copy()
        self.b = theta[d * self.K:].copy()
        return self

    def copy(self) -> "SoftmaxModel":
        m = SoftmaxModel(l2=self.l2, K=self.K)
        m.W = None if self.W is None else self.W.copy()
        m.b = None if self.b is None else self.b.copy()
        return m


# ----------------------------------------------------------------------------
# Model factory + generic local training
# ----------------------------------------------------------------------------

def make_model(d: int, n_classes: int, l2: float = 1e-2):
    """Return an initialized model appropriate for the number of classes."""
    if n_classes <= 2:
        return LogisticModel(l2=l2).init(d)
    return SoftmaxModel(l2=l2, K=n_classes).init(d)


def local_train(model, X: np.ndarray, y: np.ndarray, epochs: int = 25,
                lr: float = 0.3):
    """Full-batch gradient descent on a copy of ``model`` (any model exposing
    ``grad`` / ``get_params`` / ``set_params``)."""
    m = model.copy()
    if getattr(m, "w", "x") is None or getattr(m, "W", "x") is None:
        # (re)initialize if the passed model has no weights yet
        d = X.shape[1]
        if isinstance(m, SoftmaxModel):
            m.init(d)
        else:
            m.init(d)
    for _ in range(epochs):
        theta = m.get_params()
        g = m.grad(X, y)
        m.set_params(theta - lr * g)
    return m


def _cross_entropy(model, X, y) -> float:
    P = model.predict_proba(X)
    eps = 1e-9
    return float(-np.mean(np.log(P[np.arange(len(y)), y] + eps)))


@dataclass
class FedResult:
    global_model: object
    history: list = field(default_factory=list)     # per-round list of dicts


def _infer_n_classes(sites, names) -> int:
    return int(max(int(sites[n].y.max()) for n in names) + 1)


def federated_averaging(
    sites: dict[str, SiteData],
    rounds: int = 30,
    local_epochs: int = 3,
    lr: float = 0.3,
    l2: float = 1e-2,
    train_sites: list[str] | None = None,
    n_classes: int | None = None,
    seed: int = 0,
) -> FedResult:
    """Run FedAvg across the given sites and return the global model.

    The model type (binary logistic vs. multinomial softmax) is chosen from the
    number of classes, inferred from the data unless ``n_classes`` is given.

    ``train_sites`` selects which sites participate in training; holding a site
    out mimics external validation / covariate shift.
    """
    names = train_sites or list(sites.keys())
    d = sites[names[0]].X.shape[1]
    K = n_classes or _infer_n_classes(sites, names)

    global_model = make_model(d, K, l2=l2)
    sizes = np.array([sites[n].n for n in names], dtype=float)
    weights = sizes / sizes.sum()

    history = []
    for r in range(rounds):
        local_params = []
        for name in names:
            sd = sites[name]
            local = local_train(global_model, sd.X, sd.y, epochs=local_epochs, lr=lr)
            local_params.append(local.get_params())
        new_theta = np.average(np.vstack(local_params), axis=0, weights=weights)
        global_model.set_params(new_theta)

        round_log = {"round": r}
        for name in names:
            sd = sites[name]
            round_log[f"loss_{name}"] = _cross_entropy(global_model, sd.X, sd.y)
        history.append(round_log)

    return FedResult(global_model=global_model, history=history)


def train_centralized(
    sites: dict[str, SiteData],
    train_sites: list[str] | None = None,
    epochs: int = 300,
    lr: float = 0.3,
    l2: float = 1e-2,
    n_classes: int | None = None,
):
    """Pool the training sites and train one model (the non-federated baseline)."""
    names = train_sites or list(sites.keys())
    X = np.vstack([sites[n].X for n in names])
    y = np.concatenate([sites[n].y for n in names])
    K = n_classes or _infer_n_classes(sites, names)
    model = make_model(X.shape[1], K, l2=l2)
    return local_train(model, X, y, epochs=epochs, lr=lr)
