# Research results and model registry

Run: `nhanes-20261023-v2` · schema `ckd-research-v2.0` · seed `20261023`

These are real executed experiments. Scores are not clinical validation or a claim of superiority over the legacy pipeline.

## Cohorts

| Cohort | Source participants | Eligible adults | Positive | Negative |
|---|---:|---:|---:|---:|
| NHANES August 2021–August 2023 | 11,933 | 5,552 | 949 | 4,603 |
| NHANES 2017–2018 stress test | 9,254 | 5,063 | 939 | 4,124 |

Both cycles are separate cross-sectional samples. The earlier cycle remains unpooled and has assay and design differences. All metrics are unweighted. There are no prospective patient outcomes.

### Component downloads

| Component | 2021–2023 records | 2017–2018 records |
|---|---:|---:|
| DEMO_L.xpt / DEMO_J.xpt | 11,933 | 9,254 |
| BIOPRO_L.xpt / BIOPRO_J.xpt | 7,199 | 6,401 |
| ALB_CR_L.xpt / ALB_CR_J.xpt | 8,493 | 7,936 |
| BMX_L.xpt / BMX_J.xpt | 8,860 | 8,704 |
| BPXO_L.xpt / BPXO_J.xpt | 7,801 | 7,132 |
| DIQ_L.xpt / DIQ_J.xpt | 11,744 | 8,897 |
| SMQ_L.xpt / SMQ_J.xpt | 9,015 | 6,724 |

Official CDC/NCHS sources, download URLs, retrieval timestamps and SHA-256 hashes are in `frontend/data/sources.json`. NCHS public-use terms apply: statistical analysis/reporting only; no re-identification. Component row counts must not be summed as independent people. One-to-one joins use SEQN.

### Existing local data

| File | Rows | Labels | Audit notes |
|---|---:|---|---|
| `data/processed/ckd_cleaned.csv` | 6,171 | {'1': 3205, '0': 2966} | Legacy processed NHANES output; participant IDs removed, full-data outlier filtering; excluded from v2 fitting. |
| `data/raw/chronic_kidney_disease.arff` | 399 | {'ckd': 250, 'notckd': 149} | UCI-derived local copy (CC BY 4.0, hospital-based convenience sample); CSV/ARFF are alternate representations, not independent cohorts. 2 extra trailing empty fields normalized for audit only; originals unchanged. 1 ambiguous malformed row(s) excluded from column statistics; source has 400 records. |
| `data/raw/chronic_kidney_disease.csv` | 399 | {'ckd': 250, 'notckd': 149} | UCI-derived local copy (CC BY 4.0, hospital-based convenience sample); CSV/ARFF are alternate representations, not independent cohorts. 2 extra trailing empty fields normalized for audit only; originals unchanged. 1 ambiguous malformed row(s) excluded from column statistics; source has 400 records. |
| `data/raw/CKD_NHANES_2021_2023.csv` | 11,933 | {'1': 8341, '0': 3592} | Local NHANES-derived CSV, source acquisition and label-generation code absent. Compare with official components; not used for v2 fitting. 1644 provided-label disagreements on adults with complete measurements; 5661 positive labels without both kidney measurements. |

The UCI source has 400 records, 24 predictors and CC BY 4.0 licensing. In each local copy, 399 records parse after normalizing two trailing commas: 250 CKD / 149 non-CKD. One additional non-CKD row has an ambiguous embedded extra field and is excluded from column statistics. The CSV/ARFF represent the same hospital sample; no second UCI cohort was acquired. No documented longitudinal participant identity exists. Full missingness, duplicate and numeric audits are in `ml/reports/data-audit.json`.

## Model comparison

All rows use the same eligible cohort and participant partitions. CV and validation choose models; test metrics are descriptive after selection.

| Pathway | Model | CV AP | Validation AP | Test ROC-AUC | Test AP | Sensitivity | Specificity | PPV | NPV | F1 | Balanced acc. | Brier |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| screening | logistic | 0.4375 | 0.5314 | 0.7606 | 0.4463 | 0.7684 | 0.6189 | 0.2938 | 0.9283 | 0.4250 | 0.6937 | 0.1225 |
| screening | forest **selected** | 0.4394 | 0.5330 | 0.7901 | 0.4639 | 0.8421 | 0.6091 | 0.3077 | 0.9492 | 0.4507 | 0.7256 | 0.1184 |
| screening | hist_gradient | 0.3992 | 0.4894 | 0.7834 | 0.4433 | 0.8737 | 0.5472 | 0.2847 | 0.9545 | 0.4295 | 0.7105 | 0.1187 |
| biomarker | logistic | 0.5479 | 0.5805 | 0.7807 | 0.5388 | 0.7895 | 0.6048 | 0.2918 | 0.9330 | 0.4261 | 0.6971 | 0.1115 |
| biomarker | forest **selected** | 0.5566 | 0.5842 | 0.8053 | 0.5606 | 0.7474 | 0.7068 | 0.3447 | 0.9313 | 0.4718 | 0.7271 | 0.1086 |
| biomarker | hist_gradient | 0.5258 | 0.5674 | 0.8075 | 0.5658 | 0.8211 | 0.6374 | 0.3184 | 0.9452 | 0.4588 | 0.7292 | 0.1071 |

