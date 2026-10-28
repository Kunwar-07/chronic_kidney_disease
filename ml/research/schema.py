"""Single source of truth for training, inference and exported UI schema.

Bounds are broad input plausibility checks, not diagnostic/healthy ranges.
"""
VERSION = "ckd-research-v2.0"
SEED = 20261023
FIELDS = {
    "age": dict(label="Age", unit="years", min=18, max=80, required=True, group="Basic information", note="NHANES public age is top-coded at 80. This model supports ages 18–80 only."),
    "sex": dict(label="Sex recorded in survey", unit="", choices={"0": "Female", "1": "Male"}, required=True, group="Basic information", note="NHANES records binary sex; this limitation is inherited by the model."),
    "bmi": dict(label="Body mass index", unit="kg/m²", min=10, max=100, group="Measurements"),
    "bp_systolic": dict(label="Systolic blood pressure", unit="mmHg", min=50, max=300, group="Measurements"),
    "bp_diastolic": dict(label="Diastolic blood pressure", unit="mmHg", min=20, max=180, group="Measurements"),
    "diabetes": dict(label="Ever told you have diabetes", unit="", choices={"0": "No", "1": "Yes"}, group="Health history", note="Borderline, refused or unknown responses are treated as missing."),
    "ever_smoked": dict(label="Smoked at least 100 cigarettes", unit="", choices={"0": "No", "1": "Yes"}, group="Health history"),
    "poverty_income_ratio": dict(label="Family income-to-poverty ratio", unit="ratio", min=0, max=5, group="Optional context", note="US survey measure, top-coded at 5. Leave blank if unknown."),
    "blood_urea_nitrogen": dict(label="Blood urea nitrogen", unit="mg/dL", min=1, max=200, group="Secondary biomarkers"),
    "albumin_serum": dict(label="Serum albumin", unit="g/dL", min=0.5, max=7, group="Secondary biomarkers"),
    "phosphorus": dict(label="Phosphorus", unit="mg/dL", min=0.5, max=20, group="Secondary biomarkers"),
    "bicarbonate": dict(label="Bicarbonate", unit="mmol/L", min=5, max=50, group="Secondary biomarkers"),
    "calcium": dict(label="Total calcium", unit="mg/dL", min=3, max=20, group="Secondary biomarkers"),
    "uric_acid": dict(label="Uric acid", unit="mg/dL", min=0.1, max=30, group="Secondary biomarkers"),
}
SCREENING = list(FIELDS)[:8]
BIOMARKER = list(FIELDS)
TASKS = {"screening": SCREENING, "biomarker": BIOMARKER}
CATEGORICAL = ["sex", "diabetes", "ever_smoked"]
FORBIDDEN = {"target", "ckd_present", "ckd_stage", "egfr", "uacr", "serum_creatinine", "urine_albumin", "urine_creatinine", "albumin_creatinine_ratio", "participant_id"}
LABEL = "Single-visit reduced eGFR (<60 mL/min/1.73 m²) or elevated UACR (≥30 mg/g)"
LIMITATIONS = [
    "Research prototype, not a diagnosis or a clinically validated medical device.",
    "Cross-sectional, single-visit outcome; chronicity and future progression are not established.",
    "Age and sex are also terms of the eGFR equation defining part of the outcome; screening is not free of mathematical coupling.",
    "US NHANES adult sample with both kidney measurements available; complete-outcome selection can bias results.",
    "Training, calibration, evaluation and bootstrap intervals are unweighted; they do not estimate US population risk or complex-survey uncertainty.",
    "Missing inputs use training-only imputation. Marginal range checks do not establish that an input is in distribution.",
    "Model associations and hypothetical scenarios are not causal effects or treatment advice.",
]
