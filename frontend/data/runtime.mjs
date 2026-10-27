/** Shared ML-owned portable inference runtime. The frontend imports this exported file.
 * Consumes fitted parameters, never retrains or substitutes a scoring formula.
 */
const sigmoid = x => x >= 0 ? 1 / (1 + Math.exp(-x)) : Math.exp(x) / (1 + Math.exp(x));
export function validateInput(artifact, input) {
  const values = {}, quality = [], errors = [];
  for (const key of Object.keys(input)) if (!artifact.features.includes(key)) errors.push(`Unknown feature: ${key}`);
  for (const name of artifact.features) {
    const field = artifact.fields[name], raw = input[name];
    const missing = raw === null || raw === undefined || raw === '';
    if (missing) {
      values[name] = null;
      quality.push({feature: name, state: field.required ? 'required' : 'imputed', message: field.required ? 'Required input missing' : 'Missing; training-set value will be imputed'});
      if (field.required) errors.push(`${field.label} is required`);
      continue;
    }
    const value = typeof raw === 'number' ? raw : NaN;
    const invalid = !Number.isFinite(value) || (field.choices ? !Object.hasOwn(field.choices, String(value)) : value < field.min || value > field.max);
    if (invalid) {
      values[name] = null;
      quality.push({feature: name, state: 'invalid', message: 'Invalid type, category or plausibility range'});
      errors.push(`${field.label}: enter a valid value in ${field.unit || 'the available categories'}`);
    } else {
      values[name] = value;
      const range = artifact.ranges[name];
      const outside = value < range.min || value > range.max;
      const tail = !field.choices && (value < range.p01 || value > range.p99);
      quality.push({feature: name, state: outside ? 'outside' : tail ? 'unusual' : 'observed', message: outside ? 'Outside observed training range; reliability is unknown' : tail ? 'In a tail of the training distribution (outside 1st–99th percentiles)' : 'Observed input'});
    }
  }
  const present = Object.values(values).filter(v => v !== null).length;
  if (present < Math.ceil(artifact.features.length / 2)) errors.push('At least half of the model inputs must be supplied; this is a research completeness gate, not a clinical rule.');
  if (artifact.task === 'biomarker' && artifact.features.slice(8).filter(c => values[c] !== null).length < 2) errors.push('Supply at least two secondary biomarkers for this pathway.');
  if (values.bp_systolic !== null && values.bp_diastolic !== null && values.bp_systolic <= values.bp_diastolic) errors.push('Systolic pressure must exceed diastolic pressure.');
  return {values, quality, errors, present};
}

function transform(artifact, values) {
  const x = [];
  for (const field of artifact.preprocessing) {
    const v = values[field.name] ?? field.impute;
    if (field.kind === 'numeric') x.push((v - field.mean) / field.scale);
    else for (const category of field.categories) x.push(v === category ? 1 : 0);
  }
  return x;
}
function treeValue(tree, x, histogram) {
  let i = 0;
  while (histogram ? !tree.leaf[i] : tree.left[i] !== -1) {
    // sklearn forests cast input to float32; histogram models retain float64.
    const value = histogram ? x[tree.feature[i]] : Math.fround(x[tree.feature[i]]);
    i = value <= tree.threshold[i] ? tree.left[i] : tree.right[i];
  }
  return tree.value[i];
}
export function score(artifact, values) {
  const x = transform(artifact, values), model = artifact.estimator;
  let raw;
  if (model.kind === 'linear') raw = sigmoid(model.intercept + model.coefficients.reduce((sum, coefficient, i) => sum + coefficient * x[i], 0));
  else if (model.kind === 'forest') raw = model.trees.reduce((sum, tree) => sum + treeValue(tree, x, false), 0) / model.trees.length;
  else if (model.kind === 'hist') raw = sigmoid(model.baseline + model.trees.reduce((sum, tree) => sum + treeValue(tree, x, true), 0));
  else throw new Error('Unsupported estimator artifact');
  raw = Math.max(1e-7, Math.min(1 - 1e-7, raw));
  return sigmoid(artifact.calibration.slope * Math.log(raw / (1 - raw)) + artifact.calibration.intercept);
}
export function assess(artifact, input) {
  if (artifact.schema_version !== 1) throw new Error('Incompatible model schema');
  const validation = validateInput(artifact, input);
  if (validation.errors.length) return {status: 'invalid', ...validation};
  const probability = score(artifact, validation.values);
  const explanations = artifact.features.filter(name => validation.values[name] !== null).map(feature => {
    const reference = artifact.preprocessing.find(item => item.name === feature).impute;
    const alternate = score(artifact, {...validation.values, [feature]: reference});
    return {feature, observed: validation.values[feature], reference, probability_difference: probability - alternate};
  }).sort((a, b) => Math.abs(b.probability_difference) - Math.abs(a.probability_difference));
  return {status: 'ok', task: artifact.task, model_version: artifact.version, run_id: artifact.run_id, model: artifact.model,
    label: artifact.label, probability, outcome: probability >= artifact.threshold ? 'Above research operating threshold' : 'Below research operating threshold',
    threshold: artifact.threshold, calibration: 'Sigmoid calibration on a separate partition; not clinical validation',
    explanation_method: 'One-feature replacement at training reference; probability differences are non-additive, not SHAP and not causal effects.',
    explanations, quality: validation.quality, present: validation.present, total: artifact.features.length, limitations: artifact.limitations};
}
