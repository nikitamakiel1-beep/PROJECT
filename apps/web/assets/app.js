const DEFAULT_CONFIG = Object.freeze({
  demoMode: true,
  intakeEndpoint: "",
  consentVersion: "assessment-v1-2026-07",
  requestTimeoutMs: 12000
});

const config = Object.freeze({ ...DEFAULT_CONFIG, ...(window.VENTURE_CONFIG || {}) });
const elements = {
  language: document.getElementById('language'),
  theme: document.getElementById('theme'),
  menu: document.getElementById('menu'),
  nav: document.getElementById('primary-nav'),
  serviceGrid: document.getElementById('service-grid'),
  serviceSelect: document.getElementById('service-select'),
  demoGrid: document.getElementById('demo-grid'),
  form: document.getElementById('assessment-form'),
  submit: document.getElementById('submit-button'),
  status: document.getElementById('form-status'),
  modeBanner: document.getElementById('mode-banner'),
  consentLabel: document.getElementById('consent-label'),
  problem: document.querySelector('textarea[name="problem"]'),
  problemCount: document.getElementById('problem-count')
};

let language = localStorage.getItem('igv-language') === 'es' ? 'es' : 'en';
let translations = null;
let services = null;
let demonstrations = null;
let ready = false;

async function fetchJson(path) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Could not load ${path}: ${response.status}`);
  return response.json();
}

function assertDataContracts() {
  const languages = Object.keys(translations);
  if (languages.length !== 2 || !languages.includes('en') || !languages.includes('es')) throw new Error('Expected English and Spanish translations.');
  const englishKeys = Object.keys(translations.en).sort().join('|');
  const spanishKeys = Object.keys(translations.es).sort().join('|');
  if (englishKeys !== spanishKeys) throw new Error('Translation keys are not equivalent.');
  if (!Array.isArray(services) || !services.some(service => service.status === 'active')) throw new Error('No active services are available.');
  for (const service of services) {
    for (const locale of languages) {
      if (!service.name?.[locale] || !service.description?.[locale] || !service.ideal_for?.[locale]) throw new Error(`Service ${service.code} is missing ${locale} content.`);
      if (!Array.isArray(service.deliverables?.[locale]) || service.deliverables[locale].length < 1) throw new Error(`Service ${service.code} has no ${locale} deliverables.`);
    }
  }
}

async function loadData() {
  [translations, services, demonstrations] = await Promise.all([
    fetchJson('assets/translations.json'),
    fetchJson('../../schemas/services.json'),
    fetchJson('assets/demonstrations.json')
  ]);
  assertDataContracts();
  ready = true;
  render();
}

function t(key) { return translations?.[language]?.[key] || key; }

function render() {
  document.documentElement.lang = language;
  document.title = t('page_title');
  document.querySelector('meta[name="description"]').setAttribute('content', t('meta_description'));
  document.querySelectorAll('[data-i18n]').forEach(element => {
    const key = element.dataset.i18n;
    if (translations[language][key]) element.textContent = translations[language][key];
  });
  elements.language.textContent = language === 'en' ? 'ES' : 'EN';
  elements.language.setAttribute('aria-label', t('language_label'));
  elements.menu.querySelector('.sr-only').textContent = elements.menu.getAttribute('aria-expanded') === 'true' ? t('menu_close_label') : t('menu_label');
  renderThemeControl();
  renderServices();
  renderDemonstrations();
  renderMode();
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function renderServices() {
  const active = services.filter(service => service.status === 'active');
  elements.serviceGrid.replaceChildren();
  elements.serviceSelect.replaceChildren(createElement('option', '', t('service_placeholder')));
  elements.serviceSelect.firstElementChild.value = '';
  for (const service of active) {
    const article = createElement('article', 'service-card');
    article.dataset.serviceCode = service.code;
    const meta = createElement('div', 'service-meta');
    meta.append(createElement('span', 'badge', service.code), createElement('span', 'badge', `${service.delivery_days} ${t('days')}`));
    const title = createElement('h3', '', service.name[language]);
    const description = createElement('p', 'service-description', service.description[language]);
    const ideal = createElement('p', 'service-ideal', service.ideal_for[language]);
    const includesLabel = createElement('strong', '', t('includes'));
    const list = createElement('ul');
    service.deliverables[language].forEach(item => list.append(createElement('li', '', item)));
    const price = createElement('div', 'price', `${t('from')} €${service.price_eur}`);
    price.append(createElement('small', '', service.revision_limit === 1 ? t('one_revision') : ''));
    article.append(meta, title, description, ideal, includesLabel, list, price);
    elements.serviceGrid.append(article);
    const option = createElement('option', '', service.name[language]);
    option.value = service.code;
    elements.serviceSelect.append(option);
  }
}

function renderDemonstrations() {
  elements.demoGrid.replaceChildren();
  for (const demo of demonstrations) {
    const article = createElement('article', 'demo-card');
    article.append(createElement('span', 'badge', t('demo_badge')));
    article.append(createElement('h3', '', demo.title[language]));
    article.append(createElement('p', '', demo.description[language]));
    article.append(createElement('strong', '', t('preview_includes')));
    const list = createElement('ul');
    demo.includes[language].forEach(item => list.append(createElement('li', '', item)));
    article.append(list);
    elements.demoGrid.append(article);
  }
}

function isLiveMode() {
  return config.demoMode === false && typeof config.intakeEndpoint === 'string' && config.intakeEndpoint.startsWith('https://');
}

function renderMode() {
  const live = isLiveMode();
  const heading = elements.modeBanner.querySelector('strong');
  const body = elements.modeBanner.querySelector('span');
  heading.textContent = t(live ? 'live_mode_title' : 'demo_mode_title');
  body.textContent = t(live ? 'live_mode_body' : 'demo_mode_body');
  elements.consentLabel.textContent = t(live ? 'field_consent' : 'field_demo_acknowledgement');
  elements.submit.textContent = t(live ? 'submit_live' : 'submit');
}

function renderThemeControl() {
  const dark = document.documentElement.dataset.theme === 'dark';
  elements.theme.setAttribute('aria-pressed', String(dark));
  elements.theme.setAttribute('aria-label', t(dark ? 'theme_light_label' : 'theme_dark_label'));
}

function setStatus(message, state = '') {
  elements.status.textContent = message;
  if (state) elements.status.dataset.state = state;
  else delete elements.status.dataset.state;
}

function closeMenu() {
  elements.nav.dataset.open = 'false';
  elements.menu.setAttribute('aria-expanded', 'false');
  elements.menu.querySelector('.sr-only').textContent = t('menu_label');
}

function validateFields(form) {
  let valid = true;
  form.querySelectorAll('input, select, textarea').forEach(field => {
    if (field.name === 'website_confirm') return;
    const fieldValid = field.checkValidity();
    field.setAttribute('aria-invalid', String(!fieldValid));
    if (!fieldValid) valid = false;
  });
  return valid;
}

function createSubmission(form) {
  const formData = new FormData(form);
  const fallbackId = `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return {
    submission_id: crypto.randomUUID ? crypto.randomUUID() : fallbackId,
    company_name: String(formData.get('company_name') || '').trim(),
    contact_name: String(formData.get('contact_name') || '').trim(),
    email: String(formData.get('email') || '').trim().toLowerCase(),
    website: String(formData.get('website') || '').trim(),
    service_code: String(formData.get('service_code') || ''),
    problem: String(formData.get('problem') || '').trim(),
    consent_version: config.consentVersion,
    preferred_language: language,
    source: 'Website assessment',
    submitted_at: new Date().toISOString()
  };
}

