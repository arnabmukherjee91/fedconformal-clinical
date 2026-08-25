"""
End-to-end pipeline: data loading through cross-site conformal evaluation.

Runs the full pipeline and writes every figure to ``figures/``:

  1. Load the 4-site UCI Heart Disease federation.
  2. Quantify site-level heterogeneity (label shift, measurement heterogeneity,
     JS divergence, domain-classifier AUC).
  3. Train a global model with FedAvg (holding one site out as an external site).
  4. Fit split-conformal predictors (LAC & APS) and check coverage.
  5. THE punchline: calibrate at one site, deploy at another -> coverage breaks.
  6. Adaptivity (set sizes) and the calibration-set-size effect.

Run:  python scripts/run_end_to_end_pipeline.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

# make ``src`` importable when run from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, conformal, evaluate as ev, federated, heterogeneity as het, viz

FIG = os.path.join(os.path.dirname(__file__), "..", "figures")
os.makedirs(FIG, exist_ok=True)
ALPHA = 0.10
RNG = np.random.default_rng(0)


def fig(name):
    return os.path.join(FIG, name)


def split_calib_test(sd, frac_cal=0.5, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(sd.n)
    k = int(sd.n * frac_cal)
    return idx[:k], idx[k:]


def main():
    print("== 1. Load sites ==")
    df = data.load_raw()
    sites = data.load_sites(shared_scaler=True)
    summary = data.summarize_sites(sites, df)
    print(summary.to_string(index=False))
    viz.plot_site_overview(summary, save=fig("01_site_overview.png"))

    print("\n== 2. Heterogeneity diagnostics ==")
    miss = het.missingness_report(df)
    print("Unrecorded fractions:\n", miss.to_string())
    viz.plot_missingness(miss, save=fig("02_missingness.png"))
    viz.plot_feature_distributions(df, "chol", save=fig("03_chol_distributions.png"))

    js = het.js_divergence_matrix(df, "thalach")
    viz.plot_divergence_matrix(js, "Jensen-Shannon divergence (max heart rate)",
                               save=fig("04_js_divergence.png"))
    auc = het.domain_auc_matrix(sites)
    print("Domain-classifier AUC:\n", auc.round(2).to_string())
    viz.plot_divergence_matrix(auc, "Domain-classifier AUC (site vs site)",
                               save=fig("05_domain_auc.png"), cmap="Oranges")

    print("\n== 3. Federated training (hold out Switzerland as external site) ==")
    train_sites = ["cleveland", "hungarian", "va"]
    fed = federated.federated_averaging(sites, rounds=200, local_epochs=3,
                                        train_sites=train_sites, seed=0)
    viz.plot_fed_learning_curves(fed.history, save=fig("06_fed_curves.png"))
    model = fed.global_model

    print("\n== 4. Split-conformal at a pooled calibration set ==")
    # build a pooled calibration/test split over the TRAIN sites
    cal_probs, cal_y, test_probs, test_y, test_site = [], [], [], [], []
    for s in train_sites:
        sd = sites[s]
        ci, ti = split_calib_test(sd, seed=1)
        cal_probs.append(model.predict_proba(sd.X[ci])); cal_y.append(sd.y[ci])
        test_probs.append(model.predict_proba(sd.X[ti])); test_y.append(sd.y[ti])
        test_site += [s] * len(ti)
    cal_probs = np.vstack(cal_probs); cal_y = np.concatenate(cal_y)
    test_probs = np.vstack(test_probs); test_y = np.concatenate(test_y)
    test_site = np.array(test_site)

    lac = conformal.LACPredictor(alpha=ALPHA).calibrate(cal_probs, cal_y)
    scores = conformal.lac_scores(cal_probs, cal_y)
    viz.plot_calibration_scores(scores, lac.qhat, ALPHA, save=fig("07_calibration_scores.png"))

    sets = lac.predict_set(test_probs)
    res = ev.evaluate_all(sets, test_y, groups=test_site)
    print(f"Pooled test coverage = {res['coverage']:.3f}  (target {1-ALPHA:.2f}), "
          f"avg set size = {res['avg_set_size']:.2f}")

    print("\n== 5. Cross-site transfer: calibrate at site i, deploy at site j ==")
    all_sites = data.SITES
    cov_matrix = pd.DataFrame(index=all_sites, columns=all_sites, dtype=float)
    for si in all_sites:
        sd_i = sites[si]
        cal_p = model.predict_proba(sd_i.X)
        cp = conformal.LACPredictor(alpha=ALPHA).calibrate(cal_p, sd_i.y)
        for sj in all_sites:
            sd_j = sites[sj]
            s = cp.predict_set(model.predict_proba(sd_j.X))
            cov_matrix.loc[si, sj] = ev.coverage(s, sd_j.y)
    print(cov_matrix.astype(float).round(2).to_string())
    viz.plot_transfer_matrix(cov_matrix.astype(float), ALPHA,
                             save=fig("08_transfer_matrix.png"))

    # deploy a Cleveland-calibrated predictor everywhere (the headline story)
    sd_c = sites["cleveland"]
    cp_c = conformal.LACPredictor(alpha=ALPHA).calibrate(model.predict_proba(sd_c.X), sd_c.y)
    cov_by_site = {s: ev.coverage(cp_c.predict_set(model.predict_proba(sites[s].X)),
                                  sites[s].y) for s in all_sites}
    viz.plot_coverage_by_site(cov_by_site, ALPHA, n_cal=sd_c.n,
                              title="Coverage of a Cleveland-calibrated model across sites",
                              save=fig("09_coverage_by_site.png"))

    print("\n== 6. Adaptivity & calibration-set size ==")
    sizes_by_site = {}
    for s in all_sites:
        st = cp_c.predict_set(model.predict_proba(sites[s].X))
        sizes_by_site[s] = ev.set_sizes(st)
    viz.plot_set_size_distribution(sizes_by_site, save=fig("10_set_sizes.png"))
    viz.plot_coverage_beta(alpha=ALPHA, ns=(50, 150, 1000), save=fig("11_coverage_beta.png"))

    print(f"\nAll figures written to {os.path.abspath(FIG)}")


if __name__ == "__main__":
    main()
