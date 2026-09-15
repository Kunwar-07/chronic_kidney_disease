"""
verify_test_predictions.py
--------------------------
Pulls 5 real patients directly from the held-out test set (same random_state=42
split used during training) and runs them through all models.

Verifies:
  - Ground truth label vs prediction for each model
  - SHAP top features for the XGBoost model
  - Progression stage (for CKD-positive patients)
  - Clinical recommendations
"""

import pandas as pd
import numpy as np
import sys, os, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.model_selection import train_test_split
from preprocessing.pipeline import ALL_FEATURES
from models.ckd_detection.predict import predict
from explainability.shap_explainer import CKDExplainer
from models.progression.progression_model import predict_progression
from models.recommendation.rules import generate_recommendations
import joblib

# ─── Load data & recreate exact train/test split ──────────────────────────────
df = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "processed", "ckd_cleaned.csv"))

X = df[ALL_FEATURES]
y = df["target"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ─── Select 5 diverse patients ────────────────────────────────────────────────
# 2 confirmed CKD, 2 confirmed No CKD, 1 borderline
ckd_idx   = y_test[y_test == 1].index[:2].tolist()
nocd_idx  = y_test[y_test == 0].index[:2].tolist()

# Find a borderline patient (XGBoost probability 0.35–0.65)
pipeline_xgb = joblib.load(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts", "xgboost_ckd_model.pkl"))
probs = pd.Series(pipeline_xgb.predict_proba(X_test)[:, 1], index=X_test.index)
borderline = probs[(probs > 0.35) & (probs < 0.65)]
border_idx = [borderline.index[0]] if len(borderline) > 0 else [y_test.index[15]]

selected = ckd_idx + nocd_idx + border_idx
labels_map = {0: "No CKD", 1: "CKD"}

explainer = CKDExplainer("xgboost")

print("\n" + "="*70)
print("  LIVE VERIFICATION — 5 REAL TEST-SET PATIENTS")
print("="*70)

for rank, idx in enumerate(selected, 1):
    patient_row = df.loc[idx]
    true_label  = int(patient_row["target"])
    patient_dict = {feat: patient_row.get(feat, None) for feat in ALL_FEATURES}

    print(f"\n{'-'*70}")
    print(f"  PATIENT {rank}  (Dataset row #{idx})")
    print(f"{'-'*70}")
    print(f"  Ground Truth  : {labels_map[true_label]}")

    # ── Key clinical features ────────────────────────────────────────────────
    print(f"\n  Key Clinical Values:")
    show = ["age", "bp_systolic", "blood_urea_nitrogen", "albumin_serum",
            "uric_acid", "bicarbonate", "bmi", "diabetes_diagnosed", "gender"]
    for feat in show:
        val = patient_dict.get(feat)
        if val is not None and str(val) not in ("nan", "None", ""):
            print(f"    {feat:<28}: {val}")

    # ── All 3 model predictions ──────────────────────────────────────────────
    print(f"\n  Model Predictions:")
    all_correct = True
    for model_name in ["xgboost", "catboost", "lightgbm"]:
        result = predict(patient_dict.copy(), model_name)
        correct = result["prediction"] == ("ckd" if true_label == 1 else "notckd")
        flag = "[OK]" if correct else "[WRONG]"
        if not correct:
            all_correct = False
        print(f"    {model_name.upper():<12}: {result['prediction'].upper():<7}  "
              f"P(CKD)={result['probability_ckd']:.3f}  {flag}")

    # ── SHAP top 3 features ──────────────────────────────────────────────────
    print(f"\n  Top 3 SHAP Features (XGBoost):")
    shap_result = explainer.explain(patient_dict.copy(), top_k=3)
    for feat in shap_result["top_contributing_features"]:
        arrow = "(+)" if feat["direction"] == "increases_risk" else "(-)"
        print(f"    {arrow}  {feat['feature_name']:<28}  SHAP={feat['shap_value']:+.3f}")

    # ── Progression prediction (only for CKD patients) ───────────────────────
    if true_label == 1:
        prog = predict_progression(patient_dict.copy())
        print(f"\n  Progression Stage: {prog['predicted_stage']}")
        top_stage = max(prog["stage_probabilities"], key=prog["stage_probabilities"].get)
        print(f"  Stage Probabilities: " +
              "  ".join(f"{s}:{p:.2f}" for s, p in prog["stage_probabilities"].items()))

    # ── Clinical recommendations ─────────────────────────────────────────────
    risk_level = "HIGH" if shap_result["probability_ckd"] >= 0.6 else (
                 "MODERATE" if shap_result["probability_ckd"] >= 0.4 else "LOW")
    recs = generate_recommendations(patient_dict, {"risk_level": risk_level})
    print(f"\n  Clinical Recommendations ({risk_level} risk):")
    for r in recs[:3]:
        print(f"    [{r['priority'].upper()}] {r['category']}: {r['recommendation'][:65]}...")

print("\n" + "="*70)
print("  VERIFICATION COMPLETE")
print("="*70)
