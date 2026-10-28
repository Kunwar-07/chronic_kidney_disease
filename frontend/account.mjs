import {client} from './api.mjs';
import {reportHTML, downloadReport} from './report.mjs';
import {escape, percent, loadJSON} from './ui.mjs';

export async function renderLogin(target, connectionError = '') {
  target.innerHTML = `<div class="page-shell login-shell"><section class="panel account-panel"><span class="eyebrow">WELCOME TO NEPHRA</span><h1>Your account.<br>All your assessments.</h1><p>Sign in once to enter. Every assessment you submit is automatically saved to your private history.</p><form id="login-form"><div class="field"><label for="login-email">Email</label><input id="login-email" name="email" type="email" autocomplete="email" required></div><div class="field"><label for="login-password">Password</label><input id="login-password" name="password" type="password" autocomplete="current-password" minlength="6" required></div><div class="account-actions"><button class="button" type="submit" disabled>Sign in</button><button class="text-button" id="login-mode" type="button">New here? Create account</button></div></form><p class="small-copy">You stay signed in on this browser until you sign out or your session is revoked. No separate database account is needed.</p><p id="login-status" role="status"></p></section></div>`;
  const form = target.querySelector('form'), status = target.querySelector('#login-status'), submit = form.querySelector('[type=submit]'), toggle = form.querySelector('#login-mode');
  let signup = false, busy = false;
  status.textContent = connectionError;
  toggle.addEventListener('click', () => {
    signup = !signup;
    submit.textContent = signup ? 'Create account' : 'Sign in';
    toggle.textContent = signup ? 'Already registered? Sign in' : 'New here? Create account';
    form.elements.password.autocomplete = signup ? 'new-password' : 'current-password';
    status.textContent = '';
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    busy = true; submit.disabled = toggle.disabled = true;
    status.textContent = signup ? 'Creating your account…' : 'Signing in…';
    try {
      const email = form.elements.email.value.trim(), password = form.elements.password.value;
      if (signup) {
        if (!await client.signUp(email,password)) throw new Error('Email confirmation is still enabled in the project settings. The site owner needs to finish account setup.');
      } else await client.signIn(email,password);
      form.elements.password.value = '';
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; submit.disabled = toggle.disabled = false; }
  });
  try { await client.configure(); submit.disabled = false; }
  catch (error) { status.textContent = `${error.message} Reload after the backend is available.`; }
}

export async function mountHistory(target) {
  let historyVersion = 0;
  target.className = 'panel account-panel';
  target.innerHTML = `<span class="eyebrow">YOUR SAVED ASSESSMENTS</span><p>Every assessment you submit is saved automatically.</p><button class="text-button" id="refresh-history" type="button">Refresh saved assessments</button><div id="assessment-history"></div>`;
  const history = target.querySelector('#assessment-history');
  const refreshHistory = async () => {
    const version = ++historyVersion;
    if (!client.getUser()) { history.innerHTML = ''; return; }
    history.textContent = 'Loading saved assessments…';
    try {
      const page = await client.listAssessments();
      if (version !== historyVersion || !client.getUser()) return;
      history.innerHTML = `<h3>Recent saved assessments</h3>${page.assessments.length ? `<ul class="saved-list">${page.assessments.map(row =>
        `<li><span>${escape(row.task === 'biomarker' ? 'Biomarker-assisted' : 'Screening')} · ${escape(new Date(row.created_at).toLocaleString())} · ${percent(row.probability)}</span><small>Record ID: ${escape(row.id)}</small><button class="text-button history-view" data-record="${escape(row.id)}" type="button">View full report</button><button class="text-button history-export" data-record="${escape(row.id)}" type="button">Export report</button></li>`).join('')}</ul>` : '<p>No saved assessments yet. Your next submission will appear here.</p>'}`;
    } catch (error) {
      if (version !== historyVersion) return;
      history.textContent = `Could not load saved assessments: ${error.message}`;

    }
  };
  history.addEventListener('click', async event => {
    const button = event.target.closest('.history-export, .history-view');
    if (!button) return;
    const owner = client.getUser()?.id;
    button.disabled = true; button.textContent = 'Preparing report…';
    try {
      const saved = await client.getAssessment(button.dataset.record);
      const artifact = await loadJSON(`${saved.task}.json`);
      if (!target.isConnected || client.getUser()?.id !== owner) return;
      const html = reportHTML(artifact, saved, client.getUser());
      if (button.classList.contains('history-view')) {
        const result = target.closest('.assessment-page').querySelector('#assessment-result');
        result.innerHTML = `<section class="full-report"><div class="report-actions"><button class="button saved-download" type="button">Download full report ↧</button><button class="text-button saved-print" type="button">Print / Save as PDF</button></div>${html}</section>`;
        result.querySelector('.saved-download').addEventListener('click', () => downloadReport(html, saved.id));
        result.querySelector('.saved-print').addEventListener('click', () => window.print());
        result.scrollIntoView({behavior:'instant'});
        button.textContent = 'View full report';
      } else {
        downloadReport(html, saved.id); button.textContent = 'Export report';
      }
    } catch (error) { button.textContent = `Export failed: ${error.message}. Retry`; }
    finally { button.disabled = false; }
  });
  target.querySelector('#refresh-history').addEventListener('click', refreshHistory);
  await refreshHistory();
  return {refreshHistory};
}
