"""
Recreations of the explanatory figures from Angelopoulos & Bates (2022),
"A Gentle Introduction to Conformal Prediction and Distribution-Free
Uncertainty Quantification" (arXiv:2107.07511).

These are the iconic teaching diagrams the paper uses to explain *how* each
method works. We recreate them as clean, runnable Matplotlib figures so they can
go straight onto workshop slides and be regenerated / tweaked at will:

    fig01_prediction_set_examples : Fig 1  -- three progressively harder examples
                                    and their prediction sets
    fig02_conformal_illustration : Fig 2  -- scores -> quantile -> prediction set
    fig04_aps_illustration       : Fig 4  -- adaptive prediction sets (cumulative)
    fig06_cqr_illustration       : Fig 6  -- conformalized quantile regression
    fig08_uncertainty_scalar     : Fig 8  -- f(x) +/- q_hat * u(x)
    fig09_bayes_superlevel       : Fig 9  -- conformalized Bayes (superlevel set)
    fig10_coverage_notions       : Fig 10 -- no / marginal / conditional coverage
    fig11_coverage_distribution  : Fig 11 -- distribution of coverage vs n_cal

For the classification illustrations (Fig 1, 2, 4) we use the dataset's
*original* 5-class severity target (0 = none ... 4 = severe) so the multiclass
picture matches the paper while staying tied to the workshop data. Figure 1's
original photographs (three ImageNet images of a fox squirrel) have no
analogue here -- there is no patient photography in this dataset, and there
should not be -- so each example is instead a small clinical "patient card"
carrying the same role: something to be uncertain about, standing in for the
photo. Unlike Fig 2 and Fig 4 (which use hand-picked softmax numbers for
clarity, exactly as the paper's own illustrations do), Fig 1 trains the real
federated model, calibrates a real conformal predictor, and selects three
real patients from the dataset -- it exists specifically to show what this
project's pipeline actually outputs, not an idealized illustration of it. The
regression illustrations (Fig 6, 8, 9) use small synthetic examples, exactly
as the paper does.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from .viz import set_style, INK, INK_2, MUTED, GRID, _save

# Paper-ish accents
TEAL = "#2bb6c4"        # the paper's cyan bars
TEAL_DARK = "#1b8894"
RED = "#d03b3b"         # q_hat threshold (paper uses dashed red/pink)
GREYBAR = "#c9c8c2"

SEVERITY = ["0\nnone", "1\nmild", "2\nmod", "3\nsevere", "4\ncrit"]

GREEN = "#1baf7a"       # the paper's green true-class text
CARD_FILL = "#eef3fb"
CARD_EDGE = "#9fb8d9"


# ----------------------------------------------------------------------------
# Figure 1 -- Prediction set examples
# ----------------------------------------------------------------------------

#: Compact site labels for the patient card (data.SITE_LABELS is too long to fit).
_CARD_SITE = {"cleveland": "Cleveland", "hungarian": "Hungary",
             "switzerland": "Switzerland", "va": "V.A."}


def fig01_prediction_set_examples(alpha=0.1, seed=0, save=None):
    """Recreate Figure 1 using this workshop's real, live pipeline in place of
    ImageNet photographs: train the federated model, calibrate an APS
    conformal predictor on a held-out pool, and select three *real* patients
    -- all with the same true label, "No disease" -- whose prediction sets
    grow from a confident singleton to a four-class set in which "No disease"
    is not even the model's top guess, mirroring the paper's marmot/fox
    squirrel panel exactly, but with genuine model output rather than
    illustrative numbers.

    "No disease" is used as the shared true class deliberately, not
    arbitrarily: it is the only one of the five severity classes for which
    the calibrated model actually produces the full range of covered set
    sizes (1 through 4) needed to tell this story: the ordinal classes in
    between (Mild/Moderate/Severe) are hard enough that no confident,
    correctly-covered singleton exists for them in this dataset -- itself a
    small, honest finding about where this model is and is not confident.

    Every other classification illustration in this module (Fig 2, Fig 4)
    uses hand-picked softmax numbers for clarity, exactly as the source paper
    does. This figure is the exception: it exists specifically to show what
    conformal prediction looks like on this project's own data and model, so
    it recomputes everything live from fedconformal.data / federated /
    conformal rather than hand-authoring the numbers.
    """
    from . import data as _data
    from . import federated as _federated
    from . import conformal as _conformal
    from .eda import CATEGORY_LABELS

    set_style()

    sites = _data.load_sites(task="disease", shared_scaler=True)
    train_sites = ["cleveland", "hungarian", "va"]
    fed = _federated.federated_averaging(sites, rounds=40, local_epochs=3,
                                         train_sites=train_sites, seed=seed)
    model = fed.global_model
    class_names = _data.class_names("disease")

    df = _data.load_raw()
    X = np.vstack([sites[s].X for s in _data.SITES])
    y = np.concatenate([sites[s].y for s in _data.SITES])

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    cal, test = idx[: len(y) // 2], idx[len(y) // 2:]
    P = model.predict_proba(X)
    cp = _conformal.APSPredictor(alpha=alpha, seed=seed).calibrate(P[cal], y[cal])
    test_sets = cp.predict_set(P[test])
    sizes = np.array([len(s) for s in test_sets])
    covered = np.array([y[test[i]] in test_sets[i] for i in range(len(test))])

    TRUE = 0  # "No disease"

    def pick(size, choose):
        cand = np.where((y[test] == TRUE) & covered & (sizes == size))[0]
        return cand[choose(P[test[cand], TRUE])]

    tiers = [
        pick(1, np.argmax),                              # most confident singleton
        pick(3, lambda c: np.argsort(c)[len(c) // 2]),    # a representative 3-class case
        pick(4, np.argmin),                               # least confident 4-class case
    ]

    examples = []
    for local_i in tiers:
        orig = test[local_i]
        row = df.iloc[orig]
        cp_label = CATEGORY_LABELS["cp"].get(row["cp"], "unknown")
        thal_label = CATEGORY_LABELS["thal"].get(row["thal"], "not recorded")
        ranked = sorted(test_sets[local_i], key=lambda c: -P[orig, c])
        examples.append({
            "card": f"{_CARD_SITE[row['site']]} · patient #{orig}",
            "detail": f"age {row['age']:.0f} · {cp_label}\nthal: {thal_label}",
            "set": [(class_names[c], float(P[orig, c]), c == TRUE) for c in ranked],
        })

    fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.6))

    for ax, ex in zip(axes, examples):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # ---- "patient card", standing in for the paper's photograph ----
        card = FancyBboxPatch((0.06, 0.56), 0.88, 0.40,
                              boxstyle="round,pad=0.02,rounding_size=0.035",
                              fc=CARD_FILL, ec=CARD_EDGE, lw=1.4)
        ax.add_patch(card)
        ax.text(0.5, 0.885, ex["card"], ha="center", va="center",
                fontsize=10.8, fontweight="bold", color=INK)

        # stylized ECG pulse trace
        t = np.linspace(0, 1, 400)
        pulse = np.full_like(t, 0.735)
        spike = (t > 0.40) & (t < 0.60)
        st = (t[spike] - 0.40) / 0.20
        pulse[spike] += 0.075 * np.sin(st * np.pi) - 0.02 * np.sin(2 * st * np.pi)
        ax.plot(0.13 + 0.74 * t, pulse, color=TEAL_DARK, lw=1.7,
                solid_capstyle="round", zorder=3)

        ax.text(0.5, 0.615, ex["detail"], ha="center", va="center",
                fontsize=8.6, color=INK_2, linespacing=1.5)

        # ---- prediction set: braces + class names + probabilities ----
        items = ex["set"]
        n = len(items)
        name_size = {1: 15, 3: 10, 4: 9}.get(n, 10)
        prob_size = {1: 11, 3: 8.5, 4: 7.8}.get(n, 8.5)
        brace_size = {1: 44, 3: 32, 4: 28}.get(n, 30)

        left, right = 0.02, 0.98
        ax.text(left, 0.30, "{", ha="left", va="center", fontsize=brace_size,
                color=INK, family="serif")
        ax.text(right, 0.30, "}", ha="right", va="center", fontsize=brace_size,
                color=INK, family="serif")

        xs = np.linspace(left + 0.20, right - 0.20, n) if n > 1 else np.array([0.5])
        for x, (name, prob, is_true) in zip(xs, items):
            label = name if n == 1 else name.replace(" ", "\n")
            color = GREEN if is_true else INK
            weight = "bold" if is_true else "normal"
            ax.text(x, 0.335, label, ha="center", va="center", fontsize=name_size,
                    color=color, fontweight=weight, family="monospace",
                    linespacing=1.2)
            ax.text(x, 0.335 - 0.017 * (label.count("\n") + 1) - 0.075, f"{prob:.2f}",
                    ha="center", va="center", fontsize=prob_size, color=INK_2,
                    family="monospace")

    fig.suptitle("Figure 1 — Prediction set examples", fontsize=14,
                 fontweight="bold", y=1.01)
    fig.text(0.5, 0.965,
             "Three real patients, all truly “No disease,” and the APS prediction set "
             "C(x_test) the federated model actually returns for each (α = "
             f"{alpha:.2f}). Green = the true class.",
             ha="center", fontsize=9.5, color=INK_2, style="italic")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 2 -- Illustration of conformal prediction (3 panels)
# ----------------------------------------------------------------------------

def fig02_conformal_illustration(alpha=0.1, seed=0, save=None):
    """Recreate Fig 2: (1) score on a holdout point, (2) the quantile q_hat,
    (3) forming the prediction set for a new point."""
    set_style()
    rng = np.random.default_rng(seed)
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))

    # ---- Panel 1: compute score on one holdout example ----
    ax = axes[0]
    smx = np.array([0.15, 0.40, 0.30, 0.10, 0.05])      # softmax on a cal point
    true_cls = 1                                        # true label = "mild"
    colors = [GREYBAR] * 5
    colors[true_cls] = TEAL
    ax.bar(range(5), smx, color=colors, width=0.72)
    # annotate the score s = 1 - softmax(true class)
    top = smx[true_cls]
    ax.annotate("", xy=(true_cls, 1.0), xytext=(true_cls, top),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=1.6))
    ax.text(true_cls + 0.18, (top + 1.0) / 2, r"$s_i = 1 - \hat f(x)_{y_i}$",
            color=RED, fontsize=10, va="center")
    ax.text(true_cls + 0.15, 0.05, r"true class $y_i$",
            color=TEAL_DARK, fontsize=9, va="bottom")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("softmax output")
    ax.set_title("(1) compute score on holdout data", fontsize=11)
    ax.set_xticks(range(5)); ax.set_xticklabels(SEVERITY, fontsize=8)
    ax.set_xlabel("severity class")

    # ---- Panel 2: histogram of calibration scores + q_hat ----
    ax = axes[1]
    # calibration score distribution (spread so the quantile yields a non-trivial set)
    cal_scores = np.clip(rng.beta(2.0, 2.0, size=4000), 0, 1)
    n = len(cal_scores)
    level = np.ceil((n + 1) * (1 - alpha)) / n
    qhat = np.quantile(cal_scores, level, method="higher")
    ax.hist(cal_scores, bins=32, color=TEAL, edgecolor="white")
    ax.axvline(qhat, color=RED, ls="--", lw=2)
    ax.text(qhat + 0.01, ax.get_ylim()[1] * 0.9, r"$\hat q$", color=RED, fontsize=13)
    ax.set_title("(2) get the quantile", fontsize=11)
    ax.set_xlabel(r"scores  $\{s_i\}$")
    ax.set_ylabel("count")
    ax.set_yticks([])

    # ---- Panel 3: form the prediction set on a new point ----
    ax = axes[2]
    smx_t = np.array([0.30, 0.34, 0.22, 0.09, 0.05])
    keep = smx_t >= (1 - qhat)
    colors = [TEAL if k else GREYBAR for k in keep]
    ax.bar(range(5), smx_t, color=colors, width=0.72)
    ax.axhline(1 - qhat, color=RED, ls="--", lw=2)
    ax.text(4.2, 1 - qhat, r"$1-\hat q$", color=RED, fontsize=11,
            va="center", ha="left")
    inset = "{ " + ", ".join(str(i) for i in np.flatnonzero(keep)) + " }"
    ax.text(0.5, 0.92, "prediction set  " + inset, transform=ax.transAxes,
            fontsize=11, color=TEAL_DARK, ha="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="#e8f7f9", ec=TEAL))
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("softmax output")
    ax.set_title("(3) construct prediction set", fontsize=11)
    ax.set_xticks(range(5)); ax.set_xticklabels(SEVERITY, fontsize=8)
    ax.set_xlabel("severity class")

    fig.suptitle("Figure 2 — Illustration of conformal prediction",
                 fontsize=14, fontweight="bold", y=1.04)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 4 -- Adaptive Prediction Sets (cumulative softmax)
# ----------------------------------------------------------------------------

def fig04_aps_illustration(save=None):
    """Recreate Fig 4: sorted softmax and cumulative softmax with the q_hat cut."""
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))

    labels = ["asympt.", "non-ang.", "atypical", "typical", "silent"]
    smx = np.array([0.44, 0.26, 0.14, 0.10, 0.06])       # already sorted desc
    order = np.arange(5)
    cum = np.cumsum(smx)
    qhat = 0.86                                           # cumulative threshold
    kstar = int(np.searchsorted(cum, qhat)) + 1          # classes until cum>qhat
    in_set = order < kstar

    # left: softmax output
    ax = axes[0]
    ax.bar(range(5), smx, color=[TEAL if s else GREYBAR for s in in_set], width=0.72)
    ax.set_title("softmax output (sorted)", fontsize=11)
    ax.set_ylabel("softmax output")
    ax.set_xticks(range(5)); ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)

    # right: cumulative softmax with q_hat
    ax = axes[1]
    ax.bar(range(5), cum, color=[TEAL if s else GREYBAR for s in in_set], width=0.72)
    ax.axhline(qhat, color=RED, ls="--", lw=2)
    ax.text(4.2, qhat, r"$\hat q$", color=RED, fontsize=12, va="center")
    ax.set_title("cumulative softmax output", fontsize=11)
    ax.set_ylabel("cumulative softmax output")
    ax.set_xticks(range(5)); ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    # bracket under the prediction set
    ax.annotate("", xy=(-0.4, -0.22), xytext=(kstar - 0.6, -0.22),
                xycoords=ax.get_xaxis_transform(),
                arrowprops=dict(arrowstyle="-", color=TEAL_DARK, lw=2))
    ax.text((kstar - 1) / 2, -0.3, "prediction set", ha="center", va="top",
            color=TEAL_DARK, fontsize=10, transform=ax.get_xaxis_transform())

    fig.suptitle("Figure 4 — Adaptive Prediction Sets (APS)",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 6 -- Conformalized Quantile Regression
# ----------------------------------------------------------------------------

def fig06_cqr_illustration(seed=1, save=None):
    """Recreate Fig 6: quantile-regression band widened by q_hat to reach coverage."""
    set_style()
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, 220)
    f = np.sin(2.2 * x) + 0.6 * x
    noise = 0.18 + 0.5 * x                                   # heteroscedastic
    y = f + rng.normal(0, noise)

    lo = f - 1.0 * noise                                     # fitted lower quantile
    hi = f + 1.0 * noise                                     # fitted upper quantile
    qhat = 0.28                                              # conformal adjustment

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.scatter(x, y, s=10, color=MUTED, alpha=0.55, zorder=1, label="data")
    ax.plot(x, lo, color=TEAL_DARK, lw=1.6, ls="--", zorder=2)
    ax.plot(x, hi, color=TEAL_DARK, lw=1.6, ls="--", zorder=2,
            label=r"quantile regression $\hat t_{\alpha/2},\hat t_{1-\alpha/2}$")
    ax.fill_between(x, lo - qhat, hi + qhat, color=TEAL, alpha=0.22, zorder=0,
                    label=r"conformalized set  $[\hat t_{\alpha/2}-\hat q,\ \hat t_{1-\alpha/2}+\hat q]$")
    ax.plot(x, lo - qhat, color=TEAL, lw=1.8, zorder=2)
    ax.plot(x, hi + qhat, color=TEAL, lw=1.8, zorder=2)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.set_title("Figure 6 — Conformalized Quantile Regression")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 8 -- Conformalized uncertainty scalar
# ----------------------------------------------------------------------------

def fig08_uncertainty_scalar(seed=2, save=None):
    """Recreate Fig 8: point prediction f(x) with a symmetric band q_hat * u(x)."""
    set_style()
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, 200)
    f = 0.5 + 0.8 * x
    u = 0.12 + 0.9 * x                                       # uncertainty scalar u(x)
    qhat = 0.55
    y = f + rng.normal(0, 0.5 * u)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.scatter(x, y, s=10, color=MUTED, alpha=0.5, zorder=1)
    ax.fill_between(x, f - qhat * u, f + qhat * u, color=TEAL, alpha=0.22, zorder=0,
                    label=r"$\hat f(x)\ \pm\ \hat q\,u(x)$")
    ax.plot(x, f, color=TEAL_DARK, lw=2, zorder=2, label=r"$\hat f(x)$")
    ax.plot(x, f + qhat * u, color=TEAL, lw=1.6, zorder=2)
    ax.plot(x, f - qhat * u, color=TEAL, lw=1.6, zorder=2)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.set_title("Figure 8 — Conformalized uncertainty scalar")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 9 -- Conformalized Bayes (superlevel set of the posterior predictive)
# ----------------------------------------------------------------------------

def fig09_bayes_superlevel(save=None):
    """Recreate Fig 9: prediction set as the superlevel set { y : f(y|x) > -q_hat }."""
    set_style()
    y = np.linspace(-4, 4, 500)
    dens = 0.6 * np.exp(-0.5 * ((y - (-0.6)) / 0.7) ** 2) + \
           0.9 * np.exp(-0.5 * ((y - 1.1) / 0.9) ** 2)
    _trap = getattr(np, "trapezoid", getattr(np, "trapz", None))
    dens /= _trap(dens, y)
    thr = 0.16                                              # threshold q_hat

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.plot(y, dens, color=INK_2, lw=2, zorder=2)
    ax.axhline(thr, color=RED, ls="--", lw=1.8, zorder=1)
    ax.text(3.4, thr + 0.005, r"$\hat q$", color=RED, fontsize=12)
    above = dens >= thr
    ax.fill_between(y, 0, dens, where=above, color=TEAL, alpha=0.30, zorder=0)
    # mark the prediction-set interval(s) on the y axis
    idx = np.flatnonzero(above)
    if len(idx):
        y0, y1 = y[idx[0]], y[idx[-1]]
        ax.annotate("", xy=(y0, -0.02), xytext=(y1, -0.02),
                    arrowprops=dict(arrowstyle="<->", color=TEAL_DARK, lw=2))
        ax.text((y0 + y1) / 2, -0.05, "prediction set", ha="center", va="top",
                color=TEAL_DARK, fontsize=10)
    ax.set_xlabel("y"); ax.set_ylabel(r"$\hat f(y\mid x)$")
    ax.set_ylim(-0.06, dens.max() * 1.1)
    ax.set_title("Figure 9 — Conformalized Bayes (superlevel set)")
    fig.tight_layout()
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 10 -- notions of coverage (no / marginal / conditional)
# ----------------------------------------------------------------------------

def fig10_coverage_notions(seed=3, save=None):
    """Recreate Fig 10 (top row): errors by group under three coverage regimes.

    Two groups (framed here as two sites). Green = covered, red = error. The
    three columns show no coverage, marginal-only (errors concentrated in one
    group), and conditional (errors spread evenly) coverage.
    """
    set_style()
    rng = np.random.default_rng(seed)
    good = "#0ca30c"
    bad = "#d03b3b"

    def blob(ax, center, err_frac, n=90, r=1.0):
        ang = rng.uniform(0, 2 * np.pi, n)
        rad = r * np.sqrt(rng.uniform(0, 1, n))
        xs = center[0] + rad * np.cos(ang)
        ys = center[1] + rad * np.sin(ang)
        is_err = rng.uniform(size=n) < err_frac
        ax.scatter(xs[~is_err], ys[~is_err], s=12, color=good, alpha=0.85)
        ax.scatter(xs[is_err], ys[is_err], s=14, color=bad, alpha=0.9)
        circ = plt.Circle(center, r, fill=False, color=MUTED, lw=1.2)
        ax.add_patch(circ)
        return is_err.mean()

    regimes = [
        ("no coverage", 0.55, 0.50),          # both groups under-cover
        ("marginal only", 0.02, 0.20),        # errors concentrated in group 2
        ("conditional", 0.10, 0.10),          # errors even across groups
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.4))
    for ax, (title, e1, e2) in zip(axes, regimes):
        c1 = blob(ax, (-1.2, 0), e1)
        c2 = blob(ax, (1.2, 0), e2)
        ax.text(-1.2, -1.5, f"Site A\n{1-c1:.0%} cov.", ha="center", va="top", fontsize=9, color=INK_2)
        ax.text(1.2, -1.5, f"Site B\n{1-c2:.0%} cov.", ha="center", va="top", fontsize=9, color=INK_2)
        ax.set_title(title, fontsize=12)
        ax.set_xlim(-2.6, 2.6); ax.set_ylim(-2.2, 1.6)
        ax.set_aspect("equal"); ax.axis("off")

    # shared legend
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=good, markersize=8, label="covered"),
               Line2D([0], [0], marker="o", color="w", markerfacecolor=bad, markersize=8, label="error")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=10, frameon=False)
    fig.suptitle("Figure 10 — Notions of coverage (target 90%)",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return _save(fig, save)


# ----------------------------------------------------------------------------
# Figure 11 -- distribution of coverage vs calibration-set size
# ----------------------------------------------------------------------------

def fig11_coverage_distribution(alpha=0.1, ns=(100, 1000, 10000), save=None):
    """Recreate Fig 11: the Beta distribution of coverage narrows as n grows."""
    from scipy.stats import beta as beta_dist
    set_style()
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    x = np.linspace(0.82, 0.98, 900)
    palette = ["#9ec5f4", "#eb6834", "#199e70"]
    for c, n in zip(palette, ns):
        l = int(np.floor((n + 1) * alpha))
        a, b = n + 1 - l, max(l, 1)
        ax.plot(x, beta_dist.pdf(x, a, b), lw=2.4, color=c, label=f"n = {n}")
    ax.axvline(1 - alpha, ls="--", color=MUTED, lw=1.3)
    ax.text(1 - alpha + 0.002, ax.get_ylim()[1] * 0.5, r"$1-\alpha$", color=INK_2, fontsize=11)
    ax.set_title("Figure 11 — Distribution of coverage (infinite validation set)")
    ax.set_xlabel("coverage"); ax.set_ylabel("density"); ax.set_yticks([])
    ax.legend(title="calibration size")
    fig.tight_layout()
    return _save(fig, save)
