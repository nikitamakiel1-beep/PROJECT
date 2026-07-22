const AXIS_LABELS = {
  performance: { en: 'Performance', es: 'Rendimiento' },
  generalisation: { en: 'Generalisation', es: 'Generalización' },
  calibration: { en: 'Calibration', es: 'Calibración' },
  privacy: { en: 'Privacy', es: 'Privacidad' },
  robustness: { en: 'Robustness', es: 'Robustez' },
  efficiency: { en: 'Efficiency', es: 'Eficiencia' },
  rollback: { en: 'Rollback', es: 'Reversión' },
  reproducibility: { en: 'Reproducibility', es: 'Reproducibilidad' }
};

const COPY = {
  en: {
    kicker: 'Model evidence custody',
    title: 'Candidates remain cards until evidence closes every route.',
    body: 'This synthetic board demonstrates multi-axis review, route debt, shadow-rollout stability and rollback custody. It does not contain trained production results.',
    noteTitle: 'Promotion is structurally disabled',
    noteBody: 'The maximum machine-generated state is eligibility for extended shadow evaluation. Human approval and provider evidence remain mandatory.'
  },
  es: {
    kicker: 'Custodia de evidencia de modelos',
    title: 'Los candidatos siguen siendo tarjetas hasta cerrar todas las rutas de evidencia.',
    body: 'Este panel sintético demuestra revisión multieje, deuda de rutas, estabilidad en sombra y custodia de reversión. No contiene resultados productivos entrenados.',
    noteTitle: 'La promoción está desactivada por diseño',
    noteBody: 'El estado automático máximo es aptitud para evaluación en sombra ampliada. La aprobación humana y la evidencia del proveedor siguen siendo obligatorias.'
  }
};

function clamp(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function ensureStylesheet() {
  if (document.querySelector('link[data-model-evidence-board]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'assets/model-evidence-board.css';
  link.dataset.modelEvidenceBoard = 'true';
  document.head.append(link);
}

function ensureSection(language) {
  let section = document.querySelector('#model-evidence');
  if (!section) {
    section = document.createElement('section');
    section.id = 'model-evidence';
    section.className = 'section section-muted model-evidence-section';
    const assessment = document.querySelector('#assessment');
    if (assessment) assessment.before(section);
    else document.querySelector('main')?.append(section);
  }
  const copy = COPY[language] || COPY.en;
  section.innerHTML = `
    <div class="shell section-heading">
      <p class="eyebrow">${escapeHtml(copy.kicker)}</p>
      <h2>${escapeHtml(copy.title)}</h2>
      <p>${escapeHtml(copy.body)}</p>
      <div class="mode-banner" role="note"><strong>${escapeHtml(copy.noteTitle)}</strong><span>${escapeHtml(copy.noteBody)}</span></div>
    </div>
    <div class="shell model-evidence-shell"><div id="model-evidence-board" aria-live="polite"></div></div>`;
  return section.querySelector('#model-evidence-board');
}

function decisionLabel(value, language) {
  const labels = {
    en: {
      eligible_for_extended_shadow: 'Extended shadow eligible',
      human_review_required: 'Human review required',
      reject_or_rework: 'Reject or rework'
    },
    es: {
      eligible_for_extended_shadow: 'Apto para sombra ampliada',
      human_review_required: 'Requiere revisión humana',
      reject_or_rework: 'Rechazar o reelaborar'
    }
  };
  return labels[language]?.[value] || labels.en[value] || value;
}

function axisRows(axes, language) {
  return Object.entries(axes)
    .map(([name, score]) => {
      const percent = Math.round(clamp(score) * 100);
      const label = AXIS_LABELS[name]?.[language] || AXIS_LABELS[name]?.en || name;
      return `<li><span>${escapeHtml(label)}</span><meter min="0" max="1" value="${clamp(score)}">${percent}%</meter><strong>${percent}%</strong></li>`;
    })
    .join('');
}

function cardHtml(card, language) {
  const blockers = card.blockers.length
    ? `<ul class="evidence-blockers">${card.blockers.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
    : `<p class="evidence-clear">${language === 'es' ? 'Sin bloqueadores sintéticos.' : 'No synthetic blockers.'}</p>`;
  const routeDebt = card.route_debt.length
    ? card.route_debt.map(route => `<span>${escapeHtml(route)}</span>`).join('')
    : `<span>${language === 'es' ? 'Sin deuda de ruta' : 'No route debt'}</span>`;
  return `
    <article class="model-evidence-card decision-${escapeHtml(card.decision)}" data-layer="${Number(card.layer) || 1}" data-candidate-id="${escapeHtml(card.candidate_id)}">
      <div class="evidence-card-header">
        <div><small>${escapeHtml(card.framework)} · ${escapeHtml(card.task)}</small><h3>${escapeHtml(card.candidate_id)}</h3></div>
        <div class="evidence-score"><strong>${Math.round(clamp(card.score) * 100)}</strong><span>/100</span></div>
      </div>
      <p class="evidence-decision">${escapeHtml(decisionLabel(card.decision, language))}</p>
      <ul class="evidence-axes">${axisRows(card.axes, language)}</ul>
      <div class="evidence-rollout">
        <span>${language === 'es' ? 'Desacuerdo' : 'Disagreement'} ${Math.round(clamp(card.rollout.disagreement) * 100)}%</span>
        <span>${language === 'es' ? 'Abstención' : 'Abstention'} ${Math.round(clamp(card.rollout.abstention) * 100)}%</span>
        <span>${language === 'es' ? 'Incidentes' : 'Incidents'} ${Math.round(clamp(card.rollout.incidents) * 100)}%</span>
      </div>
      <div class="route-debt" aria-label="Route debt">${routeDebt}</div>
      ${blockers}
      <details><summary>${language === 'es' ? 'Limitaciones declaradas' : 'Declared limitations'}</summary><ul>${card.limitations.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></details>
      <button type="button" disabled>${language === 'es' ? 'Promoción desactivada' : 'Promotion disabled'}</button>
    </article>`;
}

function connectionSvg(cards) {
  const nodes = new Map(cards.map((card, index) => [card.candidate_id, { x: 18 + index * 32, y: 20 + (Number(card.layer) || 1) * 12 }]));
  const lines = [];
  for (const card of cards) {
    const source = nodes.get(card.candidate_id);
    for (const targetId of card.connections || []) {
      const target = nodes.get(targetId);
      if (!source || !target) continue;
      lines.push(`<line x1="${source.x}%" y1="${source.y}%" x2="${target.x}%" y2="${target.y}%" />`);
    }
  }
  return `<svg class="evidence-connections" aria-hidden="true">${lines.join('')}</svg>`;
}

export async function initialiseModelEvidenceBoard({ language = 'en' } = {}) {
  ensureStylesheet();
  const root = ensureSection(language);
  try {
    const response = await fetch('assets/model-evidence-board.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const board = await response.json();
    root.innerHTML = `${connectionSvg(board.cards)}<div class="evidence-card-grid">${board.cards.map(card => cardHtml(card, language)).join('')}</div>`;
    root.dataset.loaded = 'true';
  } catch (error) {
    root.textContent = language === 'es'
      ? 'No se pudo cargar la demostración del panel de evidencia.'
      : 'The evidence-board demonstration could not be loaded.';
    root.dataset.error = String(error);
  }
}

if (typeof document !== 'undefined') {
  initialiseModelEvidenceBoard({ language: document.documentElement.lang || 'en' });
  document.addEventListener('igv:language-change', event => initialiseModelEvidenceBoard({ language: event.detail?.language || 'en' }));
}
