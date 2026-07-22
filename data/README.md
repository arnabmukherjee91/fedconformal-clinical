# Data

## `raw/heart_disease_4sites_raw.csv`

A bundled mirror of the **UCI Heart Disease** database (Detrano et al., 1989;
UCI ML Repository ID 45). It is the concatenation, in this exact order, of the
four "processed" site files:

| Site | Institution | Rows |
|------|-------------|------|
| cleveland | Cleveland Clinic Foundation | 303 |
| hungarian | Hungarian Institute of Cardiology, Budapest | 294 |
| switzerland | University Hospital, Zurich & Basel | 123 |
| va | V.A. Medical Center, Long Beach, CA | 200 |
| **total** | | **920** |

`fedconformal.data.load_raw()` reattaches the `site` label by these known row
counts, so the four hospitals can be recovered without any per-row site column.

### Columns (13 features + target)

`age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak, slope,
ca, thal, target`

`target` is 0 (no disease) or 1–4 (increasing severity). The standard binary
task is `target > 0` (disease present), produced by
`fedconformal.data.binarize_target`.

### Why this dataset for the workshop

It is one of very few **naturally federated** public clinical datasets: the same
case-report form was collected at four hospitals, so it exhibits genuine
site-level heterogeneity — including the two kinds the workshop distinguishes:

* **True distributional shift** — disease prevalence ranges from 36% (Hungary)
  to 94% (Switzerland).
* **Measurement-induced heterogeneity** — Switzerland never recorded serum
  cholesterol, so `chol` is a constant 0 there (a curation trap if pooled naively).

### Provenance & license

Original data: UCI Machine Learning Repository, "Heart Disease" (1989),
donated by the Hungarian Institute of Cardiology, University Hospital Zurich,
University Hospital Basel, and the V.A. Medical Center Long Beach & Cleveland
Clinic Foundation (principal investigator: Robert Detrano). Distributed for
research use. Please cite the UCI repository and Detrano et al. (1989) if you
use it.

Missing values in this mirror are already coded (e.g. Switzerland `chol = 0`);
we preserve them so the measurement-heterogeneity lesson stays visible. To fetch
the pristine originals instead, use the `ucimlrepo` package
(`fetch_ucirepo(id=45)`) where network access to `archive.ics.uci.edu` allows.
