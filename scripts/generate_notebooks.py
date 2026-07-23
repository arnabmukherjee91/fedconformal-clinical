"""
Generate the workshop Jupyter notebooks programmatically with nbformat.

Keeping the notebooks in a builder script means they stay in sync with the
package API and are easy to regenerate. Run:  python scripts/generate_notebooks.py
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
    "from fedconformal import data, conformal, evaluate as ev, federated, heterogeneity as het, viz, eda, paper_figures as pf\n"
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
       "A cholesterol of exactly 0 mg/dl is not a measurement — it is an *unrecorded* value, coded "
       "that way directly in the source files. `ca` (# vessels by fluoroscopy) and `thal` (thallium "
       "stress test) are coded `?` / `-9` in the raw files and load as genuine missing values. Watch "
       "which sites simply did not record certain labs — and how much more of the panel that covers "
       "than just cholesterol."),
    code("miss = het.missingness_report(df)\n"
         "display(miss.style.format('{:.0%}'))\n"
         "viz.plot_missingness(miss);"),
    md("**Switzerland never recorded cholesterol (100% unrecorded)** — a curation error, not biology, "
       "if pooled naively. But look at `ca` and `thal`: **98%+ missing at every site except "
       "Cleveland.** Any model using those two features is, outside Cleveland, almost entirely "
       "running on the mean-imputed value. That is a measurement-heterogeneity trap far bigger than "
       "cholesterol, and it is easy to miss if you only look at accuracy."),
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
       "Here the label is the 5-class disease-severity target (0 none · 1 mild · 2 moderate · "
       "3 severe · 4 critical), so a prediction set is any *subset* of those five classes, e.g. "
       "`{No disease, Mild}`."),
    code(BOOT),
    md("## A model to be uncertain about\n"
       "We train a softmax model on Cleveland (chosen automatically for K > 2 classes) and hold "
       "out half of it for calibration."),
    code("sd = sites['cleveland']\n"
         "rng = np.random.default_rng(0)\n"
         "idx = rng.permutation(sd.n)\n"
         "tr, cal, te = idx[:120], idx[120:210], idx[210:]\n"
         "model = federated.make_model(sd.X.shape[1], sd.n_classes)\n"
         "model = federated.local_train(model, sd.X[tr], sd.y[tr], epochs=300)\n"
         "cal_probs, cal_y = model.predict_proba(sd.X[cal]), sd.y[cal]\n"
         "test_probs, test_y = model.predict_proba(sd.X[te]), sd.y[te]\n"
         "print('classes:', sd.class_names)\n"
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
         "    p = m.predict_proba(sites[s].X).argmax(axis=1)\n"
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
         "viz.plot_set_size_distribution(sizes, n_classes=sd_c.n_classes);"),
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

# ---------------------------------------------------------------------------
# 00 - Input data exploration (run this FIRST)
# ---------------------------------------------------------------------------
nb00 = nb([
    md("# 00 · Getting to know the input data\n"
       "**Run this notebook first.** Before any modeling we look at the raw inputs: "
       "what we predict, what the features mean, how they relate to the outcome, and how "
       "all of that varies across the four hospital sites."),
    code(BOOT),
    md("## The dataset in one glance\n"
       "920 patients from four hospitals, 13 clinical features, one outcome. Each row is one "
       "patient's cardiac work-up."),
    code("print('patients:', len(df))\n"
         "print('sites   :', df['site'].unique().tolist())\n"
         "print('columns :', [c for c in df.columns if c != 'site'])\n"
         "df.head()"),
    md("## What are the classes? (the target)\n"
       "The target is the **original** UCI `num` column: `0` = no disease and `1`–`4` = disease "
       "of increasing severity (roughly, the number of major vessels with >50% narrowing). Unlike "
       "many tutorials, we do **not** collapse this to binary — the workshop's default task "
       "predicts the full **5-class** severity target directly, so a conformal prediction set is "
       "a *subset* of `{No disease, Mild, Moderate, Severe, Critical}`."),
    code("print('raw target values present:', sorted(df['target'].unique()))\n"
         "print('severity class counts:')\n"
         "print(df['target'].value_counts().sort_index())\n"
         "eda.plot_target_distribution(df);"),
    md("The full cohort skews toward the lower severities, but a derived *any-disease* view is "
       "close to balanced (~45% none / ~55% any) — and both pictures are misleading on their own, "
       "because the severity mix differs a lot by site:"),
    code("eda.plot_target_by_site(df);"),
    md("## The 13 features\n"
       "Five are **continuous** (age, resting blood pressure, cholesterol, max heart rate, ST "
       "depression) and eight are **categorical / ordinal** (sex, chest-pain type, fasting blood "
       "sugar, resting ECG, exercise angina, ST slope, #vessels, thalassemia test). The full data "
       "dictionary is in the `eda` module docstring:"),
    code("print(eda.__doc__)"),
    md("### Continuous features by severity\n"
       "Where the five severity curves (light = none, dark = critical) separate, the feature is "
       "informative. Note `chol`, `trestbps`, `thalach` are shown for *measured* values only "
       "(zeros are unrecorded)."),
    code("eda.plot_continuous_grid(df);"),
    md("### Categorical features: mean severity per level\n"
       "Bar height is the mean severity (0–4) within each category; the dashed line is the "
       "overall mean. Asymptomatic chest pain, exercise-induced angina, a flat/down ST slope and "
       "a reversible thalassemia defect all carry sharply higher mean severity — clinically "
       "sensible."),
    code("eda.plot_categorical_grid(df);"),
    md("> **Curation note:** `ca` and `thal` are unrecorded (`?`/`-9` in the raw files, loaded as "
       "NaN and dropped here) for the large majority of patients outside Cleveland — a bigger "
       "measurement-heterogeneity gap than cholesterol's zero-coded missingness. Spotting these is "
       "exactly the measurement-heterogeneity check the workshop is about; see notebook 01."),
    md("### One feature across sites\n"
       "Maximum heart rate achieved, by site — a quick look at how the same measurement shifts "
       "between hospitals."),
    code("eda.plot_feature_boxplots_by_site(df, 'thalach');"),
    md("### Correlation structure\n"
       "How features move together and with the outcome. `cp`, `exang`, `oldpeak`, `thalach` and "
       "`ca` are among the strongest correlates of disease."),
    code("eda.plot_correlation_heatmap(df);"),
    md("### Exercise\n"
       "1. Call `eda.plot_feature_boxplots_by_site(df, 'age')` and `'trestbps'`. Which feature is "
       "most consistent across sites, and which is most shifted?\n"
       "2. Using `df`, compute the mean severity (`df['target']`) for males vs females *within "
       "each site*. Does the sex effect look the same everywhere? (This previews the "
       "heterogeneity notebook.)"),
])
write("00_input_data_exploration.ipynb", nb00)

# ---------------------------------------------------------------------------
# 05 - Recreating the paper's figures
# ---------------------------------------------------------------------------
nb05 = nb([
    md("# 05 · Recreating the figures from the paper\n"
       "The `paper_figures` module reproduces the explanatory diagrams from "
       "Angelopoulos & Bates (2022) as clean, editable Matplotlib figures — ready for "
       "slides. The classification illustrations use the same 5-class severity target "
       "(0 = none … 4 = critical) that notebooks 00–04 actually predict, so the multiclass "
       "picture here matches the workshop's main task, not just a toy example; the regression "
       "illustrations use small synthetic examples, exactly as the paper does."),
    code(BOOT),
    md("## Figure 1 — Prediction set examples\n"
       "Unlike every other figure in this notebook, Figure 1 is **not** illustrative: it trains "
       "the real federated model, calibrates a real APS conformal predictor, and picks three real "
       "patients — all truly *No disease* — whose prediction sets grow from a confident singleton "
       "to a 4-class set in which *No disease* is not even the model's top guess. That mirrors the "
       "paper's own fox-squirrel panel, where the third photo fools the classifier into ranking "
       "*marmot* above the true class, yet the true class still survives inside the set."),
    code("pf.fig01_prediction_set_examples();"),
    md("## Figure 2 — Illustration of conformal prediction\n"
       "Compute a score on a holdout point → take the quantile q̂ → form the prediction set "
       "for a new point by keeping every class with softmax ≥ 1 − q̂."),
    code("pf.fig02_conformal_illustration();"),
    md("## Figure 4 — Adaptive Prediction Sets (APS)\n"
       "Sort classes by softmax and accumulate until the cumulative mass crosses q̂; the "
       "classes below the cut form the (adaptive) prediction set."),
    code("pf.fig04_aps_illustration();"),
    md("## Figure 6 — Conformalized Quantile Regression\n"
       "Fitted quantile curves, then widened by q̂ to reach the coverage guarantee."),
    code("pf.fig06_cqr_illustration();"),
    md("## Figure 8 — Conformalized uncertainty scalar\n"
       "A point prediction f(x) with a symmetric band q̂·u(x)."),
    code("pf.fig08_uncertainty_scalar();"),
    md("## Figure 9 — Conformalized Bayes\n"
       "The prediction set is the *superlevel set* of the posterior predictive density: "
       "{ y : f(y|x) ≥ threshold }."),
    code("pf.fig09_bayes_superlevel();"),
    md("## Figure 10 — Notions of coverage\n"
       "No coverage vs. marginal-only vs. conditional. Framed here as two **sites**: marginal "
       "coverage can hit 90% overall while one site is badly under-covered; conditional "
       "coverage requires 90% *at every site*. This is the workshop's core distinction."),
    code("pf.fig10_coverage_notions();"),
    md("## Figure 11 — Distribution of coverage vs. calibration-set size\n"
       "Coverage is itself random (it depends on the calibration draw); its Beta distribution "
       "narrows around 1 − α as the calibration set grows."),
    code("pf.fig11_coverage_distribution();"),
    md("### Exercise\n"
       "Every function takes keyword arguments (e.g. `alpha`, `ns`, `seed`). Regenerate "
       "Figure 11 with `ns=(30, 100, 300)` and Figure 2 with `alpha=0.2`. How does a larger α "
       "change q̂ and the size of the prediction set?"),
])
write("05_recreating_paper_figures.ipynb", nb05)

# ---------------------------------------------------------------------------
# 06 - Multiclass task: predicting chest-pain type
# ---------------------------------------------------------------------------
nb06 = nb([
    md("# 06 · Multiclass conformal prediction — chest-pain type\n"
       "So far the task was the 5-class disease-severity target. Here we switch to a *different* "
       "**4-class** target: the **chest-pain type** `cp` (1 typical angina · 2 atypical angina · "
       "3 non-anginal pain · 4 asymptomatic), predicted from the other 12 clinical features. "
       "This is a second natural multiclass setting for conformal prediction — a prediction set "
       "is now a *set of chest-pain types*, e.g. `{atypical, non-anginal}`.\n\n"
       "Everything reuses the same package: only the model becomes a softmax (multinomial) "
       "logistic regression, chosen automatically from the number of classes."),
    code(BOOT + "\n"
         "# reload the four sites for the 4-class chest-pain task\n"
         "sites = data.load_sites(task='cp', shared_scaler=True)\n"
         "K = data.n_classes('cp'); names = data.class_names('cp')\n"
         "print('classes:', names)"),
    md("## Label shift: chest-pain type varies a lot across sites\n"
       "Hungary is heavy on *atypical angina*; Switzerland is ~80% *asymptomatic*. This is the "
       "multiclass analogue of the disease-prevalence shift from notebook 01."),
    code("dist = data.class_distribution(sites)\n"
         "display((dist*100).round(1))\n"
         "viz.plot_class_distribution_by_site(dist, title='Chest-pain type distribution by site');"),
    md("## Federated softmax model (hold out Switzerland)\n"
       "`federated_averaging` detects 4 classes and builds a `SoftmaxModel` automatically."),
    code("fed = federated.federated_averaging(sites, rounds=60, local_epochs=3,\n"
         "                                    train_sites=['cleveland','hungarian','va'], seed=0)\n"
         "model = fed.global_model\n"
         "print('model:', type(model).__name__, '| K =', model.n_classes)\n"
         "viz.plot_fed_learning_curves(fed.history);"),
    md("## Calibrate APS and check coverage\n"
       "A single split fluctuates; averaged over many splits, marginal coverage sits on 1−α."),
    code("import numpy as np\n"
         "train=['cleveland','hungarian','va']\n"
         "X=np.vstack([sites[s].X for s in train]); y=np.concatenate([sites[s].y for s in train])\n"
         "P=model.predict_proba(X)\n"
         "covs=[]\n"
         "for seed in range(200):\n"
         "    r=np.random.default_rng(seed).permutation(len(y)); c,t=r[:len(y)//2], r[len(y)//2:]\n"
         "    cp=conformal.APSPredictor(alpha=0.1,seed=seed).calibrate(P[c],y[c])\n"
         "    covs.append(ev.coverage(cp.predict_set(P[t]),y[t]))\n"
         "print(f'APS mean marginal coverage = {np.mean(covs):.3f}  (target 0.90)')"),
    md("## The multiclass lesson: class-conditional coverage\n"
       "Marginal coverage ≈ 90% can hide severe under-coverage of a **rare class**. Calibrate "
       "APS on a pooled set and look at coverage *within each true class*."),
    code("r=np.random.default_rng(1).permutation(len(y)); c,t=r[:len(y)//2], r[len(y)//2:]\n"
         "cp=conformal.APSPredictor(alpha=0.1,seed=0).calibrate(P[c],y[c])\n"
         "sets=cp.predict_set(P[t])\n"
         "cc=ev.class_conditional_coverage(sets,y[t],n_classes=K)\n"
         "for k,rv in cc.items(): print(f'{names[k]:18s} n={rv[\"n\"]:4d}  coverage={rv[\"coverage\"]:.3f}')\n"
         "viz.plot_class_conditional_coverage({k:v['coverage'] for k,v in cc.items()}, 0.1, class_names=names);"),
    md("**Typical angina (the rare class) is badly under-covered**, while *asymptomatic* (the "
       "common class) over-covers. Marginal coverage alone would never reveal this — a crucial "
       "point when a curation pipeline serves under-represented patient groups."),
    md("## Cross-site transfer and prediction-set sizes"),
    code("import pandas as pd\n"
         "cov=pd.DataFrame(index=data.SITES,columns=data.SITES,dtype=float)\n"
         "for si in data.SITES:\n"
         "    c=conformal.APSPredictor(alpha=0.1,seed=0).calibrate(model.predict_proba(sites[si].X),sites[si].y)\n"
         "    for sj in data.SITES:\n"
         "        cov.loc[si,sj]=ev.coverage(c.predict_set(model.predict_proba(sites[sj].X)),sites[sj].y)\n"
         "viz.plot_transfer_matrix(cov.astype(float),0.1);"),
    code("cpc=conformal.APSPredictor(alpha=0.1,seed=0).calibrate(model.predict_proba(sites['cleveland'].X),sites['cleveland'].y)\n"
         "sizes={s:ev.set_sizes(cpc.predict_set(model.predict_proba(sites[s].X))) for s in data.SITES}\n"
         "viz.plot_set_size_distribution(sizes, n_classes=K);"),
    md("### Exercise\n"
       "1. Switch APS → LAC (`conformal.LACPredictor`) and compare average set size and the "
       "class-conditional coverage. Which method is fairer to the rare class?\n"
       "2. Implement **class-conditional calibration**: fit a separate q̂ per true class "
       "(Section 4.2 of the paper). Does it lift typical-angina coverage back to 90%, and what "
       "does it cost in average set size?"),
])
write("06_chest_pain_multiclass.ipynb", nb06)

# ---------------------------------------------------------------------------
# Task comparison (descriptively named, not numbered)
# ---------------------------------------------------------------------------
nb_cmp = nb([
    md("# Which task is more heterogeneous — and which gives bigger prediction sets?\n"
       "*A head-to-head comparison of the two classification tasks, using **every** feature.*\n\n"
       "We put the **5-class disease-severity** task and the **4-class chest-pain** task side by "
       "side and ask two questions:\n\n"
       "1. **Which task carries more site-level heterogeneity?**\n"
       "2. **Which task yields more conformal labels per sample** (larger prediction sets)?\n\n"
       "Each task uses all columns except its own label as features, so the disease model uses the "
       "13 clinical variables (including chest-pain type) and the chest-pain model uses the other 12 "
       "plus the disease target. The analysis logic lives in `scripts/compare_prediction_tasks.py`; we import "
       "and call it here so the notebook stays in sync with the script."),
    code(BOOT + "\n"
         "sys.path.insert(0, os.path.abspath(os.path.join('..', 'scripts')))\n"
         "import compare_prediction_tasks as ct"),
    md("## Run the comparison\n"
       "For each task this trains one shared model on all four sites, measures three kinds of "
       "heterogeneity, and computes the average conformal set size (APS, α = 0.1)."),
    code("df = data.load_raw()\n"
         "dz = ct.analyze(df, 'disease')\n"
         "cp = ct.analyze(df, 'cp')\n"
         "tbl = pd.DataFrame([dz, cp]).set_index('task')[[\n"
         "    'n_features','K','label_js','domain_auc','cov_off_mean',\n"
         "    'cov_worst','cov_drop','marginal_cov','avg_set_size','avg_set_size_norm']]\n"
         "tbl.round(3)"),
    md("Column guide: `label_js` = mean pairwise Jensen–Shannon divergence between the four sites' "
       "class distributions (label shift); `domain_auc` = mean pairwise domain-classifier AUC "
       "(covariate shift); `cov_off_mean` / `cov_worst` = mean / worst cross-site coverage; "
       "`cov_drop` = target − mean cross-site coverage; `avg_set_size` = conformal labels per "
       "sample; `avg_set_size_norm` = that divided by the number of classes."),
    md("## The picture"),
    code("ct.plot_comparison(dz, cp);"),
    md("## Verdict"),
    code("more_het  = 'chest-pain' if cp['label_js']  > dz['label_js']  else 'disease'\n"
         "more_sets = 'chest-pain' if cp['avg_set_size'] > dz['avg_set_size'] else 'disease'\n"
         "print(f\"Label-shift heterogeneity higher in : {more_het}  \"\n"
         "      f\"(JS {max(cp['label_js'],dz['label_js']):.3f} vs {min(cp['label_js'],dz['label_js']):.3f})\")\n"
         "print(f\"More conformal labels per sample in : {more_sets}  \"\n"
         "      f\"(|C| {max(cp['avg_set_size'],dz['avg_set_size']):.2f} vs \"\n"
         "      f\"{min(cp['avg_set_size'],dz['avg_set_size']):.2f})\")"),
    md("**Reading the result.** The **5-class disease-severity** task is the more heterogeneous "
       "across sites by label shift (JS ≈ 0.13 vs ≈ 0.07 for chest-pain — the severity mix swings "
       "far more across hospitals than chest-pain type does), and it also produces the larger raw "
       "prediction sets (~2.7 labels/sample vs ~2.3), simply because it has one more class. "
       "Normalised by the number of classes the two tasks are close (chest-pain fills a slightly "
       "*larger* fraction of its label space), so once you account for K the two tasks carry "
       "comparable local uncertainty — the real gap between them is in cross-site label shift, not "
       "set size. At matched conditions, APS keeps cross-site coverage close to the 90% target for "
       "both (worst-case site still ≈ 87-88%) — so here heterogeneity shows up mainly as label "
       "shift, not as a large coverage break."),
    md("### Exercise\n"
       "1. Re-run with `ALPHA` changed in `compare_prediction_tasks.py` (e.g. 0.05). How do the set sizes and the "
       "verdict move?\n"
       "2. Restrict each task to a *shared* 12-feature set (drop the other task's label from the "
       "features) and re-compute. Does using 'every feature' change which task looks more heterogeneous?"),
])
write("07_task_comparison.ipynb", nb_cmp)

print("\nAll notebooks built.")