async function sendSubmission(payload) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), Number(config.requestTimeoutMs) || DEFAULT_CONFIG.requestTimeoutMs);
  try {
    const response = await fetch(config.intakeEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) throw new Error('Unexpected endpoint response.');
    const result = await response.json();
    if (!response.ok || result.ok !== true) throw new Error(result.error || 'Submission failed.');
    return result;
  } finally {
    window.clearTimeout(timeout);
  }
}

elements.language.addEventListener('click', () => {
  language = language === 'en' ? 'es' : 'en';
  localStorage.setItem('igv-language', language);
  render();
});

elements.theme.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('igv-theme', next);
  renderThemeControl();
});

elements.menu.addEventListener('click', () => {
  const open = elements.menu.getAttribute('aria-expanded') !== 'true';
  elements.menu.setAttribute('aria-expanded', String(open));
  elements.nav.dataset.open = String(open);
  elements.menu.querySelector('.sr-only').textContent = t(open ? 'menu_close_label' : 'menu_label');
});

elements.nav.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
elements.problem.addEventListener('input', () => { elements.problemCount.textContent = `${elements.problem.value.length} / 3000`; });
elements.form.addEventListener('input', event => {
  if (event.target.matches('input, select, textarea')) event.target.removeAttribute('aria-invalid');
  if (elements.status.textContent) setStatus('');
});

elements.form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!ready) { setStatus(t('configuration_error'), 'error'); return; }
  const form = event.currentTarget;
  if (form.elements.website_confirm.value) { setStatus(t('honeypot_error'), 'error'); return; }
  if (!validateFields(form)) { form.reportValidity(); return; }
  if (!isLiveMode()) {
    if (config.demoMode === false && config.intakeEndpoint && !config.intakeEndpoint.startsWith('https://')) {
      setStatus(t('invalid_endpoint'), 'error');
      return;
    }
    setStatus(t('demo_status'), 'success');
    return;
  }
  elements.submit.disabled = true;
  elements.submit.textContent = t('submitting');
  setStatus(t('submitting'), 'pending');
  try {
    await sendSubmission(createSubmission(form));
    form.reset();
    elements.problemCount.textContent = '0 / 3000';
    setStatus(t('success_status'), 'success');
  } catch (error) {
    console.error(error);
    setStatus(t('error_status'), 'error');
  } finally {
    elements.submit.disabled = false;
    elements.submit.textContent = t('submit_live');
  }
});

document.getElementById('year').textContent = new Date().getFullYear();
loadData().catch(error => {
  console.error(error);
  ready = false;
  elements.submit.disabled = true;
  setStatus('Website configuration error.', 'error');
});
