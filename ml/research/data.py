"""Auditable NHANES joins, units, outcome definition and eligibility."""
import numpy as np
import pandas as pd
from .acquire import BASE, CYCLES, COMPONENTS
from .schema import FIELDS, TASKS, FORBIDDEN

def egfr_2021(age, sex, creatinine):
    """CKD-EPI 2021 creatinine equation; age years, sex 0 female/1 male, Scr mg/dL."""
    k = np.where(sex == 0, 0.7, 0.9)
    alpha = np.where(sex == 0, -0.241, -0.302)
    ratio = creatinine / k
    return 142 * np.minimum(ratio, 1)**alpha * np.maximum(ratio, 1)**-1.2 * 0.9938**age * np.where(sex == 0, 1.012, 1)

def validate_ids(df):
    if "participant_id" not in df or df.participant_id.isna().any() or df.participant_id.duplicated().any():
        raise ValueError("Missing or repeated participant identifier; longitudinal data requires a group-aware protocol")

def validate_features(df, task):
    columns = TASKS[task]
    if set(columns) & FORBIDDEN:
        raise ValueError("Label leakage in feature schema")
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing schema columns: {sorted(missing)}")
    x = df[columns].copy()
    invalid = {}
    for name in columns:
        field = FIELDS[name]
        values = pd.to_numeric(x[name], errors="coerce")
        bad = x[name].notna() & values.isna()
        if "choices" in field:
            bad |= values.notna() & ~values.isin([float(k) for k in field["choices"]])
        else:
            bad |= values.notna() & ~values.between(field["min"], field["max"])
        invalid[name] = int(bad.sum())
        x[name] = values.mask(bad)
    return x, invalid

def load_official(cycle="2021-2023"):
    _, suffix = CYCLES[cycle]
    directory = BASE / "data/raw/official" / cycle
    frames, components = [], []
    for component in COMPONENTS:
        path = directory / f"{component}_{suffix}.xpt"
        frame = pd.read_sas(path, format="xport", encoding=None)
        if frame.SEQN.isna().any() or frame.SEQN.duplicated().any():
            raise ValueError(f"Invalid SEQN in {path}")
        components.append({"file": path.name, "rows": len(frame), "columns": len(frame.columns), "unique_participants": int(frame.SEQN.nunique())})
        frames.append(frame.set_index("SEQN"))
    merged = frames[0]
    for frame in frames[1:]:
        extra = [c for c in frame if c not in merged]
        merged = merged.join(frame[extra], how="left", validate="one_to_one")
    columns = {"RIDAGEYR": "age", "BMXBMI": "bmi", "INDFMPIR": "poverty_income_ratio", "LBXSCR": "serum_creatinine", "LBXSBU": "blood_urea_nitrogen", "LBXSAL": "albumin_serum", "LBXSPH": "phosphorus", "LBXSC3SI": "bicarbonate", "LBXSCA": "calcium", "LBXSUA": "uric_acid", "URXUMA": "urine_albumin", "URXUCR": "urine_creatinine", "RIDRETH3": "ethnicity", "SDMVSTRA": "stratum", "SDMVPSU": "psu"}
    df = merged[list(columns)].rename(columns=columns).copy()
    df["participant_id"] = cycle + ":" + merged.index.astype(int).astype(str)
    df["sex"] = merged.RIAGENDR.map({1: 1, 2: 0})
    df["diabetes"] = merged.DIQ010.map({1: 1, 2: 0})
    df["ever_smoked"] = merged.SMQ020.map({1: 1, 2: 0})
    for kind, dest in [("SY", "bp_systolic"), ("DI", "bp_diastolic")]:
        df[dest] = merged[[f"BPXO{kind}{i}" for i in (1, 2, 3)]].replace(0, np.nan).mean(axis=1)
    df["survey_weight"] = merged["WTPH2YR" if suffix == "L" else "WTMEC2YR"]
    # Earlier-cycle evaluation is a dataset-shift stress test, not pooled training.
    # Preserve published assays; evaluate separately with explicit method differences.
    df["uacr"] = df.urine_albumin / df.urine_creatinine * 100
    valid = (df.age >= 18) & df.sex.notna() & (df.serum_creatinine > 0) & (df.urine_creatinine > 0) & (df.urine_albumin >= 0)
    df["egfr"] = egfr_2021(df.age, df.sex, df.serum_creatinine.where(df.serum_creatinine > 0))
    df["target"] = np.where(valid, ((df.egfr < 60) | (df.uacr >= 30)).astype(int), np.nan)
    audit = {"cycle": cycle, "components": components, "merged_rows": len(df), "adults": int((df.age >= 18).sum()), "eligible_rows": int(valid.sum()), "excluded_without_complete_adult_outcome": int((~valid).sum()), "weight": "WTPH2YR" if suffix == "L" else "WTMEC2YR", "longitudinal": False}
    eligible = df.loc[valid].reset_index(drop=True)
    validate_ids(eligible)
    x, invalid = validate_features(eligible, "biomarker")
    eligible[x.columns] = x
    audit.update({"positive": int(eligible.target.sum()), "negative": int((eligible.target == 0).sum()), "missing": eligible.isna().sum().astype(int).to_dict(), "invalid_to_missing": invalid, "duplicates": int(eligible.duplicated().sum())})
    return eligible, audit
