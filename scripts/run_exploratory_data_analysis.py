"""
Input-data exploration: generate the EDA figures for the raw UCI Heart Disease
inputs. Run:  python scripts/run_exploratory_data_analysis.py  ->  writes to figures/eda/
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fedconformal import data, eda

FIG = os.path.join(os.path.dirname(__file__), "..", "figures", "eda")
os.makedirs(FIG, exist_ok=True)


def fig(name):
    return os.path.join(FIG, name)


def main():
    df = data.load_raw()
    print(f"Loaded {len(df)} patients from {df['site'].nunique()} sites.")
    print("\nRaw target class counts (0 = no disease, 1-4 = increasing severity):")
    print(df["target"].value_counts().sort_index().to_string())
    print(f"\nBinary prevalence P(disease) = {(df['target'] > 0).mean():.3f}")

    eda.plot_target_distribution(df, save=fig("e01_target_distribution.png"))
    eda.plot_target_by_site(df, save=fig("e02_target_by_site.png"))
    eda.plot_continuous_grid(df, save=fig("e03_continuous_grid.png"))
    eda.plot_feature_boxplots_by_site(df, "thalach", save=fig("e04_thalach_by_site.png"))
    eda.plot_categorical_grid(df, save=fig("e05_categorical_grid.png"))
    eda.plot_correlation_heatmap(df, save=fig("e06_correlation.png"))
    print(f"\nEDA figures written to {os.path.abspath(FIG)}")


if __name__ == "__main__":
    main()
