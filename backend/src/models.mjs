import {readFile} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
// Read the ML-owned implementation directly. No duplicate inference algorithm.
import {assess, validateInput} from '../../ml/research/runtime.mjs';

export const TASKS = ['screening', 'biomarker'];
export {assess, validateInput};

export function metadata(artifact) {
  const {schema_version, version, run_id, task, model, label, threshold,
    features, fields, ranges, limitations} = artifact;
  return {schema_version, version, run_id, task, model, label, threshold,
    features, fields, ranges, limitations};
}

export async function loadRegistry(dataDir) {
  const read = async name => JSON.parse(await readFile(path.join(dataDir, `${name}.json`), 'utf8'));
  const [screening, biomarker, report, sources] = await Promise.all(
    ['screening', 'biomarker', 'report', 'sources'].map(read));
  const models = {screening, biomarker};
  for (const task of TASKS) {
    const artifact = models[task];
    assert.equal(artifact.schema_version, 1, `${task}: unsupported model schema`);
    assert.equal(artifact.task, task, `${task}: incorrect task`);
    assert.equal(artifact.version, report.version, `${task}: report version mismatch`);
    assert.equal(artifact.run_id, report.run_id, `${task}: report run mismatch`);
    assert.equal(artifact.model, report.tasks[task].selected, `${task}: selected model mismatch`);
    assert.ok(Number.isFinite(artifact.threshold) && artifact.threshold >= 0 && artifact.threshold <= 1);
    assert.ok(Array.isArray(artifact.features) && artifact.features.length > 0);
    assert.equal(new Set(artifact.features).size, artifact.features.length);
    const reference = Object.fromEntries(artifact.features.map(feature => {
      assert.ok(artifact.fields[feature] && artifact.ranges[feature], `${task}: missing feature metadata`);
      const preprocessing = artifact.preprocessing.find(field => field.name === feature);
      assert.ok(preprocessing, `${task}: missing preprocessing`);
      return [feature, preprocessing.impute];
    }));
    // Verify that the trusted exports can run before accepting any HTTP traffic.
    const result = assess(artifact, reference);
    assert.equal(result.status, 'ok', `${task}: model startup assessment failed`);
    assert.ok(Number.isFinite(result.probability) && result.probability >= 0 && result.probability <= 1);
    assert.ok(result.explanations.every(item => Number.isFinite(item.probability_difference)));
  }
  return {models, report, sources};
}
