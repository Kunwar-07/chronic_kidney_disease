# CKD Early Warning AI Framework

Early Detection and Disease Progression Prediction of Chronic Kidney Disease
using Multi-Modal NHANES 2021-2023 data and an Adaptive Explainable AI stack.

## Architecture

```text
data/
  raw/                        — CKD_NHANES_2021_2023.csv (original)
  processed/                  — ckd_cleaned.csv (after cleaning)

preprocessing/
  cleaning.py                 — Ingest NHANES CSV, drop leakage columns, type-cast
  pipeline.py                 — sklearn ColumnTransformer (impute + scale + one-hot)

models/
  ckd_detection/
    train.py                  — Train a Stacking Ensemble (XGB, CatBoost, LightGBM) with SMOTETomek
    predict.py                — Single predict() entry point for API layer
  recommendation/
    rules.py                  — Deterministic, auditable clinical decision rules

explainability/
  shap_explainer.py           — Per-patient SHAP explanations (TreeExplainer / KernelExplainer)

evaluation/
  optuna_tuning.py            — Hyperparameter tuning via Optuna targeting ROC-AUC
  tune_threshold.py           — Probability threshold optimization
  verify_test_predictions.py  — Sanity check script for model predictions
  eda_visualization.py        — Generate diagnostic plots (ROC, SHAP, etc.)

artifacts/
  stacking_ckd_model.pkl      — Trained Stacking Ensemble pipeline
  evaluation_metrics.json     — Performance metrics (Accuracy, ROC-AUC, F1, etc.)
  optuna_tuning_results.json  — Hyperparameter configurations and CV results
  plots/                      — All generated visualization PNGs
```

## Run Order

```bash
pip install -r requirements.txt

# 1. Clean data
python -m preprocessing.cleaning

# 2. (Optional) Hyperparameter tuning
python -m evaluation.optuna_tuning --trials 50

# 3. Train the Stacking Ensemble model
python -m models.ckd_detection.train

# 4. Tune decision thresholds
python -m evaluation.tune_threshold

# 5. SHAP explanations for a sample patient
python -m explainability.shap_explainer

# 6. Rule-based recommendations
python -m models.recommendation.rules

# 7. Generate all EDA + evaluation visualizations
python -m evaluation.eda_visualization

# 8. Verify predictions on the test set
python -m evaluation.verify_test_predictions
```

## Design Decisions

### Early Warning, Not a Calculator
The diagnostic columns that doctors use to *define* CKD (`egfr`, `albumin_creatinine_ratio`, `serum_creatinine`) are **intentionally excluded** from the feature set. Without them, the models must find hidden correlations in secondary/multi-modal data:
- Demographics: age, BMI, poverty income ratio
- Blood labs: blood_urea_nitrogen, albumin_serum, calcium, uric_acid, phosphorus, bicarbonate
- Lifestyle: smoking status, diabetes history

This ensures the AI is a genuine early warning system rather than a formula replicator. Earlier versions on toy datasets (like UCI CKD) showed 99-100% accuracy, which is highly misleading in real-world clinical settings. The current pipeline works on realistic, noisy NHANES data.

### Class Imbalance & Optuna Tuning
To handle severe class imbalance (most patients don't have CKD), the framework utilizes `SMOTETomek` resampling and optimizes models strictly for `ROC-AUC` (rather than accuracy) using **Optuna**. We combine XGBoost, CatBoost, and LightGBM into a Stacking Classifier with a Logistic Regression meta-model to maximize robustness.

## Model Performance (NHANES Test Set)

Based on the latest runs in `evaluation_metrics.json` and `optuna_tuning_results.json`:

| Model / Ensemble                | Accuracy | ROC-AUC |
|---------------------------------|----------|---------|
| Stacking Ensemble (Production)  | ~76.1%   | ~0.845  |
| Optuna Tuned XGBoost            | -        | ~0.860  |
| Optuna Tuned CatBoost           | -        | ~0.860  |
| Optuna Tuned LightGBM           | -        | ~0.863  |

*(Note: While accuracy is in the 70s, the high ROC-AUC in the mid-0.80s demonstrates strong class-separation ability. Threshold tuning further balances precision vs. recall.)*

## Explainability
Each patient prediction is accompanied by a SHAP breakdown identifying the top features driving that patient's risk score, along with a mandatory clinical disclaimer. The rule-based recommendation engine then maps flagged values to auditable, traceable clinical suggestions without relying on any black-box LLM.
