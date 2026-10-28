"""Reproduce v2 research: CV on training, separate calibration/validation, untouched test."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
import argparse
import hashlib
import json
import platform
import shutil
from pathlib import Path
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from .acquire import BASE
from .audit import audit_existing
from .data import load_official, validate_ids
from .metrics import evaluate, select_threshold, curves, bootstrap
from .schema import VERSION, SEED, FIELDS, TASKS, CATEGORICAL, LABEL, LIMITATIONS
from .portable import export_pipeline, calibrated_probability

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")

def split_cohort(df):
    validate_ids(df)
    trainval, test = train_test_split(np.arange(len(df)), test_size=.2, random_state=SEED, stratify=df.target)
    traincal, validation = train_test_split(trainval, test_size=.125, random_state=SEED + 1, stratify=df.target.iloc[trainval])
    train, calibration = train_test_split(traincal, test_size=1/7, random_state=SEED + 2, stratify=df.target.iloc[traincal])
    partitions = dict(train=train, calibration=calibration, validation=validation, test=test)
    assert len(set(np.concatenate(list(partitions.values())))) == len(df)
    return partitions

def preprocessing(features):
    numeric = [c for c in features if c not in CATEGORICAL]
    categorical = [c for c in features if c in CATEGORICAL]
    return ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True)), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent", keep_empty_features=True)), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical),
    ])

def candidates():
    return {
        "logistic": (LogisticRegression(max_iter=1500, random_state=SEED), {"model__C": [0.1, 1.0], "model__class_weight": [None, "balanced"]}),
        "forest": (RandomForestClassifier(n_estimators=160, max_depth=7, min_samples_leaf=12, n_jobs=2, random_state=SEED), {"model__max_depth": [5, 8], "model__class_weight": [None, "balanced"]}),
        "hist_gradient": (HistGradientBoostingClassifier(max_iter=160, learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=25, early_stopping=False, random_state=SEED), {"model__l2_regularization": [1., 5.]}),
    }

def run(output):
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}. Use --run-id for a new experiment.")
    output.mkdir(parents=True)
    audit_existing()
    df, audit = load_official()
    external = None
    if (BASE / "data/raw/official/2017-2018/SMQ_J.xpt").exists():
        external, external_audit = load_official("2017-2018")
    else:
        external_audit = {"status": "unavailable", "reason": "Earlier official components not downloaded"}
    parts = split_cohort(df)
    for key, idx in parts.items():
        if df.target.iloc[idx].nunique() < 2:
            raise ValueError(f"Only one class in {key}")
    split_report = {key: {"n": len(idx), "positive": int(df.target.iloc[idx].sum()), "negative": int((df.target.iloc[idx] == 0).sum())} for key, idx in parts.items()}
    # Participant IDs are preserved locally only, never exported to the public frontend.
    write_json(output / "splits.json", {key: df.participant_id.iloc[idx].tolist() for key, idx in parts.items()})
    manifests = {cycle: json.loads((BASE / f"data/raw/official/{cycle}/manifest.json").read_text()) for cycle in ["2021-2023", "2017-2018"] if (BASE / f"data/raw/official/{cycle}/manifest.json").exists()}
    dataset_hash = hashlib.sha256(json.dumps([f["sha256"] for f in manifests["2021-2023"]["files"]]).encode()).hexdigest()
    report = {"version": VERSION, "run_id": output.name, "created_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "dataset": "NHANES August 2021–August 2023", "dataset_hash": dataset_hash, "label": LABEL, "limitations": LIMITATIONS, "audit": audit, "external_audit": external_audit, "splits": split_report, "selection": "Highest validation average precision within each task; thresholds maximize specificity subject to validation sensitivity ≥0.80. Test and external data never select models or thresholds.", "calibration": "Logistic sigmoid fitted to clipped model log-odds on disjoint 10% calibration partition; this is empirical calibration, not clinical reliability.", "bootstrap": "200 IID participant percentile replicates, fixed model/threshold, not complex-survey intervals", "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__, "cpu_count": os.cpu_count(), "threads": 2}, "tasks": {}}
    for task, features in TASKS.items():
        x, y = df[features], df.target.astype(int)
        task_report = {"features": features, "models": [], "selected": None}
        trained = {}
        for name, (estimator, grid) in candidates().items():
            print(f"Training {task}/{name}", flush=True)
            pipe = Pipeline([("preprocess", preprocessing(features)), ("model", estimator)])
            search = GridSearchCV(pipe, grid, scoring="average_precision", cv=StratifiedKFold(3, shuffle=True, random_state=SEED), n_jobs=1, refit=True)
            search.fit(x.iloc[parts["train"]], y.iloc[parts["train"]])
            model = search.best_estimator_
            raw_cal = np.clip(model.predict_proba(x.iloc[parts["calibration"]])[:, 1], 1e-7, 1-1e-7)
            calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=SEED).fit(np.log(raw_cal / (1-raw_cal)).reshape(-1, 1), y.iloc[parts["calibration"]])
            vp = calibrated_probability(model, calibrator, x.iloc[parts["validation"]])
            threshold = select_threshold(y.iloc[parts["validation"]], vp)
            validation = evaluate(y.iloc[parts["validation"]], vp, threshold)
            task_report["models"].append({"id": name, "cv_average_precision": float(search.best_score_), "parameters": search.best_params_, "validation": validation})
            trained[name] = (model, calibrator, threshold)
        selected = max(task_report["models"], key=lambda item: item["validation"]["average_precision"])["id"]
        task_report["selected"] = selected
        # Selection locked before any test or external predictions below.
        for item in task_report["models"]:
            name = item["id"]
            model, calibrator, threshold = trained[name]
            xt, yt = x.iloc[parts["test"]], y.iloc[parts["test"]]
            probability = calibrated_probability(model, calibrator, xt)
            item["test"] = evaluate(yt, probability, threshold)
            item["test"]["ci95"] = bootstrap(yt, probability, threshold, SEED)
            item["test"]["uncalibrated_brier"] = evaluate(yt, model.predict_proba(xt)[:, 1], threshold)["brier"]
            item["curves"] = curves(yt, probability)
            if external is not None:
                ep = calibrated_probability(model, calibrator, external[features])
                item["external"] = evaluate(external.target, ep, threshold)
                item["external"]["context"] = "2017–2018 as-published assays; dataset-shift stress test, not harmonized external clinical validation"
                # Albumin assay sensitivity: map old urine albumin forward per CDC, never alter raw data.
                adjusted_uacr = 100 * (1.381 + .8407 * external.urine_albumin) / external.urine_creatinine
                adjusted_y = ((external.egfr < 60) | (adjusted_uacr >= 30)).astype(int)
                item["external_albumin_bridge"] = evaluate(adjusted_y, ep, threshold)
                item["external_albumin_bridge"]["changed_labels"] = int((adjusted_y != external.target).sum())
            joblib.dump({"pipeline": model, "calibrator": calibrator, "threshold": threshold, "features": features, "version": VERSION, "dataset_hash": dataset_hash, "task": task}, output / f"{task}-{name}.joblib")
            if name != selected:
                continue
            importance = permutation_importance(model, x.iloc[parts["validation"]], y.iloc[parts["validation"]], scoring="average_precision", n_repeats=5, random_state=SEED, n_jobs=1)
            task_report["importance"] = sorted([{"feature": c, "mean": float(m), "std": float(s)} for c, m, s in zip(features, importance.importances_mean, importance.importances_std)], key=lambda item: -item["mean"])
            task_report["importance_context"] = "Validation-set permutation decrease in uncalibrated average precision; correlated features share information. Not SHAP or causation."
            subgroups = []
            for column, masks in {"sex": {"Female": df.sex == 0, "Male": df.sex == 1}, "age": {"18–44": df.age < 45, "45–64": df.age.between(45, 64), "65–80": df.age >= 65}}.items():
                for label, mask in masks.items():
                    select = mask.iloc[parts["test"]].to_numpy()
                    if select.sum() >= 50 and yt.to_numpy()[select].sum() >= 10 and (1-yt.to_numpy()[select]).sum() >= 10:
                        subgroups.append({"group": label, "variable": column, **evaluate(yt.to_numpy()[select], probability[select], threshold)})
                    else:
                        subgroups.append({"group": label, "variable": column, "n": int(select.sum()), "status": "Suppressed: requires n≥50 and ≥10 per class"})
            task_report["subgroups"] = subgroups
            robustness = []
            for feature in ["bmi", "bp_systolic", "diabetes"]:
                altered = xt.copy()
                altered[feature] = np.nan
                delta = calibrated_probability(model, calibrator, altered) - probability
                robustness.append({"feature": feature, "mean_absolute_probability_change_when_missing": float(np.abs(delta).mean())})
            task_report["missingness_sensitivity"] = robustness
            altered = xt.copy()
            altered["bp_systolic"] = (altered.bp_systolic + 5).clip(upper=300)
            task_report["perturbation"] = {"scenario": "Systolic BP +5 mmHg, other inputs fixed; hypothetical noncausal stress test", "mean_absolute_probability_change": float(np.abs(calibrated_probability(model, calibrator, altered) - probability).mean())}
            portable = {"schema_version": 1, "version": VERSION, "run_id": output.name, "task": task, "model": selected, "features": features, "fields": {c: FIELDS[c] for c in features}, "label": LABEL, "limitations": LIMITATIONS, "threshold": threshold, "calibration": {"slope": float(calibrator.coef_[0, 0]), "intercept": float(calibrator.intercept_[0])}, "ranges": {c: {"min": float(x.iloc[parts["train"]][c].min()), "max": float(x.iloc[parts["train"]][c].max()), "p01": float(x.iloc[parts["train"]][c].quantile(.01)), "p99": float(x.iloc[parts["train"]][c].quantile(.99))} for c in features}, **export_pipeline(model)}
            write_json(output / f"{task}.json", portable)
            # Only aggregate/archetypal synthetic test inputs, never participant records, leave ML directory.
            medians = {c: float(x.iloc[parts["train"]][c].median()) for c in features}
            for c in CATEGORICAL:
                medians[c] = float(x.iloc[parts["train"]][c].mode().iloc[0])
            fixtures = [medians, {**medians, "age": 30, "bmi": 23, "sex": 0}, {**medians, "age": 75, "bp_systolic": 155, "sex": 1}, {**medians, "bmi": None, "diabetes": None}]
            expected = calibrated_probability(model, calibrator, pd.DataFrame(fixtures).astype(float)[features])
            write_json(output / f"{task}-parity.json", [{"input": row, "expected": float(p)} for row, p in zip(fixtures, expected)])
        report["tasks"][task] = task_report
    write_json(output / "report.json", report)
    write_json(output / "sources.json", manifests)
    public = BASE.parent / "frontend/data"
    public.mkdir(parents=True, exist_ok=True)
    for name in ["report.json", "sources.json", "screening.json", "biomarker.json", "screening-parity.json", "biomarker-parity.json"]:
        shutil.copyfile(output / name, public / name)
    for name in ["runtime.mjs", "contracts.d.ts"]:
        shutil.copyfile(BASE / "research" / name, public / name)
    write_json(BASE / "reports/research-v2.json", report)
    print(f"Complete: {output}\nSelected: " + str({k: v["selected"] for k, v in report["tasks"].items()}), flush=True)
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="nhanes-20261023")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Run ID must contain only letters, numbers, hyphens and underscores")
    run(BASE / "artifacts/research-v2" / args.run_id)
