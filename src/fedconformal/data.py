"""
Data loading and preprocessing for the multi-site UCI Heart Disease dataset.

The UCI Heart Disease database (Detrano et al., 1989) is one of the very few
*naturally federated* public clinical datasets: the exact same case-report form
was collected at four different institutions:

    - Cleveland Clinic Foundation      (cleveland)   n = 303
    - Hungarian Institute of Cardiology (hungarian)  n = 294
    - University Hospital, Zurich/Basel (switzerland) n = 123
    - V.A. Medical Center, Long Beach   (va)          n = 200

Because each "site" is a real hospital, the dataset exhibits genuine
*site-level heterogeneity* -- both true distributional shift (e.g. disease
prevalence ranges from 36% at Hungary to 93% at Switzerland) and
*measurement-induced* heterogeneity (e.g. serum cholesterol was simply not
recorded at Switzerland, so it appears as a constant 0). This makes it an ideal
teaching dataset for a workshop on federated ML and uncertainty quantification
for research-data curation.

This module loads a bundled mirror of the four concatenated processed files and
reconstructs the per-site labels from the (well documented) row counts, so the
notebooks run offline with no external download.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

#: Column names of the 13 "processed" UCI Heart Disease features + target.
COLUMNS = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal", "target",
]

FEATURES = COLUMNS[:-1]

#: The four sites, in the canonical order the processed files are concatenated.
SITES = ["cleveland", "hungarian", "switzerland", "va"]

#: Human-readable names for plots.
SITE_LABELS = {
    "cleveland": "Cleveland Clinic",
    "hungarian": "Hungarian Inst. of Cardiology",
    "switzerland": "Univ. Hospital Zurich (Switzerland)",
    "va": "V.A. Long Beach",
}

#: Row counts of each processed site file (used to reconstruct site labels).
SITE_COUNTS = {"cleveland": 303, "hungarian": 294, "switzerland": 123, "va": 200}

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CSV = os.path.normpath(
    os.path.join(_HERE, "..", "..", "data", "raw", "heart_disease_4sites_raw.csv")
)


# ----------------------------------------------------------------------------
# Site container
# ----------------------------------------------------------------------------

@dataclass
class SiteData:
    """Holds one hospital's data in a federated simulation."""

    name: str
    X: np.ndarray                       # (n, d) preprocessed feature matrix
    y: np.ndarray                       # (n,) binary label (0 = no disease, 1 = disease)
    feature_names: list = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.y)

    @property
    def label(self) -> str:
        return SITE_LABELS.get(self.name, self.name)

    def __repr__(self) -> str:
        return f"SiteData({self.name!r}, n={self.n}, prevalence={self.y.mean():.2f})"


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def load_raw(csv_path: str | None = None) -> pd.DataFrame:
    """Load the bundled 4-site CSV and attach a ``site`` column.

    Returns a DataFrame with the 13 raw features, the raw ``target`` (0-4)
    and a ``site`` column. Missing values in this mirror are already coded
    (e.g. Switzerland cholesterol = 0), which we preserve so that the
    measurement-heterogeneity story stays visible.
    """
    path = csv_path or _DEFAULT_CSV
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if len(df) != sum(SITE_COUNTS.values()):
        raise ValueError(
            f"Expected {sum(SITE_COUNTS.values())} rows, got {len(df)}. "
            "The bundled mirror may have changed; site reconstruction is unsafe."
        )
    site_col = []
    for name in SITES:
        site_col.extend([name] * SITE_COUNTS[name])
    df = df.copy()
    df["site"] = site_col
    return df


def binarize_target(target: pd.Series | np.ndarray) -> np.ndarray:
    """UCI target is 0 (no disease) or 1-4 (increasing severity).

    The standard binary task is disease present (>0) vs. absent (0).
    """
    t = np.asarray(target)
    return (t > 0).astype(int)


def preprocess(
    df: pd.DataFrame,
    standardize: bool = True,
    scaler_stats: tuple | None = None,
) -> tuple[np.ndarray, np.ndarray, tuple]:
    """Turn raw rows into a model-ready (X, y).

    We keep the feature engineering deliberately simple and *identical across
    sites* so that any residual differences reflect the data, not the pipeline
    -- this is the whole point of a curation-focused workshop.

    Parameters
    ----------
    standardize:
        If True, z-score each feature. To avoid leaking global statistics into
        a federated setting, pass ``scaler_stats=(mean, std)`` computed on a
        reference site (or shared) so every site uses the *same* transform.
    scaler_stats:
        Optional ``(mean, std)`` arrays to apply. If None and standardize is
        True, statistics are computed from ``df`` itself.
    """
    X = df[FEATURES].astype(float).to_numpy()
    y = binarize_target(df["target"])

    stats = scaler_stats
    if standardize:
        if stats is None:
            mean = X.mean(axis=0)
            std = X.std(axis=0)
            std[std == 0] = 1.0
            stats = (mean, std)
        mean, std = stats
        X = (X - mean) / std
    return X, y, stats


def load_sites(
    csv_path: str | None = None,
    standardize: bool = True,
    shared_scaler: bool = True,
) -> dict[str, SiteData]:
    """Load the dataset already split into the four hospital sites.

    Parameters
    ----------
    shared_scaler:
        If True (default) all sites are standardized with statistics pooled
        across every site. This mimics a curation pipeline that has agreed on a
        common normalization. Set False to standardize each site independently
        (which *hides* real scale differences -- a useful contrast to show in
        the workshop).
    """
    df = load_raw(csv_path)

    shared_stats = None
    if standardize and shared_scaler:
        Xall = df[FEATURES].astype(float).to_numpy()
        mean = Xall.mean(axis=0)
        std = Xall.std(axis=0)
        std[std == 0] = 1.0
        shared_stats = (mean, std)

    sites: dict[str, SiteData] = {}
    for name in SITES:
        sub = df[df["site"] == name]
        X, y, _ = preprocess(
            sub, standardize=standardize, scaler_stats=shared_stats
        )
        sites[name] = SiteData(name=name, X=X, y=y, feature_names=list(FEATURES))
    return sites


def summarize_sites(sites: dict[str, SiteData], df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a tidy per-site summary table (n, prevalence, key measurements).

    If the raw ``df`` is passed, adds raw-scale clinical descriptors that make
    the heterogeneity legible (mean cholesterol, fraction with cholesterol
    unrecorded, mean age).
    """
    rows = []
    raw_by_site = {s: df[df["site"] == s] for s in SITES} if df is not None else None
    for name, sd in sites.items():
        row = {
            "site": name,
            "label": sd.label,
            "n": sd.n,
            "prevalence": round(float(sd.y.mean()), 3),
        }
        if raw_by_site is not None:
            r = raw_by_site[name]
            row["mean_age"] = round(float(r["age"].mean()), 1)
            row["frac_female"] = round(float((r["sex"] == 0).mean()), 3)
            row["chol_unrecorded_frac"] = round(float((r["chol"] == 0).mean()), 3)
            nz = r.loc[r["chol"] > 0, "chol"]
            row["mean_chol_recorded"] = round(float(nz.mean()), 0) if len(nz) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = load_raw()
    sites = load_sites()
    print(summarize_sites(sites, df).to_string(index=False))
