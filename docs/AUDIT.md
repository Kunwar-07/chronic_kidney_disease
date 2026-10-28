# Repository audit

Initial repository: one `ml/` tree, no frontend, router, package manifest or visual component system. Git working state was clean. No applicable AGENTS.md was found. Original images are EDA/evaluation plots; no suitable kidney hero asset existed.

## Retained useful work

- Existing NHANES feature naming, source CSV, UCI CSV/ARFF and preprocessing/training modules.
- Sklearn pipeline structure and serializable model artifacts.
- XGBoost, CatBoost, LightGBM and stacking experiments; original performance reports and EDA graphics.
- Existing explainability caveat distinguishing association from causation.

All originals remain intact. `ml/README.md` now has a prominent link to the new supported workflow; legacy experiment descriptions remain available beneath it.

## Findings that required a separate v2 pipeline

1. `preprocessing/cleaning.py` fits imputation/IsolationForest on all data before splitting, automatically removes 2% of records, and removes participant IDs. Positive-label-specific missingness exclusions also affect the eligible population.
2. `evaluation/tune_threshold.py` explicitly tunes on the same test split used for evaluation. Those threshold performance claims are optimistic.
3. `models/ckd_detection/train.py` performs feature selection/preprocessing and SMOTETomek before the stacking estimator's internal CV. This contaminates internal meta-learning folds, although the outer test remains separated at that stage.
4. Reported legacy precision/recall are weighted averages rather than positive-class sensitivity/PPV. The reported 0.845 AUC is an existing artifact, not a v2 result or directly comparable baseline.
5. `model_metadata.json` describes an older UCI random forest and perfect performance, while the current training code uses NHANES stacking. Metadata does not consistently identify the actual artifact.
6. `models/ckd_detection/predict.py` claims automatic calibration from a logistic meta-model and labels distance from 0.5 as confidence; neither establishes clinical calibration or uncertainty. Its example calls a one-argument function with two arguments.
7. `explainability/shap_explainer.py` averages base-estimator SHAP values even though the final stacking layer combines their probabilities; those values do not explain the full stacked prediction. The preprocessing slice assumes the stacking layout and does not support every legacy model path.
8. `models/progression/progression_model.py` predicts cross-sectional stage, without time or a prediction horizon. It does not save the fitted stage label encoder and reconstructs a mapping from possible stages, which can be wrong when classes are absent.
9. `evaluation/optuna_tuning.py` claims AUC optimization improves calibration, overwrites original artifacts, and assumes model keys absent from the present `evaluation_metrics.json`. Its dependencies and those of the training code (Optuna, imbalanced-learn) are missing from the old requirements file.
10. Feature-engineering comparisons turn missing measurements into negative flags, and rules default a missing `risk_level` to LOW despite a different inference contract. These paths are not used in the new interface.
11. The local NHANES CSV contains 11,933 records, 8,341 positives / 3,592 negatives. Among complete adult outcome records, 1,644 labels disagree with the explicit eGFR/UACR endpoint. There are 5,661 positives without both kidney measurements. The local eGFR values closely match CKD-EPI 2021 (median absolute difference ≈0.0025), but label-generation provenance is absent.
12. Both UCI representations contain 400 source records, two extra trailing delimiters and one row with an ambiguous embedded extra field. The audit normalizes the harmless trailing delimiters in memory and reports the ambiguous record separately. The two files are not independent samples.

## Implementation choices

Extend the existing Python repository with `ml/research/`, rather than overwrite old modules. Official source XPTs and acquisition hashes establish provenance. Use one documented single-visit endpoint; exclude its direct lab components from both feature sets. Split unique participants before fitting, CV-tune only training data, calibrate separately, select thresholds/models on validation, then evaluate test and the earlier cycle.

A dependency-free static frontend is appropriate because no prior stack exists and backend development is excluded. The shared ML-owned JS runtime evaluates exported fitted parameters, including preprocessing and calibration. Three family implementations are tested against Python, with actual selected random forests used in the interface. The visual system uses the supplied reference's aqua/navy palette and editorial composition with an original conceptual kidney image.
