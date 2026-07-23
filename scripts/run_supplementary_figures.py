"""
Supplementary diagnostic figures that fill gaps in the original figure set:
scatter views of site separability (no scatterplot existed before) and a
pipeline schematic. Written for the workshop write-up.
Run: python scripts/run_supplementary_figures.py
Writes to figures/extra/.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, viz

FIG = os.path.join(os.path.dirname(__file__), "..", "figures", "extra")
os.makedirs(FIG, exist_ok=True)


def fig(name):
    return os.path.join(FIG, name)


def main():
    df = data.load_raw()
    sites = data.load_sites(shared_scaler=True)

    viz.plot_pca_scatter(sites, save=fig("x01_pca_scatter.png"))
    viz.plot_age_thalach_scatter(df, save=fig("x02_age_thalach_scatter.png"))
    viz.plot_pipeline_overview(save=fig("x03_pipeline_overview.png"))

    print(f"Extra figures written to {os.path.abspath(FIG)}")


if __name__ == "__main__":
    main()
