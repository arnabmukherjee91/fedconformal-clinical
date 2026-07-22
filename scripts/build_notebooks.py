"""
Generate the workshop Jupyter notebooks programmatically with nbformat.

Keeping the notebooks in a builder script means they stay in sync with the
package API and are easy to regenerate. Run:  python scripts/build_notebooks.py
"""

import os
import nbformat as nbf

NB_DIR = os.path.join(os.path.dirname(__file__), "..", "notebooks")
os.makedirs(NB_DIR, exist_ok=True)

BOOT = (
    "# --- workshop bootstrap: make the package importable ---\n"
    "import sys, os\n"
    "sys.path.insert(0, os.path.abspath(os.path.join('..', 'src')))\n"
    "import numpy as np, pandas as pd\n"
    "from fedconformal import data, conformal, evaluate as ev, federated, heterogeneity as het, viz\n"
    "viz.set_style()\n"
    "%matplotlib inline\n"
    "# load the federation once (each notebook is self-contained)\n"
    "df = data.load_raw()\n"
    "sites = data.load_sites(shared_scaler=True)"
)


def nb(cells):
    d = nbf.v4.new_notebook()
    d.cells = cells
    d.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    return d


def md(t):
    return nbf.v4.new_markdown_cell(t)


def code(t):
    return nbf.v4.new_code_cell(t)


def write(name, notebook):
    path = os.path.join(NB_DIR, name)
    with open(path, "w") as f:
        nbf.write(notebook, f)
    print("wrote", path)


# ---------------------------------------------------------------------------
# 01 - Site heterogeneity
# ---------------------------------------------------------------------------
nb01 = nb([
    md("# 01 · Seeing site-level heterogeneity\n"
       "**Workshop: Beyond Interoperability — Federated ML for Research Data Curation**\n\n"
       "Interoperability lets data cross institutional lines. It does *not* guarantee that "
       "a variable *means* the same thing at every site. Before we integrate any data or "
       "models, we quantify how the four hospitals in the UCI Heart Disease federation differ, "
       "and we separate two very different phenomena:\n\n"
       "* **True distributional shift** — the populations genuinely differ (e.g. disease prevalence).\n"
       "* **Measurement-induced heterogeneity** — the *measurement process* differs "
       "(e.g. a site never recorded serum cholesterol).\n"),
    code(BOOT),
    md("## The four sites\n"
       "Cleveland, Hungary, Switzerland (Zurich/Basel) and the V.A. Long Beach each ran the "
       "*same* case-report form. That is what makes this dataset a natural federation."),
    code("df = data.load_raw()\n"
         "sites = data.load_sites(shared_scaler=True)\n"
         "summary = data.summarize_sites(sites, df)\n"
         "summary"),
    code("viz.plot_site_overview(summary);"),
    md("Notice prevalence swings from **36% (Hungary)** to **94% (Switzerland)** — a large "
       "*true* label shift driven by referral patterns (Switzerland is a tertiary cardiac centre)."),
    md("## Measurement-induced heterogeneity\n"
       "A cholesterol of exactly 0 mg/dl is not a measurement — it is an *unrecorded* value. "
       "Watch which sites simply did not record certain labs."),
    code("miss = het.missingness_report(df)\n"
         "display(miss.style.format('{:.0%}'))\n"
         "viz.plot_missingness(miss);"),
    md("**Switzerland never recorded cholesterol (100% unrecorded).** If you naively pooled the "
       "raw feature, Switzerland's 'cholesterol = 0' would look like a population with impossibly "
       "low cholesterol — a curation error, not biology."),
    code("viz.plot_feature_distributions(df, 'chol');"),
    md("## A single-number covariate-shift alarm\n"
       "Train a classifier to guess *which site* a patient came from. If it cannot do better than "
       "chance (AUC ≈ 0.5) the sites are exchangeable; AUC ≈ 1.0 signals strong covariate shift."),
    code("auc = het.domain_auc_matrix(sites)\n"
         "display(auc.round(2))\n"
         "viz.plot_divergence_matrix(auc, 'Domain-classifier AUC (site vs site)', cmap='Oranges');"),
    md("Every off-diagonal AUC is **0.93–1.00**: a model can almost perfectly tell any two sites "
       "apart. This is exactly the setting where a model — or a calibration — from one site is at "
       "risk of failing silently at another. That is what the next notebooks make precise."),
    md("### Exercise\n"
       "1. Swap `shared_scaler=True` for `False` in `load_sites` and re-plot. What does per-site "
       "standardization *hide*?\n"
       "2. Compute `het.js_divergence_matrix(df, 'age')` and compare with `'thalach'`. Which "
       "feature is most shifted across sites?"),
])
write("01_site_heterogeneity.ipynb", nb01)


