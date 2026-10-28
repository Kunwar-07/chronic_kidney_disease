import {pageHeading, errorState} from './ui.mjs';
import {renderAssessment} from './assessment.mjs';
import {renderResearch} from './research.mjs';
import {mountMotion} from './motion.mjs';

const main = document.querySelector('main');
const arrow = '<span aria-hidden="true">↗</span>';
function home() {
  return `<section class="hero">
    <div class="hero-top"><span class="eyebrow"><i class="status-dot"></i> KIDNEY HEALTH, THROUGH A RESEARCH LENS</span><span class="edition">RESEARCH EDITION / 02</span></div>
    <div class="hero-visual"><img src="./assets/kidney-hero.png" alt="Conceptual glass kidney with branching aqua vessels" fetchpriority="high"><span class="visual-coordinate">01 / RENAL INTELLIGENCE</span><div class="visual-tag"><span class="sparkle">✳</span><span>Small signals.<br>A clearer picture.</span></div></div>
    <div class="hero-copy"><h1>Better insight.<br>Earlier in the<br><em>kidney journey.</em></h1><p>Explore the signals behind kidney health with explainable machine learning and research you can see.</p><div class="actions"><a class="button" href="#/assessment">Explore assessment ${arrow}</a><a class="text-link" href="#/research">Inside the research ${arrow}</a></div></div>
    <div class="hero-foot"><a href="#/?section=introduction" aria-label="Scroll to introduction">↓</a></div>
  </section>
  <section class="intro section" id="introduction"><div class="section-kicker"><span class="eyebrow">01 / THE BIGGER PICTURE</span><span class="tiny-cross">+</span></div><div class="intro-layout"><h2>Kidney health has a story.<br><span class="muted">Let’s make the signals<br>easier to understand.</span></h2><div class="intro-side"><div class="orbital" aria-hidden="true"><span></span><span></span><span></span></div><p>Nephra is the research interface for the CKD Early Warning AI Framework. It brings available health information, transparent models, and their limitations into one considered experience.</p><a class="text-link" href="#/methodology">Meet the methodology ${arrow}</a></div></div></section>
  <section class="pathways section"><div class="section-head"><span class="eyebrow">02 / TWO WAYS TO EXPLORE</span><h2>Different inputs.<br>A shared commitment to clarity.</h2></div><div class="pathway-grid"><a href="#/assessment?task=screening" class="pathway-card"><div class="card-top"><span>01 / WITHOUT KIDNEY LABS</span>${arrow}</div><div class="line-art" aria-hidden="true"><svg viewBox="0 0 320 100"><path d="M0 55H55l15-16 18 38 17-68 22 89 20-43H320"/></svg></div><h3>Start with the<br>signals you know.</h3><p>Explore a screening model using demographics, history, body measurements and blood pressure.</p><span class="pill">Early risk screening</span></a><a href="#/assessment?task=biomarker" class="pathway-card blue"><div class="card-top"><span>02 / WITH SECONDARY LABS</span>${arrow}</div><div class="molecule" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><h3>A little more data.<br>A different perspective.</h3><p>Add secondary blood biomarkers. The measurements defining the research outcome stay out of the predictors.</p><span class="pill">Biomarker-assisted assessment</span></a></div><p class="section-note">Both estimate a single-visit research outcome. Neither confirms CKD, establishes chronicity, or predicts progression.</p></section>
  <section class="process section" id="how-it-works"><div class="section-head"><span class="eyebrow">03 / FROM INPUT TO INSIGHT</span><h2>Understand every step.</h2></div><div class="steps">${[['01','Bring what you know','Choose a pathway and provide the information you have. Missing is never treated as normal.'],['02','Check the context','Review units, completeness and inputs beyond the observed training range.'],['03','Explore an estimate','A saved model runs locally in your browser. Health inputs stay in memory.'],['04','See the whole picture','Read model influences, validation evidence and limitations alongside the estimate.']].map(([n,t,d])=>`<article><span class="step-number">${n}</span><h3>${t}</h3><p>${d}</p></article>`).join('')}</div></section>
  <section class="capabilities section"><div class="section-head"><h2>A closer look.<br>From individual signals<br>to the science behind them.</h2><p>Purposeful tools for exploring kidney-health research. Evidence first, at every scale.</p></div><div class="capability-grid">${[
    ['01','Understand your inputs','Missing-data awareness','assessment','data'],['02','Look beneath the estimate','Model explanations','assessment','waves'],['03','See the evidence','Validation & calibration','research','curve'],['04','Compare perspectives','Model comparison','research','bars'],['05','Know the boundaries','Research methodology','methodology','mesh'],['06','Follow kidney health','Measurement context','health','kidney']
  ].map(([n,t,s,link,style])=>`<a class="capability ${style}" href="#/${link}"><div><span>${n}</span>${arrow}</div><div class="capability-art" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div><h3>${t}</h3><p>${s}</p></a>`).join('')}</div></section>
  <section class="research-story section"><div><span class="eyebrow">04 / OPEN TO SCRUTINY</span><h2>Good research<br>shows its workings.</h2><p>Official data. Separate validation. Visible limitations. Explore exactly how an estimate was built, where it was evaluated, and what it cannot tell you.</p><a class="button light" href="#/research">Open the research explorer ${arrow}</a></div><div class="research-index"><a href="#/methodology"><span>01</span> Traceable NHANES data ${arrow}</a><a href="#/research"><span>02</span> Calibration & operating thresholds ${arrow}</a><a href="#/research"><span>03</span> An untouched test partition ${arrow}</a><a href="#/methodology"><span>04</span> Reproducible experiments ${arrow}</a><p>No invented accuracy claims. No hidden clinical promises.</p></div></section>
  <section class="closing section"><span class="eyebrow">CURIOUS ABOUT THE SIGNALS?</span><h2>Begin with information.<br>Leave with perspective.</h2><a class="button" href="#/assessment">Explore your assessment ${arrow}</a><p>For research and education. Discuss health concerns with a qualified professional.</p></section>`;
}
function methodology() {
  return `<div class="page-shell">${pageHeading('THE SCIENCE / METHODOLOGY','Transparent by design.','A reproducible cross-sectional research workflow, with a clear boundary between a model estimate and a diagnosis.')}<div class="method-layout"><aside class="method-index"><a href="#/methodology?section=data">01 · Data & provenance</a><a href="#/methodology?section=endpoint">02 · Outcome & features</a><a href="#/methodology?section=validation">03 · Evaluation</a><a href="#/methodology?section=reproduce">04 · Reproduce</a></aside><div class="prose">
    <section id="data"><span class="eyebrow">01 / DATA & PROVENANCE</span><h2>Official records. Explicit inclusion.</h2><p>Training uses official NHANES August 2021–August 2023 demographics, biochemistry, urine albumin and creatinine, body measurements, oscillometric blood pressure, diabetes and smoking questionnaires. Components are joined one-to-one using SEQN. Adults aged 18+ with both kidney measurements available are eligible.</p><p>Earlier NHANES 2017–2018 data are held separately for a dataset-shift stress test. They are not pooled with training. Urine albumin and biochemistry methods changed across cycles; an albumin-bridging sensitivity analysis accompanies the as-published evaluation. This is not hospital or prospective clinical validation.</p><p>Original local NHANES and UCI files remain preserved. UCI’s small hospital convenience sample is not merged with NHANES. Its CSV and ARFF are alternate representations of the same cohort.</p><div class="source-links"><a href="https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Cycle=2021-2023" target="_blank" rel="noreferrer">CDC data & codebooks ↗</a><a href="https://www.cdc.gov/nchs/policy/data-user-agreement.html" target="_blank" rel="noreferrer">NCHS data-use terms ↗</a><a href="https://archive.ics.uci.edu/dataset/336/chronic+kidney+disease" target="_blank" rel="noreferrer">UCI · CC BY 4.0 ↗</a></div></section>
    <section id="endpoint"><span class="eyebrow">02 / THE RESEARCH QUESTION</span><h2>A single-visit outcome.<br>Not a future diagnosis.</h2><p>The positive label is eGFR below 60 mL/min/1.73 m² or UACR at least 30 mg/g at one survey visit. eGFR uses the 2021 CKD-EPI creatinine equation; UACR uses urine albumin (µg/mL) divided by urine creatinine (mg/dL), multiplied by 100. Public age is top-coded at 80, which limits equation accuracy for older adults.</p><div class="formula">142 × min(SCr/κ, 1)<sup>α</sup> × max(SCr/κ, 1)<sup>−1.200</sup> × 0.9938<sup>age</sup> × sex factor</div><p>SCr is mg/dL. κ = 0.7 female / 0.9 male; α = −0.241 female / −0.302 male; sex factor = 1.012 female / 1 male. This equation is documented by <a href="https://www.niddk.nih.gov/research-funding/research-programs/kidney-clinical-research-epidemiology/laboratory/glomerular-filtration-rate-equations/adults" target="_blank" rel="noreferrer">NIDDK</a>.</p><p>Screening excludes kidney laboratory predictors. The biomarker pathway adds BUN, serum albumin, phosphorus, bicarbonate, calcium and uric acid. Both exclude creatinine, eGFR, UACR, urine albumin and urine creatinine. Age and sex remain mathematically coupled to the eGFR-defined endpoint. Other biomarkers may reflect existing impairment, so these are contemporaneous associations.</p></section>
    <section id="validation"><span class="eyebrow">03 / EVALUATION</span><h2>Keep the test set untouched.</h2><p>A fixed participant split allocates approximately 60% to training, 10% to calibration, 10% to validation and 20% to test. Three-fold training-only cross-validation selects hyperparameters. Imputation, scaling and encoding are fitted within each training fold. No observations are removed by an automatic outlier detector, and no synthetic resampling is used.</p><p>Logistic regression, random forest and histogram gradient boosting are compared. Sigmoid calibration uses the separate calibration partition. The selected model maximizes validation average precision. The operating threshold maximizes specificity subject to validation sensitivity of at least 80%; this is a research criterion, not an established clinical threshold.</p><p>Test results include discrimination, predictive values, calibration, confusion matrices and 200-replicate bootstrap intervals. Subgroups need at least 50 observations and 10 in each class. Training and evaluation are unweighted. NHANES weights, strata and PSUs are preserved, but these experiments and their IID confidence intervals must not be interpreted as nationally representative estimates.</p><p>Local explanations replace one observed feature with its training reference and measure the change in output. These differences do not add to the prediction, are not SHAP values, and do not estimate causal effects. Marginal range checks cannot detect every out-of-distribution case.</p></section>
    <section id="reproduce"><span class="eyebrow">04 / REPRODUCIBILITY</span><h2>Run it locally.</h2><p>From the repository root, create a virtual environment and install the research requirements. Each run has a unique directory and refuses to overwrite an existing experiment.</p><pre><code>python -m venv .venv
.venv/Scripts/python -m pip install -r ml/requirements-research-lock.txt
.venv/Scripts/python -m ml.research.acquire --cycle 2021-2023
.venv/Scripts/python -m ml.research.acquire --cycle 2017-2018
.venv/Scripts/python -m ml.research.train --run-id my-experiment
.venv/Scripts/python -m unittest discover -s ml/research/tests
cd frontend
npm test
npm run build
npm run dev</code></pre><p>The training workflow exports model parameters, schema, aggregate evaluation and the shared inference runtime to the frontend. Browser inputs are kept in memory and cleared on navigation; they are not sent to a prediction service or stored in browser storage.</p><a class="button" href="#/research">Inspect actual results ↗</a></section>
    </div></div></div>`;
}
function health() {
  return `<div class="page-shell">${pageHeading('KIDNEY HEALTH / CONTEXT','One measurement is<br>part of a bigger picture.','Kidney assessment combines laboratory findings, history, repeat measurements and professional interpretation.')}<div class="health-grid"><article class="panel"><span class="eyebrow">FILTRATION</span><h2>eGFR</h2><p>Estimated glomerular filtration rate is an estimate of kidney filtration. The creatinine-based equation uses serum creatinine, age and sex. It is an estimate with limitations, not a direct measurement.</p><span class="pill">mL/min/1.73 m²</span></article><article class="panel"><span class="eyebrow">URINE ALBUMIN</span><h2>UACR</h2><p>The urine albumin-to-creatinine ratio measures albumin relative to creatinine in a urine sample. It provides a different view of kidney health from eGFR.</p><span class="pill">mg/g</span></article></div><div class="trend-empty"><span class="eyebrow">A VIEW OVER TIME</span><h2>Trends need real observations.</h2><div class="empty-trend" aria-hidden="true"><i></i><i></i><i></i><span>No recorded measurements</span></div><p>This project has cross-sectional survey data. There is no patient timeline or validated progression model to display. CKD assessment requires evidence of persistent abnormalities over more than three months and clinical interpretation.</p><a class="text-link" href="https://www.niddk.nih.gov/health-information/professionals/clinical-tools-patient-management/kidney-disease/identify-manage-patients/evaluate-ckd" target="_blank" rel="noreferrer">Read NIDDK’s evaluation guidance ↗</a></div><section class="health-bottom"><h2>Bring questions to a professional.</h2><p>These experimental estimates cannot confirm or rule out CKD. Discuss symptoms, existing conditions and laboratory results with a qualified healthcare professional. This interface does not prescribe treatment or medication changes.</p><a class="button" href="#/assessment">Explore the research pathways ↗</a></section></div>`;
}
let routeToken = 0;
let mountedPage;
let motion;
function moveToSection(id, smooth = false) {
  const target = document.getElementById(id);
  if (!target || !main.contains(target)) return false;
  motion?.revealWithin(target);
  target.setAttribute('tabindex', '-1');
  target.focus({preventScroll:true});
  target.scrollIntoView({behavior:smooth && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'instant'});
  return true;
}
async function route() {
  const token = ++routeToken;
  const [path, query] = (location.hash.slice(1) || '/').split('?');
  const params = new URLSearchParams(query);
  const page = path.split('/')[1] || 'home';
  document.body.dataset.page = page;
  document.querySelectorAll('[data-nav]').forEach(el => { if(el.dataset.nav === page) el.setAttribute('aria-current','page'); else el.removeAttribute('aria-current'); });
  document.querySelector('#navigation').classList.remove('open');
  document.querySelector('.menu-toggle').setAttribute('aria-expanded','false');
  document.querySelector('.menu-toggle').setAttribute('aria-label','Open navigation');
  // Section links keep the mounted page and its reveal state intact.
  if (mountedPage === page && ['home','methodology'].includes(page)) {
    if (!moveToSection(params.get('section'), true)) {
      window.scrollTo({top:0, behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
      main.focus({preventScroll:true});
    }
    return;
  }
  motion?.destroy();
  motion = undefined;
  mountedPage = undefined;
  if (page === 'home') main.innerHTML = home();
  else if (page === 'methodology') main.innerHTML = methodology();
  else if (page === 'health') main.innerHTML = health();
  else if (page === 'assessment' || page === 'research') {
    main.innerHTML = '<div class="loading" role="status"><span></span>Loading saved research artifacts…</div>';
    try {
      const content = document.createElement('div');
      if (page === 'assessment') await renderAssessment(content, params.get('task') === 'biomarker' ? 'biomarker' : 'screening');
      else await renderResearch(content);
      if (token !== routeToken) return;
      main.replaceChildren(content);
    } catch(error) { if (token === routeToken) main.innerHTML = errorState(error.message); }
  } else main.innerHTML = `${pageHeading('404','This page isn’t here.','Use the navigation to return to the research interface.')}<a class="button" href="#/">Back to overview</a>`;
  if (token !== routeToken) return;
  document.title = `${({home:'Kidney health research', assessment:'Assessment', research:'Research explorer', methodology:'Methodology', health:'Kidney health'}[page] || 'Page not found')} · Nephra`;
  mountedPage = page;
  if (!moveToSection(params.get('section'))) {
    window.scrollTo({top:0, behavior:'instant'});
    main.focus({preventScroll:true});
  }
  motion = mountMotion(main);
}
document.querySelector('.menu-toggle').addEventListener('click', event => {
  const open = document.querySelector('#navigation').classList.toggle('open');
  event.currentTarget.setAttribute('aria-expanded', String(open));
  event.currentTarget.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
});
window.addEventListener('hashchange', route);
// Repeated section links do not emit hashchange; they should still navigate.
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#/"]');
  if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  if (link?.getAttribute('href') === location.hash && ['home','methodology'].includes(mountedPage)) {
    event.preventDefault();
    route();
  }
});
document.querySelector('.skip-link').addEventListener('click', event => { event.preventDefault(); main.focus(); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.querySelector('#navigation').classList.contains('open')) {
    document.querySelector('#navigation').classList.remove('open');
    const toggle = document.querySelector('.menu-toggle');
    toggle.setAttribute('aria-expanded','false'); toggle.setAttribute('aria-label','Open navigation'); toggle.focus();
  }
});
route();
