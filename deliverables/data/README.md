# Data

## Source files

The four hospital sites are loaded directly from the **original UCI Heart
Disease** per-site files (Detrano et al., 1989; UCI ML Repository ID 45
— [dataset page](https://archive.ics.uci.edu/dataset/45/heart+disease)), not
from a pre-cleaned mirror:

| Site | Institution | File | Rows |
|------|-------------|------|------|
| cleveland | Cleveland Clinic Foundation | `processed.cleveland.data` | 303 |
| hungarian | Hungarian Institute of Cardiology, Budapest | `reprocessed.hungarian.data` | 294 |
| switzerland | University Hospital, Zurich & Basel | `processed.switzerland.data` | 123 |
| va | V.A. Medical Center, Long Beach, CA | `processed.va.data` | 200 |
| **total** | | | **920** |

Hungary uses the **reprocessed** file rather than `processed.hungarian.data`:
the standard "processed" mirror has its target pre-collapsed to binary (only
0/1 present), while `reprocessed.hungarian.data` preserves the full 0-4
severity range needed for the 5-class task.

`fedconformal.data.load_raw()` reads all four files, attaches a `site` column,
and returns them concatenated. Missing values, coded `?` or `-9` in the
source files, are loaded as NaN.

### Columns (13 features + target)

`age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak, slope,
ca, thal, target`

`target` (the UCI `num` column) is `0` (no disease) or `1`-`4` (increasing
severity). This is the **default 5-class task** (`fedconformal.data`, task
`"disease"`); a binary "any disease" view is also available via
`fedconformal.data.binarize_target`.

### Why this dataset for the workshop

It is one of very few **naturally federated** public clinical datasets: the same
case-report form was collected at four hospitals, so it exhibits genuine
site-level heterogeneity — including the two kinds the workshop distinguishes:

* **True distributional shift** — disease prevalence ranges from 36% (Hungary)
  to 94% (Switzerland), and the severity mix shifts even more sharply.
* **Measurement-induced heterogeneity** — two distinct fingerprints:
  * Switzerland never recorded serum cholesterol, so `chol` is a constant `0`
    there (coded that way directly in the source file — a curation trap if
    pooled naively).
  * `ca` (# vessels by fluoroscopy) and `thal` (thallium stress test) are
    coded `?`/`-9` and are missing for **80-99% of patients at every site
    except Cleveland** — a far larger measurement gap than cholesterol, and
    one a model naively trained on all four sites will barely notice without
    explicitly checking for it (see `heterogeneity.missingness_report`).

### Provenance & license

Original data: UCI Machine Learning Repository, "Heart Disease" (1989),
donated by the Hungarian Institute of Cardiology, University Hospital Zurich,
University Hospital Basel, and the V.A. Medical Center Long Beach & Cleveland
Clinic Foundation (principal investigator: Robert Detrano). Distributed for
research use. Please cite the UCI repository and Detrano et al. (1989) if you
use it.

**Dataset link:** https://archive.ics.uci.edu/dataset/45/heart+disease

The other files in this directory (`cleveland.data`, `hungarian.data`,
`switzerland.data`, `long-beach-va.data`, `new.data`, `cleve.mod`, `bak`,
`Index`, `WARNING`, `ask-detrano`, `heart-disease.names`) are the rest of the
original UCI distribution archive, kept for provenance; only the four files
in the table above are read by `fedconformal.data.load_raw()`. To fetch the
pristine originals instead, use the `ucimlrepo` package
(`fetch_ucirepo(id=45)`) where network access to `archive.ics.uci.edu` allows.
