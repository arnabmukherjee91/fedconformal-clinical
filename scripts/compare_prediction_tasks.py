"""
Compare the two classification tasks head-to-head, using EVERY available feature.

Question 1: which task carries more site-level heterogeneity?
Question 2: which task yields more conformal labels per sample (larger sets)?

Tasks (each uses all columns except its own label -> "every feature"):
  * disease : label = target, the 5-class severity target (0 none ... 4 critical).
              Features = the 13 clinical variables (this includes cp).
  * cp      : label = chest-pain type (4 classes). Features = the other 12 clinical
              variables PLUS the disease target -> 13 features.

Heterogeneity is measured three complementary ways:
  A. Label-shift    : mean pairwise Jensen-Shannon divergence between the four
                      sites' CLASS distributions (how differently the target is
                      distributed across hospitals). Bits in [0, 1].
  B. Covariate-shift: mean pairwise domain-classifier AUC on that task's feature
                      set (can a model tell two sites apart? 0.5 = identical).
  C. Conformal drop : train one shared model, calibrate split-conformal at each
                      site, deploy at the others; report how far cross-site
                      coverage falls below the 1-alpha target.

"Conformal labels per sample" = average prediction-set size |C(x)| under APS at
the same alpha, reported raw and normalised by the number of classes.

Run:  python scripts/compare_prediction_tasks.py   ->  writes figures/compare/
"""

from __future__ import annotations

import os
import sys
import itertools

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, conformal, evaluate as ev, federated
from fedconformal import heterogeneity as het
from fedconformal.viz import set_style, SITE_COLORS, INK, INK_2, MUTED, GOOD, CRITICAL, _save
import matplotlib.pyplot as plt

FIG = os.path.join(os.path.dirname(__file__), "..", "figures", "compare")
os.makedirs(FIG, exist_ok=True)
ALPHA = 0.10
SITES = data.SITES


# ----------------------------------------------------------------------------
# Build per-task, per-site arrays using EVERY feature (all cols except label)
# ----------------------------------------------------------------------------

def task_arrays(df: pd.DataFrame, task: str):
    """Return (features, y_by_site, X_by_site, class_names) using every column
    except the label as a feature (shared standardization across sites)."""
    if task == "disease":
        label = df["target"].astype(int).to_numpy()         # 0..4 severity
        feats = [c for c in data.FEATURES]                 # 13 clinical (incl cp)
        class_names = ["No disease", "Mild", "Moderate", "Severe", "Critical"]
    elif task == "cp":
        label = df["cp"].astype(int).to_numpy() - 1        # 0..3
        feats = [c for c in data.COLUMNS if c not in ("cp",)]  # 12 clinical + target
        class_names = ["typ. angina", "atyp. angina", "non-anginal", "asympt."]
    else:
        raise ValueError(task)

    X = df[feats].astype(float).to_numpy()
    mean = np.nanmean(X, 0); std = np.nanstd(X, 0); std[std == 0] = 1.0
    X = np.where(np.isnan(X), mean, X)      # mean-impute (ca/thal are mostly missing)
    Xz = (X - mean) / std

    site = df["site"].to_numpy()
    X_by = {s: Xz[site == s] for s in SITES}
    y_by = {s: label[site == s] for s in SITES}
    return feats, y_by, X_by, class_names


# ----------------------------------------------------------------------------
# Heterogeneity + conformal metrics for one task
# ----------------------------------------------------------------------------

def label_js_heterogeneity(y_by, K):
    """Mean pairwise Jensen-Shannon divergence between sites' class distributions."""
    dists = {}
    for s in SITES:
        c = np.bincount(y_by[s], minlength=K).astype(float)
        dists[s] = c / c.sum()
    vals = [het.js_divergence(dists[a].copy(), dists[b].copy())
            for a, b in itertools.combinations(SITES, 2)]
    return float(np.mean(vals))


def domain_auc_mean(X_by):
    vals = [het.domain_classifier_auc(X_by[a], X_by[b])
            for a, b in itertools.combinations(SITES, 2)]
    return float(np.mean(vals))


def make_sitedata(X_by, y_by, class_names):
    return {s: data.SiteData(name=s, X=X_by[s], y=y_by[s], class_names=class_names)
            for s in SITES}


