# Conformal Prediction — Research Reading List

A curated set of papers for going deeper on conformal prediction (CP) after the
workshop, weighted toward the themes we worked on: **federated / multi-site**,
**clinical applications**, and **distribution shift**. Each entry has a link, the
year, and a one-line note on why it's worth your time.

> Suggested order: **Foundations → Core methods → Distribution shift → Federated
> → Clinical → Critiques & frontiers.** If you only read three to start:
> the Gentle Introduction, the Covariate-Shift paper, and Federated Conformal
> Predictors.

_Last updated: 2026-09 · maintained alongside the `fedconformal-clinical` project._

---

## 0. Foundations (read first)

- **A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification** — Angelopoulos & Bates, 2022. *Our workshop baseline; the clearest on-ramp with code.*
  https://arxiv.org/abs/2107.07511
- **A Tutorial on Conformal Prediction** — Shafer & Vovk, JMLR 2008. *The canonical tutorial from the field's founders; the theory behind exchangeability and validity.*
  https://arxiv.org/abs/0706.3188
- **Conformal Prediction: A Data Perspective** — 2024. *Recent survey organizing CP methods by the data setting (i.i.d., shift, time series, graphs) — a great map of the field.*
  https://arxiv.org/abs/2410.06494
- **Algorithmic Learning in a Random World** (2nd ed.) — Vovk, Gammerman & Shafer, 2022 (book, Springer). *The definitive reference text; not free, but the source of everything.* https://link.springer.com/book/10.1007/978-3-031-06649-8

---

## 1. Core methods (the standard toolbox)

- **Conformalized Quantile Regression (CQR)** — Romano, Patterson & Candès, 2019. *The go-to method for prediction intervals in regression.*
  https://arxiv.org/abs/1905.03222
- **Classification with Valid and Adaptive Coverage (APS)** — Romano, Sesia & Candès, 2020. *The adaptive prediction-set method we implemented for the multiclass task.*
  https://arxiv.org/abs/2006.02544
- **Uncertainty Sets for Image Classifiers using Conformal Prediction (RAPS)** — Angelopoulos et al., 2021. *Regularized APS that produces smaller, stable sets on hard problems.*
  https://arxiv.org/abs/2009.14193
- **Predictive Inference with the Jackknife+** — Barber, Candès, Ramdas & Tibshirani, 2021. *Cross-validation-style CP (jackknife+, CV+) that avoids a separate calibration split.*
  https://arxiv.org/abs/1905.02928

---

## 2. Distribution shift (most relevant to multi-site data)

- **Conformal Prediction Under Covariate Shift** — Tibshirani, Foygel Barber, Candès & Ramdas, 2019. *Weighted conformal prediction — the theoretical basis for transferring coverage across sites.*
  https://arxiv.org/abs/1904.06019
- **Conformal Prediction Beyond Exchangeability** — Barber, Candès, Ramdas & Tibshirani, 2022. *What happens (and how to reweight) when the exchangeability assumption fails — directly our cross-site problem.*
  https://arxiv.org/abs/2202.13415
- **Adaptive Conformal Inference Under Distribution Shift (ACI)** — Gibbs & Candès, 2021. *Online recalibration that keeps coverage under drift over time.*
  https://arxiv.org/abs/2106.00170
- **Conformal Prediction Under Generalized Covariate Shift with Posterior Drift** — 2025. *Extends weighted CP to when both the covariates and the label mechanism shift.*
  https://arxiv.org/abs/2502.17744
- **Conformal Prediction under Lévy–Prokhorov Distribution Shifts** — 2025. *Robustness guarantees to bounded local + global perturbations of the distribution.*
  https://arxiv.org/abs/2502.14105
- **Weighted Conformal Prediction for Survival Analysis under Covariate Shift** — 2025. *Applies the covariate-shift machinery to time-to-event / survival outcomes.*
  https://arxiv.org/abs/2512.03738

---

## 3. Federated & distributed conformal prediction (our core topic)

- **Federated Conformal Predictors for Distributed Uncertainty Quantification** — Lu et al., ICML 2023. *The foundational federated-CP paper; partial-exchangeability and how to calibrate across clients. Start here.*
  https://arxiv.org/abs/2305.17564
- **Conformal Prediction for Federated Graph Neural Networks with Missing Neighbor Information** — 2024. *Federated CP when each client sees only part of a graph.*
  https://arxiv.org/abs/2410.14010
- **Decoding Federated Learning: The FedNAM+ Conformal Revolution** — 2025. *Combines neural additive models with CP for interpretable, calibrated federated predictions.*
  https://arxiv.org/abs/2506.17872
- **Federated Conditional Conformal Prediction via Generative Models** — 2025. *Pushes toward feature-conditional (not just marginal) coverage in the federated setting — the next step beyond what we built.*
  https://arxiv.org/abs/2510.13297

---

## 4. Clinical / medical applications (our domain)

- **A Critical Perspective on Finite-Sample Conformal Prediction Theory in Medical Applications** — 2025. *Where the finite-sample guarantees can mislead in real clinical deployments — read before trusting CP in production.*
  https://arxiv.org/abs/2512.14727
- **Conformal Uncertainty Quantification for Predictive Fairness of a Foundation Model across Patient Demographics (skin lesions)** — 2025. *Uses CP to audit fairness across demographic subgroups — the class/group-conditional coverage theme from our work.*
  https://arxiv.org/abs/2503.23819
- **COMPASS: Robust Feature Conformal Prediction for Medical Segmentation Metrics** — 2025. *CP for image-segmentation quality in medical imaging.*
  https://arxiv.org/abs/2509.22240
- **Making Conformal Predictors Robust in Healthcare Settings: a Case Study on EEG Classification** — 2026. *Practical robustness of CP under the messiness of real clinical signals.*
  https://arxiv.org/abs/2602.19483

---

## 5. Critiques, practice & frontiers

- **On Some Practical Challenges of Conformal Prediction** — 2025. *An honest catalogue of where CP is harder than the tutorials suggest — pairs well with our workshop's caveats.*
  https://arxiv.org/abs/2510.10324
- **A Gentle Introduction to Conformal Time-Series Forecasting** — 2025. *If you extend to temporal clinical data (vitals, trajectories).*
  https://arxiv.org/abs/2511.13608
- **Conformal Prediction for Time-Series Forecasting with Change Points** — 2025. *CP that adapts when the series regime changes.*
  https://arxiv.org/abs/2509.02844

---

## How these connect to what we built

| Our workshop piece | Papers to read next |
|---|---|
| Split conformal, APS (`conformal.py`) | §1 CQR, APS, RAPS |
| Cross-site coverage breaking (`04_conformal_under_site_shift`) | §2 Covariate Shift, Beyond Exchangeability |
| Federated FedAvg + CP | §3 Federated Conformal Predictors, Federated Conditional CP |
| Class-conditional coverage (`cp` task) | §4 Fairness/skin-lesion, §3 Federated Conditional CP |
| "Confident but wrong" failure mode | §5 Practical Challenges, §4 Critical Perspective |

## Notes

- Links point to arXiv abstract pages; use the "PDF" link there, or append `.pdf`.
- arXiv IDs encode date: e.g. `25MM.xxxxx` = 20YY-MM. `2107.07511` = July 2021.
- A machine-readable `references.bib` sits next to this file for your citation manager.
- To extend this list, search arXiv listing **stat.ML / cs.LG** with `ti:"conformal"`,
  or follow the "Awesome Conformal Prediction" repo: https://github.com/valeman/awesome-conformal-prediction
