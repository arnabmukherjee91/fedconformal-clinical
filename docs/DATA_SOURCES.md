# Recommended clinical data sources for the workshop

The workshop needs *multi-site* clinical data so that "site" is a real axis of
heterogeneity, not a synthetic split. Below are the practical options, ordered by
how quickly a workshop attendee can get running, with access requirements and how
each maps onto the conformal + federated story.

## TL;DR recommendation

- **Use now (bundled in this repo): UCI Heart Disease — 4 real hospitals.**
  Zero credentialing, small, and it *already* contains both true shift (prevalence
  36% → 94%) and measurement-induced heterogeneity (Switzerland's unrecorded
  cholesterol). This is the fastest path to a hands-on lab and is what the
  notebooks use.
- **Scale up to realism: eICU Collaborative Research Database (multi-hospital ICU).**
  A genuinely multi-center EHR; the *demo* subset is openly downloadable for
  teaching, the full set needs free PhysioNet credentialing.
- **For a pre-built federated benchmark: FLamby.** Ready-made cross-silo splits
  (incl. `Fed-Heart-Disease`, which is the same 4-site UCI data, and
  `Fed-ISIC2019`, `Fed-Camelyon16`, etc.).

---

## Tier 1 — Ready for a live, credential-free lab

### 1. UCI Heart Disease (bundled here) ⭐ primary
- **Sites:** Cleveland, Hungary, Switzerland, V.A. Long Beach (4 hospitals).
- **Size:** 920 patients, 13 features, binary disease target.
- **Access:** fully open, no registration. Bundled in `data/raw/`.
- **Why it fits:** naturally federated; exhibits *both* kinds of site heterogeneity
  the workshop distinguishes. Small enough to train + calibrate live.
- **Get the pristine originals:** `pip install ucimlrepo` →
  `from ucimlrepo import fetch_ucirepo; fetch_ucirepo(id=45)` (needs access to
  `archive.ics.uci.edu`).
- **Links:** https://archive.ics.uci.edu/dataset/45/heart+disease

### 2. Diabetes 130-US Hospitals (readmission)
- **Sites:** 130 US hospitals, ~100k encounters (1999–2008).
- **Access:** open, no registration (UCI ID 296).
- **Why it fits:** far larger and messier — a more realistic *data-curation* story
  (inconsistent coding across hospitals, missingness patterns). Heavier to run live;
  good as a "take-home" or an advanced module.
- **Task:** predict 30-day readmission (binary) — plugs straight into the binary
  conformal code here.
- **Links:** https://archive.ics.uci.edu/dataset/296

---

## Tier 2 — Realistic EHR, light credentialing

### 3. eICU Collaborative Research Database (PhysioNet) ⭐ realism upgrade
- **Sites:** 200+ US ICUs, ~200k admissions; hospital ID is a first-class column,
  so site-level federation is native.
- **Access:** a **demo** subset (~2,500 stays) is openly downloadable for teaching;
  the full database requires a free PhysioNet credentialed account + CITI "Data or
  Specimens Only Research" training + signing the data use agreement.
- **Why it fits:** the canonical dataset for *federated critical-care* studies
  (see Sadilek/van der Schaar-style multi-center work); real measurement
  heterogeneity across ICUs.
- **Prep effort:** moderate (relational tables → per-patient features).
- **Links:** https://physionet.org/content/eicu-crd-demo/ (demo),
  https://physionet.org/content/eicu-crd/ (full)

### 4. MIMIC-IV (PhysioNet)
- **Sites:** single center (Beth Israel Deaconess), but often *combined with eICU*
  to create a genuine two-hospital shift experiment — a compelling workshop demo:
  calibrate on MIMIC, deploy on eICU.
- **Access:** free PhysioNet credentialing (same CITI training as eICU); a small
  open demo exists.
- **Links:** https://physionet.org/content/mimiciv/, https://physionet.org/content/mimic-iv-demo/

---

## Tier 3 — Pre-packaged federated benchmarks

### 5. FLamby (owkin) ⭐ least setup for FL
- **What:** a cross-silo *federated* healthcare benchmark. Ships natural-partition
  datasets with train/test splits per silo, including `Fed-Heart-Disease`
  (the same 4-site UCI data), `Fed-ISIC2019` (dermoscopy, 6 centers),
  `Fed-Camelyon16` (histology, 2 hospitals), `Fed-IXI`, `Fed-KiTS19`,
  `Fed-LIDC-IDRI`, `Fed-TCGA-BRCA`.
- **Why it fits:** if you want to move beyond tabular data (images/genomics) while
  keeping *real* site partitions, FLamby is the fastest on-ramp. Some datasets need
  their own access approvals (ISIC, Camelyon).
- **Links:** https://github.com/owkin/FLamby , paper: arXiv:2210.04620

---

## What to avoid / caveats

- **Random splits of a single-site dataset** create *no* real heterogeneity — the
  conformal guarantee will transfer perfectly and the workshop's punchline
  disappears. If you must simulate, inject controlled covariate/label shift
  deliberately (and say so).
- **PHI / IRB:** eICU, MIMIC, and several FLamby datasets are governed by data use
  agreements. For a public workshop, distribute only the open demo subsets or have
  attendees complete credentialing beforehand.
- **"Interoperable ≠ comparable":** even fully interoperable schemas (e.g. OMOP
  CDM) can hide measurement heterogeneity. That is precisely the gap the
  heterogeneity diagnostics in `src/fedconformal/heterogeneity.py` are meant to
  surface — run them on whatever dataset you choose *before* integrating.

---

## Mapping to your own in-site data

When you bring your institution's data, you only need, per site: a feature matrix
`X`, a label `y`, and a site id. Everything in this repo (`SiteData`, FedAvg,
conformal predictors, coverage/heterogeneity metrics) then applies unchanged.
Start with `heterogeneity.domain_auc_matrix` to decide whether you even have a
shift problem, then measure per-site conformal coverage to locate it.
