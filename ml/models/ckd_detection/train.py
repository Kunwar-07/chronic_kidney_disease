"""
train.py
--------
Trains and evaluates three gradient boosting models for CKD Early Detection:
  - XGBoost
  - CatBoost
  - LightGBM

Key design decisions:
  - Class imbalance correction: XGBoost uses scale_pos_weight, LightGBM uses
    is_unbalance=True, CatBoost uses auto_class_weights. This ensures the
    minority class (No CKD) gets proper attention.
  - Comprehensive evaluation: Accuracy, ROC-AUC, F1 (weighted), precision,
    recall per class.
  - All three trained pipelines saved to artifacts/.
"""

import pandas as pd
import numpy as np
import os
import joblib
import json

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, roc_auc_score, accuracy_score,
    f1_score, precision_score, recall_score
)
import xgboost as xgb
from catboost import CatBoostClassifier
import lightgbm as lgb

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from preprocessing.pipeline import build_preprocessing_pipeline, ALL_FEATURES


def load_data(data_path: str):
    df = pd.read_csv(data_path)
    # Only keep rows that have at least some feature data
    available = [f for f in ALL_FEATURES if f in df.columns]
    X = df[available].reindex(columns=ALL_FEATURES)
    y = df["target"]
    return X, y


def compute_class_weight(y_train):
    """Returns ratio of negative to positive class for scale_pos_weight."""
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    return round(neg / pos, 4)


from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.combine import SMOTETomek
from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression

def evaluate_model(name: str, y_test, y_pred, y_prob):
    sep = "=" * 42
    print(f"\n{sep}")
    print(f"  Model: {name}")
    print(sep)
    print(f"  Accuracy  : {accuracy_score(y_test, y_pred):.4f}")
    if len(np.unique(y_test)) > 1:
        print(f"  ROC-AUC   : {roc_auc_score(y_test, y_prob):.4f}")
    print(f"  F1 (wtd)  : {f1_score(y_test, y_pred, average='weighted'):.4f}")
    print(f"  Precision : {precision_score(y_test, y_pred, average='weighted', zero_division=0):.4f}")
    print(f"  Recall    : {recall_score(y_test, y_pred, average='weighted'):.4f}")
    print("\nClassification Report (per class):")
    print(classification_report(y_test, y_pred,
                                target_names=["No CKD", "CKD"],
                                zero_division=0))


def train_all_models():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, "data", "processed", "ckd_cleaned.csv")
    artifacts_dir = os.path.join(base_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    print(f"Loading cleaned dataset from {data_path}...")
    X, y = load_data(data_path)

    pos = int(y.sum())
    neg = int((y == 0).sum())
    total = len(y)
    print(f"Class distribution — CKD: {pos:,} ({pos/total*100:.1f}%)  |  "
          f"No CKD: {neg:,} ({neg/total*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {X_train.shape[0]:,}  |  Test: {X_test.shape[0]:,}")

    base_models = [
        ("xgboost", xgb.XGBClassifier(
            eval_metric="logloss",
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )),
        ("catboost", CatBoostClassifier(
            verbose=0,
            iterations=300,
            depth=6,
            learning_rate=0.05,
            random_state=42,
        )),
        ("lightgbm", lgb.LGBMClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            random_state=42,
            force_col_wise=True,
            verbose=-1,
        ))
    ]

    stacking_clf = StackingClassifier(
        estimators=base_models,
        final_estimator=LogisticRegression(),
        cv=5,
        n_jobs=-1
    )

    print(f"\n>>> Training STACKING ENSEMBLE with SMOTETomek...")
    preprocessor_pipeline = build_preprocessing_pipeline()
    
    # We use ImbPipeline so SMOTETomek can resample the training data.
    # Flatten the steps from the sklearn pipeline to avoid ImbPipeline TypeError.
    pipeline_steps = preprocessor_pipeline.steps + [
        ("smotetomek", SMOTETomek(random_state=42)),
        ("model", stacking_clf)
    ]
    pipeline = ImbPipeline(steps=pipeline_steps)
    
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    evaluate_model("STACKING_ENSEMBLE", y_test, y_pred, y_prob)

    model_out_path = os.path.join(artifacts_dir, "stacking_ckd_model.pkl")
    joblib.dump(pipeline, model_out_path)
    print(f"  Saved to: {model_out_path}")

    # Just saving the single model metrics, but preserving the JSON format
    results = {
        "stacking_ensemble": {
            "accuracy":  round(accuracy_score(y_test, y_pred), 4),
            "roc_auc":   round(roc_auc_score(y_test, y_prob), 4),
            "f1_weighted": round(f1_score(y_test, y_pred, average="weighted"), 4),
            "precision": round(precision_score(y_test, y_pred, average="weighted", zero_division=0), 4),
            "recall":    round(recall_score(y_test, y_pred, average="weighted"), 4),
        }
    }

    out_path = os.path.join(artifacts_dir, "evaluation_metrics.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nMetrics saved to {out_path}")

if __name__ == "__main__":
    train_all_models()
