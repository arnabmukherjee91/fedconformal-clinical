"""
Visualization helpers for the workshop.

Every figure is built for teaching: clear titles, direct labels, a colorblind-
safe categorical palette applied in a *fixed* order (so a given site is always
the same color), recessive gridlines, and no dual axes. The palette is the
validated reference palette from the data-viz design system.

All functions return a Matplotlib ``Figure`` and optionally save it, so they can
be dropped into notebooks or the batch demo script alike.
"""

from __future__ import annotations

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from .data import SITES, SITE_LABELS
from . import evaluate as ev

# ----------------------------------------------------------------------------
# Palette & global style (validated reference palette, fixed site order)
# ----------------------------------------------------------------------------

# Four well-separated categorical hues, assigned to sites in fixed order.
SITE_COLORS = {
    "cleveland":   "#2a78d6",   # blue
    "hungarian":   "#eb6834",   # orange
    "switzerland": "#008300",   # green
    "va":          "#4a3aa7",   # violet
}
SITE_MARKERS = {"cleveland": "o", "hungarian": "s", "switzerland": "^", "va": "D"}

INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"
WARNING = "#fab219"
ACCENT = "#2a78d6"


def set_style():
    """Apply a clean, teaching-friendly Matplotlib style globally."""
    mpl.rcParams.update({
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "savefig.facecolor": "#fcfcfb",
        "axes.edgecolor": "#c3c2b7",
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "text.color": INK,
        "font.size": 11,
        "legend.frameon": False,
        "figure.dpi": 110,
    })


def _save(fig, save):
    if save:
        fig.savefig(save, bbox_inches="tight", dpi=150)
    return fig


def _slabel(s):
    return SITE_LABELS.get(s, s)


# ----------------------------------------------------------------------------
# 1. Site heterogeneity overview
# ----------------------------------------------------------------------------

def plot_site_overview(summary_df, save=None):
    """Two-panel: patients per site and disease prevalence per site."""
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    order = list(summary_df["site"])
    colors = [SITE_COLORS[s] for s in order]

    axes[0].bar(range(len(order)), summary_df["n"], color=colors, width=0.66)
    for i, v in enumerate(summary_df["n"]):
        axes[0].text(i, v + 4, str(int(v)), ha="center", va="bottom",
                     fontsize=10, color=INK_2)
    axes[0].set_title("Patients per site")
    axes[0].set_ylabel("count")

    axes[1].bar(range(len(order)), summary_df["prevalence"], color=colors, width=0.66)
    axes[1].axhline(summary_df["prevalence"].mean(), ls="--", lw=1.2,
                    color=MUTED, zorder=0)
    for i, v in enumerate(summary_df["prevalence"]):
        axes[1].text(i, v + 0.02, f"{v:.0%}", ha="center", va="bottom",
                     fontsize=10, color=INK_2)
    axes[1].set_title("Disease prevalence  P(y = 1)  — true label shift")
    axes[1].set_ylabel("prevalence")
    axes[1].set_ylim(0, 1.05)

    for ax in axes:
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels([s.capitalize() for s in order], rotation=15, ha="right")
    fig.suptitle("Site-level heterogeneity in the UCI Heart Disease federation",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, save)


def plot_missingness(miss_df, save=None):
    """Heatmap of 'unrecorded' (implausible-zero) fractions per feature/site."""
    set_style()
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    M = miss_df.to_numpy()
    im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(miss_df.shape[1]))
    ax.set_xticklabels(miss_df.columns, rotation=0)
    ax.set_yticks(range(miss_df.shape[0]))
    ax.set_yticklabels([s.capitalize() for s in miss_df.index])
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            val = M[i, j]
            ax.text(j, i, f"{val:.0%}", ha="center", va="center",
                    color="white" if val > 0.5 else INK_2, fontsize=10)
    ax.grid(False)
    ax.set_title("Measurement-induced heterogeneity:\nfraction of unrecorded (zero) values")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("fraction unrecorded", color=INK_2)
    fig.tight_layout()
    return _save(fig, save)


