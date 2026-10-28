# CKD Early Warning AI Framework

**Nephra** is the local research interface for this existing CKD project. The upgrade preserves the original `ml/` scripts, datasets and checkpoints and adds a separate reproducible research pipeline and a complete static frontend. No backend, authentication, database or cloud deployment is introduced.

This is an academic prototype. Its outcome is **single-visit reduced eGFR or elevated UACR**, not clinically confirmed CKD, future disease incidence or progression.

## Start the interface

The committed browser-safe model exports and evaluation report allow the interface to run without Python or an inference server. Node.js 22+ is recommended. No npm dependencies need installing.

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:4173**. On PowerShell systems that block `npm.ps1`, use `npm.cmd`.

```powershell
npm test
npm run check
npm run build
```

The build writes `frontend/dist/`. It contains only static application assets and aggregate research/model exports. The development server binds to loopback. Stop it with Ctrl+C. Do not use it as a production server.

## Pages and working features

- Overview: original Nephra identity, conceptual kidney illustration, two pathways, process, capabilities and research links.
- Assessment: screening and secondary-biomarker forms, units, completeness gates, validation, missingness and training-range warnings. Actual fitted random forests plus fitted sigmoid calibrators run in browser memory.
- Results: experimental probability, validation-selected operating threshold, actual one-feature replacement explanations, quality flags, evaluation context and hypothetical input exploration.
- Research explorer: pathway/model selectors, ROC/PR/calibration charts with exact-data tables, confusion matrices, all requested binary metrics, bootstrap intervals, model comparison, earlier-cycle stress test, permutation importance, subgroups and sensitivity analyses.
- Methodology: source documents, label/equation, feature exclusions, inclusion criteria, split protocol, limitations and commands.
- Kidney health: eGFR/UACR context and an honest empty state for longitudinal observations.

There is no patient storage, login, prediction API or health-data telemetry. Inputs remain in memory and are cleared when leaving the assessment. The shared inference runtime is owned by ML and exported alongside fitted parameters; the UI does not implement a separate score.

## Reproduce the research

Run these commands from the repository root. The executed environment used Python 3.14.0; exact package versions are captured in the lock file. For another supported Python version use `ml/requirements-research.txt` and record any resulting differences.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements-research-lock.txt
.\.venv\Scripts\python.exe -m ml.research.acquire --cycle 2021-2023
.\.venv\Scripts\python.exe -m ml.research.acquire --cycle 2017-2018
.\.venv\Scripts\python.exe -m ml.research.train --run-id my-experiment
.\.venv\Scripts\python.exe -m ml.research.report
.\.venv\Scripts\python.exe -m unittest discover -s ml/research/tests -v
```

On macOS/Linux substitute `.venv/bin/python`. Data downloads require network access to CDC and agreement with the [NCHS data-use terms](https://www.cdc.gov/nchs/policy/data-user-agreement.html). Cached XPTs are checksum-checked and reused. Each training run refuses to overwrite an existing experiment directory; choose a fresh `--run-id`. A successful run updates the frontend's selected exports and the aggregate `ml/reports/research-v2.json`. Training takes a few minutes on the available 12-logical-CPU system and limits numerical/forest work to two threads.

The pipeline includes acquisition, audit, preprocessing, CV, calibration, validation-only threshold/model selection, test and earlier-cycle evaluation, confidence intervals, explanations, reliability analyses and report export. No test-set tuning is performed. The selected models have test AUC 0.7901 (screening) and 0.8053 (biomarker); see [the full results and model registry](docs/RESULTS.md), including the calibration caveat and all six model rows.

Optional local Python inference takes JSON on stdin and writes a result to stdout, without saving inputs:

```powershell
Get-Content path/to/local-input.json | .\.venv\Scripts\python.exe -m ml.research.inference --artifact ml/artifacts/research-v2/nhanes-20261023-v2/screening-forest.joblib
```

Use only locally trusted joblib files. Feature names, units and categories are defined in `ml/research/schema.py` and exported in `frontend/data/screening.json` or `biomarker.json`. Supply numbers or nulls, not numeric strings. `age` and `sex` are required; at least half the features must be present. The biomarker task additionally requires two secondary labs. These gates are research interface rules, not clinical thresholds.

## Data and scientific boundaries

Official NHANES 2021–2023: 11,933 source participants, 5,552 eligible adults with both kidney measurements; 949 positive / 4,603 negative. Earlier NHANES 2017–2018: 9,254 source participants, 5,063 eligible adults; 939 positive / 4,124 negative. Component-level counts, source URLs, terms and hashes are in [RESULTS](docs/RESULTS.md), [SOURCES](docs/SOURCES.md), and `frontend/data/sources.json`.

The original local NHANES labels disagree with the documented threshold endpoint for 1,644 complete adult records; 5,661 positive labels lack both outcome measurements. The old cleaning script also applies a full-dataset IsolationForest and drops IDs. The old threshold script tunes on the test set; stacked base-model SHAP averages do not explain the final calibrated ensemble; distance to threshold does not establish confidence. Legacy metadata includes a separate UCI experiment, and the stage script is not a longitudinal progression model. These files and original artifacts remain preserved for review, but are not invoked by Nephra.

The new experiments do not prove superior clinical performance. Calibration slightly worsened the selected models' test Brier scores. Both tasks share an equation-derived endpoint and age/sex coupling; the biomarker task uses correlated secondary markers. Single-visit data cannot establish chronicity. The earlier cycle has assay/design shifts and is a stress test, not fully harmonized external clinical validation. Training and evaluation are unweighted, so they do not represent population risk or survey-design-adjusted uncertainty.

Not available: future progression prediction, validated CKD stage inference, real patient trends, clinical validation, causal treatment counterfactuals, final-model SHAP, joint OOD detection or individual uncertainty intervals. The UI states these limits rather than presenting fake results.

## Structure and deliverables

```text
ml/                         original ML work retained
  research/                 v2 acquisition, schema, audit, train, metrics,
                            export/runtime, inference, report and tests
  data/raw/official/         official cycle-specific XPTs + source manifests (ignored)
  artifacts/research-v2/     versioned pipelines, calibrators, IDs, reports (ignored)
  reports/                  aggregate data audit and evaluation
frontend/                   dependency-free modular web application
  assets/                   generated conceptual kidney hero + SVG wordmark
  data/                     portable model parameters, shared runtime, schema,
                            aggregate reports and synthetic parity fixtures
  tests/                    runtime tests + responsive preview harness
  scripts/                  loopback dev server and static build
docs/                       audit, sources, results, verification and checklist
```

Large raw data, original pickles, new joblib artifacts, participant split IDs, virtual environments and build outputs are ignored. The frontend exports contain no participant rows. The conceptual kidney image is AI-generated decorative artwork, not an anatomical teaching diagram.

See [verification](docs/VERIFICATION.md) for executed checks and remaining limits, [audit](docs/AUDIT.md) for the original implementation, and [progress](docs/PROGRESS.md) for completion status.
