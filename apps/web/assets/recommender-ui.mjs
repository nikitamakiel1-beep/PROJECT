import { recommendServices } from './neural-recommender.mjs';
import { renderFloatingCardFabric } from './deep-card-fabric.mjs';

for (const href of ['assets/neural-fabric.css', 'assets/deep-card-fabric.css']) {
  const styleLink = document.createElement('link');
  styleLink.rel = 'stylesheet';
  styleLink.href = href;
  document.head.append(styleLink);
}

const form = document.getElementById('neural-recommender-form');
const output = document.getElementById('neural-recommendations');
const status = document.getElementById('neural-recommender-status');
const serviceSelect = document.getElementById('service-select');
let services = [];
let translations = null;
let lastResult = null;

function language() {
  return localStorage.getItem('igv-language') === 'es' ? 'es' : 'en';
}

function t(key) {
  return translations?.[language()]?.[key] || key;
}

function numeric(formData, key) {
  return Math.max(0, Math.min(1, Number(formData.get(key) || 0) / 100));
}

function answersFromForm() {
  const data = new FormData(form);
  return {
    goal: String(data.get('goal') || ''),
    international_readiness: numeric(data, 'international_readiness'),
    multilingual_need: numeric(data, 'multilingual_need'),
    complexity_tolerance: numeric(data, 'complexity_tolerance'),
    automation_priority: numeric(data, 'automation_priority'),
    urgency: numeric(data, 'urgency'),
    budget_sensitivity: numeric(data, 'budget_sensitivity')
  };
}

function serviceForCode(code) {
  return services.find(service => (service.code === 'OSP' ? 'IOP' : service.code) === code) || null;
}

function reasonText(reason) {
  return t(`neural_reason_${reason}`);
}

function stepText(step) {
  const service = step.service_code ? serviceForCode(step.service_code) : null;
  const base = t(`neural_step_${step.action}`);
  return service ? `${base}: ${service.name[language()]}` : base;
}

function renderExecutionPlan(result) {
  const section = document.createElement('section');
  section.className = 'neural-execution-plan';
  const heading = document.createElement('div');
  heading.className = 'neural-plan-heading';
  const title = document.createElement('h3');
  title.textContent = t('neural_next_steps_title');
  const summary = document.createElement('p');
  summary.textContent = t('neural_next_steps_body');
  heading.append(title, summary);

  const model = document.createElement('div');
  model.className = 'neural-model-state';
  model.append(
    Object.assign(document.createElement('span'), { textContent: `3D CNN · ${result.tensor_shape.join('×')}` }),
    Object.assign(document.createElement('span'), { textContent: `${t('neural_latent_dimensions')}: ${result.latent_dimensions}` }),
    Object.assign(document.createElement('span'), { textContent: `${t('neural_connected_path')}: ${result.connected_path.join(' → ')}` })
  );

  const list = document.createElement('ol');
  list.className = 'neural-step-list';
  result.next_steps.forEach(step => {
    const item = document.createElement('li');
    const phase = document.createElement('span');
    phase.className = 'badge';
    phase.textContent = t(`neural_phase_${step.phase}`);
    const body = document.createElement('div');
    const action = document.createElement('strong');
    action.textContent = stepText(step);
    const control = document.createElement('small');
    control.textContent = step.human_gate ? t('neural_step_human_gate') : t('neural_step_internal');
    body.append(action, control);
    item.append(phase, body);
    list.append(item);
  });
  section.append(heading, model, list);
  return section;
}

function floatingCards(result) {
  const recommendationCards = result.recommendations.slice(0, 3).map((recommendation, index) => {
    const service = serviceForCode(recommendation.code);
    return {
      card_id: `WEB-SERVICE-${recommendation.code}`,
      card_type: 'service',
      title: service?.name?.[language()] || recommendation.code,
      summary: recommendation.reasons.map(reasonText).join(' '),
      confidence: recommendation.confidence,
      layer: index + 2,
      related_cards: index === 0 ? result.next_steps.map((_, stepIndex) => `WEB-STEP-${stepIndex + 1}`) : [`WEB-SERVICE-${result.recommendations[0].code}`],
      actions: ['review', 'select_service'],
      human_review: true
    };
  });
  const stepCards = result.next_steps.map((step, index) => ({
    card_id: `WEB-STEP-${index + 1}`,
    card_type: step.human_gate ? 'risk' : 'task',
    title: stepText(step),
    summary: step.human_gate ? t('neural_step_human_gate') : t('neural_step_internal'),
    confidence: result.confidence,
    layer: Math.min(7, index + 1),
    related_cards: index > 0 ? [`WEB-STEP-${index}`] : [`WEB-SERVICE-${result.recommendations[0].code}`],
    actions: ['review'],
    human_review: true
  }));
  return [...recommendationCards, ...stepCards];
}

