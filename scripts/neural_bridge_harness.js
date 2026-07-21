#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'automations/google-apps-script/NeuralBridgeCore.gs'), 'utf8');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source, sandbox, {filename: 'NeuralBridgeCore.gs'});
const core = sandbox.NeuralBridgeCore;
if (!core) throw new Error('NeuralBridgeCore was not exported');

function hashHex(value) {
  return crypto.createHash('sha256').update(String(value), 'utf8').digest('hex');
}

function hashBytes(value) {
  return Array.from(crypto.createHash('sha256').update(String(value), 'utf8').digest());
}

function pseudonymize(namespace, value) {
  return String(namespace).toUpperCase() + '-' + crypto.createHmac('sha256', 'synthetic-test-salt')
    .update(String(namespace) + '|' + String(value), 'utf8').digest('hex').slice(0, 16).toUpperCase();
}

function fixture(overrides) {
  const tables = {
    Leads: [{
      'Lead ID': 'LEAD-PRIVATE-001',
      'Company': 'Private Example Industries',
      'Contact Name': 'Taylor Private',
      'Email': 'taylor.private@example.test',
      'Phone': '+34 600 000 000',
      'Website': 'https://private.example.test',
      'Company ID': 'COM-PRIVATE-001',
      'Contact ID': 'CON-PRIVATE-001',
      'Service Interest': 'OSP',
      'Fit Score': 84,
      'Status': 'Qualified',
      'Consent Basis': 'Assessment consent recorded',
      'Last Contact': '2026-07-18',
      'Next Action Date': '2026-07-21',
      'Next Action': 'Review international sales narrative',
      'Owner': 'Synthetic Owner',
      'Opportunity ID': '',
      'Notes': 'Private customer note that must become a vector and then disappear.'
    }],
    Companies: [{
      'Company ID': 'COM-PRIVATE-001',
      'Company Name': 'Private Example Industries',
      'Website': 'https://private.example.test',
      'Sector': 'Industrial simulation',
      'Subsector': 'Process engineering',
      'International Fit': 82,
      'Notes': 'Private organisation note.'
    }],
    Contacts: [{
      'Contact ID': 'CON-PRIVATE-001',
      'Company ID': 'COM-PRIVATE-001',
      'Full Name': 'Taylor Private',
      'Email': 'taylor.private@example.test',
      'Phone': '+34 600 000 000',
      'Consent Status': 'Assessment consent recorded',
      'Relationship Strength': 65,
      'Last Contact': '2026-07-18'
    }],
    Services: [{
      'Service Code': 'OSP',
      'Service Name': 'International Sales One-Pager',
      'Active': true,
      'Standard Price €': 249,
      'Automation Target %': 50,
      'Delivery Days': 4
    }],
    Activities: [{
      'Activity ID': 'ACT-PRIVATE-001',
      'Date': '2026-07-12',
      'Company ID': 'COM-PRIVATE-001',
      'Contact ID': 'CON-PRIVATE-001',
      'Activity Type': 'Email',
      'Channel': 'Email',
      'Summary': 'Sent requested diagnostic questions',
      'Outcome': 'Replied with useful detail',
      'Duration Minutes': 18
    }, {
      'Activity ID': 'ACT-PRIVATE-002',
      'Date': '2026-07-18',
      'Company ID': 'COM-PRIVATE-001',
      'Contact ID': 'CON-PRIVATE-001',
      'Activity Type': 'Discovery call',
      'Channel': 'Video',
      'Summary': 'Discussed international sales narrative',
      'Outcome': 'Interested in one-pager',
      'Duration Minutes': 35
    }],
    Opportunities: []
  };
  if (overrides) Object.keys(overrides).forEach((key) => { tables[key] = overrides[key]; });
  return tables;
}

function build(tables) {
  return core.buildPackages(tables, {
    syntheticOnly: true,
    today: new Date('2026-07-21T12:00:00Z'),
    pseudonymize,
    hashHex,
    hashBytes
  });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function runTests() {
  const evidence = [];
  function test(name, fn) {
    fn();
    evidence.push({case: name, result: 'passed'});
  }

  test('qualified lead creates one PII-free package', () => {
    const items = build(fixture());
    assert(items.length === 1, 'expected one package');
    const payload = JSON.stringify(items[0].package);
    ['Taylor Private', 'Private Example Industries', 'taylor.private@example.test', '+34 600', 'private.example.test', 'Private customer note'].forEach((marker) => {
      assert(payload.indexOf(marker) < 0, 'PII or free text leaked: ' + marker);
    });
    assert(payload.indexOf('@') < 0, 'email marker leaked');
    assert(payload.indexOf('http') < 0, 'URL leaked');
    assert(items[0].internal.lead_id === 'LEAD-PRIVATE-001', 'internal mapping missing');
  });

  test('legacy OSP service canonicalises to IOP', () => {
    const item = build(fixture())[0];
    assert(item.package.service_code === 'IOP', 'service alias not canonicalised');
    assert(item.internal.service_code === 'IOP', 'internal alias not canonicalised');
    assert(item.package.service_price_eur === 249, 'canonical price missing');
  });

  test('package and feature digest are deterministic', () => {
    const first = build(fixture())[0].package;
    const second = build(fixture())[0].package;
    assert(first.package_id === second.package_id, 'package ID changed');
    assert(first.feature_digest === second.feature_digest, 'feature digest changed');
    assert(JSON.stringify(first.features) === JSON.stringify(second.features), 'features changed');
  });

  test('low-fit and unqualified leads are excluded', () => {
    const low = fixture();
    low.Leads[0]['Fit Score'] = 40;
    assert(build(low).length === 0, 'low-fit lead exported');
    const unqualified = fixture();
    unqualified.Leads[0].Status = 'New';
    assert(build(unqualified).length === 0, 'unqualified lead exported');
  });

  test('existing Opportunity is preserved', () => {
    const tables = fixture({Opportunities: [{
      'Opportunity ID': 'OPP-MANUAL-001',
      'Service Code': 'IOP',
      'Notes': 'lead_id=LEAD-PRIVATE-001; human_curated=true'
    }]});
    assert(build(tables).length === 0, 'duplicate Opportunity package generated');
  });

  test('synthetic gate is fail-closed', () => {
    let error = null;
    try {
      core.buildPackages(fixture(), {syntheticOnly: false, pseudonymize, hashHex, hashBytes});
    } catch (caught) { error = caught; }
    assert(error && String(error.message) === 'synthetic_gate_closed', 'synthetic gate did not close');
  });

  test('shadow decision validator blocks mutation policy', () => {
    const expected = build(fixture())[0].package;
    const base = {
      decision_version: 'neural-provider-decision-v1',
      package_id: expected.package_id,
      feature_digest: expected.feature_digest,
      decision_digest: 'a'.repeat(64),
      execution_policy: {
        mutation_permitted: false,
        external_communication_permitted: false
      }
    };
    assert(core.validateDecision(base, expected) === true, 'valid shadow decision rejected');
    const unsafe = JSON.parse(JSON.stringify(base));
    unsafe.execution_policy.external_communication_permitted = true;
    let error = null;
    try { core.validateDecision(unsafe, expected); } catch (caught) { error = caught; }
    assert(error && String(error.message) === 'external_communication_policy_invalid', 'unsafe decision accepted');
  });

  return {ok: true, tests: evidence, package: build(fixture())[0].package};
}

const result = runTests();
if (process.argv.indexOf('--emit') >= 0) {
  process.stdout.write(JSON.stringify(result.package));
} else {
  process.stdout.write(JSON.stringify({ok: result.ok, tests: result.tests}, null, 2) + '\n');
}
