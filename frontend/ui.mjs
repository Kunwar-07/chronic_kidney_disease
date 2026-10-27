export const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number = (value, digits=3) => value === null || value === undefined ? '—' : Number(value).toFixed(digits);
export const percent = value => value === null || value === undefined ? '—' : `${(100 * value).toFixed(1)}%`;
export async function loadJSON(file) {
  const response = await fetch(`./data/${file}`, {cache:'no-store'});
  if (!response.ok) throw new Error(`Saved research artifact unavailable (${response.status}). Run the documented ML workflow to export it.`);
  return response.json();
}
export const modelName = id => ({logistic:'Logistic regression', forest:'Random forest', hist_gradient:'Histogram gradient boosting'}[id] || id);
export const pageHeading = (eyebrow, title, description) => `<div class="page-heading"><span class="eyebrow">${eyebrow}</span><h1>${title}</h1><p>${description}</p></div>`;
export const errorState = message => `<div class="empty-state"><span class="eyebrow">ARTIFACT UNAVAILABLE</span><h2>Research results aren’t loaded.</h2><p>${escape(message)}</p><a class="button" href="#/methodology">View reproduction instructions ↗</a></div>`;
