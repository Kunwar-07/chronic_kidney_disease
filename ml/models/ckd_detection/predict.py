"""
predict.py
----------
Production prediction entry point for the CKD Early Warning Framework.

Supports three modes:
  - Single model prediction  (model_name="xgboost" | "catboost" | "lightgbm")
  - Ensemble prediction      (model_name="ensemble") -- RECOMMENDED
    Averages probabilities across all 3 models and applies the Youden-optimal
    threshold to minimize borderline mis-classifications.

Output includes a 3-tier CONFIDENCE level:
  HIGH     : |P(CKD) - threshold| > 0.20  (model is very decisive)
  MODERATE : |P(CKD) - threshold| between 0.10 and 0.20
  LOW      : |P(CKD) - threshold| < 0.10  (borderline — flag for clinical review)

This replaces the binary 0.5 cutoff and surfaces uncertain cases to clinicians
rather than forcing a wrong hard prediction.
"""

import pandas as pd
import numpy as np
import joblib
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.pipeline import ALL_FEATURES

BASE    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART_DIR = os.path.join(BASE, "artifacts")

# Cache loaded models so they are loaded only once per process
_model_cache = {}


def _load_model(name: str):
    if name not in _model_cache:
        path = os.path.join(ART_DIR, f"{name}_ckd_model.pkl")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found: {path}. Run train.py first.")
        _model_cache[name] = joblib.load(path)
    return _model_cache[name]


def _load_thresholds() -> dict:
    path = os.path.join(ART_DIR, "optimal_thresholds.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}  # falls back to 0.5 if thresholds not yet tuned


def _confidence_label(prob_ckd: float, threshold: float) -> str:
    """Convert the distance from threshold into a clinical confidence tier."""
    distance = abs(prob_ckd - threshold)
    if distance >= 0.20:
        return "HIGH"
    elif distance >= 0.10:
        return "MODERATE"
    else:
        return "LOW"


def predict(patient_dict: dict) -> dict:
    """
    Args:
        patient_dict: dict of patient features (keys = ALL_FEATURES)

    Returns dict with:
        model_used        : name of model(s) used
        prediction        : 'ckd' or 'notckd'
        probability_ckd   : P(CKD) from the model
        probability_notckd: 1 - P(CKD)
        confidence        : 'HIGH' | 'MODERATE' | 'LOW'
        threshold_used    : the decision threshold applied
        clinical_note     : guidance string for LOW-confidence predictions
    """
    # Fill missing features with None (will be imputed by pipeline)
    for f in ALL_FEATURES:
        if f not in patient_dict:
            patient_dict[f] = None

    X_new = pd.DataFrame([patient_dict])[ALL_FEATURES]
    
    # Load the Stacking Meta-Model
    pipeline  = _load_model("stacking")
    prob_ckd  = float(pipeline.predict_proba(X_new)[0, 1])
    
    # We use a default threshold of 0.5 since the Stacking meta-model
    # (Logistic Regression) naturally calibrates probabilities well.
    threshold = 0.5
    used = "Stacking Ensemble (XGB, CatBoost, LGBM -> LogisticRegression)"

    prediction = "ckd" if prob_ckd >= threshold else "notckd"
    confidence = _confidence_label(prob_ckd, threshold)

    result = {
        "model_used":         used,
        "prediction":         prediction,
        "probability_ckd":    round(prob_ckd, 4),
        "probability_notckd": round(1 - prob_ckd, 4),
        "confidence":         confidence,
        "threshold_used":     threshold,
    }

    if confidence == "LOW":
        result["clinical_note"] = (
            f"Borderline prediction (P(CKD)={prob_ckd:.2f}, threshold={threshold:.2f}). "
            "Confidence is LOW. Clinical review and additional lab tests are strongly recommended "
            "before acting on this prediction."
        )

    return result


if __name__ == "__main__":
    import json

    # High-risk patient
    high_risk = {
        "age": 72, "poverty_income_ratio": 0.5, "bmi": 35.0, "weight_kg": 105.0,
        "height_cm": 172.0, "bp_systolic": 158, "bp_diastolic": 98,
        "blood_urea_nitrogen": 42.0, "albumin_serum": 2.9, "phosphorus": 5.5,
        "bicarbonate": 18.0, "calcium": 8.5, "uric_acid": 9.2,
        "urine_creatinine": 60.0, "gender": "Male",
        "ethnicity": "Non-Hispanic Black", "education_level": "2.0",
        "diabetes_diagnosed": "1.0", "insulin_use": "1.0",
        "diabetes_pills": "1.0", "ever_smoked": "1.0", "current_smoker": "1.0"
    }

    # Low-risk patient
    low_risk = {
        "age": 28, "poverty_income_ratio": 4.5, "bmi": 22.0, "weight_kg": 65.0,
        "height_cm": 170.0, "bp_systolic": 115, "bp_diastolic": 72,
        "blood_urea_nitrogen": 11.0, "albumin_serum": 4.2, "phosphorus": 3.5,
        "bicarbonate": 25.0, "calcium": 9.8, "uric_acid": 4.5,
        "urine_creatinine": 150.0, "gender": "Female",
        "ethnicity": "Non-Hispanic White", "education_level": "5.0",
        "diabetes_diagnosed": "2.0", "insulin_use": "2.0",
        "diabetes_pills": "2.0", "ever_smoked": "2.0", "current_smoker": "2.0"
    }

    # Borderline patient (similar to the one we found before)
    borderline = {
        "age": 59, "poverty_income_ratio": 3.27, "bmi": 36.3, "weight_kg": 95.0,
        "height_cm": 170.0, "bp_systolic": 128, "bp_diastolic": 80,
        "blood_urea_nitrogen": 14.0, "albumin_serum": 4.2, "phosphorus": 3.8,
        "bicarbonate": 23.0, "calcium": 9.5, "uric_acid": 5.5,
        "urine_creatinine": 120.0, "gender": "Female",
        "ethnicity": "Non-Hispanic White", "education_level": "3.0",
        "diabetes_diagnosed": "2.0", "insulin_use": "2.0",
        "diabetes_pills": "2.0", "ever_smoked": "2.0", "current_smoker": "2.0"
    }

    for label, patient in [("HIGH-RISK", high_risk), ("LOW-RISK", low_risk), ("BORDERLINE", borderline)]:
        print(f"\n--- {label} PATIENT ---")
        result = predict(patient.copy(), "ensemble")
        print(json.dumps(result, indent=2))
