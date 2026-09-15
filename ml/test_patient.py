"""
test_patient.py
---------------
Loads a real patient from the cleaned dataset and runs them through the entire
framework (Detection -> Progression -> SHAP -> Rules).
"""

import os
import json
import pandas as pd
from pprint import pprint

from models.ckd_detection.predict import predict
from models.progression.progression_model import predict_progression
from explainability.shap_explainer import CKDExplainer
from models.recommendation.rules import generate_recommendations

def test_real_patient():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "data", "processed", "ckd_cleaned.csv")
    
    df = pd.read_csv(data_path)
    
    # Pick a high-risk patient (someone who actually has CKD)
    ckd_patients = df[df["target"] == 1]
    
    # Let's pick a specific patient with clear markers (e.g., high BUN)
    patient_row = ckd_patients.sort_values(by="blood_urea_nitrogen", ascending=False).iloc[5]
    
    # Convert to dict
    patient_dict = patient_row.drop("target").to_dict()
    
    print("\n" + "="*60)
    print("  PATIENT PROFILE (from actual dataset)")
    print("="*60)
    # Print a few key features
    print(f"Age: {patient_dict.get('age')} | Gender: {patient_dict.get('gender')}")
    print(f"BUN: {patient_dict.get('blood_urea_nitrogen')} | Uric Acid: {patient_dict.get('uric_acid')}")
    print(f"Systolic BP: {patient_dict.get('bp_systolic')} | BMI: {patient_dict.get('bmi')}")
    
    print("\n" + "="*60)
    print("  1. EARLY DETECTION (Stacking Meta-Model)")
    print("="*60)
    detection_result = predict(patient_dict)
    print(json.dumps(detection_result, indent=2))
    
    print("\n" + "="*60)
    print("  2. DISEASE PROGRESSION PREDICTION")
    print("="*60)
    if detection_result["prediction"] == "ckd":
        progression_result = predict_progression(patient_dict)
        print(f"Predicted Stage: {progression_result['predicted_stage']}")
        print(f"Probabilities: {json.dumps(progression_result['stage_probabilities'], indent=2)}")
    else:
        print("Patient not predicted to have CKD. Skipping progression.")
        progression_result = None
        
    print("\n" + "="*60)
    print("  3. SHAP EXPLAINABILITY")
    print("="*60)
    explainer = CKDExplainer("stacking")
    shap_result = explainer.explain(patient_dict, top_k=5)
    for idx, feat in enumerate(shap_result["top_contributing_features"], 1):
        direction = "[+] Increases Risk" if feat["direction"] == "increases_risk" else "[-] Decreases Risk"
        print(f"{idx}. {feat['feature_name']:<25} ({direction})  SHAP: {feat['shap_value']:.4f}")
        
    print("\n" + "="*60)
    print("  4. CLINICAL RECOMMENDATIONS")
    print("="*60)
    risk_profile = {
        "risk_level": "HIGH" if detection_result["confidence"] == "HIGH" else "MODERATE",
        "predicted_stage": progression_result["predicted_stage"] if progression_result else None
    }
    rules = generate_recommendations(patient_dict, risk_profile)
    
    for r in rules:
        prio = r["priority"].upper()
        print(f"[{prio}] {r['category']}: {r['recommendation']}")
        print(f"      Reason: {r.get('reason', '')}\n")

if __name__ == "__main__":
    test_real_patient()
