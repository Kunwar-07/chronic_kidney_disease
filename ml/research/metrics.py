"""Binary metrics and chart data, with explicit denominators and limitations."""
import numpy as np
from sklearn.metrics import (roc_auc_score, average_precision_score, confusion_matrix,
    brier_score_loss, roc_curve, precision_recall_curve)
from sklearn.calibration import calibration_curve

def ratio(a, b):
    return float(a / b) if b else None

def evaluate(y, p, threshold):
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    tn, fp, fn, tp = confusion_matrix(y, p >= threshold, labels=[0, 1]).ravel()
    sensitivity, specificity = ratio(tp, tp + fn), ratio(tn, tn + fp)
    return {"n": len(y), "positive": int(y.sum()), "negative": int(len(y) - y.sum()),
        "prevalence": float(y.mean()), "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        "average_precision": float(average_precision_score(y, p)) if y.sum() else None,
        "sensitivity": sensitivity, "specificity": specificity, "precision": ratio(tp, tp + fp),
        "npv": ratio(tn, tn + fn), "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "balanced_accuracy": (sensitivity + specificity) / 2 if sensitivity is not None and specificity is not None else None,
        "brier": float(brier_score_loss(y, p)), "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]], "threshold": float(threshold)}

def select_threshold(y, p, minimum_sensitivity=0.8):
    """Prespecified research criterion: maximum specificity at validation recall >= 0.80."""
    fpr, tpr, thresholds = roc_curve(y, p)
    eligible = np.flatnonzero((tpr >= minimum_sensitivity) & np.isfinite(thresholds))
    i = eligible[np.argmin(fpr[eligible])]
    return float(thresholds[i])

def curves(y, p):
    fpr, tpr, _ = roc_curve(y, p)
    precision, recall, _ = precision_recall_curve(y, p)
    observed, predicted = calibration_curve(y, p, n_bins=10, strategy="quantile")
    def points(x, y):
        idx = np.unique(np.linspace(0, len(x) - 1, min(len(x), 151)).astype(int))
        return [[float(x[i]), float(y[i])] for i in idx]
    return {"roc": points(fpr, tpr), "pr": points(recall, precision), "calibration": points(predicted, observed)}

def bootstrap(y, p, threshold, seed, repetitions=200):
    """Individual IID percentile intervals, NOT survey design or model-selection uncertainty."""
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    keys = ["roc_auc", "average_precision", "sensitivity", "specificity", "precision", "npv", "f1", "balanced_accuracy", "brier"]
    samples = {key: [] for key in keys}
    for _ in range(repetitions):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        result = evaluate(y[idx], p[idx], threshold)
        for key in keys:
            if result[key] is not None:
                samples[key].append(result[key])
    return {key: np.quantile(values, [0.025, 0.975]).tolist() for key, values in samples.items() if values}
