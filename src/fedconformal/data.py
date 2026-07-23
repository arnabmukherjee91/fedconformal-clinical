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
*site-level heterogeneity* -- both true distributional shift and
measurement-induced heterogeneity. This makes it an ideal teaching dataset for a
workshop on federated ML and uncertainty quantification for research-data
curation.

We load the original per-site UCI files directly (``data/*.data``), not a
pre-cleaned mirror. Missing values are coded in the source files as ``?`` or
``-9`` and are read in as NaN; the Hungarian site uses the *reprocessed*
file (``reprocessed.hungarian.data``) because the standard ``processed.
hungarian.data`` mirror has its target already collapsed to binary --
the reprocessed file is the one that preserves the full 0-4 severity range.

Two prediction tasks are supported (choose with ``task=``):

  * ``"disease"`` (5-class, the default) -- predict the presence and severity
    of heart disease: the original UCI ``num`` target, 0 (no presence) through
    4 (most severe / most vessels affected). Features: all 13 clinical
    variables.
  * ``"cp"`` (4-class multiclass) -- predict the *chest-pain type*
    (1 typical angina / 2 atypical angina / 3 non-anginal pain / 4 asymptomatic)
    from the other 12 clinical variables. A prediction set is a set of
    chest-pain types.
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
#: ``target`` (a.k.a. ``num`` in the UCI docs) is 0 (no disease) or 1-4
#: (increasing severity / number of major vessels affected).
COLUMNS = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal", "target",
]

#: All 13 clinical feature columns (excludes the disease ``target``).
FEATURES = COLUMNS[:-1]

#: The four sites.
SITES = ["cleveland", "hungarian", "switzerland", "va"]

#: Human-readable names for plots.
SITE_LABELS = {
    "cleveland": "Cleveland Clinic",
    "hungarian": "Hungarian Inst. of Cardiology",
    "switzerland": "Univ. Hospital Zurich (Switzerland)",
    "va": "V.A. Long Beach",
}

#: Expected row counts per site (used as a sanity check after loading).
SITE_COUNTS = {"cleveland": 303, "hungarian": 294, "switzerland": 123, "va": 200}

#: Original UCI per-site source files, relative to the ``data/`` directory.
#: Hungarian uses the *reprocessed* file -- the standard ``processed.
#: hungarian.data`` mirror has its target pre-collapsed to binary (only 0/1
#: present), while ``reprocessed.hungarian.data`` preserves the full 0-4 range.
RAW_FILES = {
    "cleveland": "processed.cleveland.data",
    "hungarian": "reprocessed.hungarian.data",
    "switzerland": "processed.switzerland.data",
    "va": "processed.va.data",
}

#: Values used in the raw UCI files to code a missing measurement.
_MISSING_CODES = ["?", "-9"]

# ---- Task definitions ------------------------------------------------------
# Each task says: which column is the label, how to turn it into 0-indexed
# integer classes, the human-readable class names, and which columns are the
# input features. The chest-pain task uses the other 12 clinical variables and
# does NOT use the disease target as a feature.

CP_FEATURES = [c for c in FEATURES if c != "cp"]

TASKS = {
    "disease": {
        "label_col": "target",
        "features": FEATURES,
        "class_names": ["No disease", "Mild", "Moderate", "Severe", "Critical"],
        # target is already 0-4; just make sure it's a clean int array
        "encode": lambda s: np.asarray(s).astype(int),
    },
    "cp": {
        "label_col": "cp",
        "features": CP_FEATURES,
        "class_names": ["typical angina", "atypical angina",
                        "non-anginal pain", "asymptomatic"],
        # cp is coded 1-4; shift to 0-indexed classes 0-3
        "encode": lambda s: (np.asarray(s).astype(int) - 1),
    },
}

DEFAULT_TASK = "disease"

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DATA_DIR = os.path.normpath(os.path.join(_HERE, "..", "..", "data"))


# ----------------------------------------------------------------------------
# Site container
# ----------------------------------------------------------------------------

@dataclass
class SiteData:
    """Holds one hospital's data in a federated simulation."""

    name: str
    X: np.ndarray                       # (n, d) preprocessed feature matrix
    y: np.ndarray                       # (n,) integer class label (0-indexed)
    feature_names: list = field(default_factory=list)
    class_names: list = field(default_factory=list)
    task: str = DEFAULT_TASK

    @property
    def n(self) -> int:
        return len(self.y)

    @property
    def n_classes(self) -> int:
        return len(self.class_names) if self.class_names else int(self.y.max() + 1)

    @property
    def prevalence(self) -> float:
        """Fraction with *any* disease (``y > 0``) -- meaningful for any K."""
        return float((self.y > 0).mean())

    @property
    def label(self) -> str:
        return SITE_LABELS.get(self.name, self.name)

    def __repr__(self) -> str:
        return f"SiteData({self.name!r}, n={self.n}, K={self.n_classes})"


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def _read_site_file(path: str) -> pd.DataFrame:
    """Read one raw UCI per-site file (comma- or whitespace-separated, ``?``/
    ``-9`` coded missing values) into a 14-column DataFrame."""
    df = pd.read_csv(
        path, header=None, names=COLUMNS,
        sep=r"[,\s]+", engine="python",
        na_values=_MISSING_CODES,
    )
    return df


def load_raw(data_dir: str | None = None) -> pd.DataFrame:
    """Load the four original UCI per-site files and attach a ``site`` column.

    Returns a DataFrame with the 13 raw features, the raw 0-4 ``target``, and a
    ``site`` column. Missing values (coded ``?`` / ``-9`` in the source files)
    are left as NaN -- except cholesterol, which the source files themselves
    code as a literal ``0`` for "not recorded" (this is preserved deliberately
    so the measurement-heterogeneity story stays visible; see ``eda.py`` /
    ``heterogeneity.py``).
    """
    ddir = data_dir or _DEFAULT_DATA_DIR
    frames = []
    for name in SITES:
        path = os.path.join(ddir, RAW_FILES[name])
        sub = _read_site_file(path)
        if len(sub) != SITE_COUNTS[name]:
            raise ValueError(
                f"Expected {SITE_COUNTS[name]} rows for site {name!r} from "
                f"{RAW_FILES[name]!r}, got {len(sub)}. The source file may "
                "have changed; site loading is unsafe."
            )
        sub = sub.copy()
        sub["site"] = name
        frames.append(sub)
    df = pd.concat(frames, ignore_index=True)
    return df


def binarize_target(target: pd.Series | np.ndarray) -> np.ndarray:
    """Collapse the 0-4 UCI disease target to binary: 0 (no disease) or 1
    (any disease, severity 1-4). Kept as a utility for callers that want the
    coarser binary view; the default ``"disease"`` task uses all 5 classes."""
    return (np.asarray(target) > 0).astype(int)


def _task_config(task: str) -> dict:
    if task not in TASKS:
        raise ValueError(f"Unknown task {task!r}. Choose from {list(TASKS)}.")
    return TASKS[task]


def encode_labels(df: pd.DataFrame, task: str = DEFAULT_TASK) -> np.ndarray:
    """Return 0-indexed integer class labels for the chosen task."""
    cfg = _task_config(task)
    return cfg["encode"](df[cfg["label_col"]])


def preprocess(
    df: pd.DataFrame,
    task: str = DEFAULT_TASK,
    standardize: bool = True,
    scaler_stats: tuple | None = None,
) -> tuple[np.ndarray, np.ndarray, tuple]:
    """Turn raw rows into a model-ready ``(X, y)`` for the chosen task.

    The feature engineering is deliberately simple and *identical across sites*,
    so any residual differences reflect the data, not the pipeline. Missing
    values (NaN, from the raw ``?``/``-9`` codes -- heavily concentrated in
    ``ca``/``thal`` at the non-Cleveland sites) are mean-imputed using the same
    population as the standardization statistics, so an imputed cell lands
    exactly at 0 after z-scoring.

    Parameters
    ----------
    task:
        ``"disease"`` (5-class severity) or ``"cp"`` (4-class chest-pain type).
    standardize:
        z-score each feature. Pass ``scaler_stats=(mean, std)`` to apply shared
        statistics (so every site uses the same transform).
    """
    cfg = _task_config(task)
    feats = cfg["features"]
    X = df[feats].astype(float).to_numpy()
    y = cfg["encode"](df[cfg["label_col"]])

    stats = scaler_stats
    if stats is None:
        mean = np.nanmean(X, axis=0)
        std = np.nanstd(X, axis=0)
        std[std == 0] = 1.0
        stats = (mean, std)
    mean, std = stats

    nan_mask = np.isnan(X)
    if nan_mask.any():
        X = np.where(nan_mask, mean, X)

    if standardize:
        X = (X - mean) / std
    return X, y, stats


def load_sites(
    csv_path: str | None = None,
    task: str = DEFAULT_TASK,
    standardize: bool = True,
    shared_scaler: bool = True,
) -> dict[str, SiteData]:
    """Load the dataset already split into the four hospital sites.

    Parameters
    ----------
    csv_path:
        Directory containing the raw ``data/*.data`` files (defaults to the
        bundled ``data/`` directory).
    task:
        ``"disease"`` (5-class severity, default) or ``"cp"`` (4-class
        chest-pain type).
    shared_scaler:
        If True (default) all sites are standardized with statistics pooled
        across every site (a curation pipeline that agreed on a common
        normalization). Set False to standardize each site independently.
    """
    cfg = _task_config(task)
    feats = cfg["features"]
    df = load_raw(csv_path)

    shared_stats = None
    if standardize and shared_scaler:
        Xall = df[feats].astype(float).to_numpy()
        mean = np.nanmean(Xall, axis=0)
        std = np.nanstd(Xall, axis=0)
        std[std == 0] = 1.0
        shared_stats = (mean, std)

    sites: dict[str, SiteData] = {}
    for name in SITES:
        sub = df[df["site"] == name]
        X, y, _ = preprocess(sub, task=task, standardize=standardize,
                             scaler_stats=shared_stats)
        sites[name] = SiteData(name=name, X=X, y=y, feature_names=list(feats),
                               class_names=list(cfg["class_names"]), task=task)
    return sites


def class_names(task: str = DEFAULT_TASK) -> list:
    return list(_task_config(task)["class_names"])


def n_classes(task: str = DEFAULT_TASK) -> int:
    return len(_task_config(task)["class_names"])


def summarize_sites(sites: dict[str, SiteData], df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-site summary: size, class count, prevalence of *any* disease, and
    (for multiclass tasks) the majority class and its share.
    """
    rows = []
    raw_by_site = {s: df[df["site"] == s] for s in SITES} if df is not None else None
    for name, sd in sites.items():
        row = {"site": name, "label": sd.label, "n": sd.n, "n_classes": sd.n_classes,
               "prevalence": round(sd.prevalence, 3)}
        if sd.n_classes > 2:
            counts = np.bincount(sd.y, minlength=sd.n_classes)
            maj = int(counts.argmax())
            row["majority_class"] = sd.class_names[maj] if sd.class_names else maj
            row["majority_share"] = round(float(counts.max() / sd.n), 3)
        if raw_by_site is not None:
            r = raw_by_site[name]
            row["mean_age"] = round(float(r["age"].mean()), 1)
            row["chol_unrecorded_frac"] = round(float((r["chol"] == 0).mean()), 3)
            row["ca_missing_frac"] = round(float(r["ca"].isna().mean()), 3)
            row["thal_missing_frac"] = round(float(r["thal"].isna().mean()), 3)
        rows.append(row)
    return pd.DataFrame(rows)


def class_distribution(sites: dict[str, SiteData]) -> pd.DataFrame:
    """Per-site class fractions (rows = site, cols = class name). Useful to see
    label shift for the multiclass task."""
    any_sd = next(iter(sites.values()))
    K = any_sd.n_classes
    names = any_sd.class_names or [str(i) for i in range(K)]
    rows = {}
    for name, sd in sites.items():
        counts = np.bincount(sd.y, minlength=K).astype(float)
        rows[name] = counts / counts.sum()
    return pd.DataFrame(rows, index=names).T


if __name__ == "__main__":
    for task in ("disease", "cp"):
        print(f"\n=== task = {task} ===")
        sites = load_sites(task=task)
        print(summarize_sites(sites, load_raw()).to_string(index=False))
