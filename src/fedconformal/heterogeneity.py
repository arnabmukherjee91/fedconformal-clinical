"""
Quantifying site-level heterogeneity BEFORE integrating data or models.

This is the conceptual heart of the workshop: interoperability lets data cross
institutional lines, but it does not tell you whether "cholesterol" or "disease
label" *mean* the same thing at each site. Here we provide simple, transparent
diagnostics that separate two very different phenomena:

  1. TRUE distributional shift        -- the underlying population really differs
                                          (e.g. a referral hospital sees sicker
                                          patients; higher disease prevalence).
  2. MEASUREMENT-INDUCED heterogeneity -- the *measurement process* differs
                                          (e.g. a site never records serum
                                          cholesterol, so it reads as 0).

The tools:
  * `feature_shift_table`   -- per-feature, per-site means/std vs. a reference.
  * `missingness_report`    -- fraction of "unrecorded" values per feature/site,
                               a fingerprint of measurement heterogeneity.
  * `js_divergence_matrix`  -- pairwise Jensen-Shannon divergence between sites
                               on a feature, a symmetric [0,1] shift score.
  * `label_shift_table`     -- prevalence P(y=1) per site (pure label shift).
  * `domain_classifier_auc` -- can a classifier tell which site a row came from?
                               AUC ~ 0.5 => sites look exchangeable; AUC ~ 1.0
                               => strong covariate shift (a single-number alarm).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import roc_auc_score

from .data import FEATURES, SITES


# ----------------------------------------------------------------------------
# Distributional descriptors
# ----------------------------------------------------------------------------

def label_shift_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-site disease prevalence P(y>0) -- the simplest form of shift."""
    rows = []
    for s in SITES:
        sub = df[df["site"] == s]
        rows.append({"site": s, "n": len(sub),
                     "prevalence": float((sub["target"] > 0).mean())})
    return pd.DataFrame(rows)


def missingness_report(df: pd.DataFrame, unrecorded_value=0,
                       features=("chol", "trestbps", "thalach")) -> pd.DataFrame:
    """Fraction of physiologically-implausible zeros per feature/site.

    A value of exactly 0 for cholesterol, resting blood pressure or maximum
    heart rate is not a real measurement -- it is the fingerprint of an
    *unrecorded* value. (We deliberately exclude features whose zero is clinically
    valid, e.g. ``oldpeak`` = 0 means a flat ST segment, not a missing value.)
    A feature that is 100% "unrecorded" at one site (Switzerland cholesterol) is
    the canonical measurement-induced heterogeneity.
    """
    rows = []
    for s in SITES:
        sub = df[df["site"] == s]
        row = {"site": s}
        for f in features:
            row[f] = float((sub[f] == unrecorded_value).mean())
        rows.append(row)
    return pd.DataFrame(rows).set_index("site")


def feature_shift_table(df: pd.DataFrame, feature: str, reference: str = "cleveland") -> pd.DataFrame:
    """Mean / std of one feature per site, plus a standardized difference vs.
    a reference site (Cohen's d style). Large |d| flags a shifted feature.
    """
    ref = df[df["site"] == reference][feature]
    ref_mu, ref_sd = ref.mean(), ref.std()
    rows = []
    for s in SITES:
        v = df[df["site"] == s][feature]
        pooled = np.sqrt((v.std() ** 2 + ref_sd ** 2) / 2) or 1.0
        rows.append({
            "site": s,
            "mean": float(v.mean()),
            "std": float(v.std()),
            "std_diff_vs_ref": float((v.mean() - ref_mu) / pooled),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Divergences
# ----------------------------------------------------------------------------

def _hist_prob(x: np.ndarray, bins: np.ndarray) -> np.ndarray:
    h, _ = np.histogram(x, bins=bins)
    h = h.astype(float)
    if h.sum() == 0:
        return np.ones_like(h) / len(h)
    return h / h.sum()


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence (base 2, in [0, 1]) between two distributions."""
    p = p + 1e-12
    q = q + 1e-12
    p /= p.sum()
    q /= q.sum()
    m = 0.5 * (p + q)

    def _kl(a, b):
        return float(np.sum(a * np.log2(a / b)))

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def js_divergence_matrix(df: pd.DataFrame, feature: str, bins: int = 15) -> pd.DataFrame:
    """Pairwise JS divergence between all sites for one feature.

    Excludes the unrecorded sentinel (0) so the divergence reflects the shape of
    the *measured* distribution, not the missingness (which the missingness
    report already captures separately).
    """
    vals = df.loc[df[feature] > 0, feature]
    edges = np.linspace(vals.min(), vals.max(), bins + 1)
    probs = {}
    for s in SITES:
        v = df.loc[(df["site"] == s) & (df[feature] > 0), feature].to_numpy()
        probs[s] = _hist_prob(v, edges)
    M = np.zeros((len(SITES), len(SITES)))
    for i, a in enumerate(SITES):
        for j, b in enumerate(SITES):
            M[i, j] = js_divergence(probs[a].copy(), probs[b].copy())
    return pd.DataFrame(M, index=SITES, columns=SITES)


# ----------------------------------------------------------------------------
# Domain classifier: a single-number covariate-shift alarm
# ----------------------------------------------------------------------------

def domain_classifier_auc(
    X_a: np.ndarray, X_b: np.ndarray, seed: int = 0
) -> float:
    """Train a classifier to distinguish site A rows from site B rows.

    Cross-validated AUC ~ 0.5 means the two sites are (feature-wise)
    indistinguishable -- exchangeable, conformal guarantees should transfer.
    AUC close to 1.0 means a model can perfectly tell them apart -- strong
    covariate shift, and a warning that a model/calibration from one will not
    transfer to the other.
    """
    X = np.vstack([X_a, X_b])
    y = np.concatenate([np.zeros(len(X_a)), np.ones(len(X_b))])
    clf = LogisticRegression(max_iter=1000)
    proba = cross_val_predict(clf, X, y, cv=5, method="predict_proba")[:, 1]
    return float(roc_auc_score(y, proba))


def domain_auc_matrix(sites: dict, seed: int = 0) -> pd.DataFrame:
    """Pairwise domain-classifier AUC between every pair of sites."""
    names = list(sites.keys())
    M = np.full((len(names), len(names)), 0.5)
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i < j:
                auc = domain_classifier_auc(sites[a].X, sites[b].X, seed=seed)
                M[i, j] = M[j, i] = auc
    return pd.DataFrame(M, index=names, columns=names)
