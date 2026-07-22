import assert from 'node:assert/strict';
import { deepCardContract, layoutFloatingCards, normaliseCard } from '../apps/web/assets/deep-card-fabric.mjs';

const source = [
  { card_id: 'CARD-LEAD', card_type: 'lead', title: 'Synthetic lead', summary: 'Qualified internal review.', confidence: .82, layer: 3, related_cards: ['CARD-SERVICE'], actions: ['review'] },
  { card_id: 'CARD-SERVICE', card_type: 'service', title: 'IVA', summary: 'Visibility audit.', confidence: .91, layer: 2, related_cards: ['CARD-LEAD'], actions: ['select_service'] },
  { card_id: 'CARD-TASK', card_type: 'task', title: 'Review evidence', summary: 'No automatic send.', confidence: .75, layer: 4, related_cards: ['CARD-LEAD'], actions: ['review'] }
];

const first = layoutFloatingCards(source);
const second = layoutFloatingCards(source);
assert.deepEqual(first, second, 'floating layout is not deterministic');
assert.equal(first.length, 3);
assert.ok(first.every(card => card.x >= 0 && card.x <= 1 && card.y >= 0 && card.y <= 1), 'card position outside canvas');
assert.ok(first.every(card => card.layer >= 1 && card.layer <= 7), 'floating layer outside contract');
assert.ok(first.every(card => card.human_review), 'human review custody lost');
assert.equal(new Set(first.map(card => `${card.x}:${card.y}`)).size, first.length, 'cards collapsed to duplicate positions');

const generated = normaliseCard({ card_type: 'insight', title: 'Generated', summary: 'Stable ID and position.' });
assert.match(generated.card_id, /^CARD-/);
assert.equal(normaliseCard({ card_type: 'insight', title: 'Generated', summary: 'Stable ID and position.' }).card_id, generated.card_id);

assert.equal(deepCardContract.floating_layers, 7);
assert.equal(deepCardContract.automatic_crm_write, false);
assert.equal(deepCardContract.automatic_external_action, false);
assert.equal(deepCardContract.personal_data_required, false);
assert.equal(deepCardContract.action_default, 'disabled');

console.log(JSON.stringify({
  ok: true,
  model: 'floating-card-fabric-v0.1',
  cases: [
    'deterministic layered layout',
    'bounded positions',
    'stable generated card IDs',
    'human review custody',
    'no automatic CRM or external action'
  ]
}, null, 2));
