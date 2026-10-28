"""
rules.py
--------
Deterministic, rule-based clinical decision-support recommendations.
Updated to use NHANES dataset feature names.

Deliberately NOT an LLM or black-box model: recommendations must be
traceable to an explicit rule for clinical safety and auditability.
Every recommendation is phrased as a suggestion for clinician review,
never as an autonomous instruction or diagnosis.
"""

from typing import List, Dict


def generate_recommendations(patient: dict, prediction: dict) -> List[Dict]:
    recs = []
    risk_level = prediction.get("risk_level", "LOW")

    def add(category, text, priority):
        recs.append({"category": category, "recommendation": text, "priority": priority})

    # --- Risk-level driven ---
    if risk_level == "HIGH":
        add("Specialist Referral",
            "Consider nephrology referral for further evaluation, subject to clinician judgment.",
            "high")
    elif risk_level == "MODERATE":
        add("Laboratory Follow-up",
            "Consider repeating renal function panel (BUN, blood urea nitrogen, creatinine) to confirm trend.",
            "medium")

    # --- Blood Pressure ---
    bp_sys = patient.get("bp_systolic")
    if bp_sys is not None and bp_sys >= 140:
        add("Monitoring", "Stage 2 hypertension detected (systolic >= 140 mmHg); sustained elevation is a primary CKD risk factor.", "high")
    elif bp_sys is not None and bp_sys >= 130:
        add("Monitoring", "Stage 1 hypertension detected (systolic >= 130 mmHg); monitor and review antihypertensive management.", "medium")

    # --- Blood Urea Nitrogen ---
    bun = patient.get("blood_urea_nitrogen")
    if bun is not None and bun > 20:
        add("Laboratory Follow-up", f"Elevated Blood Urea Nitrogen ({bun} mg/dL); consider renal function follow-up.", "high")

    # --- BMI ---
    bmi = patient.get("bmi")
    if bmi is not None and bmi >= 30:
        add("Lifestyle", f"Obesity detected (BMI {bmi:.1f}); weight management reduces CKD progression risk.", "medium")

    # --- Diabetes ---
    if str(patient.get("diabetes_diagnosed", "2.0")) == "1.0":
        add("Monitoring", "Diabetes diagnosed; ensure glycemic control is reviewed as part of renal risk management.", "high")

    # --- Uric Acid ---
    uric = patient.get("uric_acid")
    if uric is not None and uric > 7:
        add("Laboratory Follow-up", f"Elevated uric acid ({uric} mg/dL); hyperuricemia is associated with CKD progression.", "medium")

    # --- Albumin Serum ---
    alb = patient.get("albumin_serum")
    if alb is not None and alb < 3.5:
        add("Laboratory Follow-up", f"Low serum albumin ({alb} g/dL); may indicate protein loss — review nutritional and renal status.", "medium")

    # --- Bicarbonate ---
    bicarb = patient.get("bicarbonate")
    if bicarb is not None and bicarb < 22:
        add("Monitoring", f"Low bicarbonate ({bicarb} mEq/L); may indicate metabolic acidosis associated with CKD.", "medium")

    # --- Phosphorus ---
    phos = patient.get("phosphorus")
    if phos is not None and phos > 4.5:
        add("Lifestyle", f"Elevated phosphorus ({phos} mg/dL); consider dietary phosphorus restriction review.", "low")

    # --- Smoking ---
    if str(patient.get("current_smoker", "2.0")) == "1.0":
        add("Lifestyle", "Current smoker; smoking cessation is strongly recommended as it accelerates CKD progression.", "medium")

    if not recs:
        add("Monitoring", "No specific risk factors flagged; continue routine annual monitoring.", "low")

    return recs


if __name__ == "__main__":
    import json
    patient = {
        "bp_systolic": 145, "bp_diastolic": 92, "bmi": 33.5,
        "blood_urea_nitrogen": 28, "uric_acid": 8.1, "albumin_serum": 3.2,
        "bicarbonate": 20, "phosphorus": 5.0,
        "diabetes_diagnosed": "1.0", "current_smoker": "1.0"
    }
    prediction = {"risk_level": "HIGH"}
    print(json.dumps(generate_recommendations(patient, prediction), indent=2))
