const clamp = value => Math.max(0, Math.min(1, Number(value) || 0));

function stableHash(text) {
  let hash = 2166136261;
  for (const character of String(text)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export function normaliseCard(card) {
  const id = String(card.card_id || card.id || `CARD-${stableHash(JSON.stringify(card)).toString(16).toUpperCase()}`);
  const seed = stableHash(id);
  const layer = Math.max(1, Math.min(7, Number(card.layer || (seed % 7) + 1)));
  const angle = (seed % 360) * Math.PI / 180;
  const radius = 0.16 + (seed % 31) / 100;
  return {
    card_id: id,
    card_type: String(card.card_type || 'insight'),
    title: String(card.title || 'Untitled card'),
    summary: String(card.summary || ''),
    confidence: clamp(card.confidence ?? 0.5),
    layer,
    x: clamp(card.position?.[0] ?? 0.5 + Math.cos(angle) * radius),
    y: clamp(card.position?.[1] ?? 0.5 + Math.sin(angle) * radius),
    related_cards: Array.isArray(card.related_cards) ? [...new Set(card.related_cards.map(String))] : [],
    actions: Array.isArray(card.actions) ? card.actions.map(String) : ['review'],
    human_review: card.human_review !== false
  };
}

export function layoutFloatingCards(cards) {
  const normalised = cards.map(normaliseCard);
  const byLayer = new Map();
  for (const card of normalised) {
    if (!byLayer.has(card.layer)) byLayer.set(card.layer, []);
    byLayer.get(card.layer).push(card);
  }
  for (const [layer, items] of byLayer.entries()) {
    items.sort((a, b) => a.card_id.localeCompare(b.card_id));
    items.forEach((card, index) => {
      const angle = (index / Math.max(items.length, 1)) * Math.PI * 2 + layer * 0.27;
      const radius = Math.min(0.42, 0.14 + layer * 0.035 + index * 0.006);
      card.x = clamp(0.5 + Math.cos(angle) * radius);
      card.y = clamp(0.5 + Math.sin(angle) * radius);
    });
  }
  return normalised;
}

export function renderFloatingCardFabric(container, cards, options = {}) {
  if (!(container instanceof Element)) throw new Error('container_required');
  const layout = layoutFloatingCards(cards);
  const allowActions = options.allowActions === true;
  container.classList.add('deep-card-fabric');
  container.replaceChildren();

  const connections = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  connections.setAttribute('class', 'deep-card-connections');
  connections.setAttribute('viewBox', '0 0 1000 700');
  connections.setAttribute('aria-hidden', 'true');
  const byId = new Map(layout.map(card => [card.card_id, card]));
  for (const card of layout) {
    for (const relatedId of card.related_cards) {
      const related = byId.get(relatedId);
      if (!related || card.card_id > related.card_id) continue;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', String(card.x * 1000));
      line.setAttribute('y1', String(card.y * 700));
      line.setAttribute('x2', String(related.x * 1000));
      line.setAttribute('y2', String(related.y * 700));
      line.setAttribute('data-from', card.card_id);
      line.setAttribute('data-to', related.card_id);
      connections.append(line);
    }
  }
  container.append(connections);

  for (const card of layout) {
    const article = document.createElement('article');
    article.className = 'deep-floating-card';
    article.dataset.cardId = card.card_id;
    article.dataset.cardType = card.card_type;
    article.dataset.layer = String(card.layer);
    article.style.setProperty('--card-x', String(card.x));
    article.style.setProperty('--card-y', String(card.y));
    article.style.setProperty('--card-layer', String(card.layer));
    article.innerHTML = `
      <div class="deep-card-header">
        <span class="deep-card-type">${escapeHtml(card.card_type)}</span>
        <span class="deep-card-confidence">${Math.round(card.confidence * 100)}%</span>
      </div>
      <h3>${escapeHtml(card.title)}</h3>
      <p>${escapeHtml(card.summary)}</p>
      <div class="deep-card-actions" aria-label="Card actions"></div>
      <small>${card.human_review ? 'Human review required' : 'Internal reversible automation'}</small>
    `;
    const actions = article.querySelector('.deep-card-actions');
    for (const action of card.actions) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = action.replaceAll('_', ' ');
      button.disabled = !allowActions;
      button.dataset.action = action;
      button.addEventListener('click', () => {
        container.dispatchEvent(new CustomEvent('deep-card-action', {
          bubbles: true,
          detail: { card_id: card.card_id, action, human_review: card.human_review }
        }));
      });
      actions.append(button);
    }
    container.append(article);
  }
  return { model_version: 'floating-card-fabric-v0.1', cards: layout, actions_enabled: allowActions };
}

export const deepCardContract = Object.freeze({
  floating_layers: 7,
  deterministic_layout: true,
  automatic_crm_write: false,
  automatic_external_action: false,
  personal_data_required: false,
  action_default: 'disabled'
});