function renderFloatingWorkspace(result) {
  const section = document.createElement('section');
  section.className = 'neural-floating-workspace-section';
  const title = document.createElement('h3');
  title.textContent = language() === 'es' ? 'Espacio neuronal de tarjetas conectadas' : 'Connected neural card workspace';
  const note = document.createElement('p');
  note.textContent = language() === 'es'
    ? 'Las capas flotantes representan relaciones y próximos pasos; las acciones permanecen desactivadas hasta revisión humana.'
    : 'Floating layers represent relationships and next steps; actions remain disabled until human review.';
  const container = document.createElement('div');
  section.append(title, note, container);
  output.append(section);
  renderFloatingCardFabric(container, floatingCards(result), { allowActions: false });
}

function renderResult(result) {
  lastResult = result;
  output.replaceChildren();
  const top = result.recommendations.slice(0, 3);
  top.forEach((recommendation, index) => {
    const service = serviceForCode(recommendation.code);
    if (!service) return;
    const article = document.createElement('article');
    article.className = `neural-result${index === 0 ? ' neural-result-primary' : ''}`;
    const rank = document.createElement('span');
    rank.className = 'badge';
    rank.textContent = index === 0 ? t('neural_best_match') : `#${index + 1}`;
    const title = document.createElement('h3');
    title.textContent = service.name[language()];
    const score = document.createElement('div');
    score.className = 'neural-score';
    score.innerHTML = `<strong>${recommendation.fit_pct}%</strong><span>${t('neural_fit_label')}</span>`;
    const confidence = document.createElement('p');
    confidence.className = 'neural-confidence';
    confidence.textContent = `${t('neural_confidence')}: ${Math.round(recommendation.confidence * 100)}%`;
    const reasons = document.createElement('ul');
    recommendation.reasons.forEach(reason => {
      const item = document.createElement('li');
      item.textContent = reasonText(reason);
      reasons.append(item);
    });
    const meta = document.createElement('p');
    meta.className = 'neural-meta';
    meta.textContent = `${t('from')} €${service.price_eur} · ${service.delivery_days} ${t('days')}`;
    const choose = document.createElement('button');
    choose.type = 'button';
    choose.className = 'button secondary neural-choose';
    choose.textContent = t('neural_choose_service');
    choose.addEventListener('click', () => {
      serviceSelect.value = service.code;
      document.getElementById('assessment').scrollIntoView({ behavior: 'smooth' });
      serviceSelect.focus({ preventScroll: true });
      status.textContent = t('neural_selection_applied');
    });
    article.append(rank, title, score, confidence, reasons, meta, choose);
    output.append(article);
  });
  output.append(renderExecutionPlan(result));
  renderFloatingWorkspace(result);
  status.textContent = `${t('neural_local_status')} ${t('neural_human_review')}`;
}

function updateRangeLabels() {
  form.querySelectorAll('input[type="range"]').forEach(input => {
    const outputElement = document.querySelector(`[data-range-output="${input.name}"]`);
    if (outputElement) outputElement.textContent = `${input.value}%`;
  });
}

async function initialise() {
  const [serviceData, baseTranslations, plannerTranslations] = await Promise.all([
    fetch('../../schemas/services.json', { cache: 'no-store' }).then(response => response.json()),
    fetch('assets/translations.json', { cache: 'no-store' }).then(response => response.json()),
    fetch('assets/neural-next-steps.json', { cache: 'no-store' }).then(response => response.json())
  ]);
  services = serviceData;
  translations = {
    en: { ...baseTranslations.en, ...plannerTranslations.en },
    es: { ...baseTranslations.es, ...plannerTranslations.es }
  };
  updateRangeLabels();
  form.addEventListener('input', updateRangeLabels);
  form.addEventListener('submit', event => {
    event.preventDefault();
    renderResult(recommendServices(answersFromForm(), services));
  });
  document.getElementById('language').addEventListener('click', () => {
    window.setTimeout(() => {
      if (lastResult) renderResult(recommendServices(answersFromForm(), services));
    }, 0);
  });
}

initialise().catch(error => {
  console.error(error);
  status.textContent = 'Multidimensional recommendation module unavailable.';
  form.querySelector('button[type="submit"]').disabled = true;
});
