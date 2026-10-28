# Source review and harmonization notes

Reviewed 23 October 2026. These notes record source documentation, not a clinical validation claim. NHANES public files are repeated cross-sectional samples; the proposed label identifies a contemporaneous kidney-function/albuminuria screening phenotype, not incident CKD or confirmed chronic disease.

## Component map

Files are joined within cycle on `SEQN`. Keep a separate cycle column. Official documentation and downloadable XPT files now use `/Nchs/Data/Nhanes/Public/2021/DataFiles/` for August 2021–August 2023 and `/Public/2017/DataFiles/` for 2017–2018. Replace the documentation `.htm` extension with `.xpt` for the corresponding public file; validate download content before parsing.

| Component | Variables relevant to this project | Official codebooks |
|---|---|---|
| Demographics | `SEQN`; `RIDAGEYR` (years); `RIAGENDR` (1 male, 2 female); `RIDRETH3`; `RIDEXPRG`; `INDFMPIR`; `WTMEC2YR`, `WTINT2YR`, `SDMVSTRA`, `SDMVPSU` | [DEMO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DEMO_L.htm), [DEMO_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.htm) |
| Biochemistry | `LBXSCR` serum creatinine (mg/dL), `LBDSCRSI` (µmol/L); `LBXSBU` BUN (mg/dL); `LBXSAL` serum albumin (g/dL); `LBXSNASI`, `LBXSKSI`, `LBXSC3SI` (mmol/L); `LBXSUA` uric acid (mg/dL). `WTPH2YR` exists in L. | [BIOPRO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BIOPRO_L.htm), [BIOPRO_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BIOPRO_J.htm) |
| Urine albumin/creatinine | `URDACT` UACR (mg/g); `URXUMA` albumin (µg/mL), numerically equal to `URXUMS` (mg/L); `URXUCR` creatinine (mg/dL); `URDUMALC`, `URDUCRLC` detection-limit flags | [ALB_CR_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/ALB_CR_L.htm), [ALB_CR_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/ALB_CR_J.htm) |
| Body measures | `BMXBMI` (kg/m²), `BMXWT` (kg), `BMXHT`, `BMXWAIST` (cm) | [BMX_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BMX_L.htm), [BMX_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.htm) |
| Oscillometric blood pressure | `BPXOSY1`–`BPXOSY3`, `BPXODI1`–`BPXODI3` (mmHg) | [BPXO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BPXO_L.htm), [BPXO_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPXO_J.htm) |
| Diabetes questionnaire | `DIQ010`: 1 yes, 2 no, 3 borderline, 7 refused, 9 unknown; `DIQ050` insulin; `DIQ070` oral medication | [DIQ_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DIQ_L.htm), [DIQ_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DIQ_J.htm) |
| Smoking questionnaire | `SMQ020`: lifetime 100-cigarette question (1 yes, 2 no); `SMQ040`: current smoking (1 every day, 2 some days, 3 not at all); 7/9 are refusal/unknown | [SMQ_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/SMQ_L.htm), [SMQ_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/SMQ_J.htm) |

## Analysis decisions and limitations

