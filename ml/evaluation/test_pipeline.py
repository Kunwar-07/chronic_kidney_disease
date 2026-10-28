"""
test_pipeline.py
-----------------
Complete end-to-end test suite for the CKD Adaptive Explainable AI Framework.

Tests every module:
  1. Data cleaning & preprocessing
  2. Feature engineering
  3. Early detection models (XGBoost, CatBoost, LightGBM)
  4. Disease progression model
  5. SHAP explainability
  6. Clinical recommendation rules
  7. Prediction API (predict.py)
  8. Artifacts integrity check

Run: python -m evaluation.test_pipeline
"""

import sys
import os
import json
import traceback
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

results = []

def test(name, fn):
    start = time.time()
    try:
        fn()
        elapsed = time.time() - start
        print(f"  {PASS}  {name}  ({elapsed:.2f}s)")
        results.append({"test": name, "status": "PASS", "time": round(elapsed, 2)})
    except Exception as e:
        elapsed = time.time() - start
        print(f"  {FAIL}  {name}")
        print(f"         Error: {e}")
        results.append({"test": name, "status": "FAIL", "error": str(e), "time": round(elapsed, 2)})

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH  = os.path.join(BASE, "data", "raw", "CKD_NHANES_2021_2023.csv")
PROC_PATH = os.path.join(BASE, "data", "processed", "ckd_cleaned.csv")
ART_DIR   = os.path.join(BASE, "artifacts")

SAMPLE_PATIENT = {
    "age": 65, "poverty_income_ratio": 1.5, "bmi": 32.4, "weight_kg": 95.0,
    "height_cm": 172.0, "bp_systolic": 140, "bp_diastolic": 90,
    "blood_urea_nitrogen": 25.0, "albumin_serum": 3.8, "phosphorus": 4.5,
    "bicarbonate": 22.0, "calcium": 9.2, "uric_acid": 6.8,
    "urine_creatinine": 100.0,
    "gender": "Male", "ethnicity": "Non-Hispanic White",
    "education_level": "4.0", "diabetes_diagnosed": "1.0",
    "insulin_use": "2.0", "diabetes_pills": "1.0",
    "ever_smoked": "1.0", "current_smoker": "2.0"
}

HIGH_RISK_PATIENT = {
    "age": 72, "poverty_income_ratio": 0.5, "bmi": 35.0, "weight_kg": 105.0,
    "height_cm": 172.0, "bp_systolic": 158, "bp_diastolic": 98,
    "blood_urea_nitrogen": 42.0, "albumin_serum": 2.9, "phosphorus": 5.5,
    "bicarbonate": 18.0, "calcium": 8.5, "uric_acid": 9.2,
    "urine_creatinine": 60.0,
    "gender": "Male", "ethnicity": "Non-Hispanic Black",
    "education_level": "2.0", "diabetes_diagnosed": "1.0",
    "insulin_use": "1.0", "diabetes_pills": "1.0",
    "ever_smoked": "1.0", "current_smoker": "1.0"
}

LOW_RISK_PATIENT = {
    "age": 28, "poverty_income_ratio": 4.5, "bmi": 22.0, "weight_kg": 65.0,
    "height_cm": 170.0, "bp_systolic": 115, "bp_diastolic": 72,
    "blood_urea_nitrogen": 11.0, "albumin_serum": 4.2, "phosphorus": 3.5,
    "bicarbonate": 25.0, "calcium": 9.8, "uric_acid": 4.5,
    "urine_creatinine": 150.0,
    "gender": "Female", "ethnicity": "Non-Hispanic White",
    "education_level": "5.0", "diabetes_diagnosed": "2.0",
    "insulin_use": "2.0", "diabetes_pills": "2.0",
    "ever_smoked": "2.0", "current_smoker": "2.0"
}

# =============================================================================
print("\n" + "="*60)
print("  CKD FRAMEWORK — COMPLETE END-TO-END TEST SUITE")
print("="*60)

# ── 1. RAW DATA ───────────────────────────────────────────────────────────────
print("\n[1] Raw Data")

def t_raw_exists():
    assert os.path.exists(RAW_PATH), f"Raw file not found: {RAW_PATH}"
    import pandas as pd
    df = pd.read_csv(RAW_PATH)
    assert len(df) > 10000, f"Expected > 10000 rows, got {len(df)}"
    assert "ckd_present" in df.columns, "Missing target column ckd_present"
    assert "ckd_stage" in df.columns, "Missing ckd_stage column"

