# Executed verification

Environment: Windows, Python 3.14.0, Node.js, sklearn 1.9.1; exact Python dependencies are in `ml/requirements-research-lock.txt`. Original requirements/artifacts were not replaced.

## Automated checks

- `python -m unittest discover -s ml/research/tests -v`: **9 tests passed**. Covers participant separation and deterministic splits; repeated-ID rejection; leakage exclusions; schema validation; invalid-to-missing behavior; fixed equation examples and complete outcomes; training-only preprocessing; metrics and validation threshold selection; saved artifact loading and Python inference; deterministic seeded fitting.
- The Python suite also exports and checks **all six fitted candidates** (three model families × two tasks) against the shared JavaScript evaluator on **64 synthetic inputs each**. All **384 probability comparisons** agree within absolute tolerance `1e-10`, including numeric missingness and categorical transforms.
- `npm test` in `frontend`: **12 tests passed**. Checks selected-model parity fixtures, real model-derived local explanations, required/invalid/unknown features, contradictory BP inputs, non-mutation, null versus zero, marginal OOD flags, synchronized ML/frontend runtime and validation-only model selection.
- `npm run check`: JavaScript syntax checks passed for application, assessment, research and chart modules.
- `npm run build`: static build passed with both model pathways and the actual versioned report.
- `git diff --check`: passed for tracked edits. No commits or global Git configuration changes were made.

An initial equation golden-test constant had excessive manually rounded error; the formula itself was unchanged. Corrected four-decimal reference values (male 86.1626 / female 64.4950 at age 60, creatinine 1 mg/dL) pass. An initial local CSV parse failed on malformed UCI rows; the audit now reports and handles those explicitly without changing source files.

## Browser checks

Used the Codex in-app browser against the local static server. All entered health values were synthetic QA inputs, not patient data.

- Landing-to-assessment and assessment-to-research navigation.
- Empty screening submission shows required-field/completeness errors.
- Screening synthetic input executes actual inference and displays a 6.7% experimental output, with two explicitly imputed fields and model-derived explanations.
- Hypothetical systolic BP change recalculates the same model (11.9% in that QA scenario), with noncausal labeling.
- Biomarker submission with only one secondary lab is rejected; adding a second lab executes actual inference (4.3% for the synthetic QA case).
- Clear-inputs action clears results and form values. Mobile navigation opens, and Escape closes it with the correct expanded state.
- Research task and model selectors update actual metrics; calibration tab displays saved coordinates and exact-data disclosure.
- Missing `report.json` was temporarily simulated: the UI displayed an explicit unavailable-artifact state and reproduction link, without a fabricated result. The report was restored immediately afterwards.
- Browser console had no errors/warnings during successful interactions. The deliberate missing-artifact test produces an expected 404.

## Responsive and visual checks

The IAB panel is narrow; a local iframe harness (`frontend/tests/preview.html`, excluded from the build) renders real CSS layouts at nominal widths **1440, 834, 390 and 320 px**. The usable document widths are 1425, 819, 375 and 305 px because of the scrollbar.

All five pages were checked: Overview, Assessment, Research, Methodology and Kidney health. No page-level horizontal overflow remains. Research tables intentionally scroll within their containers. A 3 px tablet overflow from decorative orbital geometry was found and fixed. The actual narrow-screen landing, scenario result and calibration chart were visually inspected. This is browser rendering QA, not an exhaustive real-device or screen-reader audit.

Visible focus styles, semantic labels, skip navigation, responsive menu states, chart text/data tables and reduced-motion CSS are implemented. Reduced-motion behavior and contrast have not undergone a formal third-party accessibility audit.

## Scope and remaining limitations

No production deployment, authentication, database, backend service or API integration was attempted. Original legacy scripts were audited, preserved and clearly marked, not installed/re-executed wholesale. Their unresolved scientific/code issues are listed in `docs/AUDIT.md`; they are not called by the new application.

No clinical validation, prospective outcomes, validated stage model, real longitudinal timeline, survey-adjusted population model, final-model SHAP, joint-distribution OOD detector or individual confidence interval is claimed. The executed sigmoid calibration slightly worsens the selected models' test Brier scores. No performance-improvement claim over the historical results is justified.

The local preview server is for development only; start it with `cd frontend` then `npm run dev` when reviewing the project.
