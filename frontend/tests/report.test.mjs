import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {assess} from '../data/runtime.mjs';
import {reportHTML,exportDocument} from '../report.mjs';
for (const task of ['screening','biomarker']) {
  const artifact = JSON.parse(await fs.readFile(new URL(`../data/${task}.json`,import.meta.url)));
  const fixtures = JSON.parse(await fs.readFile(new URL(`../data/${task}-parity.json`,import.meta.url)));
  test(`${task}: report preserves actual saved results, inputs and provenance`,()=> {
    const input = {...fixtures[0].input,diabetes:null};
    const result = assess(artifact,input);
    const before = JSON.stringify(result);
    const html = reportHTML(artifact,{id:'record-123',created_at:'2026-10-25T12:00:00Z',input,result},{email:'<script>alert(1)</script>'});
    assert.match(html, /record-123/); assert.match(html,/Not provided/); assert.match(html,/imputed/);
    assert.ok(html.includes((result.probability*100).toFixed(1)+'%'));
    assert.ok(html.includes(result.probability >= result.threshold ? 'at or above' : 'below'));
    assert.match(html,/not the percentage of kidney function/);
    assert.match(html,/differences do not add up/);
    assert.match(html,/&lt;script&gt;/); assert.doesNotMatch(html,/<script>/);
    for (const name of artifact.features) assert.ok(html.includes(artifact.fields[name].label));
    assert.equal(JSON.stringify(result),before);
    const doc = exportDocument(html);
    assert.ok(doc.includes(html)); assert.match(doc,/window.print/); assert.match(doc,/@media print/);
    assert.doesNotMatch(doc,/<script src|<link.*stylesheet/);
  });
}
