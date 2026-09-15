"""
progression_model.py
---------------------
Disease Progression Prediction — Multi-class CKD Stage Classifier.

This module addresses the second half of the research topic:
"Adaptive Explainable AI Framework for Early Detection AND Disease
Progression Prediction of Chronic Kidney Disease"

It predicts the CKD stage (1 / 2 / 3 / 4) for adult patients who already
have a confirmed CKD diagnosis, using the same clinical indicators as the
early detection module but mapping them to a severity scale.

Stage encoding (CKD-EPI / KDIGO guideline):
    1 -> CKD Stage 1  (eGFR >= 90, with kidney damage markers)
    2 -> CKD Stage 2  (eGFR 60-89)
    3 -> CKD Stage 3  (eGFR 30-59, combines 3a/3b)
    4 -> CKD Stage 4  (eGFR 15-29)

NOTE: Stage 5 (kidney failure, eGFR < 15) is excluded — the dataset has
too few cases for reliable training, and these patients require immediate
specialist care rather than a predictive model.
"""

import pandas as pd
import numpy as np
import os
import sys
import joblib
import json

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score
import xgboost as xgb
import shap

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from preprocessing.pipeline import build_preprocessing_pipeline, ALL_FEATURES


STAGE_MAP = {
    "Stage 1 (Kidney Damage)":      1,
    "Stage 2 (Mildly Decreased)":   2,
    "Stage 3a (Mild-Moderate)":     3,
    "Stage 3b (Moderate-Severe)":   3,
    "Stage 4 (Severely Decreased)": 4,
}

STAGE_LABELS = {1: "Stage 1", 2: "Stage 2", 3: "Stage 3", 4: "Stage 4"}


def load_progression_data(raw_path: str):
    """
    Loads the raw NHANES CSV, keeps only confirmed CKD patients with a
    known, non-Unknown stage, and maps to numeric stage labels.
    """
    df = pd.read_csv(raw_path)

    # Keep only adult CKD patients with a known stage
    df = df[df["age"] >= 18].copy()
    df = df[df["ckd_present"] == 1].copy()
    df = df[df["ckd_stage"].isin(STAGE_MAP.keys())].copy()

    df["stage"] = df["ckd_stage"].map(STAGE_MAP)

    # Drop leakage + direct diagnostic columns
    drop = ["participant_id", "ckd_stage", "ckd_present",
            "egfr", "albumin_creatinine_ratio", "urine_albumin", "serum_creatinine"]
    df = df.drop(columns=[c for c in drop if c in df.columns])

    available = [f for f in ALL_FEATURES if f in df.columns]
    X = df[available].reindex(columns=ALL_FEATURES)
    y = df["stage"]

    # Drop rows where ALL features are NaN
    valid_mask = X.notna().any(axis=1)
    X = X[valid_mask]
    y = y[valid_mask]

    return X.reset_index(drop=True), y.reset_index(drop=True)


def train_progression_model():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_path  = os.path.join(base_dir, "data", "raw", "CKD_NHANES_2021_2023.csv")
    art_dir   = os.path.join(base_dir, "artifacts")
    os.makedirs(art_dir, exist_ok=True)

    print("Loading progression dataset...")
    X, y = load_progression_data(raw_path)

    print(f"Progression dataset: {len(X):,} CKD patients with known stage")
    print("Stage distribution:")
    vc = y.value_counts().sort_index()
    for stage, count in vc.items():
        print(f"  {STAGE_LABELS[stage]}: {count:,} ({count/len(y)*100:.1f}%)")

    if len(y.unique()) < 2:
        print("\nNot enough stage diversity to train a meaningful model.")
        return

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\nTrain: {len(X_train):,}  |  Test: {len(X_test):,}")

    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    y_test_enc  = le.transform(y_test)

    preprocessor = build_preprocessing_pipeline()
    clf = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=len(le.classes_),
        eval_metric="mlogloss",
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )

    pipeline = Pipeline(steps=[
        ("preprocess", preprocessor),
        ("model", clf)
    ])

    print("\nTraining XGBoost multi-class progression model...")
    pipeline.fit(X_train, y_train_enc)

    y_pred_enc = pipeline.predict(X_test)
    y_pred = le.inverse_transform(y_pred_enc)
    print(f"\nAccuracy: {accuracy_score(y_test, y_pred):.4f}")
    stage_names = [STAGE_LABELS[s] for s in le.classes_]
    print("\nClassification Report:")
    print(classification_report(y_test_enc, y_pred_enc,
                                target_names=stage_names,
                                zero_division=0))

    out_path = os.path.join(art_dir, "progression_model.pkl")
    joblib.dump(pipeline, out_path)
    print(f"\nProgression model saved to: {out_path}")

    return pipeline


def predict_progression(patient: dict, pipeline=None) -> dict:
    """
    Predict CKD stage for a patient who is already diagnosed with CKD.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(base_dir, "artifacts", "progression_model.pkl")
    if pipeline is None:
        if not os.path.exists(model_path):
            raise FileNotFoundError("Run train_progression_model() first.")
        pipeline = joblib.load(model_path)

    for f in ALL_FEATURES:
        if f not in patient:
            patient[f] = None

    X_new = pd.DataFrame([patient])[ALL_FEATURES]
    proba = pipeline.predict_proba(X_new)[0]
    pred_enc = pipeline.predict(X_new)[0]

    # XGBoost classes are 0-based encoded; map back to real stage values
    # Real stages present in training (sorted): e.g. [1, 2, 3, 4]
    real_stages = sorted(STAGE_MAP.values(), key=lambda x: x)
    # Remove duplicates (3a and 3b both map to 3)
    real_stages = sorted(set(real_stages))
    # n_classes from pipeline
    n_cls = len(proba)
    enc_to_stage = {i: real_stages[i] for i in range(n_cls)}

    pred_stage = enc_to_stage[int(pred_enc)]
    prob_dict = {STAGE_LABELS[enc_to_stage[i]]: round(float(p), 4)
                 for i, p in enumerate(proba)}

    return {
        "predicted_stage": STAGE_LABELS[pred_stage],
        "stage_probabilities": prob_dict,
        "disclaimer": (
            "This progression prediction is based on secondary clinical "
            "indicators only, without eGFR. It is intended to flag patients "
            "for further specialist review, not as a clinical diagnosis."
        )
    }


if __name__ == "__main__":
    pipeline = train_progression_model()

    if pipeline is not None:
        print("\n--- Sample Progression Prediction ---")
        sample = {
            "age": 68, "poverty_income_ratio": 1.5, "bmi": 31.0,
            "weight_kg": 88.0, "height_cm": 168.0,
            "bp_systolic": 155, "bp_diastolic": 95,
            "blood_urea_nitrogen": 35.0, "albumin_serum": 3.2,
            "phosphorus": 5.1, "bicarbonate": 19.0, "calcium": 8.8,
            "uric_acid": 8.5, "urine_creatinine": 80.0,
            "gender": "Male", "ethnicity": "Non-Hispanic White",
            "education_level": "3.0", "diabetes_diagnosed": "1.0",
            "insulin_use": "1.0", "diabetes_pills": "1.0",
            "ever_smoked": "1.0", "current_smoker": "2.0"
        }
        result = predict_progression(sample, pipeline)
        print(json.dumps(result, indent=2))
