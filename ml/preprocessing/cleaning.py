"""
cleaning.py
-----------
Cleans the raw NHANES Chronic Kidney Disease dataset (2021-2023).

Key design decisions:
- Filter to ADULTS only (age >= 18). Children under 18 have incomplete lab
  panels and are coded ckd_present=1 with stage='Unknown', inflating the
  positive class artificially.
- Drop 'Unknown' stage rows that have NO numeric lab values at all. These
  are data artefacts, not genuine CKD cases.
- Drop direct diagnostic columns (egfr, albumin_creatinine_ratio,
  serum_creatinine, urine_albumin) to prevent data leakage and build a
  genuine EARLY WARNING predictor rather than a formula replicator.
"""

import pandas as pd
import numpy as np
import os

NUMERIC_COLS = [
    "age", "poverty_income_ratio", "bmi", "weight_kg", "height_cm",
    "bp_systolic", "bp_diastolic", "blood_urea_nitrogen",
    "albumin_serum", "phosphorus", "bicarbonate", "calcium", "uric_acid",
    "urine_creatinine"
]

CATEGORICAL_COLS = [
    "gender", "ethnicity", "education_level", "diabetes_diagnosed",
    "insulin_use", "diabetes_pills", "ever_smoked", "current_smoker"
]

# Drop: ID, leakage columns (used to compute eGFR/ACR which define CKD), and ckd_stage
DROP_COLS = [
    "participant_id", "ckd_stage",
    "egfr", "albumin_creatinine_ratio", "urine_albumin", "serum_creatinine"
]

TARGET_COL = "ckd_present"

# Lab columns used to detect artefact rows (all-NaN => not a real clinical record)
LAB_COLS = [
    "blood_urea_nitrogen", "albumin_serum", "phosphorus",
    "bicarbonate", "calcium", "uric_acid", "bp_systolic", "bp_diastolic"
]


def load_raw(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── 1. Drop leakage + ID columns ─────────────────────────────────────────
    for col in DROP_COLS:
        if col in df.columns:
            df = df.drop(columns=[col])

    # ── 2. Filter: adults only (age >= 18) ───────────────────────────────────
    if "age" in df.columns:
        df = df[df["age"] >= 18].copy()

    # ── 3. Drop artefact rows: CKD=1 with ALL lab values missing ─────────────
    # These are "Unknown" stage rows with no clinical measurements — not true CKD
    available_labs = [c for c in LAB_COLS if c in df.columns]
    if available_labs and TARGET_COL in df.columns:
        all_labs_null = df[available_labs].isnull().all(axis=1)
        artefact_mask = all_labs_null & (df[TARGET_COL] == 1)
        n_dropped = artefact_mask.sum()
        df = df[~artefact_mask].copy()
        print(f"  Dropped {n_dropped} artefact rows (CKD=1 with no lab values)")

    # ── 4. Type-cast columns ──────────────────────────────────────────────────
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": np.nan, "None": np.nan})

    # ── 5. Drop rows where target is missing ─────────────────────────────────
    if TARGET_COL in df.columns:
        df = df.dropna(subset=[TARGET_COL])
        df[TARGET_COL] = df[TARGET_COL].astype(int)

    # ── 6. Outlier removal using IsolationForest (2% contamination) ─────────
    # Temporarily impute NaNs with median just to run the IsolationForest
    from sklearn.ensemble import IsolationForest
    
    available_num = [c for c in NUMERIC_COLS if c in df.columns]
    num_df = df[available_num].copy()
    
    # Simple median imputation for IsolationForest
    for col in num_df.columns:
        num_df[col] = num_df[col].fillna(num_df[col].median())
    
    iso = IsolationForest(contamination=0.02, random_state=42)
    outlier_preds = iso.fit_predict(num_df)
    
    n_outliers = (outlier_preds == -1).sum()
    df = df[outlier_preds == 1].copy()
    print(f"  Dropped {n_outliers} outliers using IsolationForest")

    # ── 7. Rename target ──────────────────────────────────────────────────────
    df = df.rename(columns={TARGET_COL: "target"})
    df = df.reset_index(drop=True)
    return df


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_path = os.path.join(base_dir, "data", "raw", "CKD_NHANES_2021_2023.csv")
    out_path = os.path.join(base_dir, "data", "processed", "ckd_cleaned.csv")

    raw = load_raw(raw_path)
    print(f"Raw dataset: {raw.shape[0]:,} rows")
    cleaned = clean(raw)

    print(f"\nCleaned dataset shape: {cleaned.shape}")
    print("\nTarget distribution:")
    vc = cleaned["target"].value_counts()
    for label, count in vc.items():
        pct = count / len(cleaned) * 100
        print(f"  {'CKD' if label == 1 else 'No CKD'}: {count:,} ({pct:.1f}%)")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cleaned.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")
