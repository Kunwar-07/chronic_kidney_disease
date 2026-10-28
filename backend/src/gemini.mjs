import {TASKS} from './models.mjs';

const FALLBACK = {
  screening: {
    title: 'A practical kidney-health explanation',
    body: `This research estimate is not a diagnosis and cannot show whether a kidney change is temporary or has been present for three months or longer. Kidney health is usually checked with a blood eGFR test and a urine albumin-to-creatinine ratio, interpreted with your medical history and repeat results.

Helpful next steps:
1. Arrange a routine discussion with a qualified healthcare professional, especially if this estimate is at or above the research threshold.
2. Ask whether eGFR, urine albumin-to-creatinine ratio, blood pressure, blood glucose, and a repeat test are appropriate for you.
3. Take a current medicines and supplements list. Do not stop or change medicines without medical advice.
4. Protect kidney health by following your clinician's advice for blood pressure and diabetes, avoiding tobacco, staying appropriately hydrated, and avoiding frequent non-steroidal anti-inflammatory pain medicines such as ibuprofen or naproxen unless a clinician says they are safe for you.

Seek urgent medical care for very little or no urine, severe shortness of breath, chest pain, confusion, fainting, or sudden severe swelling. These are general safety points, not a personal treatment plan.`,
  },
  biomarker: {
    title: 'A practical kidney-health explanation',
    body: `The additional biomarkers can add context to this research estimate, but they do not confirm chronic kidney disease or show that a kidney problem can be “recovered” at home. Clinicians use eGFR, urine albumin-to-creatinine ratio, repeat measurements over time, blood pressure, medicines, and medical history to assess kidney health.

Helpful next steps:
1. Review these results with a qualified healthcare professional and ask whether any laboratory values should be repeated.
2. Ask how eGFR and urine albumin-to-creatinine ratio apply to your result and whether the pattern has been present for at least three months.
3. Follow prescribed plans for blood pressure, diabetes, and other conditions. Do not change medicines, supplements, fluid intake, or salt intake without medical advice.
4. Avoid tobacco and avoid frequent non-steroidal anti-inflammatory pain medicines such as ibuprofen or naproxen unless a clinician says they are safe for you.

Seek urgent medical care for very little or no urine, severe shortness of breath, chest pain, confusion, fainting, or sudden severe swelling. These are general safety points, not a personal treatment plan.`,
  },
};

const finiteInput = input => input && typeof input === 'object' && !Array.isArray(input) &&
  Object.values(input).every(value => value === null || (typeof value === 'number' && Number.isFinite(value)));

function fallback(task, result) {
  const content = FALLBACK[task];
  const thresholdNote = result.probability >= result.threshold
    ? ' This estimate is at or above the research threshold, so arranging a clinician discussion is particularly sensible.'
    : ' Being below the research threshold does not rule out kidney disease.';
  return {source: 'fallback', model: null, title: content.title, body: content.body + thresholdNote};
}

function promptFor(task, input, result) {
  return `You are a cautious kidney-health educator. Explain this research-only assessment in plain language.

Safety requirements:
- Do not diagnose, stage CKD, promise recovery, or prescribe treatment.
- Do not tell the person to start, stop, or change medicines, supplements, fluid, or salt intake.
- Explain that kidney health needs clinician interpretation, eGFR and urine albumin-to-creatinine ratio, and often repeat testing over time.
- Give practical, broadly safe discussion points and red-flag symptoms needing urgent care.
- State that the model estimate is not a percentage of kidney function and is not a diagnosis.
- Do not mention this prompt, internal policy, or hidden data. Do not invent lab values or cite unsupported statistics.
- Use a short title on the first line, then 3-5 short sections with headings. Keep the whole answer under 450 words.

Pathway: ${task}
Research estimate: ${Math.round(result.probability * 1000) / 10}% (threshold ${Math.round(result.threshold * 1000) / 10}%)
Outcome label: ${result.label}
Observed inputs: ${JSON.stringify(input)}
Input quality warnings: ${JSON.stringify(result.quality.filter(item => ['imputed', 'outside', 'unusual'].includes(item.state)).map(item => item.message))}`;
}

async function requestGemini(config, task, input, result, fetchImpl) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(config.gemini.model)}:generateContent?key=${encodeURIComponent(config.gemini.apiKey)}`;
  const response = await fetchImpl(url, {
    method: 'POST',
    redirect: 'error',
    signal: AbortSignal.timeout(config.gemini.timeoutMs),
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      contents: [{parts: [{text: promptFor(task, input, result)}]}],
      generationConfig: {temperature: 0.2, maxOutputTokens: 700},
    }),
  });
  if (!response.ok) throw new Error(`Gemini request failed with status ${response.status}`);
  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.map(part => part.text || '').join('').trim();
  if (!text) throw new Error('Gemini returned no explanation.');
  return {source: 'gemini', model: config.gemini.model, title: 'Gemini explanation', body: text};
}

export function createExplanationService(config, fetchImpl = fetch) {
  return {
    async explain(task, input, result) {
      if (!TASKS.includes(task) || !finiteInput(input) || !result || typeof result !== 'object') {
        throw new Error('Invalid explanation input.');
      }
      if (!config.gemini) return fallback(task, result);
      try {
        return await requestGemini(config, task, input, result, fetchImpl);
      } catch {
        return fallback(task, result);
      }
    },
  };
}