def plot_feature_distributions(df, feature="chol", save=None):
    """Overlaid per-site distributions of one feature (measured values only)."""
    set_style()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for s in SITES:
        v = df.loc[(df["site"] == s), feature].to_numpy()
        measured = v[v > 0]
        if len(measured) < 2:
            # site where the feature is essentially unrecorded
            ax.axvline(0, color=SITE_COLORS[s], lw=2.5, alpha=0.8,
                       label=f"{s.capitalize()} (unrecorded)")
            continue
        ax.hist(measured, bins=25, density=True, histtype="step", lw=2,
                color=SITE_COLORS[s], label=s.capitalize())
    ax.set_title(f"Per-site distribution of '{feature}'")
    ax.set_xlabel(feature)
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    return _save(fig, save)


def plot_divergence_matrix(mat_df, title, save=None, fmt="{:.2f}", cmap="Blues"):
    """Generic site-by-site matrix heatmap (JS divergence or domain AUC)."""
    set_style()
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    M = mat_df.to_numpy()
    im = ax.imshow(M, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(mat_df.columns)))
    ax.set_xticklabels([s.capitalize() for s in mat_df.columns], rotation=20, ha="right")
    ax.set_yticks(range(len(mat_df.index)))
    ax.set_yticklabels([s.capitalize() for s in mat_df.index])
    thr = np.nanmax(M) * 0.6
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, fmt.format(M[i, j]), ha="center", va="center",
                    color="white" if M[i, j] > thr else INK_2, fontsize=9)
    ax.grid(False)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 2. Federated training curves
# ----------------------------------------------------------------------------

def plot_fed_learning_curves(history, save=None):
    """FedAvg training loss per site across communication rounds."""
    set_style()
    fig, ax = plt.subplots(figsize=(8, 4.4))
    rounds = [h["round"] for h in history]
    for s in SITES:
        key = f"loss_{s}"
        if key in history[0]:
            ax.plot(rounds, [h[key] for h in history], lw=2,
                    color=SITE_COLORS[s], marker=SITE_MARKERS[s], markersize=4,
                    markevery=max(1, len(rounds) // 10), label=s.capitalize())
    ax.set_title("Federated training (FedAvg): per-site loss by round")
    ax.set_xlabel("communication round")
    ax.set_ylabel("cross-entropy loss")
    ax.legend()
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 3. Conformal calibration illustration
# ----------------------------------------------------------------------------

def plot_calibration_scores(scores, qhat, alpha, save=None):
    """Histogram of calibration nonconformity scores with the qhat threshold."""
    set_style()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.hist(scores, bins=30, color="#9ec5f4", edgecolor="white")
    ax.axvline(qhat, color=CRITICAL, lw=2.2, ls="--",
               label=f"q̂ = {qhat:.3f}   (1−α = {1-alpha:.0%})")
    ax.set_title("Conformal calibration: nonconformity scores and the quantile q̂")
    ax.set_xlabel("nonconformity score  s = 1 − f(x)_y")
    ax.set_ylabel("count")
    ax.legend()
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 4. THE key workshop figure: coverage across deployment sites
# ----------------------------------------------------------------------------

def plot_coverage_by_site(cov_by_site, alpha, n_cal=None, title=None, save=None):
    """Bar chart of empirical coverage at each deployment site vs. the 1-alpha target.

    ``cov_by_site`` : dict {site: coverage}. If ``n_cal`` is given, the benign
    Beta fluctuation band around 1-alpha is drawn, so attendees can see whether a
    coverage drop is real or just finite-sample noise.
    """
    set_style()
    target = 1 - alpha
    sites = list(cov_by_site.keys())
    covs = [cov_by_site[s] for s in sites]
    colors = [GOOD if c >= target - (0.0 if n_cal is None else 0.0) else CRITICAL
              for c in covs]
    # color by whether coverage falls below the target band
    if n_cal is not None:
        lo, hi = ev.coverage_beta_interval(n_cal, alpha, level=0.95)
        colors = [GOOD if c >= lo else CRITICAL for c in covs]

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    bars = ax.bar(range(len(sites)), covs, color=colors, width=0.62, zorder=3)
    ax.axhline(target, color=INK, lw=1.6, zorder=2,
               label=f"target 1−α = {target:.0%}")
    if n_cal is not None:
        ax.axhspan(lo, hi, color=MUTED, alpha=0.18, zorder=0,
                   label="benign fluctuation (95% Beta band)")
    for i, c in enumerate(covs):
        ax.text(i, c + 0.015, f"{c:.0%}", ha="center", va="bottom",
                fontsize=10, color=INK_2)
    ax.set_xticks(range(len(sites)))
    ax.set_xticklabels([s.capitalize() for s in sites], rotation=15, ha="right")
    ax.set_ylabel("empirical coverage")
    ax.set_ylim(0, 1.05)
    ax.set_title(title or "Does the coverage guarantee survive at each site?")
    # legend with a status note
    handles, labels = ax.get_legend_handles_labels()
    handles += [Patch(color=GOOD, label="meets target"),
                Patch(color=CRITICAL, label="under-covers (silent failure)")]
    ax.legend(handles=handles, loc="lower left", fontsize=9)
    fig.tight_layout()
    return _save(fig, save)


def plot_transfer_matrix(cov_matrix_df, alpha, save=None):
    """Heatmap of coverage when calibrating on site i and deploying on site j.

    Diagonal (same site) should hit 1-alpha; large off-diagonal drops are the
    quantitative signature of site shift breaking the conformal guarantee.
    """
    set_style()
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    M = cov_matrix_df.to_numpy()
    target = 1 - alpha
    # diverging around the target: below target -> red, at/above -> blue/green
    im = ax.imshow(M, cmap="RdYlGn", vmin=target - 0.35, vmax=target + 0.05,
                   aspect="auto")
    ax.set_xticks(range(len(cov_matrix_df.columns)))
    ax.set_xticklabels([s.capitalize() for s in cov_matrix_df.columns],
                       rotation=20, ha="right")
    ax.set_yticks(range(len(cov_matrix_df.index)))
    ax.set_yticklabels([s.capitalize() for s in cov_matrix_df.index])
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.0%}", ha="center", va="center",
                    color=INK, fontsize=9)
    ax.grid(False)
    ax.set_xlabel("deployed at  →")
    ax.set_ylabel("calibrated at  ↓")
    ax.set_title(f"Cross-site coverage transfer (target {target:.0%})")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="coverage")
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 5. Set-size distribution (adaptivity)
# ----------------------------------------------------------------------------