test("Raw NHANES CSV exists and has expected shape", t_raw_exists)

# ── 2. PREPROCESSING ──────────────────────────────────────────────────────────
print("\n[2] Preprocessing & Cleaning")

def t_cleaned_exists():
    assert os.path.exists(PROC_PATH), "ckd_cleaned.csv not found — run preprocessing.cleaning first"
    import pandas as pd
    df = pd.read_csv(PROC_PATH)
    assert "target" in df.columns, "target column missing from cleaned data"
    assert df["target"].isin([0, 1]).all(), "target has values other than 0/1"
    assert len(df) > 1000, f"Too few rows after cleaning: {len(df)}"
    assert (df["age"] >= 18).all(), "Non-adult rows present — cleaning filter failed"

test("Cleaned CSV exists, all-adult, valid binary target", t_cleaned_exists)

def t_class_balance():
    import pandas as pd
    df = pd.read_csv(PROC_PATH)
    ckd_pct = df["target"].mean() * 100
    # After artefact removal, CKD should be 40-65% (realistic range)
    assert 35 <= ckd_pct <= 70, f"Unexpected class ratio: {ckd_pct:.1f}% CKD"

test("Class distribution is realistic (35-70% CKD)", t_class_balance)

def t_no_leakage_cols():
    import pandas as pd
    df = pd.read_csv(PROC_PATH)
    leakage = ["egfr", "albumin_creatinine_ratio", "serum_creatinine", "urine_albumin", "ckd_stage"]
    for col in leakage:
        assert col not in df.columns, f"Leakage column found: {col}"

test("No direct diagnostic leakage columns in cleaned data", t_no_leakage_cols)

def t_pipeline_transform():
    import pandas as pd
    from preprocessing.pipeline import build_preprocessing_pipeline, ALL_FEATURES
    df = pd.read_csv(PROC_PATH)
    X = df[ALL_FEATURES]
    pre = build_preprocessing_pipeline()
    Xt = pre.fit_transform(X, df["target"])
    assert Xt.shape[0] == len(df), "Pipeline output row count mismatch"
    assert Xt.shape[1] >= len(ALL_FEATURES), "Pipeline produced fewer columns than expected"

test("Sklearn preprocessing pipeline transforms data correctly", t_pipeline_transform)

# ── 3. FEATURE ENGINEERING ────────────────────────────────────────────────────
print("\n[3] Feature Engineering")

def t_feature_engineering():
    import pandas as pd
    from features.feature_engineering import engineer_features, ENGINEERED_NUMERIC
    df = pd.read_csv(PROC_PATH)
    df_e = engineer_features(df)
    for col in ENGINEERED_NUMERIC:
        assert col in df_e.columns, f"Engineered feature missing: {col}"
    # Metabolic risk score should increase CKD rate
    rate_0 = df_e[df_e["metabolic_risk_score"] == 0]["target"].mean()
    rate_hi = df_e[df_e["metabolic_risk_score"] >= 3]["target"].mean()
    assert rate_hi > rate_0, "Metabolic risk score not correlated with CKD rate"

test("All 8 engineered features created; metabolic risk correlates with CKD", t_feature_engineering)

# ── 4. TRAINED MODEL ARTIFACTS ────────────────────────────────────────────────
print("\n[4] Trained Model Artifacts")

def t_models_exist():
    path = os.path.join(ART_DIR, "stacking_ckd_model.pkl")
    assert os.path.exists(path), f"Stacking model artifact not found: {path}"
    size = os.path.getsize(path)
    assert size > 1000, f"Model file suspiciously small: {path} ({size} bytes)"

test("Stacking model .pkl file exists and is non-trivial size", t_models_exist)

