#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'automations/google-apps-script/IntakeCore.gs'), 'utf8');
const context = { URL, Date, Math, console };
vm.createContext(context);
vm.runInContext(source, context, { filename: 'IntakeCore.gs' });
const Core = context.IntakeCore;

const options = {consentVersion: 'assessment-v1-2026-07', activeServiceCodes: ['IVA','CRM','IOP'], owner: 'Synthetic Owner'};
const blank = () => ({Companies: [], Contacts: [], Leads: [], Activities: [], 'Automation Log': []});
const basePayload = overrides => Object.assign({
  submission_id: 'synthetic-0001',
  company_name: 'Synthetic Export Lab',
  contact_name: 'Alex Example',
  email: 'alex@example.test',
  website: 'https://synthetic.example.test',
  country: 'ES',
  service_code: 'IVA',
  problem: 'Synthetic validation only.',
  consent_version: options.consentVersion,
  preferred_language: 'en',
  source: 'Website assessment',
  submitted_at: '2026-07-21T12:00:00.000Z'
}, overrides || {});

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function applyAttempt(store, payload, failOnSheet) {
  const before = clone(store);
  let plan;
  try {
    plan = Core.preparePlan(payload, before, options);
    const working = clone(before);
    if (plan.status === 'accepted') {
      for (const sheet of ['Companies','Contacts','Leads','Activities']) {
        for (const record of plan.records[sheet]) {
          if (failOnSheet === sheet) throw Object.assign(new Error('injected'), {code: 'spreadsheet_write_failed'});
          working[sheet].push(record);
        }
      }
    }
    if (failOnSheet === 'Automation Log') throw Object.assign(new Error('injected'), {code: 'spreadsheet_write_failed'});
    working['Automation Log'].push(Core.makeLogRecord({
      status: plan.status,
      submission_id: plan.payload.submission_id,
      retry_count: plan.retry_count,
      correlation_id: plan.correlation_id,
      timestamp: '2026-07-21T12:01:00.000Z',
      owner: options.owner
    }));
    Object.keys(store).forEach(key => { store[key] = working[key]; });
    return {ok: true, status: plan.status, plan};
  } catch (error) {
    const submissionId = payload && payload.submission_id ? String(payload.submission_id) : 'unresolved';
    const retryCount = before['Automation Log'].filter(row => row['Trigger Record'] === submissionId).length;
    store['Automation Log'].push(Core.makeLogRecord({
      status: String(error.code || '').startsWith('invalid_') || String(error.code || '').startsWith('missing_') || error.code === 'consent_version_mismatch' ? 'rejected' : 'failed',
      submission_id: submissionId,
      retry_count: retryCount,
      error_code: error.code || 'internal_error',
      timestamp: '2026-07-21T12:01:00.000Z',
      owner: options.owner
    }));
    return {ok: false, error: error.code || 'internal_error'};
  }
}

const evidence = [];
function test(name, fn) {
  try { fn(); evidence.push({case: name, result: 'passed'}); }
  catch (error) { evidence.push({case: name, result: 'failed', error: error.message}); throw error; }
}

test('valid new submission', () => {
  const store = blank();
  const result = applyAttempt(store, basePayload());
  assert.equal(result.status, 'accepted');
  assert.deepEqual([store.Companies.length, store.Contacts.length, store.Leads.length, store.Activities.length, store['Automation Log'].length], [1,1,1,1,1]);
  assert.equal(store['Automation Log'][0].Result, 'accepted');
});

test('exact retry is idempotent', () => {
  const store = blank();
  applyAttempt(store, basePayload());
  const idsBefore = [store.Companies[0]['Company ID'], store.Contacts[0]['Contact ID'], store.Leads[0]['Lead ID'], store.Activities[0]['Activity ID']];
  const result = applyAttempt(store, basePayload());
  assert.equal(result.status, 'duplicate');
  assert.deepEqual([store.Companies.length, store.Contacts.length, store.Leads.length, store.Activities.length], [1,1,1,1]);
  assert.deepEqual(idsBefore, [store.Companies[0]['Company ID'], store.Contacts[0]['Contact ID'], store.Leads[0]['Lead ID'], store.Activities[0]['Activity ID']]);
  assert.equal(store['Automation Log'].length, 2);
  assert.equal(store['Automation Log'][1].Result, 'duplicate');
  assert.equal(store['Automation Log'][1]['Retry Count'], 1);
});

