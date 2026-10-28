import {loadJSON, pageHeading, escape, percent, number, modelName} from './ui.mjs';
import {assess, validateInput} from './data/runtime.mjs';

export async function renderAssessment(root, task) {
  const [artifact, report] = await Promise.all([loadJSON(`${task}.json`), loadJSON('report.json')]);
  const selected = report.tasks[task].models.find(model => model.id === report.tasks[task].selected);
  root.innerHTML = `<div class="page-shell assessment-page">${pageHeading('EXPLORE / ASSESSMENT','Your information.<br>A considered perspective.','Choose what information you have. Every estimate comes with its evidence, missing inputs and limitations.')}<div class="pathway-tabs" aria-label="Assessment pathway"><a href="#/assessment?task=screening" ${task==='screening'?'aria-current="page"':''}><span>01</span> Early risk screening <small>No kidney laboratory inputs</small></a><a href="#/assessment?task=biomarker" ${task==='biomarker'?'aria-current="page"':''}><span>02</span> Biomarker-assisted <small>With secondary blood measurements</small></a></div><div class="notice"><b>Research use only.</b> This estimates a single-visit kidney-marker outcome, not confirmed CKD or future disease. Your inputs remain in this browser tab’s memory.</div><div class="assessment-layout"><form id="assessment-form" novalidate><div class="form-heading"><h2>${task==='screening'?'Start with what you know.':'Add another layer of information.'}</h2><p>* Required. Leave unknown values blank; optional missing inputs use training-only imputation.</p></div><div id="fields"></div><div id="form-errors" role="alert" tabindex="-1"></div><div class="form-actions"><button class="button" type="submit">Generate research estimate ↗</button><button class="text-button" type="reset">Clear inputs</button></div></form><aside class="assessment-context"><div class="panel completeness"><span class="eyebrow">INPUT QUALITY</span><div><strong id="present-count">0</strong><span> / ${artifact.features.length} observed</span></div><div class="progress-track"><span id="present-progress"></span></div><p id="completeness-note">Missing values are not normal values.</p><ul id="quality-summary"></ul></div><div class="panel"><span class="eyebrow">BEHIND THIS ESTIMATE</span><h3>${modelName(selected.id)}</h3><p>Separate calibration and validation. Evaluation on ${selected.test.n.toLocaleString()} held-out participants.</p><dl class="mini-metrics"><div><dt>Test ROC-AUC</dt><dd>${number(selected.test.roc_auc)}</dd></div><div><dt>Test sensitivity</dt><dd>${percent(selected.test.sensitivity)}</dd></div><div><dt>Brier score</dt><dd>${number(selected.test.brier)}</dd></div></dl><a class="text-link" href="#/research">Inspect the evidence ↗</a></div><p class="small-copy">${artifact.version}<br>${escape(report.dataset)}<br>US adults; unweighted research sample.</p></aside></div><section id="assessment-result" aria-live="polite"></section></div>`;
  const form = root.querySelector('form'), fields = root.querySelector('#fields');
  const groups = [...new Set(artifact.features.map(name=>artifact.fields[name].group))];
  fields.innerHTML = groups.map((group,i)=>`<fieldset><legend><span>0${i+1}</span> ${group}</legend><div class="field-grid">${artifact.features.filter(name=>artifact.fields[name].group===group).map(name=>{
    const field = artifact.fields[name];
    const attributes = `id="${name}" name="${name}" aria-describedby="${name}-hint" ${field.required?'required':''}`;
    return `<div class="field"><label for="${name}">${field.label}${field.required?' <span aria-hidden="true">*</span>':''}</label>${field.choices?`<select ${attributes}><option value="">Unknown / not provided</option>${Object.entries(field.choices).map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}</select>`:`<div class="unit-input"><input ${attributes} type="number" step="any" min="${field.min}" max="${field.max}" inputmode="decimal" placeholder="Not provided"><span>${field.unit}</span></div>`}<small id="${name}-hint">${field.note || (field.choices ? 'Leave unknown responses unselected.' : `Input bounds: ${field.min}–${field.max} ${field.unit}. These are plausibility bounds, not healthy ranges.`)}</small></div>`;
  }).join('')}</div></fieldset>`).join('');
  const read = () => Object.fromEntries(artifact.features.map(name => [name, form.elements[name].validity.badInput ? NaN : form.elements[name].value.trim() === '' ? null : Number(form.elements[name].value)]));
  const update = () => {
    const quality = validateInput(artifact, read());
    root.querySelector('#present-count').textContent = quality.present;
    root.querySelector('#present-progress').style.width = `${100*quality.present/artifact.features.length}%`;
    root.querySelector('#quality-summary').innerHTML = quality.quality.filter(q=>['invalid','outside','unusual'].includes(q.state)).map(q=>`<li>${artifact.fields[q.feature].label}: ${q.message}</li>`).join('');
    root.querySelector('#completeness-note').textContent = `${artifact.features.length-quality.present} missing input${artifact.features.length-quality.present===1?'':'s'}. At least half of all inputs${task==='biomarker'?' and two biomarkers':''} must be supplied.`;
    return quality;
  };
  form.addEventListener('input', () => { update(); root.querySelector('#assessment-result').innerHTML = ''; });
  form.addEventListener('reset', () => { setTimeout(()=>{update(); root.querySelector('#assessment-result').innerHTML=''; root.querySelector('#form-errors').innerHTML=''; form.querySelectorAll('[aria-invalid]').forEach(el=>el.removeAttribute('aria-invalid'));},0); });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const input = read(), result = assess(artifact,input), errors = root.querySelector('#form-errors');
    form.querySelectorAll('[aria-invalid]').forEach(el=>el.removeAttribute('aria-invalid'));
    if (result.status === 'invalid') {
      errors.innerHTML = `<div class="error-box"><b>Review these inputs before continuing.</b><ul>${result.errors.map(e=>`<li>${escape(e)}</li>`).join('')}</ul></div>`;
      result.quality.filter(q=>['required','invalid'].includes(q.state)).forEach(q=>form.elements[q.feature].setAttribute('aria-invalid','true'));
      errors.focus(); return;
    }
    errors.innerHTML = '';
    const button = form.querySelector('[type=submit]'); button.disabled=true; button.textContent='Running local model…';
    await new Promise(resolve=>requestAnimationFrame(resolve));
    renderResult(root.querySelector('#assessment-result'), artifact, result, input, selected);
    button.disabled=false; button.textContent='Generate research estimate ↗';
    root.querySelector('#assessment-result').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  });
}
function renderResult(target, artifact, result, original, selected) {
  const warnings = result.quality.filter(q=>['imputed','outside','unusual'].includes(q.state));
  const top = result.explanations.slice(0,6), maximum = Math.max(...top.map(e=>Math.abs(e.probability_difference)),.001);
  target.innerHTML = `<div class="results-heading"><span class="eyebrow">YOUR RESEARCH ESTIMATE</span><h2>Read the estimate.<br>Keep the context.</h2></div><div class="result-grid"><div class="result-score"><span class="eyebrow">CALIBRATED MODEL OUTPUT</span><div class="probability">${percent(result.probability)}</div><h3>${result.outcome}</h3><p>Estimated probability of: ${escape(result.label)}.</p><p>Research threshold: ${percent(result.threshold)}. Being below this threshold does not rule out kidney disease.</p><div class="result-meta">${modelName(result.model)} · ${result.model_version}<br>${result.present}/${result.total} inputs observed · ${result.calibration}</div></div><div class="panel"><span class="eyebrow">INFLUENTIAL OBSERVED INPUTS</span><h3>What moved this model?</h3><p class="small-copy">${result.explanation_method}</p><div class="contributions">${top.map(e=>`<div><div><span>${artifact.fields[e.feature].label}</span><b>${e.probability_difference>=0?'+':''}${(e.probability_difference*100).toFixed(1)} pp</b></div><div class="contribution-track"><i class="${e.probability_difference<0?'negative':''}" style="width:${Math.abs(e.probability_difference)/maximum*100}%"></i></div><small>Observed ${e.observed}; training reference ${number(e.reference,2)}</small></div>`).join('')}</div></div></div>
    <div class="result-grid"><div class="panel"><span class="eyebrow">COMPLETENESS & RELIABILITY</span><h3>Keep these limitations in view.</h3><p>${warnings.length ? `${warnings.length} inputs were missing or flagged.`:'All inputs were supplied within the central observed ranges.'}</p><ul class="quality-list">${result.quality.map(q=>`<li><span>${artifact.fields[q.feature].label}</span><b class="quality-state ${q.state}">${q.state}</b><small>${q.message}</small></li>`).join('')}</ul><p class="small-copy">Marginal range checks cannot detect all unusual combinations. No validated individual confidence interval is available. Test PPV ${percent(selected.test.precision)} reflects test prevalence ${percent(selected.test.prevalence)}.</p></div><div class="panel scenario-panel"><span class="eyebrow">HYPOTHETICAL EXPLORATION</span><h3>Ask “what if?”</h3><p>Change one measurement while keeping the other inputs fixed. This explores model behavior, not a treatment effect or a recommendation.</p><label for="scenario-feature">Measurement</label><select id="scenario-feature"><option value="bp_systolic">Systolic blood pressure (mmHg)</option><option value="bmi">Body mass index (kg/m²)</option></select><label for="scenario-value">Hypothetical value</label><input id="scenario-value" type="number" step="any"><button class="button" id="scenario-run" type="button">Explore scenario ↗</button><div id="scenario-output" role="status"></div></div></div><details class="limitations" open><summary>Model limits and next steps</summary><ul>${result.limitations.map(l=>`<li>${escape(l)}</li>`).join('')}</ul><p>Review concerns and laboratory findings with a qualified healthcare professional. Repeat measurements and clinical context may be necessary. Do not change medication based on this estimate.</p></details>`;
  const selector = target.querySelector('#scenario-feature'), value = target.querySelector('#scenario-value');
  const setScenario = () => { const field=artifact.fields[selector.value];value.min=field.min;value.max=field.max;value.value=original[selector.value] ?? '';target.querySelector('#scenario-output').textContent=''; };
  selector.addEventListener('change',setScenario);setScenario();
  target.querySelector('#scenario-run').addEventListener('click',()=>{
    const output=target.querySelector('#scenario-output');
    if(value.value===''){output.textContent='Enter a hypothetical measurement.';return;}
    const scenario=assess(artifact,{...original,[selector.value]:Number(value.value)});
    output.textContent=scenario.status==='invalid'?scenario.errors.join(' '):`Hypothetical estimate: ${percent(scenario.probability)} (${scenario.probability-result.probability>=0?'+':''}${((scenario.probability-result.probability)*100).toFixed(1)} percentage points). This is not a causal effect.${scenario.quality.filter(q=>['outside','unusual'].includes(q.state)).map(q=>' '+artifact.fields[q.feature].label+': '+q.message+'.').join('')}`;
  });
}
