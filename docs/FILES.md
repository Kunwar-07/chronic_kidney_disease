# Changed files and saved artifacts

## Existing files changed

- `ml/README.md`: prominent legacy-workflow notice and link to the supported v2 workflow.
- `ml/.gitignore`: allow aggregate research reports to be tracked.

No original dataset, model checkpoint, experiment script or plot was overwritten or deleted.

## New project documentation/configuration

- `.gitignore`: local environments, data, private artifacts and generated builds excluded.
- `README.md`: run/install/training/evaluation instructions, architecture and scope.
- `docs/AUDIT.md`: original code/data findings and implementation decisions.
- `docs/SOURCES.md`: official codebooks, units, assay differences, equation and data terms.
- `docs/RESULTS.md`: all model metrics, model registry, cohorts, thresholds and limitations.
- `docs/VERIFICATION.md`: executed tests, UI checks and remaining verification limits.
- `docs/PROGRESS.md`: completed implementation checklist.
- `docs/FILES.md`: this inventory.
- `docs/screenshots/nephra-mobile.png`: actual browser screenshot.

## New ML source

- `ml/requirements-research.txt`, `ml/requirements-research-lock.txt`.
- `ml/research/__init__.py`.
- `ml/research/acquire.py`: immutable official-download cache and provenance manifest.
- `ml/research/schema.py`: version, fields, units, tasks, leakage exclusions and limitations.
- `ml/research/data.py`: one-to-one joins, normalization, adult eligibility and explicit endpoint.
- `ml/research/audit.py`: original-data inventory, malformed rows and numerical/missingness audit.
- `ml/research/metrics.py`: binary metrics, validation thresholds, curves and bootstrap intervals.
- `ml/research/train.py`: reproducible compact model search, calibration, evaluation and exports.
- `ml/research/portable.py`: fitted estimator/preprocessor export and calibrated Python probability.
- `ml/research/runtime.mjs`: shared browser/Node evaluator, input quality and local explanations.
- `ml/research/contracts.d.ts`: typed frontend inference contract.
- `ml/research/inference.py`: local Python prediction entry point.
- `ml/research/report.py`: saved-results-to-Markdown report generation.
- `ml/research/tests/test_research.py`: nine tests, including all-family Python/JS parity.
- `ml/reports/data-audit.json`, `ml/reports/research-v2.json`: aggregate results.

## New frontend source

- `frontend/package.json`: dependency-free development, verification and build scripts.
- `frontend/index.html`: accessible document shell/navigation/footer.
- `frontend/app.mjs`: navigation, overview, methodology and kidney-health pages.
- `frontend/assessment.mjs`: pathway forms, results, quality and scenario exploration.
- `frontend/research.mjs`: saved-result explorer, model/task/chart controls.
- `frontend/charts.mjs`: SVG curves with exact coordinate tables.
- `frontend/ui.mjs`: shared loading, formatting, escaping and page helpers.
- `frontend/styles.css`: responsive visual system and reduced motion.
- `frontend/assets/kidney-hero.png`: generated conceptual kidney artwork.
- `frontend/assets/mark.svg`: original Nephra wordmark symbol.
- `frontend/scripts/serve.mjs`, `frontend/scripts/build.mjs`: loopback server and static packaging.
- `frontend/tests/inference.test.mjs`: twelve inference/contract tests.
- `frontend/tests/preview.html`: responsive QA harness, excluded from the build.
- `frontend/data/report.json`, `sources.json`: aggregate evaluation and official-source provenance.
- `frontend/data/screening.json`, `biomarker.json`: fitted portable models, calibration, fields and ranges.
- `frontend/data/screening-parity.json`, `biomarker-parity.json`: synthetic verification inputs and Python outputs.
- `frontend/data/runtime.mjs`, `contracts.d.ts`: exact exported copies of the ML-owned runtime/contract.

## Saved locally, excluded from Git

- `.venv/`: isolated research dependencies.
- `ml/data/raw/official/2021-2023/`: DEMO_L, BIOPRO_L, ALB_CR_L, BMX_L, BPXO_L, DIQ_L, SMQ_L XPTs and manifest.
- `ml/data/raw/official/2017-2018/`: corresponding J-cycle XPTs and manifest.
- `ml/artifacts/research-v2/nhanes-20261023-v2/`: six fitted joblib pipelines/calibrators, selected portable model JSONs, parity fixtures, report, source manifest and participant split IDs.
- `ml/artifacts/research-v2/nhanes-20261023/`: retained empty directory from the first audit/parse failure; no successful model was produced there.
- `frontend/dist/`: verified static build. No patient records, raw XPTs or joblib files are included.