# ---------------------------------------------------------------------------
# 02 - Conformal basics
# ---------------------------------------------------------------------------
nb02 = nb([
    md("# 02 · Conformal prediction in five lines\n"
       "We follow Angelopoulos & Bates (2022). Conformal prediction turns *any* model's "
       "heuristic confidence into **prediction sets with a coverage guarantee**: the true label "
       "is inside the set with probability ≥ 1 − α — *no distributional assumptions*, as long as "
       "calibration and test data are **exchangeable**.\n\n"
       "Here the label is binary (heart disease: yes / no) so a prediction set is one of "
       "`{}`, `{no}`, `{yes}`, `{no, yes}`."),
    code(BOOT),
    md("## A model to be uncertain about\n"
       "We train a simple logistic model on Cleveland and hold out half of it for calibration."),
    code("sd = sites['cleveland']\n"
         "rng = np.random.default_rng(0)\n"
         "idx = rng.permutation(sd.n)\n"
         "tr, cal, te = idx[:120], idx[120:210], idx[210:]\n"
         "model = federated.LogisticModel(l2=1e-2).init(sd.X.shape[1])\n"
         "model = federated.local_train(model, sd.X[tr], sd.y[tr], epochs=300)\n"
         "cal_probs, cal_y = model.predict_proba(sd.X[cal]), sd.y[cal]\n"
         "test_probs, test_y = model.predict_proba(sd.X[te]), sd.y[te]\n"
         "print('calibration points:', len(cal_y))"),
    md("## The calibration step\n"
       "The nonconformity score is `s = 1 − f(x)_y` (large when the model is confidently wrong). "
       "We take a finite-sample-corrected quantile `q̂` of the calibration scores."),
    code("alpha = 0.1\n"
         "scores = conformal.lac_scores(cal_probs, cal_y)\n"
         "qhat = conformal.conformal_quantile(scores, alpha)\n"
         "print(f'q̂ = {qhat:.3f}')\n"
         "viz.plot_calibration_scores(scores, qhat, alpha);"),
    md("## Forming prediction sets and checking coverage\n"
       "A label is kept in the set when `1 − f(x)_y ≤ q̂`."),
    code("cp = conformal.LACPredictor(alpha=alpha).calibrate(cal_probs, cal_y)\n"
         "sets = cp.predict_set(test_probs)\n"
         "res = ev.evaluate_all(sets, test_y)\n"
         "print(f\"coverage = {res['coverage']:.3f}  (target {1-alpha:.2f})\")\n"
         "print(f\"avg set size = {res['avg_set_size']:.2f}\")"),
    md("## Correctness check\n"
       "Any single split fluctuates. Averaged over many random calibration/test splits, coverage "
       "should sit right on 1 − α. This is how you *verify* a conformal implementation (paper §3.3)."),
    code("covs = []\n"
         "for seed in range(200):\n"
         "    r = np.random.default_rng(seed).permutation(sd.n)\n"
         "    c, t = r[:150], r[150:]\n"
         "    cpp = conformal.LACPredictor(alpha=alpha).calibrate(model.predict_proba(sd.X[c]), sd.y[c])\n"
         "    covs.append(ev.coverage(cpp.predict_set(model.predict_proba(sd.X[t])), sd.y[t]))\n"
         "print(f'mean coverage over 200 splits = {np.mean(covs):.3f}')"),
    md("## Adaptive Prediction Sets (APS)\n"
       "LAC gives the smallest sets but can under-cover hard cases. APS (Eq. 3) accumulates "
       "softmax mass and adapts set size to difficulty. Try it and compare average set size."),
    code("aps = conformal.APSPredictor(alpha=alpha, seed=0).calibrate(cal_probs, cal_y)\n"
         "aps_sets = aps.predict_set(test_probs)\n"
         "print('APS coverage   =', round(ev.coverage(aps_sets, test_y), 3))\n"
         "print('APS avg size   =', round(ev.average_set_size(aps_sets), 2))\n"
         "print('LAC avg size   =', round(res['avg_set_size'], 2))"),
    md("### Exercise\n"
       "Change `alpha` to 0.05 and 0.2. How do `q̂`, coverage and average set size respond? "
       "Explain the trade-off between coverage and set size to a colleague in one sentence."),
])
write("02_conformal_basics.ipynb", nb02)


# ---------------------------------------------------------------------------
# 03 - Federated training
# ---------------------------------------------------------------------------
nb03 = nb([
    md("# 03 · Federated training with FedAvg\n"
       "In a real federation the hospitals cannot pool raw patient records. **Federated learning** "
       "trains a shared model by exchanging *model weights*, not data. We use a transparent NumPy "
       "**FedAvg**: broadcast the global weights, each site takes a few local gradient steps, the "
       "server averages the results (weighted by site size)."),
    code(BOOT),
    md("## Hold a site out as an 'external' hospital\n"
       "We train on Cleveland, Hungary and the V.A., and keep **Switzerland** completely unseen — "
       "the classic external-validation scenario a curation pipeline must survive."),
    code("train_sites = ['cleveland', 'hungarian', 'va']\n"
         "fed = federated.federated_averaging(sites, rounds=40, local_epochs=3,\n"
         "                                    train_sites=train_sites, seed=0)\n"
         "viz.plot_fed_learning_curves(fed.history);\n"
         "global_model = fed.global_model"),
    md("The per-site loss curves fall together as the shared model improves. Note the model never "
       "saw Switzerland, yet we will still ask it (and its conformal calibration) to behave there."),
    md("## Federated vs. centralized\n"
       "As a reference, compare against a model that (hypothetically) pooled the same three sites."),
    code("central = federated.train_centralized(sites, train_sites=train_sites, epochs=400)\n"
         "def acc(m, s):\n"
         "    p = m.predict_proba(sites[s].X)[:,1] > 0.5\n"
         "    return float((p == sites[s].y).mean())\n"
         "pd.DataFrame({\n"
         "    'federated': {s: round(acc(global_model, s),3) for s in data.SITES},\n"
         "    'centralized': {s: round(acc(central, s),3) for s in data.SITES},\n"
         "})"),
    md("Accuracy is similar — FedAvg recovers most of the centralized performance **without moving "
       "data**. But accuracy alone hides *where the model is unreliable*. That is the job of "
       "conformal prediction, in the next notebook."),
    md("### Exercise\n"
       "Add Switzerland to `train_sites` and re-run. Does including the most-shifted site help or "
       "hurt the other sites? Relate your answer to the domain-AUC matrix from notebook 01."),
])
write("03_federated_training.ipynb", nb03)