## Selected models

Highest validation average precision within each task; thresholds maximize specificity subject to validation sensitivity ≥0.80. Test and external data never select models or thresholds.

### screening: forest

Validation AP 0.5330; operating threshold 0.113135. Test AUC 0.7901 (IID bootstrap 95% CI 0.7564–0.8261).

Confusion matrix (rows observed 0/1, columns predicted 0/1): `[[561, 360], [30, 160]]`. Test sample: 190 positive / 921 negative. Test prevalence 17.102%.

Test Brier before sigmoid calibration: 0.11725; after: 0.11843. Calibration did not improve the selected model's test Brier score; it must not be described as clinically reliable.

Earlier-cycle stress test: AUC 0.7768, AP 0.4666, sensitivity 0.7774, specificity 0.6283. Urine-albumin bridge changes 56 labels; bridged AP 0.4593. Other analyte method shifts are unadjusted; this is not fully harmonized external validation.

### biomarker: forest

Validation AP 0.5842; operating threshold 0.167798. Test AUC 0.8053 (IID bootstrap 95% CI 0.7727–0.8398).

Confusion matrix (rows observed 0/1, columns predicted 0/1): `[[651, 270], [48, 142]]`. Test sample: 190 positive / 921 negative. Test prevalence 17.102%.

Test Brier before sigmoid calibration: 0.10814; after: 0.10863. Calibration did not improve the selected model's test Brier score; it must not be described as clinically reliable.

Earlier-cycle stress test: AUC 0.8040, AP 0.5722, sensitivity 0.7338, specificity 0.7338. Urine-albumin bridge changes 56 labels; bridged AP 0.5698. Other analyte method shifts are unadjusted; this is not fully harmonized external validation.

The biomarker histogram model has a slightly higher test AUC/AP than the selected forest. We retain the validation-selected forest rather than using the test set to change the selection. The validation AP margins are small and do not establish superiority.

## Protocol

| Partition | n | Positive | Negative |
|---|---:|---:|---:|
| train | 3330 | 569 | 2761 |
| calibration | 555 | 95 | 460 |
| validation | 556 | 95 | 461 |
| test | 1111 | 190 | 921 |

Logistic sigmoid fitted to clipped model log-odds on disjoint 10% calibration partition; this is empirical calibration, not clinical reliability.

Median numeric imputation + standardization, mode categorical imputation + one-hot encoding are fitted within training folds. Three-fold CV searches compact grids. Class-weighted logistic/forest candidates are compared with unweighted alternatives; no synthetic resampling. Two threads limit CPU usage. Full parameters and library versions are saved with the report.

## Limits and available research features

- Research prototype, not a diagnosis or a clinically validated medical device.
- Cross-sectional, single-visit outcome; chronicity and future progression are not established.
- Age and sex are also terms of the eGFR equation defining part of the outcome; screening is not free of mathematical coupling.
- US NHANES adult sample with both kidney measurements available; complete-outcome selection can bias results.
- Training, calibration, evaluation and bootstrap intervals are unweighted; they do not estimate US population risk or complex-survey uncertainty.
- Missing inputs use training-only imputation. Marginal range checks do not establish that an input is in distribution.
- Model associations and hypothetical scenarios are not causal effects or treatment advice.
- eGFR is approximate for ages top-coded at 80. Pregnancy and all causes of transient biomarker abnormalities are not separately adjudicated.
- No clinically validated CKD stage or future progression model is offered; legacy stage code is preserved only for history.
- Global permutation importance, non-additive local replacement explanations, missingness sensitivity, BP perturbation, subgroup summaries and marginal input-range flags are available.
- SHAP for the final calibrated model, joint-distribution OOD detection, causal counterfactuals, individual uncertainty intervals and survey-design-adjusted population estimates remain unavailable.

## Artifacts

Local fitted pipelines, calibrators, split identifiers, selected portable parameters, parity fixtures and report: `ml/artifacts/research-v2/nhanes-20261023-v2/` (ignored by Git).

Aggregate report and audit: `ml/reports/`. Browser-safe parameters, schemas, synthetic parity fixtures, source manifest and report: `frontend/data/`. No participant-level data are exported to the frontend.

Rebuild this summary with `python -m ml.research.report`. See the root README for the complete workflow.