def conformal_metrics(sites, K, seed=0):
    """Train one shared (centralized) model on all sites, then:
      - cross-site coverage transfer matrix (APS)
      - avg |C(x)| pooled (APS), averaged over calibration/test splits
    """
    model = federated.train_centralized(sites, epochs=400, n_classes=K)

    # cross-site transfer: calibrate at i, deploy at j
    M = np.zeros((len(SITES), len(SITES)))
    for i, si in enumerate(SITES):
        cp = conformal.APSPredictor(alpha=ALPHA, seed=seed).calibrate(
            model.predict_proba(sites[si].X), sites[si].y)
        for j, sj in enumerate(SITES):
            s = cp.predict_set(model.predict_proba(sites[sj].X))
            M[i, j] = ev.coverage(s, sites[sj].y)
    off = M[~np.eye(len(SITES), dtype=bool)]
    cov_off_mean = float(off.mean())
    cov_worst = float(off.min())

    # pooled avg set size, averaged over random cal/test splits (stable)
    X = np.vstack([sites[s].X for s in SITES])
    y = np.concatenate([sites[s].y for s in SITES])
    P = model.predict_proba(X)
    sizes, covs = [], []
    for sd in range(120):
        r = np.random.default_rng(sd).permutation(len(y))
        c, t = r[: len(y) // 2], r[len(y) // 2:]
        cp = conformal.APSPredictor(alpha=ALPHA, seed=sd).calibrate(P[c], y[c])
        st = cp.predict_set(P[t])
        sizes.append(ev.average_set_size(st))
        covs.append(ev.coverage(st, y[t]))
    return {
        "transfer": M,
        "cov_off_mean": cov_off_mean,
        "cov_worst": cov_worst,
        "avg_set_size": float(np.mean(sizes)),
        "marginal_cov": float(np.mean(covs)),
    }


def analyze(df, task):
    feats, y_by, X_by, names = task_arrays(df, task)
    K = len(names)
    res = {
        "task": task,
        "n_features": len(feats),
        "K": K,
        "label_js": label_js_heterogeneity(y_by, K),
        "domain_auc": domain_auc_mean(X_by),
    }
    sites = make_sitedata(X_by, y_by, names)
    res.update(conformal_metrics(sites, K))
    res["cov_drop"] = (1 - ALPHA) - res["cov_off_mean"]
    res["avg_set_size_norm"] = res["avg_set_size"] / K
    return res


# ----------------------------------------------------------------------------
# Plot
# ----------------------------------------------------------------------------

def plot_comparison(dz, cp, save=None):
    set_style()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
    blue, orange = "#2a78d6", "#eb6834"

    # Panel 1: heterogeneity (label JS + domain AUC-0.5 + coverage drop)
    ax = axes[0]
    metrics = ["label shift\n(JS div.)", "covariate shift\n(AUC − 0.5)", "conformal\ncoverage drop"]
    dz_vals = [dz["label_js"], dz["domain_auc"] - 0.5, dz["cov_drop"]]
    cp_vals = [cp["label_js"], cp["domain_auc"] - 0.5, cp["cov_drop"]]
    x = np.arange(len(metrics)); w = 0.38
    ax.bar(x - w/2, dz_vals, w, color=blue, label="disease (5-class)")
    ax.bar(x + w/2, cp_vals, w, color=orange, label="chest-pain (4-class)")
    for xi, (a, b) in enumerate(zip(dz_vals, cp_vals)):
        ax.text(xi - w/2, a + 0.005, f"{a:.2f}", ha="center", va="bottom", fontsize=8, color=INK_2)
        ax.text(xi + w/2, b + 0.005, f"{b:.2f}", ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_xticks(x); ax.set_xticklabels(metrics, fontsize=9)
    ax.set_title("Site-level heterogeneity (higher = more)")
    ax.set_ylabel("heterogeneity score")
    ax.legend(fontsize=8)

    # Panel 2: conformal labels per sample
    ax = axes[1]
    ax.bar([0, 1], [dz["avg_set_size"], cp["avg_set_size"]], color=[blue, orange], width=0.6)
    for i, v in enumerate([dz["avg_set_size"], cp["avg_set_size"]]):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=10, color=INK_2)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["disease\n(K=5)", "chest-pain\n(K=4)"])
    ax.set_ylabel("avg labels per sample  |C(x)|")
    ax.set_title(f"Conformal labels per sample (α={ALPHA})")

    # Panel 3: cross-site min coverage (worst deployment)
    ax = axes[2]
    ax.bar([0, 1], [dz["cov_worst"], cp["cov_worst"]], color=[blue, orange], width=0.6, zorder=3)
    ax.axhline(1 - ALPHA, color=INK, lw=1.5, label=f"target {1-ALPHA:.0%}")
    for i, v in enumerate([dz["cov_worst"], cp["cov_worst"]]):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", va="bottom", fontsize=10, color=INK_2)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["disease", "chest-pain"])
    ax.set_ylim(0, 1.05); ax.set_ylabel("worst cross-site coverage")
    ax.set_title("Worst-case coverage across sites")
    ax.legend(fontsize=8, loc="lower right")

    fig.suptitle("Disease (5-class) vs Chest-pain (4-class): heterogeneity & conformal set size",
                 fontsize=14, fontweight="bold", y=1.03)
    fig.tight_layout()
    return _save(fig, save)


def main():
    df = data.load_raw()
    dz = analyze(df, "disease")
    cp = analyze(df, "cp")

    tbl = pd.DataFrame([dz, cp]).set_index("task")[
        ["n_features", "K", "label_js", "domain_auc", "cov_off_mean",
         "cov_worst", "cov_drop", "marginal_cov", "avg_set_size", "avg_set_size_norm"]
    ]
    pd.set_option("display.width", 160)
    print("\n=== Task comparison (every feature used) ===\n")
    print(tbl.round(3).to_string())

    print("\n--- Verdict ---")
    more_het = "chest-pain (cp)" if cp["label_js"] > dz["label_js"] else "disease"
    print(f"Label-shift heterogeneity higher in : {more_het} "
          f"(JS disease={dz['label_js']:.3f} vs cp={cp['label_js']:.3f})")
    more_drop = "chest-pain (cp)" if cp["cov_drop"] > dz["cov_drop"] else "disease"
    print(f"Cross-site coverage drop larger in  : {more_drop} "
          f"(drop disease={dz['cov_drop']:.3f} vs cp={cp['cov_drop']:.3f})")
    more_sets = "chest-pain (cp)" if cp["avg_set_size"] > dz["avg_set_size"] else "disease"
    print(f"More conformal labels per sample in : {more_sets} "
          f"(|C| disease={dz['avg_set_size']:.2f} vs cp={cp['avg_set_size']:.2f})")

    plot_comparison(dz, cp, save=os.path.join(FIG, "task_comparison.png"))
    print(f"\nFigure written to {os.path.abspath(FIG)}")
    return dz, cp


if __name__ == "__main__":
    main()
