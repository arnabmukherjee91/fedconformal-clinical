"""
End-to-end demo for the 4-class CHEST-PAIN-TYPE task.

Predict `cp` (1 typical angina / 2 atypical angina / 3 non-anginal / 4
asymptomatic) from the other 12 clinical features, in the federated multi-site
setting. This is the natural multiclass showcase for conformal prediction: a
prediction set is now a set of chest-pain types.

Writes every figure to figures/cp/.  Run:  python scripts/run_demo_cp.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, conformal, evaluate as ev, federated, viz

FIG = os.path.join(os.path.dirname(__file__), "..", "figures", "cp")
os.makedirs(FIG, exist_ok=True)
ALPHA = 0.10
TASK = "cp"


def fig(name):
    return os.path.join(FIG, name)


def split_calib_test(sd, frac_cal=0.5, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(sd.n)
    k = int(sd.n * frac_cal)
    return idx[:k], idx[k:]


def main():
    print("== 1. Load sites (task = chest-pain type, 4 classes) ==")
    df = data.load_raw()
    sites = data.load_sites(task=TASK, shared_scaler=True)
    K = data.n_classes(TASK)
    names = data.class_names(TASK)
    print(data.summarize_sites(sites, df).to_string(index=False))

    dist = data.class_distribution(sites)
    print("\nPer-site class fractions:\n", (dist * 100).round(1).to_string())
    viz.plot_class_distribution_by_site(
        dist, save=fig("c01_class_distribution.png"),
        title="Chest-pain type distribution by site (label shift)")

    print("\n== 2. Federated training (softmax FedAvg, hold out Switzerland) ==")
    train_sites = ["cleveland", "hungarian", "va"]
    fed = federated.federated_averaging(sites, rounds=60, local_epochs=3,
                                        train_sites=train_sites, seed=0)
    viz.plot_fed_learning_curves(fed.history, save=fig("c02_fed_curves.png"))
    model = fed.global_model
    print("global model type:", type(model).__name__, "| K =", model.n_classes)

    print("\n== 3. Split-conformal (APS) on a pooled calibration set ==")
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

    aps = conformal.APSPredictor(alpha=ALPHA, seed=0).calibrate(cal_probs, cal_y)
    lac = conformal.LACPredictor(alpha=ALPHA).calibrate(cal_probs, cal_y)
    aps_sets = aps.predict_set(test_probs)
    lac_sets = lac.predict_set(test_probs)
    print(f"APS (single split): coverage={ev.coverage(aps_sets, test_y):.3f}  "
          f"avg|C|={ev.average_set_size(aps_sets):.2f}")
    print(f"LAC (single split): coverage={ev.coverage(lac_sets, test_y):.3f}  "
          f"avg|C|={ev.average_set_size(lac_sets):.2f}")
    # a single split fluctuates; average over many splits should sit on 1-alpha
    pooled_X = np.vstack([sites[s].X for s in train_sites])
    pooled_y = np.concatenate([sites[s].y for s in train_sites])
    pooled_P = model.predict_proba(pooled_X)
    covs = []
    for seed in range(200):
        r = np.random.default_rng(seed).permutation(len(pooled_y))
        c, t = r[: len(pooled_y) // 2], r[len(pooled_y) // 2:]
        cp = conformal.APSPredictor(alpha=ALPHA, seed=seed).calibrate(pooled_P[c], pooled_y[c])
        covs.append(ev.coverage(cp.predict_set(pooled_P[t]), pooled_y[t]))
    print(f"APS mean coverage over 200 splits = {np.mean(covs):.3f}  (target {1-ALPHA:.2f})")

    scores = conformal.lac_scores(cal_probs, cal_y)
    viz.plot_calibration_scores(scores, lac.qhat, ALPHA,
                                save=fig("c03_calibration_scores.png"))

    print("\n== 4. Class-conditional coverage (APS, pooled test) ==")
    cc = ev.class_conditional_coverage(aps_sets, test_y, n_classes=K)
    for c, r in cc.items():
        print(f"  {names[c]:18s} n={r['n']:4d}  coverage={r['coverage']:.3f}")
    viz.plot_class_conditional_coverage({c: r["coverage"] for c, r in cc.items()},
                                        ALPHA, class_names=names,
                                        save=fig("c04_class_conditional.png"))

    print("\n== 5. Cross-site coverage transfer (APS, calibrate i / deploy j) ==")
    all_sites = data.SITES
    cov = pd.DataFrame(index=all_sites, columns=all_sites, dtype=float)
    for si in all_sites:
        sd_i = sites[si]
        cp = conformal.APSPredictor(alpha=ALPHA, seed=0).calibrate(
            model.predict_proba(sd_i.X), sd_i.y)
        for sj in all_sites:
            sd_j = sites[sj]
            s = cp.predict_set(model.predict_proba(sd_j.X))
            cov.loc[si, sj] = ev.coverage(s, sd_j.y)
    print(cov.astype(float).round(2).to_string())
    viz.plot_transfer_matrix(cov.astype(float), ALPHA, save=fig("c05_transfer_matrix.png"))

    # Cleveland-calibrated, deployed everywhere
    sd_c = sites["cleveland"]
    cp_c = conformal.APSPredictor(alpha=ALPHA, seed=0).calibrate(
        model.predict_proba(sd_c.X), sd_c.y)
    cov_by_site = {s: ev.coverage(cp_c.predict_set(model.predict_proba(sites[s].X)),
                                  sites[s].y) for s in all_sites}
    viz.plot_coverage_by_site(cov_by_site, ALPHA, n_cal=sd_c.n,
                              title="APS coverage of a Cleveland-calibrated model (cp task)",
                              save=fig("c06_coverage_by_site.png"))

    print("\n== 6. Prediction-set size distribution (adaptivity) ==")
    sizes_by_site = {s: ev.set_sizes(cp_c.predict_set(model.predict_proba(sites[s].X)))
                     for s in all_sites}
    viz.plot_set_size_distribution(sizes_by_site, n_classes=K,
                                   save=fig("c07_set_sizes.png"))

    print(f"\nAll cp-task figures written to {os.path.abspath(FIG)}")


if __name__ == "__main__":
    main()
