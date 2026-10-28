import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {assess, score, validateInput} from '../data/runtime.mjs';
for (const task of ['screening','biomarker']) {
  const artifact=JSON.parse(await fs.readFile(new URL(`../data/${task}.json`,import.meta.url)));
  const fixtures=JSON.parse(await fs.readFile(new URL(`../data/${task}-parity.json`,import.meta.url)));
  test(`${task}: Python and JS predictions agree for exported synthetic fixtures`,()=>{
    for(const row of fixtures) assert.ok(Math.abs(score(artifact,row.input)-row.expected)<1e-10);
  });
  test(`${task}: valid input executes the trained model and yields model-derived explanations`,()=>{
    const result=assess(artifact,fixtures[0].input);
    assert.equal(result.status,'ok');
    assert.equal(result.probability,score(artifact,fixtures[0].input));
    for(const e of result.explanations) assert.ok(Math.abs(e.probability_difference-(result.probability-score(artifact,{...fixtures[0].input,[e.feature]:e.reference})))<1e-12);
  });
  test(`${task}: missing and invalid inputs fail explicitly`,()=>{
    assert.equal(assess(artifact,{}).status,'invalid');
    for(const value of [NaN,Infinity,-1,120,'55',true]) assert.equal(assess(artifact,{...fixtures[0].input,age:value}).status,'invalid');
    assert.equal(assess(artifact,{...fixtures[0].input,sex:2}).status,'invalid');
    assert.equal(assess(artifact,{...fixtures[0].input,egfr:95}).status,'invalid');
    assert.equal(assess(artifact,{...fixtures[0].input,bp_systolic:80,bp_diastolic:90}).status,'invalid');
  });
  test(`${task}: missing differs from zero and inputs are not mutated`,()=>{
    const input={...fixtures[0].input,diabetes:null};const before=structuredClone(input);
    const result=assess(artifact,input);assert.deepEqual(input,before);
    assert.equal(result.quality.find(q=>q.feature==='diabetes').state,'imputed');
    assert.equal(assess(artifact,{...input,diabetes:0}).quality.find(q=>q.feature==='diabetes').state,'observed');
  });
  test(`${task}: marginal distribution flags are visible`,()=>{
    const quality=validateInput(artifact,{...fixtures[0].input,bmi:99});
    assert.equal(quality.quality.find(q=>q.feature==='bmi').state,'outside');
  });
}
test('schema and ML-owned runtime stay synchronized',async()=>{
  const a=await fs.readFile(new URL('../data/runtime.mjs',import.meta.url),'utf8');
  const b=await fs.readFile(new URL('../../ml/research/runtime.mjs',import.meta.url),'utf8');
  assert.equal(a,b);
});
test('selected models are selected on validation AP, not test results',async()=>{
  const report=JSON.parse(await fs.readFile(new URL('../data/report.json',import.meta.url)));
  for(const task of Object.values(report.tasks)) {
    const best=task.models.reduce((a,b)=>a.validation.average_precision>b.validation.average_precision?a:b);
    assert.equal(task.selected,best.id);
  }
});
