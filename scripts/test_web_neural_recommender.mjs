import assert from 'node:assert/strict';
import { recommendServices, recommenderContract } from '../apps/web/assets/neural-recommender.mjs';

const services = [
  { code: 'IVA', status: 'active', price_eur: 149, delivery_days: 3 },
  { code: 'CRM', status: 'active', price_eur: 299, delivery_days: 5 },
  { code: 'IOP', status: 'active', price_eur: 249, delivery_days: 4 },
  { code: 'WAB', status: 'addon', price_eur: 129, delivery_days: 2 },
  { code: 'ISS', status: 'hidden_until_sale', price_eur: 599, delivery_days: 8 }
];

const base = {
  goal: 'visibility',
  international_readiness: 0.65,
  multilingual_need: 0.55,
  complexity_tolerance: 0.25,
  automation_priority: 0.75,
  urgency: 0.75,
  budget_sensitivity: 0.80
};

function top(goal, overrides = {}) {
  return recommendServices({ ...base, goal, ...overrides }, services);
}

const visibility = top('visibility');
assert.equal(visibility.recommendations[0].code, 'IVA', 'visibility need should prioritise IVA');
assert.equal(visibility.local_only, true);
assert.equal(visibility.requires_human_review, true);
assert.equal(visibility.recommendations.length, 3, 'only active launch services should be ranked');
assert.ok(!visibility.recommendations.some(item => item.code === 'ISS' || item.code === 'WAB'), 'hidden and add-on services entered primary ranking');

const followUp = top('follow_up', { automation_priority: 0.95 });
assert.equal(followUp.recommendations[0].code, 'CRM', 'follow-up need should prioritise CRM');

const sales = top('sales_message', { multilingual_need: 0.90 });
assert.equal(sales.recommendations[0].code, 'IOP', 'sales-message need should prioritise IOP');

for (const result of [visibility, followUp, sales]) {
  const probabilitySum = result.recommendations.reduce((sum, item) => sum + item.probability, 0);
  assert.ok(Math.abs(probabilitySum - 1) < 1e-9, 'recommendation probabilities do not sum to one');
  assert.ok(result.confidence >= 0 && result.confidence <= 1, 'overall confidence outside range');
  for (const recommendation of result.recommendations) {
    assert.ok(recommendation.confidence >= 0 && recommendation.confidence <= 1, 'service confidence outside range');
    assert.ok(recommendation.uncertainty >= 0 && recommendation.uncertainty <= 1, 'service uncertainty outside range');
    assert.equal(recommendation.reasons.length, 3, 'explanation does not contain three bounded reasons');
  }
}

const repeat = top('visibility');
assert.deepEqual(visibility, repeat, 'local neural recommendation is not deterministic');

assert.equal(recommenderContract.personal_data_required, false);
assert.equal(recommenderContract.automatic_contact, false);
assert.equal(recommenderContract.automatic_purchase, false);
assert.deepEqual(recommenderContract.cnn_sequence_shape, [3, 4]);
assert.equal(recommenderContract.feature_count, 10);

assert.throws(() => recommendServices(base, []), /services_required/);
assert.throws(() => recommendServices(base, [{ code: 'ISS', status: 'hidden_until_sale' }]), /active_services_required/);

console.log(JSON.stringify({
  ok: true,
  model: recommenderContract.model_version,
  cases: [
    'visibility maps to IVA',
    'follow-up maps to CRM',
    'sales message maps to IOP',
    'inactive services excluded',
    'probabilities conserved',
    'confidence bounded',
    'deterministic inference',
    'no personal data required',
    'no automatic contact or purchase'
  ]
}, null, 2));