def plot_set_size_distribution(sizes_by_site, save=None):
    """Grouped bars of prediction-set-size frequencies per site (binary task: 0,1,2)."""
    set_style()
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    sizes = [0, 1, 2]
    width = 0.2
    for k, s in enumerate(SITES):
        if s not in sizes_by_site:
            continue
        arr = np.asarray(sizes_by_site[s])
        freqs = [np.mean(arr == sz) for sz in sizes]
        ax.bar(np.array(sizes) + (k - 1.5) * width, freqs, width=width,
               color=SITE_COLORS[s], label=s.capitalize())
    ax.set_xticks(sizes)
    ax.set_xticklabels(["∅ (size 0)", "singleton (size 1)", "both labels (size 2)"])
    ax.set_ylabel("fraction of patients")
    ax.set_title("Prediction-set size distribution by site (adaptivity)")
    ax.legend()
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# 6. Coverage distribution / calibration-set-size effect (Beta)
# ----------------------------------------------------------------------------

def plot_coverage_beta(alpha=0.1, ns=(50, 150, 1000), save=None):
    """The analytic distribution of coverage for several calibration-set sizes."""
    from scipy.stats import beta as beta_dist
    set_style()
    fig, ax = plt.subplots(figsize=(8, 4.4))
    x = np.linspace(0.7, 1.0, 800)
    palette = ["#9ec5f4", "#3987e5", "#0d366b"]
    for c, n in zip(palette, ns):
        l = int(np.floor((n + 1) * alpha))
        a, b = n + 1 - l, max(l, 1)
        ax.plot(x, beta_dist.pdf(x, a, b), lw=2.2, color=c, label=f"n_cal = {n}")
    ax.axvline(1 - alpha, ls="--", color=MUTED, lw=1.2, label=f"1−α = {1-alpha:.0%}")
    ax.set_title("Why calibration-set size matters:\ndistribution of coverage (Vovk)")
    ax.set_xlabel("coverage")
    ax.set_ylabel("density")
    ax.set_yticks([])
    ax.legend()
    fig.tight_layout()
    return _save(fig, save)
