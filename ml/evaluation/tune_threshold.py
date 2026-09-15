"""
tune_threshold.py
------------------
Finds the mathematically optimal decision threshold for each model and the
ensemble, using:
  - Youden's J statistic (maximizes sensitivity + specificity simultaneously)
  - F1-optimal threshold (maximizes F1 score)

Saves the optimal thresholds to artifacts/optimal_thresholds.json.
No retraining required — runs on the same test split as training.

Run: python -m evaluation.tune_threshold
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_curve, f1_score, classification_report
from preprocessing.pipeline import ALL_FEATURES

BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_DIR  = os.path.join(BASE, "artifacts")
DATA     = os.path.join(BASE, "data", "processed", "ckd_cleaned.csv")

def youden_threshold(y_true, y_prob):
    """Find threshold that maximizes Sensitivity + Specificity - 1 (Youden's J)."""
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    return float(thresholds[best_idx]), float(j_scores[best_idx])

def f1_optimal_threshold(y_true, y_prob):
    """Find threshold that maximizes F1 score via grid search."""
    best_f1, best_thresh = 0, 0.5
    for t in np.arange(0.3, 0.8, 0.01):
        preds = (y_prob >= t).astype(int)
        f1 = f1_score(y_true, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_thresh = f1, t
    return round(float(best_thresh), 2), round(float(best_f1), 4)

def run_tuning():
    df = pd.read_csv(DATA)
    X  = df[ALL_FEATURES]
    y  = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model_names = ["xgboost", "catboost", "lightgbm"]
    all_probs   = []
    thresholds  = {}

    print("\n" + "="*60)
    print("  THRESHOLD OPTIMIZATION")
    print("="*60)

    for name in model_names:
        path = os.path.join(ART_DIR, f"{name}_ckd_model.pkl")
        pipeline = joblib.load(path)
        probs    = pipeline.predict_proba(X_test)[:, 1]
        all_probs.append(probs)

        y_thresh, j_score = youden_threshold(y_test, probs)
        f1_thresh, best_f1 = f1_optimal_threshold(y_test, probs)

        print(f"\n  {name.upper()}")
        print(f"    Default 0.50  -> F1 = {f1_score(y_test, (probs>=0.5).astype(int)):.4f}")
        print(f"    Youden  {y_thresh:.2f}  -> J  = {j_score:.4f}")
        print(f"    F1-opt  {f1_thresh:.2f}  -> F1 = {best_f1:.4f}")

        thresholds[name] = {
            "youden_threshold": round(y_thresh, 3),
            "f1_threshold": f1_thresh,
        }

    # Ensemble: average probabilities across all 3 models
    ensemble_probs = np.mean(all_probs, axis=0)
    e_thresh, e_j  = youden_threshold(y_test, ensemble_probs)
    e_f1t, e_f1    = f1_optimal_threshold(y_test, ensemble_probs)

    print(f"\n  ENSEMBLE (avg of all 3)")
    print(f"    Default 0.50  -> F1 = {f1_score(y_test, (ensemble_probs>=0.5).astype(int)):.4f}")
    print(f"    Youden  {e_thresh:.2f}  -> J  = {e_j:.4f}")
    print(f"    F1-opt  {e_f1t:.2f}  -> F1 = {e_f1:.4f}")
    print(f"\n  Classification Report (Ensemble, Youden threshold {e_thresh:.2f}):")
    y_pred_ens = (ensemble_probs >= e_thresh).astype(int)
    print(classification_report(y_test, y_pred_ens,
                                target_names=["No CKD", "CKD"], zero_division=0))

    thresholds["ensemble"] = {
        "youden_threshold": round(e_thresh, 3),
        "f1_threshold": e_f1t,
    }

    # Uncertainty band: cases where even ensemble is in [0.35, 0.65]
    borderline_mask = (ensemble_probs >= 0.35) & (ensemble_probs <= 0.65)
    print(f"  Borderline cases (ensemble prob 0.35-0.65): "
          f"{borderline_mask.sum()} / {len(y_test)} "
          f"({borderline_mask.mean()*100:.1f}%)")
    borderline_mask2 = (ensemble_probs >= 0.40) & (ensemble_probs <= 0.60)
    print(f"  Borderline cases (ensemble prob 0.40-0.60): "
          f"{borderline_mask2.sum()} / {len(y_test)} "
          f"({borderline_mask2.mean()*100:.1f}%)")

    out_path = os.path.join(ART_DIR, "optimal_thresholds.json")
    with open(out_path, "w") as f:
        json.dump(thresholds, f, indent=2)
    print(f"\n  Thresholds saved to: {out_path}")
    print("="*60)

    return thresholds

if __name__ == "__main__":
    run_tuning()
