"""
shap_explainer.py
------------------
Generates per-patient SHAP explanations for a CKD prediction using any of the 
three models (XGBoost, CatBoost, LightGBM).

Important distinction (surface this to clinicians/users):
A SHAP value tells you how much a feature pushed THIS MODEL's output for
THIS PATIENT, relative to the model's average output. It is a statement
about model behavior, not a proven causal clinical relationship.
"""

import joblib
import numpy as np
import pandas as pd
import shap
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.pipeline import ALL_FEATURES, get_feature_names


class CKDExplainer:
    def __init__(self, model_name: str = "stacking"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, "artifacts", f"{model_name}_ckd_model.pkl")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
            
        self.pipeline = joblib.load(model_path)
        
        # In ImbPipeline, everything before the resampler and model is preprocessing
        self.preprocessor = self.pipeline[:-2]
        self.model = self.pipeline.named_steps["model"]
        
        self.feature_names = get_feature_names(self.preprocessor)
            
        self.is_stacking = type(self.model).__name__ == "StackingClassifier"

        # Initialize explainers
        if self.is_stacking:
            self.explainers = [shap.TreeExplainer(est) for est in self.model.estimators_]
        else:
            self.explainers = [shap.TreeExplainer(self.model)]

    def _get_shap_values(self, explainer, X_transformed):
        shap_values = explainer.shap_values(X_transformed)
        if isinstance(shap_values, list):
            sv = shap_values[1][0]  # class 1 = CKD
        elif shap_values.ndim == 3:
            sv = shap_values[0, :, 1]
        elif shap_values.ndim == 2:
            sv = shap_values[0]
        else:
            sv = shap_values
        return sv

    def explain(self, patient: dict, top_k: int = 5) -> dict:
        """
        patient: dict of raw clinical feature values (same keys as ALL_FEATURES)
        Returns: dict with prediction, probability, and ranked feature contributions.
        """
        X = pd.DataFrame([patient])[ALL_FEATURES]
        X_transformed = self.preprocessor.transform(X)
        
        # Dense array if sparse
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()

        proba = self.pipeline.predict_proba(X)[0]
        pred = int(np.argmax(proba))

        all_sv = []
        for explainer in self.explainers:
            sv = self._get_shap_values(explainer, X_transformed)
            all_sv.append(sv)
            
        # Average SHAP values across base estimators
        avg_sv = np.mean(all_sv, axis=0)

        contributions = list(zip(self.feature_names, avg_sv, X_transformed[0]))
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)

        top_features = [
            {
                "feature_name": name,
                "shap_value": float(val),
                "direction": "increases_risk" if val > 0 else "decreases_risk",
            }
            for name, val, _ in contributions[:top_k]
        ]

        return {
            "prediction": "ckd" if pred == 1 else "notckd",
            "probability_ckd": float(proba[1]),
            "top_contributing_features": top_features,
            "disclaimer": (
                "These values show how each factor influenced THIS model's "
                "prediction. They reflect statistical association learned "
                "from data, not proven clinical causation, and should be "
                "reviewed by a clinician."
            ),
        }


if __name__ == "__main__":
    sample_patient = {
        "age": 65, "poverty_income_ratio": 1.5, "bmi": 32.4, "weight_kg": 95.0, 
        "height_cm": 172.0, "bp_systolic": 140, "bp_diastolic": 90, 
        "blood_urea_nitrogen": 25.0, 
        "albumin_serum": 3.8, "phosphorus": 4.5, "bicarbonate": 22.0, 
        "calcium": 9.2, "uric_acid": 6.8, "urine_creatinine": 100.0, 
        "gender": "Male", "ethnicity": "Non-Hispanic White", "education_level": "4.0",
        "diabetes_diagnosed": "1.0", "insulin_use": "2.0", "diabetes_pills": "1.0",
        "ever_smoked": "1.0", "current_smoker": "2.0"
    }

    print("=== SHAP Explanation for Stacking Ensemble ===")
    explainer = CKDExplainer("stacking")
    result = explainer.explain(sample_patient)
    import json
    print(json.dumps(result, indent=2))
