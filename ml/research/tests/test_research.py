import json
import subprocess
import unittest
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from ml.research.acquire import BASE
from ml.research.data import egfr_2021, load_official, validate_features, validate_ids
from ml.research.schema import TASKS, FORBIDDEN, SEED
from ml.research.train import split_cohort, preprocessing, candidates
from ml.research.metrics import evaluate, select_threshold
from ml.research.portable import export_pipeline, calibrated_probability
from ml.research.inference import predict

class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.audit = load_official()
        cls.report = json.loads((BASE / "reports/research-v2.json").read_text(encoding="utf-8"))
        cls.output = BASE / "artifacts/research-v2" / cls.report["run_id"]

    def test_participant_splits_are_disjoint_and_reproducible(self):
        first, second = split_cohort(self.df), split_cohort(self.df)
        all_ids = []
        saved = json.loads((self.output / "splits.json").read_text())
        for name, indices in first.items():
            np.testing.assert_array_equal(indices, second[name])
            ids = self.df.participant_id.iloc[indices].tolist()
            self.assertEqual(ids, saved[name])
            all_ids.extend(ids)
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(len(all_ids), len(self.df))
        with self.assertRaises(ValueError):
            validate_ids(pd.concat([self.df, self.df.iloc[:1]]))

    def test_schemas_exclude_label_components(self):
        for task, features in TASKS.items():
            self.assertFalse(set(features) & FORBIDDEN)
            x, _ = validate_features(self.df, task)
            self.assertEqual(list(x), features)
            with self.assertRaises(ValueError):
                validate_features(self.df.drop(columns=[features[0]]), task)

    def test_invalid_values_are_missing_not_dropped(self):
        source = self.df.iloc[:3].copy()
        source.loc[0, "bmi"] = -2
        source.loc[1, "diabetes"] = 9
        x, invalid = validate_features(source, "screening")
        self.assertTrue(np.isnan(x.loc[0,"bmi"]))
        self.assertTrue(np.isnan(x.loc[1,"diabetes"]))
        self.assertEqual(len(x), 3)
        self.assertEqual(invalid["bmi"], 1)

    def test_equation_units_and_outcome(self):
        self.assertAlmostEqual(float(egfr_2021(60, 1, 1.0)), 86.1626, places=4)
        self.assertAlmostEqual(float(egfr_2021(60, 0, 1.0)), 64.4950, places=4)
        self.assertTrue(self.df.egfr.notna().all())
        self.assertTrue(self.df.uacr.notna().all())
        np.testing.assert_array_equal(self.df.target, ((self.df.egfr < 60) | (self.df.uacr >= 30)).astype(int))

    def test_preprocessing_fit_is_training_only(self):
        features = TASKS["screening"]
        frame = self.df[features].iloc[:100].copy()
        fitted = preprocessing(features).fit(frame)
        median = fitted.named_transformers_["numeric"].named_steps["imputer"].statistics_.copy()
        future = frame.copy()
        future["age"] = 999
        fitted.transform(future)
        np.testing.assert_array_equal(median, fitted.named_transformers_["numeric"].named_steps["imputer"].statistics_)
        self.assertAlmostEqual(median[0], frame.age.median())

    def test_metrics_and_threshold(self):
        result = evaluate([0, 0, 1, 1], [.1, .6, .4, .9], .5)
        self.assertEqual(result["confusion_matrix"], [[1,1],[1,1]])
        self.assertEqual(result["sensitivity"], .5)
        self.assertEqual(result["specificity"], .5)
        threshold = select_threshold([0, 0, 1, 1], [.1, .2, .4, .9])
        self.assertEqual(threshold, .4)
        self.assertIsNone(evaluate([0,0], [.1,.2], .5)["roc_auc"])

    def test_artifacts_and_python_inference(self):
        for task, result in self.report["tasks"].items():
            bundle = joblib.load(self.output / f"{task}-{result['selected']}.joblib")
            fixtures = json.loads((self.output / f"{task}-parity.json").read_text())
            for fixture in fixtures:
                self.assertAlmostEqual(predict(bundle, fixture["input"])["probability"], fixture["expected"], places=12)
            with self.assertRaises(ValueError):
                predict(bundle, {})
            with self.assertRaises(ValueError):
                predict(bundle, {**fixtures[0]["input"], "age": "50"})

    def test_all_model_families_match_shared_js_runtime(self):
        rng = np.random.default_rng(SEED)
        for task, group in self.report["tasks"].items():
            features = TASKS[task]
            # Synthetic independent inputs, never real participant rows.
            frame = pd.DataFrame({c: rng.uniform(self.df[c].min(), self.df[c].max(), 64) for c in features})
            for c in ["sex", "diabetes", "ever_smoked"]:
                frame[c] = rng.integers(0,2,len(frame)).astype(float)
            frame.loc[::4,"bmi"] = np.nan
            rows = json.loads(frame.to_json(orient="records"))
            for item in group["models"]:
                bundle = joblib.load(self.output / f"{task}-{item['id']}.joblib")
                exported = export_pipeline(bundle["pipeline"])
                exported["calibration"] = {"slope": float(bundle["calibrator"].coef_[0,0]), "intercept": float(bundle["calibrator"].intercept_[0])}
                script = "import {score} from './frontend/data/runtime.mjs'; let s=''; for await (const c of process.stdin) s+=c; const d=JSON.parse(s); console.log(JSON.stringify(d.rows.map(r=>score(d.model,r))));"
                completed = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps({"model":exported,"rows":rows}), text=True, capture_output=True, cwd=BASE.parent, check=True)
                actual = np.array(json.loads(completed.stdout))
                expected = calibrated_probability(bundle["pipeline"], bundle["calibrator"], frame)
                np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=0)

    def test_seeded_fitting_is_reproducible(self):
        from sklearn.pipeline import Pipeline
        features = TASKS["screening"]
        x,y = self.df[features].iloc[:300], self.df.target.iloc[:300]
        model,_ = candidates()["logistic"]
        a = Pipeline([("preprocess",preprocessing(features)),("model",model)])
        b = clone(a)
        a.fit(x,y); b.fit(x,y)
        np.testing.assert_array_equal(a.predict_proba(x),b.predict_proba(x))

if __name__ == "__main__":
    unittest.main()
