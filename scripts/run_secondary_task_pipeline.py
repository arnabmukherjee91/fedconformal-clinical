"""
End-to-end federated + conformal pipeline for a secondary clinical-variable
prediction task, run against every task in ``TASKS_TO_RUN``.

This generalizes ``run_chest_pain_pipeline.py`` (which stays as-is, since the
report references it by name) to any task registered in
``fedconformal.data.TASKS``: same federated model, same split-conformal
calibration, same cross-site transfer-matrix diagnostic, just parameterized by
task instead of hard-coded to ``"cp"``. Each task's figures land in its own
``figures/<task>/`` directory.

Run:  python scripts/run_secondary_task_pipeline.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, conformal, evaluate as ev, federated, viz

FIG_ROOT = os.path.join(os.path.dirname(__file__), "..", "figures")
ALPHA = 0.10
TRAIN_SITES = ["cleveland", "hungarian", "va"]

#: Task -> (plain-language title for the class-distribution plot, FedAvg rounds).
#: Rounds is lower than the 5-class disease task (200) since these tasks have
#: fewer classes and converge faster; matches the 60 already used for "cp".
TASKS_TO_RUN = {
    "restecg": ("Resting ECG result distribution by site (label shift)", 60),
    "exang": ("Exercise-induced angina distribution by site (label shift)", 60),
}


def split_calib_test(sd, frac_cal=0.5, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(sd.n)
    k = int(sd.n * frac_cal)
    return idx[:k], idx[k:]


def run_task(task: str, title: str, rounds: int):
    fig_dir = os.path.join(FIG_ROOT, task)
    os.makedirs(fig_dir, exist_ok=True)

    def fig(name):
        return os.path.join(fig_dir, name)

    print(f"\n{'=' * 70}\nTask = {task!r}\n{'=' * 70}")

    print("== 1. Load sites ==")
    df = data.load_raw()
    sites = data.load_sites(task=task, shared_scaler=True)
    K = data.n_classes(task)
    names = data.class_names(task)
    print(data.summarize_sites(sites, df).to_string(index=False))

    dist = data.class_distribution(sites)
    print("\nPer-site class fractions:\n", (dist * 100).round(1).to_string())
    viz.plot_class_distribution_by_site(dist, save=fig("01_class_distribution.png"),
                                        title=title)

    print(f"\n== 2. Federated training ({'softmax' if K > 2 else 'logistic'} "
          f"FedAvg, hold out Switzerland) ==")
    fed = federated.federated_averaging(sites, rounds=rounds, local_epochs=3,
                                        train_sites=TRAIN_SITES, n_classes=K, seed=0)
    viz.plot_fed_learning_curves(fed.history, save=fig("02_fed_curves.png"))
    model = fed.global_model
    print("global model type:", type(model).__name__, "| K =", model.n_classes)

    print("\n== 3. Split-conformal (APS) on a pooled calibration set ==")
    cal_probs, cal_y, test_probs, test_y, test_site = [], [], [], [], []
    for s in TRAIN_SITES:
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

    scores = conformal.lac_scores(cal_probs, cal_y)
    viz.plot_calibration_scores(scores, lac.qhat, ALPHA, save=fig("03_calibration_scores.png"))

    print("\n== 4. Class-conditional coverage (APS, pooled test) ==")
    cc = ev.class_conditional_coverage(aps_sets, test_y, n_classes=K)
    for c, r in cc.items():
        print(f"  {names[c]:24s} n={r['n']:4d}  coverage={r['coverage']:.3f}")
    viz.plot_class_conditional_coverage({c: r["coverage"] for c, r in cc.items()},
                                        ALPHA, class_names=names,
                                        save=fig("04_class_conditional.png"))

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
    viz.plot_transfer_matrix(cov.astype(float), ALPHA, save=fig("05_transfer_matrix.png"))

    # Cleveland-calibrated, deployed everywhere -- the same headline framing
    # used for the disease task (Fig. 7.3) and the chest-pain task (Fig. 9.5).
    sd_c = sites["cleveland"]
    cp_c = conformal.APSPredictor(alpha=ALPHA, seed=0).calibrate(
        model.predict_proba(sd_c.X), sd_c.y)
    cov_by_site = {s: ev.coverage(cp_c.predict_set(model.predict_proba(sites[s].X)),
                                  sites[s].y) for s in all_sites}
    viz.plot_coverage_by_site(cov_by_site, ALPHA, n_cal=sd_c.n,
                              title=f"APS coverage of a Cleveland-calibrated model ({task} task)",
                              save=fig("06_coverage_by_site.png"))

    print("\n== 6. Prediction-set size distribution (adaptivity) ==")
    sizes_by_site = {s: ev.set_sizes(cp_c.predict_set(model.predict_proba(sites[s].X)))
                     for s in all_sites}
    viz.plot_set_size_distribution(sizes_by_site, n_classes=K, save=fig("07_set_sizes.png"))

    print(f"\n{task} figures written to {os.path.abspath(fig_dir)}")
    return cov.astype(float)


def main():
    results = {}
    for task, (title, rounds) in TASKS_TO_RUN.items():
        results[task] = run_task(task, title, rounds)

    print(f"\n{'=' * 70}\nSummary: worst-case cross-site coverage drop vs. {1 - ALPHA:.0%} target\n{'=' * 70}")
    for task, cov in results.items():
        offdiag = cov.to_numpy().copy()
        np.fill_diagonal(offdiag, np.nan)
        worst = np.nanmin(offdiag)
        print(f"  {task:10s} worst off-diagonal coverage = {worst:.3f} "
              f"({(worst - (1 - ALPHA)) * 100:+.1f} pp vs target)")


if __name__ == "__main__":
    main()
