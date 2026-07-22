const AXIS_LABELS = {
  performance: 'Performance',
  generalisation: 'Generalisation',
  calibration: 'Calibration',
  privacy: 'Privacy',
  robustness: 'Robustness',
  efficiency: 'Efficiency',
  rollback: 'Rollback',
  reproducibility: 'Reproducibility'
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

function axisRows(axes) {
  return Object.entries(axes)
    .map(([name, score]) => {
      const percent = Math.round(clamp(score) * 100);
      return `<li><span>${escapeHtml(AXIS_LABELS[name] || name)}</span><meter min="0" max="1" value="${clamp(score)}">${percent}%</meter><strong>${percent}%</strong></li>`;
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
      <ul class="evidence-axes">${axisRows(card.axes)}</ul>
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
  const root = document.querySelector('#model-evidence-board');
  if (!root) return;
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