def t_evaluation_metrics():
    metrics_path = os.path.join(ART_DIR, "evaluation_metrics.json")
    assert os.path.exists(metrics_path), "evaluation_metrics.json not found"
    with open(metrics_path) as f:
        m = json.load(f)
    
    assert "stacking_ensemble" in m, f"Missing stacking_ensemble in metrics"
    assert 0.5 < m["stacking_ensemble"]["accuracy"] < 1.0, f"Suspicious accuracy: {m['stacking_ensemble']['accuracy']}"
    assert 0.5 < m["stacking_ensemble"]["roc_auc"]  < 1.0, f"Suspicious ROC-AUC: {m['stacking_ensemble']['roc_auc']}"
    # Ensure accuracy is NOT suspiciously perfect (leakage check)
    assert m["stacking_ensemble"]["accuracy"] < 0.98, "Accuracy is suspiciously perfect — possible leakage!"

test("evaluation_metrics.json has realistic scores for Stacking Ensemble", t_evaluation_metrics)

# ── 5. EARLY DETECTION PREDICTION ─────────────────────────────────────────────
print("\n[5] Early Detection — Prediction API")

def t_predict_high_risk():
    from models.ckd_detection.predict import predict
    result = predict(HIGH_RISK_PATIENT.copy())
    assert "prediction" in result
    assert "probability_ckd" in result
    assert result["prediction"] in ["ckd", "notckd"]
    assert 0.0 <= result["probability_ckd"] <= 1.0
    # High-risk patient should likely be predicted as CKD
    assert result["prediction"] == "ckd", \
        f"Expected high-risk patient to predict CKD, got {result['prediction']} (prob={result['probability_ckd']:.2f})"

test("High-risk patient predicted as CKD by Stacking Ensemble", t_predict_high_risk)

def t_predict_low_risk():
    from models.ckd_detection.predict import predict
    result = predict(LOW_RISK_PATIENT.copy())
    assert result["prediction"] == "notckd", \
        f"Expected low-risk patient to predict notckd, got {result['prediction']} (prob={result['probability_ckd']:.2f})"

test("Low-risk patient predicted as No CKD by Stacking Ensemble", t_predict_low_risk)

def t_predict_output_schema():
    from models.ckd_detection.predict import predict
    result = predict(SAMPLE_PATIENT.copy())
    required = ["model_used", "prediction", "probability_ckd", "probability_notckd"]
    for key in required:
        assert key in result, f"Missing key in predict output: {key}"
    assert abs(result["probability_ckd"] + result["probability_notckd"] - 1.0) < 0.001, \
        "Probabilities don't sum to 1"

test("Prediction output schema is valid and probabilities sum to 1", t_predict_output_schema)

def t_predict_handles_missing_features():
    from models.ckd_detection.predict import predict
    # Patient with only a few features — rest should be imputed
    sparse_patient = {"age": 60, "bp_systolic": 145, "diabetes_diagnosed": "1.0"}
    result = predict(sparse_patient)
    assert "prediction" in result, "Failed to handle sparse patient input"

test("Prediction gracefully handles patients with missing features", t_predict_handles_missing_features)

# ── 6. SHAP EXPLAINABILITY ─────────────────────────────────────────────────────
print("\n[6] SHAP Explainability")

def t_shap_output_schema():
    from explainability.shap_explainer import CKDExplainer
    explainer = CKDExplainer("stacking")
    result = explainer.explain(SAMPLE_PATIENT.copy(), top_k=5)
    assert "prediction" in result
    assert "probability_ckd" in result
    assert "top_contributing_features" in result
    assert "disclaimer" in result
    assert len(result["top_contributing_features"]) == 5
    for feat in result["top_contributing_features"]:
        assert "feature_name" in feat
        assert "shap_value" in feat
        assert "direction" in feat
        assert feat["direction"] in ["increases_risk", "decreases_risk"]

test("SHAP explainer returns valid schema for Stacking Ensemble", t_shap_output_schema)

# ── 7. DISEASE PROGRESSION ────────────────────────────────────────────────────
print("\n[7] Disease Progression")

def t_progression_model_exists():
    path = os.path.join(ART_DIR, "progression_model.pkl")
    assert os.path.exists(path), "progression_model.pkl not found"
    assert os.path.getsize(path) > 1000, "Progression model file is too small"

test("Progression model artifact exists", t_progression_model_exists)

