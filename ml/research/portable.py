"""Export fitted preprocessing and model parameters for the shared local JS runtime."""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

def export_pipeline(pipeline):
    pre = pipeline.named_steps["preprocess"]
    fields = []
    for kind, pipe, columns in pre.transformers_:
        if kind == "remainder":
            continue
        imputer = pipe.named_steps["imputer"]
        for i, name in enumerate(columns):
            item = {"name": name, "impute": float(imputer.statistics_[i])}
            if kind == "numeric":
                scaler = pipe.named_steps["scale"]
                item.update({"kind": "numeric", "mean": float(scaler.mean_[i]), "scale": float(scaler.scale_[i])})
            else:
                item.update({"kind": "categorical", "categories": pipe.named_steps["encode"].categories_[i].tolist()})
            fields.append(item)
    model = pipeline.named_steps["model"]
    if isinstance(model, LogisticRegression):
        exported = {"kind": "linear", "intercept": float(model.intercept_[0]), "coefficients": model.coef_[0].tolist()}
    elif isinstance(model, RandomForestClassifier):
        trees = []
        for estimator in model.estimators_:
            tree = estimator.tree_
            values = tree.value[:, 0, :]
            probability = values[:, 1] / values.sum(axis=1)
            trees.append({"left": tree.children_left.tolist(), "right": tree.children_right.tolist(), "feature": tree.feature.tolist(), "threshold": tree.threshold.tolist(), "value": probability.tolist()})
        exported = {"kind": "forest", "trees": trees}
    elif isinstance(model, HistGradientBoostingClassifier):
        trees = []
        for iteration in model._predictors:
            nodes = iteration[0].nodes
            trees.append({"left": nodes["left"].astype(int).tolist(), "right": nodes["right"].astype(int).tolist(), "feature": nodes["feature_idx"].astype(int).tolist(), "threshold": nodes["num_threshold"].tolist(), "value": nodes["value"].tolist(), "leaf": nodes["is_leaf"].astype(int).tolist()})
        exported = {"kind": "hist", "baseline": float(model._baseline_prediction[0, 0]), "trees": trees}
    else:
        raise TypeError(f"Unsupported portable model: {type(model)}")
    return {"preprocessing": fields, "estimator": exported}

def calibrated_probability(pipeline, calibrator, x):
    raw = np.clip(pipeline.predict_proba(x)[:, 1], 1e-7, 1 - 1e-7)
    return calibrator.predict_proba(np.log(raw / (1 - raw)).reshape(-1, 1))[:, 1]
