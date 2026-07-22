import assert from 'node:assert/strict';
import { recommendServices, recommenderContract } from '../apps/web/assets/neural-recommender.mjs';

const services = [
  { code: 'IVA', status: 'active', price_eur: 149, delivery_days: 3, estimated_hours: 2.5, automation_target_pct: 55 },
  { code: 'CRM', status: 'active', price_eur: 299, delivery_days: 5, estimated_hours: 4, automation_target_pct: 65 },
  { code: 'IOP', status: 'active', price_eur: 249, delivery_days: 4, estimated_hours: 3, automation_target_pct: 50 },
  { code: 'WAB', status: 'addon', price_eur: 129, delivery_days: 2, estimated_hours: 1.5, automation_target_pct: 45 },
  { code: 'ISS', status: 'hidden_until_sale', price_eur: 599, delivery_days: 8, estimated_hours: 7.5, automation_target_pct: 60 }
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
assert.deepEqual(visibility.tensor_shape, [3, 3, 4], 'multidimensional tensor shape is incorrect');
assert.ok(visibility.latent_dimensions >= 30, 'latent representation is unexpectedly shallow');
assert.ok(visibility.next_steps.length >= 4, 'connected next-step plan is incomplete');
assert.equal(visibility.next_steps.at(-1).action, 'evaluate_connected_service', 'cross-service connection step missing');
assert.equal(visibility.connected_path[0], 'IVA', 'connected path does not begin with top service');

const followUp = top('follow_up', { automation_priority: 0.95 });
assert.equal(followUp.recommendations[0].code, 'CRM', 'follow-up need should prioritise CRM');
assert.ok(followUp.next_steps.some(step => step.action === 'define_pipeline_ownership'), 'CRM execution plan missing pipeline ownership');

const sales = top('sales_message', { multilingual_need: 0.90 });
assert.equal(sales.recommendations[0].code, 'IOP', 'sales-message need should prioritise IOP');
assert.ok(sales.next_steps.some(step => step.action === 'collect_commercial_proof'), 'IOP execution plan missing proof collection');

for (const result of [visibility, followUp, sales]) {
  const probabilitySum = result.recommendations.reduce((sum, item) => sum + item.probability, 0);
  assert.ok(Math.abs(probabilitySum - 1) < 1e-9, 'recommendation probabilities do not sum to one');
  assert.ok(result.confidence >= 0 && result.confidence <= 1, 'overall confidence outside range');
  assert.ok(Number.isFinite(result.latent_summary.mean), 'latent mean is not finite');
  assert.ok(Number.isFinite(result.latent_summary.energy), 'latent energy is not finite');
  for (const recommendation of result.recommendations) {
    assert.ok(recommendation.confidence >= 0 && recommendation.confidence <= 1, 'service confidence outside range');
    assert.ok(recommendation.uncertainty >= 0 && recommendation.uncertainty <= 1, 'service uncertainty outside range');
    assert.equal(recommendation.reasons.length, 3, 'explanation does not contain three bounded reasons');
  }
  for (const step of result.next_steps) {
    assert.equal(typeof step.action, 'string');
    assert.ok(Array.isArray(step.depends_on), 'step dependencies are not explicit');
    assert.equal(typeof step.human_gate, 'boolean');
  }
}

const urgent = top('visibility', { urgency: 0.98 });
assert.equal(urgent.next_steps[0].action, 'protect_urgent_scope', 'urgent scope protection was not prioritised');

const repeat = top('visibility');
assert.deepEqual(visibility, repeat, 'multidimensional neural recommendation is not deterministic');

const changedAxis = top('visibility', { automation_priority: 0.05, complexity_tolerance: 0.95 });
assert.notDeepEqual(visibility.latent_summary, changedAxis.latent_summary, 'cross-axis feature changes did not affect latent state');

assert.equal(recommenderContract.personal_data_required, false);
assert.equal(recommenderContract.automatic_contact, false);
assert.equal(recommenderContract.automatic_purchase, false);
assert.equal(recommenderContract.automatic_crm_write, false);
assert.equal(recommenderContract.online_learning, false);
assert.deepEqual(recommenderContract.tensor_shape, [3, 3, 4]);
assert.deepEqual(recommenderContract.convolution_kernel, [2, 2, 2]);
assert.equal(recommenderContract.convolution_dimensions, 3);
assert.equal(recommenderContract.ensemble_size, 7);
assert.equal(recommenderContract.graph_layers, 2);
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
    'true 3D tensor and kernel contract',
    'multiscale cross-axis latent state',
    'connected dependency-aware next steps',
    'urgent scope protection',
    'inactive services excluded',
    'probabilities conserved',
    'confidence bounded',
    'deterministic inference',
    'no personal data or automatic action'
  ]
}, null, 2));