def t_progression_prediction():
    from models.progression.progression_model import predict_progression
    result = predict_progression(HIGH_RISK_PATIENT.copy())
    assert "predicted_stage" in result
    assert "stage_probabilities" in result
    assert "disclaimer" in result
    assert result["predicted_stage"] in ["Stage 1", "Stage 2", "Stage 3", "Stage 4"]
    probs = result["stage_probabilities"]
    assert len(probs) == 4, f"Expected 4 stage probabilities, got {len(probs)}"
    total = sum(probs.values())
    assert abs(total - 1.0) < 0.01, f"Stage probabilities don't sum to 1: {total}"

test("Progression model returns valid 4-stage prediction with probabilities", t_progression_prediction)

def t_progression_high_stage():
    from models.progression.progression_model import predict_progression
    result = predict_progression(HIGH_RISK_PATIENT.copy())
    # Very high-risk patient (BUN=42, bicarb=18, uric=9.2) — should be Stage 3 or 4
    assert result["predicted_stage"] in ["Stage 3", "Stage 4"], \
        f"High-risk patient predicted as {result['predicted_stage']} — expected Stage 3 or 4"

test("High-risk patient progression predicted as Stage 3 or 4", t_progression_high_stage)

# ── 8. CLINICAL RECOMMENDATIONS ───────────────────────────────────────────────
print("\n[8] Clinical Recommendation Engine")

def t_rules_high_risk():
    from models.recommendation.rules import generate_recommendations
    recs = generate_recommendations(HIGH_RISK_PATIENT, {"risk_level": "HIGH"})
    assert len(recs) > 0, "No recommendations generated for high-risk patient"
    categories = [r["category"] for r in recs]
    priorities = [r["priority"] for r in recs]
    assert "Specialist Referral" in categories, "No specialist referral for HIGH risk"
    assert "high" in priorities, "No high-priority recommendations"
    for r in recs:
        assert "recommendation" in r
        assert r["priority"] in ["high", "medium", "low"]

test("High-risk patient generates specialist referral + high-priority recommendations", t_rules_high_risk)

def t_rules_low_risk():
    from models.recommendation.rules import generate_recommendations
    recs = generate_recommendations(LOW_RISK_PATIENT, {"risk_level": "LOW"})
    assert len(recs) > 0, "Should always return at least one recommendation"

test("Low-risk patient always gets at least one monitoring recommendation", t_rules_low_risk)

# ── 9. ARTIFACTS INTEGRITY ────────────────────────────────────────────────────
print("\n[9] Artifacts Integrity")

def t_evaluation_json_correct():
    path = os.path.join(ART_DIR, "evaluation_metrics.json")
    with open(path) as f:
        m = json.load(f)
    
    keys = set(m["stacking_ensemble"].keys())
    expected = {"accuracy", "roc_auc", "f1_weighted", "precision", "recall"}
    missing = expected - keys
    assert not missing, f"stacking_ensemble missing metrics: {missing}"

test("evaluation_metrics.json has all 5 metric keys for Stacking Ensemble", t_evaluation_json_correct)

def t_model_comparison_annotated():
    path = os.path.join(ART_DIR, "model_comparison.json")
    with open(path) as f:
        m = json.load(f)
    assert "_note" in m, "model_comparison.json should have a _note marking it as legacy"
    assert "LEGACY" in m.get("_note", "").upper() or "LEGACY" in m.get("selected_model", "").upper()

test("model_comparison.json correctly annotated as legacy UCI file", t_model_comparison_annotated)

def t_plots_exist():
    plots_dir = os.path.join(ART_DIR, "plots")
    assert os.path.isdir(plots_dir), "plots/ directory not found"
    pngs = [f for f in os.listdir(plots_dir) if f.endswith(".png")]
    assert len(pngs) >= 9, f"Expected >= 9 plot files, found {len(pngs)}"

test("All 9 visualization plots exist in artifacts/plots/", t_plots_exist)

# ─── SUMMARY ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
total  = len(results)
print(f"  RESULTS: {passed}/{total} tests passed  |  {failed} failed")
print("="*60)

if failed:
    print("\nFailed tests:")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  - {r['test']}")
            print(f"    Error: {r.get('error', '')}")

# Save test report
report_path = os.path.join(ART_DIR, "test_report.json")
with open(report_path, "w") as f:
    json.dump({
        "summary": {"passed": passed, "failed": failed, "total": total},
        "tests": results
    }, f, indent=2)
print(f"\nTest report saved to: {report_path}")

if failed > 0:
    sys.exit(1)
