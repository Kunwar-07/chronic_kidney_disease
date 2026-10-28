"""Inventory original tabular data; never mutate source files."""
import hashlib
import csv
import io
import re
import json
from pathlib import Path
import pandas as pd
import numpy as np
from .acquire import BASE
from .data import egfr_2021

def audit_existing():
    results = []
    for path in sorted((BASE / "data").rglob("*")):
        if path.suffix.lower() not in {".csv", ".arff"} or "official" in path.parts:
            continue
        malformed = []
        normalized_trailing_empty = []
        if path.suffix == ".arff":
            text = path.read_text()
            rows = text.lower().split("@data", 1)[1].strip().splitlines()
            parsed = [line.split(",") for line in rows if line.strip() and not line.startswith("%")]
            for i, row in enumerate(parsed):
                if len(row) == 26 and not row[-1].strip():
                    normalized_trailing_empty.append(i + 1)
                    row.pop()
            malformed = [{"line": i + 1, "fields": len(row)} for i, row in enumerate(parsed) if len(row) != 25]
            df = pd.DataFrame([row for row in parsed if len(row) == 25])
            df.columns = re.findall(r"@attribute\s+'?([a-z_]+)'?\s", text, re.IGNORECASE)
        else:
            parsed = list(csv.reader(io.StringIO(path.read_text())))
            header = parsed[0]
            for i, row in enumerate(parsed[1:]):
                if len(row) == len(header) + 1 and not row[-1].strip():
                    normalized_trailing_empty.append(i + 2)
                    row.pop()
            malformed = [{"line": i + 2, "fields": len(row)} for i, row in enumerate(parsed[1:]) if len(row) != len(header)]
            df = pd.DataFrame([row for row in parsed[1:] if len(row) == len(header)], columns=header)
        df.columns = df.columns.str.strip("' ")
        df = df.map(lambda v: v.strip("\t '\r") if isinstance(v, str) else v).replace({"?": np.nan, "": np.nan})
        item = {"file": str(path.relative_to(BASE)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(df), "malformed_rows_excluded_from_audit_statistics": malformed, "total_source_rows": len(df) + len(malformed), "columns": len(df.columns), "feature_columns": list(df.columns), "missing": df.isna().sum().astype(int).to_dict(), "duplicates": int(df.duplicated().sum()), "longitudinal": False}
        item["trailing_empty_fields_normalized_for_audit_only"] = normalized_trailing_empty
        numeric_candidates = {"age", "bp", "sg", "al", "su", "bgr", "bu", "sc", "sod", "pot", "hemo", "pcv", "wbcc", "rbcc", "poverty_income_ratio", "bmi", "weight_kg", "height_cm", "bp_systolic", "bp_diastolic", "serum_creatinine", "blood_urea_nitrogen", "albumin_serum", "phosphorus", "bicarbonate", "calcium", "uric_acid", "urine_creatinine", "urine_albumin", "albumin_creatinine_ratio", "egfr"}
        item["numeric_audit"] = {}
        for col in sorted(numeric_candidates & set(df.columns)):
            values = pd.to_numeric(df[col], errors="coerce")
            item["numeric_audit"][col] = {"invalid_non_numeric": int((df[col].notna() & values.isna()).sum()), "min": float(values.min()), "max": float(values.max()), "negative": int((values < 0).sum())}
        id_col = next((x for x in ["participant_id", "id"] if x in df), None)
        item["unique_record_ids"] = int(df[id_col].nunique()) if id_col else None
        item["unique_participants"] = int(df.participant_id.nunique()) if "participant_id" in df else None
        item["identity_note"] = "Participant identifier retained" if "participant_id" in df else "Unique longitudinal participants cannot be verified; any local id is only a row identifier"
        for label in ["target", "ckd_present", "class"]:
            if label in df:
                item["labels"] = {str(k): int(v) for k, v in df[label].value_counts(dropna=False).items()}
        if "ckd_present" in df:
            for col in ["age", "egfr", "albumin_creatinine_ratio", "ckd_present", "serum_creatinine"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            usable = (df.age >= 18) & df.egfr.notna() & df.albumin_creatinine_ratio.notna()
            rebuilt = ((df.egfr < 60) | (df.albumin_creatinine_ratio >= 30)).astype(int)
            item["adult_complete_outcome"] = int(usable.sum())
            item["provided_label_disagreements_on_complete_adults"] = int((rebuilt[usable] != df.loc[usable, "ckd_present"]).sum())
            item["positive_without_both_kidney_measurements"] = int(((~(df.egfr.notna() & df.albumin_creatinine_ratio.notna())) & (df.ckd_present == 1)).sum())
            calculated = egfr_2021(df.age, df.gender.map({"Female": 0, "Male": 1}), df.serum_creatinine)
            item["median_egfr_absolute_difference_from_2021_equation"] = float(np.nanmedian(np.abs(calculated[usable] - df.loc[usable, "egfr"])))
            item["provenance"] = "Local NHANES-derived CSV, source acquisition and label-generation code absent. Compare with official components; not used for v2 fitting."
        else:
            item["provenance"] = "UCI-derived local copy (CC BY 4.0, hospital-based convenience sample); CSV/ARFF are alternate representations, not independent cohorts." if "chronic_kidney" in path.name else "Legacy processed NHANES output; participant IDs removed, full-data outlier filtering; excluded from v2 fitting."
        results.append(item)
    output = BASE / "reports/data-audit.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
    return results

if __name__ == "__main__":
    for item in audit_existing():
        print(item["file"], item["rows"], item.get("labels"), item.get("positive_without_both_kidney_measurements"))
