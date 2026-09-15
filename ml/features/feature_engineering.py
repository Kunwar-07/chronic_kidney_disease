"""
feature_engineering.py
-----------------------
Creates interpretable composite risk features on top of the raw NHANES columns.

These engineered features:
  - Improve model interpretability for clinical explainability
  - Encode domain knowledge about CKD risk thresholds
  - Provide cleaner SHAP feature names for clinician-facing outputs

Usage:
    from features.feature_engineering import engineer_features
    df_enriched = engineer_features(df_cleaned)
"""

import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds composite clinical risk features to a cleaned NHANES DataFrame.
    Input df should already have the NHANES columns (post-cleaning).
    Returns the df with additional engineered columns.
    """
    df = df.copy()

    # ── 1. Hypertension Flag ──────────────────────────────────────────────────
    # JNC 8 / ACC-AHA guideline: Stage 1 HTN = systolic >= 130
    if "bp_systolic" in df.columns:
        df["hypertension_flag"] = (df["bp_systolic"] >= 130).astype(float)

    # ── 2. Obesity Flag ───────────────────────────────────────────────────────
    if "bmi" in df.columns:
        df["obesity_flag"] = (df["bmi"] >= 30).astype(float)

    # ── 3. Age Group (ordinal) ────────────────────────────────────────────────
    # CDC risk grouping: 18-44 = 0, 45-64 = 1, 65+ = 2
    if "age" in df.columns:
        df["age_group"] = pd.cut(
            df["age"],
            bins=[0, 44, 64, 999],
            labels=[0, 1, 2]
        ).astype(float)

    # ── 4. Elevated BUN Flag ──────────────────────────────────────────────────
    # Normal adult BUN: 7-20 mg/dL
    if "blood_urea_nitrogen" in df.columns:
        df["elevated_bun_flag"] = (df["blood_urea_nitrogen"] > 20).astype(float)

    # ── 5. Hyperuricemia Flag ─────────────────────────────────────────────────
    # Normal: < 7 mg/dL (men), < 6 mg/dL (women). Using 7 as general threshold.
    if "uric_acid" in df.columns:
        df["hyperuricemia_flag"] = (df["uric_acid"] > 7).astype(float)

    # ── 6. Low Bicarbonate Flag ───────────────────────────────────────────────
    # Normal: 22-29 mEq/L. Low bicarbonate suggests metabolic acidosis (CKD sign)
    if "bicarbonate" in df.columns:
        df["low_bicarbonate_flag"] = (df["bicarbonate"] < 22).astype(float)

    # ── 7. Hypoalbuminemia Flag ───────────────────────────────────────────────
    # Normal serum albumin: >= 3.5 g/dL
    if "albumin_serum" in df.columns:
        df["hypoalbuminemia_flag"] = (df["albumin_serum"] < 3.5).astype(float)

    # ── 8. Metabolic Risk Score ───────────────────────────────────────────────
    # Count of risk flags (0–5 scale), higher = more systemic metabolic burden
    flag_cols = [
        "hypertension_flag", "obesity_flag",
        "elevated_bun_flag", "hyperuricemia_flag", "low_bicarbonate_flag"
    ]
    available_flags = [c for c in flag_cols if c in df.columns]
    if available_flags:
        df["metabolic_risk_score"] = df[available_flags].sum(axis=1)

    return df


ENGINEERED_NUMERIC = [
    "hypertension_flag", "obesity_flag", "age_group",
    "elevated_bun_flag", "hyperuricemia_flag", "low_bicarbonate_flag",
    "hypoalbuminemia_flag", "metabolic_risk_score"
]


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "processed", "ckd_cleaned.csv")

    df = pd.read_csv(data_path)
    df_enriched = engineer_features(df)

    new_cols = [c for c in ENGINEERED_NUMERIC if c in df_enriched.columns]
    print("Engineered features added:")
    for col in new_cols:
        non_null = df_enriched[col].notna().sum()
        print(f"  {col}: {non_null:,} non-null values")

    print("\nMetabolic risk score distribution:")
    print(df_enriched["metabolic_risk_score"].value_counts().sort_index())

    print("\nCKD rate by metabolic risk score:")
    print(df_enriched.groupby("metabolic_risk_score")["target"].mean().round(3))
