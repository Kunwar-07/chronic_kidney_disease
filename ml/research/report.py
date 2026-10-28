"""Render a reviewable research summary from saved aggregate results."""
import json
from .acquire import BASE

def main():
    r = json.loads((BASE / "reports/research-v2.json").read_text(encoding="utf-8"))
    audit = json.loads((BASE / "reports/data-audit.json").read_text(encoding="utf-8"))
    lines = ["# Research results and model registry", "", f"Run: `{r['run_id']}` · schema `{r['version']}` · seed `{r['seed']}`", "", "These are real executed experiments. Scores are not clinical validation or a claim of superiority over the legacy pipeline.", "", "## Cohorts", "", "| Cohort | Source participants | Eligible adults | Positive | Negative |", "|---|---:|---:|---:|---:|"]
    for name, a in [(r["dataset"],r["audit"]),("NHANES 2017–2018 stress test",r["external_audit"])]:
        if "eligible_rows" in a:
            lines.append(f"| {name} | {a['merged_rows']:,} | {a['eligible_rows']:,} | {a['positive']:,} | {a['negative']:,} |")
    lines += ["", "Both cycles are separate cross-sectional samples. The earlier cycle remains unpooled and has assay and design differences. All metrics are unweighted. There are no prospective patient outcomes.", "", "### Component downloads", "", "| Component | 2021–2023 records | 2017–2018 records |", "|---|---:|---:|"]
    for latest, earlier in zip(r["audit"]["components"],r["external_audit"].get("components",[])):
        lines.append(f"| {latest['file']} / {earlier['file']} | {latest['rows']:,} | {earlier['rows']:,} |")
    lines += ["", "Official CDC/NCHS sources, download URLs, retrieval timestamps and SHA-256 hashes are in `frontend/data/sources.json`. NCHS public-use terms apply: statistical analysis/reporting only; no re-identification. Component row counts must not be summed as independent people. One-to-one joins use SEQN.", "", "### Existing local data", "", "| File | Rows | Labels | Audit notes |", "|---|---:|---|---|"]
    for a in audit:
        notes = a["provenance"]
        if a["trailing_empty_fields_normalized_for_audit_only"]:
            notes += f" {len(a['trailing_empty_fields_normalized_for_audit_only'])} extra trailing empty fields normalized for audit only; originals unchanged."
        if a["malformed_rows_excluded_from_audit_statistics"]:
            notes += f" {len(a['malformed_rows_excluded_from_audit_statistics'])} ambiguous malformed row(s) excluded from column statistics; source has {a['total_source_rows']} records."
        if "provided_label_disagreements_on_complete_adults" in a:
            notes += f" {a['provided_label_disagreements_on_complete_adults']} provided-label disagreements on adults with complete measurements; {a['positive_without_both_kidney_measurements']} positive labels without both kidney measurements."
        lines.append(f"| `{a['file']}` | {a['rows']:,} | {a.get('labels')} | {notes} |")
    lines += ["", "The UCI source has 400 records, 24 predictors and CC BY 4.0 licensing. In each local copy, 399 records parse after normalizing two trailing commas: 250 CKD / 149 non-CKD. One additional non-CKD row has an ambiguous embedded extra field and is excluded from column statistics. The CSV/ARFF represent the same hospital sample; no second UCI cohort was acquired. No documented longitudinal participant identity exists. Full missingness, duplicate and numeric audits are in `ml/reports/data-audit.json`.", "", "## Model comparison", "", "All rows use the same eligible cohort and participant partitions. CV and validation choose models; test metrics are descriptive after selection.", "", "| Pathway | Model | CV AP | Validation AP | Test ROC-AUC | Test AP | Sensitivity | Specificity | PPV | NPV | F1 | Balanced acc. | Brier |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for task, group in r["tasks"].items():
        for item in group["models"]:
            m=item["test"]
            numbers=[item["cv_average_precision"],item["validation"]["average_precision"]]+[m[k] for k in ["roc_auc","average_precision","sensitivity","specificity","precision","npv","f1","balanced_accuracy","brier"]]
            lines.append(f"| {task} | {item['id']}{' **selected**' if item['id']==group['selected'] else ''} | "+" | ".join(f"{v:.4f}" for v in numbers)+" |")
    lines += ["", "## Selected models", "", r["selection"], ""]
    for task, group in r["tasks"].items():
        m=next(item for item in group["models"] if item["id"]==group["selected"])
        t=m["test"]
        lines += [f"### {task}: {group['selected']}", "", f"Validation AP {m['validation']['average_precision']:.4f}; operating threshold {t['threshold']:.6f}. Test AUC {t['roc_auc']:.4f} (IID bootstrap 95% CI {t['ci95']['roc_auc'][0]:.4f}–{t['ci95']['roc_auc'][1]:.4f}).", "", f"Confusion matrix (rows observed 0/1, columns predicted 0/1): `{t['confusion_matrix']}`. Test sample: {t['positive']} positive / {t['negative']} negative. Test prevalence {t['prevalence']:.3%}.", "", f"Test Brier before sigmoid calibration: {t['uncalibrated_brier']:.5f}; after: {t['brier']:.5f}. Calibration did not improve the selected model's test Brier score; it must not be described as clinically reliable.", ""]
        if "external" in m:
            e=m["external"]; bridge=m["external_albumin_bridge"]
            lines += [f"Earlier-cycle stress test: AUC {e['roc_auc']:.4f}, AP {e['average_precision']:.4f}, sensitivity {e['sensitivity']:.4f}, specificity {e['specificity']:.4f}. Urine-albumin bridge changes {bridge['changed_labels']} labels; bridged AP {bridge['average_precision']:.4f}. Other analyte method shifts are unadjusted; this is not fully harmonized external validation.", ""]
    lines += ["The biomarker histogram model has a slightly higher test AUC/AP than the selected forest. We retain the validation-selected forest rather than using the test set to change the selection. The validation AP margins are small and do not establish superiority.", "", "## Protocol", "", "| Partition | n | Positive | Negative |", "|---|---:|---:|---:|"]
    for k,v in r["splits"].items():
        lines.append(f"| {k} | {v['n']} | {v['positive']} | {v['negative']} |")
    lines += ["", r["calibration"], "", "Median numeric imputation + standardization, mode categorical imputation + one-hot encoding are fitted within training folds. Three-fold CV searches compact grids. Class-weighted logistic/forest candidates are compared with unweighted alternatives; no synthetic resampling. Two threads limit CPU usage. Full parameters and library versions are saved with the report.", "", "## Limits and available research features", ""]
    lines += [f"- {text}" for text in r["limitations"]]
    lines += ["- eGFR is approximate for ages top-coded at 80. Pregnancy and all causes of transient biomarker abnormalities are not separately adjudicated.", "- No clinically validated CKD stage or future progression model is offered; legacy stage code is preserved only for history.", "- Global permutation importance, non-additive local replacement explanations, missingness sensitivity, BP perturbation, subgroup summaries and marginal input-range flags are available.", "- SHAP for the final calibrated model, joint-distribution OOD detection, causal counterfactuals, individual uncertainty intervals and survey-design-adjusted population estimates remain unavailable.", "", "## Artifacts", "", f"Local fitted pipelines, calibrators, split identifiers, selected portable parameters, parity fixtures and report: `ml/artifacts/research-v2/{r['run_id']}/` (ignored by Git).", "", "Aggregate report and audit: `ml/reports/`. Browser-safe parameters, schemas, synthetic parity fixtures, source manifest and report: `frontend/data/`. No participant-level data are exported to the frontend.", "", "Rebuild this summary with `python -m ml.research.report`. See the root README for the complete workflow."]
    path = BASE.parent / "docs/RESULTS.md"
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(path)

if __name__ == "__main__":
    main()