# ---------------------------------------------------------------------------
# 04 - Conformal under site shift (capstone)
# ---------------------------------------------------------------------------
nb04 = nb([
    md("# 04 · When the coverage guarantee breaks — the curation punchline\n"
       "Conformal prediction guarantees coverage **only under exchangeability**. Across sites, "
       "exchangeability fails (we measured AUC ≈ 1.0 in notebook 01). Here we show the "
       "consequence directly: a model calibrated at one hospital can **silently under-cover** at "
       "another — *confident but wrong*, the worst failure mode for cross-institution deployment."),
    code(BOOT),
    md("## Train the federated model (holding out Switzerland)"),
    code("train_sites = ['cleveland', 'hungarian', 'va']\n"
         "fed = federated.federated_averaging(sites, rounds=40, local_epochs=3,\n"
         "                                    train_sites=train_sites, seed=0)\n"
         "model = fed.global_model\n"
         "alpha = 0.1"),
    md("## Calibrate at Cleveland, deploy everywhere"),
    code("sd_c = sites['cleveland']\n"
         "cp = conformal.LACPredictor(alpha=alpha).calibrate(model.predict_proba(sd_c.X), sd_c.y)\n"
         "cov_by_site = {s: ev.coverage(cp.predict_set(model.predict_proba(sites[s].X)), sites[s].y)\n"
         "               for s in data.SITES}\n"
         "cov_by_site"),
    code("viz.plot_coverage_by_site(cov_by_site, alpha, n_cal=sd_c.n,\n"
         "        title='Coverage of a Cleveland-calibrated model across sites');"),
    md("Cleveland and Hungary land on the 90% target; **Switzerland falls to ~82%**, well below "
       "the benign-fluctuation band. The guarantee did not travel with the model."),
    md("## The full transfer matrix\n"
       "Calibrate at site *i* (row), deploy at site *j* (column). The diagonal is honest; the "
       "off-diagonal drops quantify how far the guarantee degrades."),
    code("cov = pd.DataFrame(index=data.SITES, columns=data.SITES, dtype=float)\n"
         "for si in data.SITES:\n"
         "    c = conformal.LACPredictor(alpha=alpha).calibrate(model.predict_proba(sites[si].X), sites[si].y)\n"
         "    for sj in data.SITES:\n"
         "        cov.loc[si, sj] = ev.coverage(c.predict_set(model.predict_proba(sites[sj].X)), sites[sj].y)\n"
         "display(cov.astype(float).round(2))\n"
         "viz.plot_transfer_matrix(cov.astype(float), alpha);"),
    md("## Adaptivity: are the sets bigger where the model is unsure?"),
    code("sizes = {s: ev.set_sizes(cp.predict_set(model.predict_proba(sites[s].X))) for s in data.SITES}\n"
         "viz.plot_set_size_distribution(sizes);"),
    md("## Why calibration-set size matters"),
    code("viz.plot_coverage_beta(alpha=0.1, ns=(50, 150, 1000));"),
    md("## Takeaways for research-data curation\n"
       "1. **Interoperability ≠ comparability.** Measure site heterogeneity *before* integrating "
       "(notebook 01).\n"
       "2. **Conformal coverage is only marginal & exchangeable.** Report coverage *per site*, not "
       "just pooled — a pooled 90% can hide a site at 82%.\n"
       "3. **Cross-site coverage drop is a curation signal.** A large off-diagonal drop tells you a "
       "site's data or measurement process differs enough to break transfer.\n"
       "4. **Mitigations to explore next:** per-site (group-balanced) calibration, conformal under "
       "covariate shift (importance weighting), and flagging measurement-heterogeneous features "
       "before they enter the model.\n"),
    md("### Capstone exercise\n"
       "Implement **per-site calibration**: calibrate a separate `q̂` for each site and re-draw the "
       "coverage-by-site chart. Does group-balanced calibration restore 90% coverage at Switzerland? "
       "What did you have to assume to do it (hint: you needed labelled data *at* Switzerland)?"),
])
write("04_conformal_under_site_shift.ipynb", nb04)

print("\nAll notebooks built.")
