"""
optuna_tuning.py
-----------------
Hyperparameter tuning using Optuna for XGBoost, CatBoost, and LightGBM.

Objective: Maximize ROC-AUC on stratified 5-fold cross-validation.
Optimizing for AUC directly improves probability calibration, which
reduces borderline predictions (models become more decisive).

After tuning, each model is retrained on the full training set with the
best found hyperparameters and saved over the existing .pkl artifacts.

Run: python -m evaluation.optuna_tuning
     python -m evaluation.optuna_tuning --trials 30   (faster)
     python -m evaluation.optuna_tuning --trials 100  (thorough)
"""

import argparse
import json
import os
import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, classification_report, f1_score

import xgboost as xgb
from catboost import CatBoostClassifier
import lightgbm as lgb

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.pipeline import build_preprocessing_pipeline, ALL_FEATURES

# ─── Config ───────────────────────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA     = os.path.join(BASE, "data", "processed", "ckd_cleaned.csv")
ART_DIR  = os.path.join(BASE, "artifacts")
CV       = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# ─── Data ─────────────────────────────────────────────────────────────────────
def load_data():
    df = pd.read_csv(DATA)
    X  = df[ALL_FEATURES]
    y  = df["target"]
    return train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# ─── Objective functions ───────────────────────────────────────────────────────

def objective_xgboost(trial, X_train, y_train, preprocessor):
    params = {
        "n_estimators":      trial.suggest_int("n_estimators", 100, 600),
        "max_depth":         trial.suggest_int("max_depth", 3, 9),
        "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "gamma":             trial.suggest_float("gamma", 0.0, 5.0),
        "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 2.0),
        "reg_lambda":        trial.suggest_float("reg_lambda", 0.5, 5.0),
        "min_child_weight":  trial.suggest_int("min_child_weight", 1, 10),
        "eval_metric":       "logloss",
        "random_state":      42,
    }
    # Compute scale_pos_weight from training data
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    params["scale_pos_weight"] = neg / pos

    clf = xgb.XGBClassifier(**params)
    pipeline = Pipeline([("pre", preprocessor), ("clf", clf)])
    scores = cross_val_score(pipeline, X_train, y_train,
                             cv=CV, scoring="roc_auc", n_jobs=-1)
    return scores.mean()


def objective_catboost(trial, X_train, y_train, preprocessor):
    params = {
        "iterations":        trial.suggest_int("iterations", 100, 600),
        "depth":             trial.suggest_int("depth", 3, 9),
        "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "l2_leaf_reg":       trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 1.0),
        "random_strength":   trial.suggest_float("random_strength", 0.0, 2.0),
        "border_count":      trial.suggest_int("border_count", 32, 255),
        "auto_class_weights": "Balanced",
        "verbose":           0,
        "random_state":      42,
    }
    clf = CatBoostClassifier(**params)
    pipeline = Pipeline([("pre", preprocessor), ("clf", clf)])
    scores = cross_val_score(pipeline, X_train, y_train,
                             cv=CV, scoring="roc_auc", n_jobs=1)
    return scores.mean()


def objective_lightgbm(trial, X_train, y_train, preprocessor):
    params = {
        "n_estimators":      trial.suggest_int("n_estimators", 100, 600),
        "max_depth":         trial.suggest_int("max_depth", 3, 9),
        "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "num_leaves":        trial.suggest_int("num_leaves", 20, 150),
        "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 2.0),
        "reg_lambda":        trial.suggest_float("reg_lambda", 0.0, 5.0),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
        "is_unbalance":      True,
        "force_col_wise":    True,
        "verbose":           -1,
        "random_state":      42,
    }
    clf = lgb.LGBMClassifier(**params)
    pipeline = Pipeline([("pre", preprocessor), ("clf", clf)])
    scores = cross_val_score(pipeline, X_train, y_train,
                             cv=CV, scoring="roc_auc", n_jobs=-1)
    return scores.mean()


# ─── Tune one model ────────────────────────────────────────────────────────────

