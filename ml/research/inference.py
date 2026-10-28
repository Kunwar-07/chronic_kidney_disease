"""Local Python inference; JSON input via stdin, no health-data logging or persistence."""
import argparse
import json
import sys
import joblib
import numpy as np
import pandas as pd
from .schema import FIELDS, TASKS, LABEL, LIMITATIONS, VERSION
from .portable import calibrated_probability

def predict(bundle, inputs):
    if bundle["version"] != VERSION:
        raise ValueError("Incompatible model version")
    features = TASKS[bundle["task"]]
    if features != bundle["features"]:
        raise ValueError("Feature schema mismatch")
    if set(inputs) - set(features):
        raise ValueError("Unexpected input features")
    values, quality = {}, []
    for name in features:
        value, field = inputs.get(name), FIELDS[name]
        if value is None:
            if field.get("required"):
                raise ValueError(f"Required: {name}")
            values[name] = np.nan
            quality.append({"feature": name, "state": "imputed"})
            continue
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value):
            raise ValueError(f"Invalid number: {name}")
        if "choices" in field:
            valid = value in [float(k) for k in field["choices"]]
        else:
            valid = field["min"] <= value <= field["max"]
        if not valid:
            raise ValueError(f"Outside supported range/category: {name}")
        values[name] = value
        quality.append({"feature": name, "state": "observed"})
    if sum(np.isfinite(v) for v in values.values()) < np.ceil(len(features) / 2):
        raise ValueError("At least half the inputs must be observed")
    if bundle["task"] == "biomarker" and sum(np.isfinite(values[c]) for c in features[8:]) < 2:
        raise ValueError("At least two secondary biomarkers are required")
    if values["bp_systolic"] <= values["bp_diastolic"]:
        raise ValueError("Systolic pressure must exceed diastolic pressure")
    probability = float(calibrated_probability(bundle["pipeline"], bundle["calibrator"], pd.DataFrame([values])[features])[0])
    return {"task": bundle["task"], "model_version": VERSION, "label": LABEL, "probability": probability, "threshold": bundle["threshold"], "quality": quality, "limitations": LIMITATIONS}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, help="Trusted local joblib artifact only")
    args = parser.parse_args()
    print(json.dumps(predict(joblib.load(args.artifact), json.load(sys.stdin)), allow_nan=False))