test('existing company and new contact', () => {
  const store = blank();
  store.Companies.push({'Company ID':'COM-MANUAL01','Company Name':'Curated Name','Website':'https://synthetic.example.test','Sector':'Curated sector','Notes':'Human note'});
  const result = applyAttempt(store, basePayload({submission_id:'synthetic-0002',email:'new@example.test',contact_name:'New Contact'}));
  assert.equal(result.status, 'accepted');
  assert.equal(store.Companies.length, 1);
  assert.equal(store.Companies[0].Sector, 'Curated sector');
  assert.equal(store.Contacts[0]['Company ID'], 'COM-MANUAL01');
});

test('existing contact preserves curated fields', () => {
  const store = blank();
  store.Companies.push({'Company ID':'COM-CURATED','Company Name':'Curated Company','Website':'https://curated.example.test','Notes':'Human company note'});
  store.Contacts.push({'Contact ID':'CON-CURATED','Company ID':'COM-CURATED','Full Name':'Human Curated','Role':'Director','Email':'alex@example.test','Notes':'Human contact note'});
  const result = applyAttempt(store, basePayload({submission_id:'synthetic-0003',company_name:'Conflicting Submitted Company',website:'https://different.example.test'}));
  assert.equal(result.status, 'accepted');
  assert.equal(store.Companies.length, 1);
  assert.equal(store.Contacts.length, 1);
  assert.equal(store.Contacts[0].Role, 'Director');
  assert.equal(store.Leads[0]['Company ID'], 'COM-CURATED');
  assert.ok(result.plan.warnings.includes('existing_contact_company_precedence'));
});

test('malformed email rejected without partial writes', () => {
  const store = blank();
  const result = applyAttempt(store, basePayload({submission_id:'synthetic-0004',email:'invalid'}));
  assert.equal(result.ok, false);
  assert.deepEqual([store.Companies.length,store.Contacts.length,store.Leads.length,store.Activities.length],[0,0,0,0]);
  assert.equal(store['Automation Log'][0].Result, 'rejected');
});

test('missing required field rejected without partial writes', () => {
  const store = blank();
  const result = applyAttempt(store, basePayload({submission_id:'synthetic-0005',company_name:''}));
  assert.equal(result.ok, false);
  assert.deepEqual([store.Companies.length,store.Contacts.length,store.Leads.length,store.Activities.length],[0,0,0,0]);
  assert.equal(store['Automation Log'][0].Result, 'rejected');
});

test('invalid service code rejected', () => {
  const store = blank();
  const result = applyAttempt(store, basePayload({submission_id:'synthetic-0006',service_code:'ISS'}));
  assert.equal(result.ok, false);
  assert.equal(result.error, 'invalid_service_code');
  assert.equal(store.Leads.length, 0);
});

test('spreadsheet write failure rolls back operational records', () => {
  const store = blank();
  const result = applyAttempt(store, basePayload({submission_id:'synthetic-0007'}), 'Leads');
  assert.equal(result.ok, false);
  assert.deepEqual([store.Companies.length,store.Contacts.length,store.Leads.length,store.Activities.length],[0,0,0,0]);
  assert.equal(store['Automation Log'][0].Result, 'failed');
  assert.equal(store['Automation Log'][0].Error, 'spreadsheet_write_failed');
});

test('deterministic recovery from partial prior rows', () => {
  const store = blank();
  const payload = basePayload({submission_id:'synthetic-0008'});
  const initial = Core.preparePlan(payload, store, options);
  store.Companies.push(initial.records.Companies[0]);
  store.Contacts.push(initial.records.Contacts[0]);
  const result = applyAttempt(store, payload);
  assert.equal(result.status, 'accepted');
  assert.equal(store.Companies.length, 1);
  assert.equal(store.Contacts.length, 1);
  assert.equal(store.Leads.length, 1);
  assert.equal(store.Activities.length, 1);
});

console.log(JSON.stringify({ok: true, tests: evidence}, null, 2));