def tune_model(name, objective_fn, clf_class, X_train, y_train, X_test, y_test,
               n_trials, best_params_extra=None):
    print(f"\n{'='*55}")
    print(f"  Tuning {name.upper()} ({n_trials} trials)...")
    print(f"{'='*55}")

    preprocessor = build_preprocessing_pipeline()

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(lambda t: objective_fn(t, X_train, y_train, preprocessor),
                   n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    print(f"  Best CV ROC-AUC : {study.best_value:.4f}")
    print(f"  Best params     : {json.dumps(best, indent=4)}")

    # Retrain on full train set with best params
    if best_params_extra:
        best.update(best_params_extra)

    clf = clf_class(**best)
    final_pipeline = Pipeline([
        ("preprocess", build_preprocessing_pipeline()),
        ("model", clf)
    ])
    final_pipeline.fit(X_train, y_train)

    y_pred = final_pipeline.predict(X_test)
    y_prob = final_pipeline.predict_proba(X_test)[:, 1]
    test_auc = roc_auc_score(y_test, y_prob)

    print(f"\n  Test Set ROC-AUC: {test_auc:.4f}")
    print(f"  Test F1 (wtd)   : {f1_score(y_test, y_pred, average='weighted'):.4f}")
    print(classification_report(y_test, y_pred,
                                target_names=["No CKD", "CKD"],
                                zero_division=0))

    # Check borderline improvement
    borderline = ((y_prob >= 0.40) & (y_prob <= 0.60)).sum()
    print(f"  Borderline (0.40-0.60): {borderline}/{len(y_test)} "
          f"({borderline/len(y_test)*100:.1f}%)")

    # Save model
    model_path = os.path.join(ART_DIR, f"{name}_ckd_model.pkl")
    joblib.dump(final_pipeline, model_path)
    print(f"  Saved tuned model to: {model_path}")

    return {
        "best_cv_auc": round(study.best_value, 4),
        "test_auc":    round(test_auc, 4),
        "best_params": best,
        "borderline_pct": round(borderline / len(y_test) * 100, 1)
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(n_trials=50):
    print(f"\n{'='*55}")
    print("  OPTUNA HYPERPARAMETER TUNING — CKD FRAMEWORK")
    print(f"  Trials per model: {n_trials}")
    print(f"{'='*55}")

    X_train, X_test, y_train, y_test = load_data()
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    spw = round(neg / pos, 4)

    all_results = {}

    # ── XGBoost ────────────────────────────────────────────────────────────────
    all_results["xgboost"] = tune_model(
        "xgboost",
        objective_xgboost,
        xgb.XGBClassifier,
        X_train, y_train, X_test, y_test,
        n_trials=n_trials,
        best_params_extra={"scale_pos_weight": spw, "eval_metric": "logloss",
                           "random_state": 42}
    )

    # ── CatBoost ───────────────────────────────────────────────────────────────
    all_results["catboost"] = tune_model(
        "catboost",
        objective_catboost,
        CatBoostClassifier,
        X_train, y_train, X_test, y_test,
        n_trials=n_trials,
        best_params_extra={"auto_class_weights": "Balanced", "verbose": 0,
                           "random_state": 42}
    )

    # ── LightGBM ───────────────────────────────────────────────────────────────
    all_results["lightgbm"] = tune_model(
        "lightgbm",
        objective_lightgbm,
        lgb.LGBMClassifier,
        X_train, y_train, X_test, y_test,
        n_trials=n_trials,
        best_params_extra={"is_unbalance": True, "force_col_wise": True,
                           "verbose": -1, "random_state": 42}
    )

    # ── Save tuning results ────────────────────────────────────────────────────
    tuning_path = os.path.join(ART_DIR, "optuna_tuning_results.json")
    with open(tuning_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull tuning results saved to: {tuning_path}")

    # ── Update evaluation_metrics.json ────────────────────────────────────────
    metrics_path = os.path.join(ART_DIR, "evaluation_metrics.json")
    with open(metrics_path) as f:
        metrics = json.load(f)
    for m in ["xgboost", "catboost", "lightgbm"]:
        metrics[m]["roc_auc"] = all_results[m]["test_auc"]
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # ── Re-run threshold optimization ──────────────────────────────────────────
    print("\nRe-running threshold optimization with tuned models...")
    from evaluation.tune_threshold import run_tuning
    run_tuning()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("  TUNING SUMMARY")
    print(f"{'='*55}")
    for m, r in all_results.items():
        print(f"  {m.upper():<12} CV-AUC={r['best_cv_auc']:.4f}  "
              f"Test-AUC={r['test_auc']:.4f}  "
              f"Borderline={r['borderline_pct']}%")
    print(f"{'='*55}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=50,
                        help="Number of Optuna trials per model (default: 50)")
    args = parser.parse_args()
    main(n_trials=args.trials)
