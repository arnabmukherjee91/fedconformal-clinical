"""
Regenerate the recreations of the paper's explanatory figures
(Angelopoulos & Bates, 2022). Run:  python scripts/run_paper_figure_recreations.py
Writes to figures/paper/.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import paper_figures as pf

FIG = os.path.join(os.path.dirname(__file__), "..", "figures", "paper")
os.makedirs(FIG, exist_ok=True)


def f(name):
    return os.path.join(FIG, name)


def main():
    pf.fig01_prediction_set_examples(save=f("fig01_prediction_set_examples.png"))
    pf.fig02_conformal_illustration(save=f("fig02_conformal_illustration.png"))
    pf.fig04_aps_illustration(save=f("fig04_adaptive_prediction_sets.png"))
    pf.fig06_cqr_illustration(save=f("fig06_conformalized_quantile_regression.png"))
    pf.fig08_uncertainty_scalar(save=f("fig08_uncertainty_scalar.png"))
    pf.fig09_bayes_superlevel(save=f("fig09_conformalized_bayes.png"))
    pf.fig10_coverage_notions(save=f("fig10_coverage_notions.png"))
    pf.fig11_coverage_distribution(save=f("fig11_coverage_distribution.png"))
    print(f"Paper-figure recreations written to {os.path.abspath(FIG)}")


if __name__ == "__main__":
    main()
