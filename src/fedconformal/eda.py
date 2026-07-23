"""
Exploratory data analysis (EDA) for the raw UCI Heart Disease inputs.

Before any modeling, attendees should *see* the inputs: what the target classes
are, which features are categorical vs. continuous, how they relate to the
outcome, and how all of this differs across the four hospital sites. These
helpers produce that first-look picture.

Feature dictionary (raw UCI coding)
-----------------------------------
age       : age in years                                     (continuous)
sex       : 1 = male, 0 = female                             (binary)
cp        : chest pain type -- 1 typical angina, 2 atypical,
            3 non-anginal, 4 asymptomatic                    (categorical)
trestbps  : resting blood pressure (mm Hg)                   (continuous)
chol      : serum cholesterol (mg/dl); 0 = unrecorded        (continuous)
fbs       : fasting blood sugar > 120 mg/dl (1 = true)       (binary)
restecg   : resting ECG -- 0 normal, 1 ST-T abnormality,
            2 left-ventricular hypertrophy                   (categorical)
thalach   : maximum heart rate achieved                      (continuous)
exang     : exercise-induced angina (1 = yes)                (binary)
oldpeak   : ST depression induced by exercise                (continuous)
slope     : slope of peak exercise ST segment --
            1 upsloping, 2 flat, 3 downsloping               (categorical)
ca        : # major vessels (0-3) colored by fluoroscopy;
            mostly unrecorded (NaN) outside Cleveland         (ordinal)
thal      : 3 normal, 6 fixed defect, 7 reversible defect;
            mostly unrecorded (NaN) outside Cleveland         (categorical)
target    : 0 = no disease; 1-4 = disease, increasing
            severity (label; this workshop's default task
            predicts all 5 classes)
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from .data import SITES, SITE_LABELS
from .viz import (set_style, SITE_COLORS, INK, INK_2, MUTED, _save)

#: The 5 severity classes of the disease target, and a sequential palette
#: (light -> dark) so "more severe" reads as "darker" in every plot.
SEVERITY_NAMES = ["No disease", "Mild", "Moderate", "Severe", "Critical"]
SEVERITY_COLORS = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

# Two-class colors, used only for the derived "any disease" summary view.
TARGET_COLORS = {0: "#2a78d6", 1: "#eb6834"}      # no disease / any disease
TARGET_NAMES = {0: "No disease", 1: "Any disease"}

CONTINUOUS = ["age", "trestbps", "chol", "thalach", "oldpeak"]
CATEGORICAL = ["sex", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"]

# Human-readable value labels for the categorical features.
CATEGORY_LABELS = {
    "sex": {0: "female", 1: "male"},
    "cp": {1: "typ. angina", 2: "atyp. angina", 3: "non-anginal", 4: "asymptomatic"},
    "fbs": {0: "fbs≤120", 1: "fbs>120"},
    "restecg": {0: "normal", 1: "ST-T abn.", 2: "LV hyper."},
    "exang": {0: "no", 1: "yes"},
    "slope": {1: "up", 2: "flat", 3: "down"},
    "thal": {3: "normal", 6: "fixed", 7: "reversible"},
}


# ----------------------------------------------------------------------------
# 1. The target
# ----------------------------------------------------------------------------

def plot_target_distribution(df, save=None):
    """Target overview: the full 5-class severity breakdown, plus the derived
    binary "any disease" collapse for a quick summary stat."""
    set_style()
    raw = df["target"].value_counts().sort_index()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].bar(raw.index.astype(int), raw.values,
                color=[SEVERITY_COLORS[min(int(k), 4)] for k in raw.index], width=0.7)
    for k, v in zip(raw.index.astype(int), raw.values):
        axes[0].text(k, v + 3, str(int(v)), ha="center", va="bottom",
                     fontsize=10, color=INK_2)
    axes[0].set_title("The target: severity 0 (none) … 4 (critical)")
    axes[0].set_xlabel("target (num)")
    axes[0].set_ylabel("patients")
    axes[0].set_xticks([0, 1, 2, 3, 4])
    axes[0].set_xticklabels(SEVERITY_NAMES, rotation=15, ha="right")

    ax = axes[1]
    binv = (df["target"] > 0).astype(int).value_counts().sort_index()
    total = binv.values.sum()
    ax.bar([TARGET_NAMES[i] for i in binv.index], binv.values,
           color=[TARGET_COLORS[i] for i in binv.index], width=0.6)
    for i, v in zip(range(len(binv)), binv.values):
        ax.text(i, v + 3, f"{v}  ({v/total:.0%})", ha="center", va="bottom",
                fontsize=10, color=INK_2)
    ax.set_title("Derived summary: any disease vs. none")
    ax.set_ylabel("patients")

    fig.suptitle("What are we predicting? The heart-disease severity target",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, save)


def plot_target_by_site(df, save=None):
    """Stacked bars: full 5-class severity composition within each site."""
    set_style()
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    x = np.arange(len(SITES))
    counts = {k: [] for k in range(5)}
    totals = []
    for s in SITES:
        sub = df[df["site"] == s]["target"]
        totals.append(len(sub))
        for k in range(5):
            counts[k].append(int((sub == k).sum()))

    bottom = np.zeros(len(SITES))
    for k in range(5):
        vals = np.array(counts[k])
        ax.bar(x, vals, bottom=bottom, color=SEVERITY_COLORS[k],
               label=SEVERITY_NAMES[k], width=0.62)
        bottom += vals
    for i, (s, tot) in enumerate(zip(SITES, totals)):
        prev = 1 - counts[0][i] / tot
        ax.text(i, tot + 4, f"{prev:.0%} any disease", ha="center", va="bottom",
                fontsize=9, color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels([s.capitalize() for s in SITES], rotation=15, ha="right")
    ax.set_ylabel("patients")
    ax.set_title("Severity composition differs sharply by site (label shift)")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=8)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 2. Continuous features
# ----------------------------------------------------------------------------

def plot_continuous_grid(df, save=None):
    """Histograms of the continuous features, split by severity class."""
    set_style()
    n = len(CONTINUOUS)
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    axes = axes.ravel()
    y = df["target"].astype(int)
    for ax, feat in zip(axes, CONTINUOUS):
        v = df[feat]
        measured = v > 0 if feat in ("chol", "trestbps", "thalach") else np.ones(len(v), bool)
        for cls in range(5):
            mask = (y == cls) & measured
            if mask.sum() < 2:
                continue
            ax.hist(df.loc[mask, feat], bins=18, density=True, histtype="step",
                    lw=1.8, color=SEVERITY_COLORS[cls], label=SEVERITY_NAMES[cls])
        ax.set_title(feat)
        ax.set_yticks([])
    axes[0].legend(fontsize=7)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("Continuous features by severity class (measured values only)",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    return _save(fig, save)


def plot_feature_boxplots_by_site(df, feature="thalach", save=None):
    """Box plots of one continuous feature across the four sites."""
    set_style()
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    data = []
    for s in SITES:
        v = df[df["site"] == s][feature]
        if feature in ("chol", "trestbps", "thalach"):
            v = v[v > 0]
        data.append(v.dropna().values)
    bp = ax.boxplot(data, patch_artist=True, widths=0.55,
                    medianprops=dict(color=INK, lw=1.6),
                    flierprops=dict(marker="o", markersize=3, alpha=0.4))
    for patch, s in zip(bp["boxes"], SITES):
        patch.set_facecolor(SITE_COLORS[s])
        patch.set_alpha(0.75)
    ax.set_xticklabels([s.capitalize() for s in SITES], rotation=15, ha="right")
    ax.set_ylabel(feature)
    ax.set_title(f"'{feature}' distribution across sites (measured values)")
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 3. Categorical features
# ----------------------------------------------------------------------------

def plot_categorical_grid(df, save=None):
    """Grid of categorical features: mean disease severity within each level."""
    set_style()
    feats = ["cp", "sex", "exang", "slope", "restecg", "thal"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    axes = axes.ravel()
    y = df["target"].astype(float)
    for ax, feat in zip(axes, feats):
        levels = sorted(df[feat].dropna().unique())
        counts, rates, labels = [], [], []
        for lv in levels:
            mask = df[feat] == lv
            if mask.sum() == 0:
                continue
            counts.append(int(mask.sum()))
            rates.append(float(y[mask].mean()))
            lab = CATEGORY_LABELS.get(feat, {}).get(int(lv), str(int(lv))) \
                if float(lv).is_integer() else str(lv)
            labels.append(lab)
        xs = np.arange(len(labels))
        colors = [SEVERITY_COLORS[min(int(round(r)), 4)] for r in rates]
        bars = ax.bar(xs, rates, color=colors, width=0.66, alpha=0.9)
        for xi, r, c in zip(xs, rates, counts):
            ax.text(xi, r + 0.05, f"{r:.2f}\nn={c}", ha="center", va="bottom",
                    fontsize=8, color=INK_2)
        ax.axhline(y.mean(), ls="--", lw=1, color=MUTED)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
        ax.set_ylim(0, 4.6)
        ax.set_title(feat)
        ax.set_ylabel("mean severity (0-4)")
    fig.suptitle("Categorical features: mean severity per level (dashed = overall mean)",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 4. Correlation structure
# ----------------------------------------------------------------------------

def plot_correlation_heatmap(df, save=None):
    """Pearson correlation among features + the 5-class severity target."""
    set_style()
    from .data import FEATURES
    d = df[FEATURES].copy()
    d["target"] = df["target"].astype(int)
    corr = d.corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(8.5, 7))
    im = ax.imshow(corr.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index, fontsize=9)
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            val = corr.iloc[i, j]
            if abs(val) >= 0.25:
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=7, color="white" if abs(val) > 0.6 else INK)
    ax.grid(False)
    ax.set_title("Feature correlation (with the 5-class severity target)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Pearson r")
    fig.tight_layout()
    return _save(fig, save)