- **Weights:** For L analyses using blood analytes, CDC specifies `WTPH2YR`, addressing phlebotomy nonresponse. Preserve the demographic design variables. For J full-sample examination/laboratory analyses, use `WTMEC2YR`; fasting components require their own subsample weights. An ordinary random split, unweighted metric, or individual bootstrap does not become nationally representative merely because weights were retained. [BIOPRO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BIOPRO_L.htm), [SMQ_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/SMQ_J.htm), [DIQ_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DIQ_L.htm).
- **Biochemistry:** The L instrument changed from Cobas 6000 to 8000. CDC recommends no adjustment for serum creatinine. Its bridging table gives analyte-specific equations for BUN, sodium, potassium, bicarbonate and others. Reference-component glucose, cholesterol and triglycerides are preferred over BIOPRO values. Record any chosen transformations explicitly. [BIOPRO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BIOPRO_L.htm).
- **Albumin assay:** L uses LC-MS/MS; prior cycles used fluorescent immunoassay. CDC gives `albumin_new = 1.381 + 0.8407 * albumin_old` and `albumin_old = -1.643 + 1.189 * albumin_new`, according to analytic aims. Recompute `UACR = 100 * URXUMA / URXUCR` after adjustment. No urinary-creatinine correction is recommended. Below-detection values already contain LLOD/√2 substitutions. [ALB_CR_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/ALB_CR_L.htm). Project inference: preserve raw values and report a sensitivity analysis; the backward equation can yield negative results at very low concentrations, so a handling policy must be stated rather than silently clipping.
- **Blood pressure:** Prefer BPXO_J for comparison with BPXO_L: both contain three oscillometric measurements. J also collected auscultatory measurements in [BPX_J](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPX_J.htm); auscultatory collection stopped after that cycle. Do not silently mix methods. A mean of available oscillometric readings is an explicit project aggregation, not a claim that a single visit diagnoses hypertension. [BPXO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BPXO_L.htm).
- **Age/design:** Public age is top-coded at 80; eGFR calculated using that value has a limitation for older participants. L restarted after pandemic suspension with updated sample design and procedures. A held-out cycle tests temporal transport within NHANES, not transport to hospitals or another country. [DEMO_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DEMO_L.htm).
- **Questionnaire missingness:** Preserve diabetes borderline responses separately from no diabetes. The insulin question's target changed in L. Smoking status must combine SMQ020 and SMQ040: skips are not ordinary observed negative answers. Project mapping: never = SMQ020 2; current = SMQ020 1 and SMQ040 1/2; former = SMQ020 1 and SMQ040 3; unresolved responses remain missing. [DIQ_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DIQ_L.htm), [SMQ_L](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/SMQ_L.htm).

## Kidney endpoint

For adults aged at least 18, the race-free 2021 CKD-EPI creatinine equation is:

`eGFR = 142 * min(SCr/k, 1)^a * max(SCr/k, 1)^(-1.200) * 0.9938^age * (1.012 if female else 1)`

SCr is standardized serum creatinine in mg/dL; k = 0.7 for females / 0.9 for males; a = −0.241 / −0.302 respectively. Output is mL/min/1.73 m². Convert µmol/L creatinine to mg/dL by dividing by 88.4. NIDDK stresses that eGFR is an estimate; creatinine plus cystatin C is more accurate when available. [NIDDK adult equations](https://www.niddk.nih.gov/research-funding/research-programs/kidney-clinical-research-epidemiology/laboratory/glomerular-filtration-rate-equations/adults).

A research endpoint of `eGFR < 60 OR UACR >= 30 mg/g` is a screening phenotype. CKD diagnosis requires persistent abnormalities for more than three months; one cross-sectional observation cannot establish that chronicity. Do not describe its model probability as future CKD incidence. [NIDDK evaluation guidance](https://www.niddk.nih.gov/health-information/professionals/clinical-tools-patient-management/kidney-disease/identify-manage-patients/evaluate-ckd), [NKF diagnostic criteria](https://www.kidney.org/what-criteria-ckd).

Project leakage rule: if this endpoint is derived from creatinine/eGFR and urine albumin/UACR, those values, unit-converted duplicates and direct transformations cannot be predictors in the primary screening model. Age and sex remain predictors but are also equation inputs; report that dependency. Other renal laboratory variables may be correlated proxies and belong in a clearly separated sensitivity model if used.

## Data terms

NCHS public-use data are restricted to statistical analysis/reporting. Users must not attempt identification, link to individually identifiable datasets, or investigate re-identification/disclosure-protection methods. Use signifies agreement. These terms are distinct from the project's source-code license. [NCHS Data User Agreement](https://www.cdc.gov/nchs/policy/data-user-agreement.html).
