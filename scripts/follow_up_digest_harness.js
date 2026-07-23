#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'automations/google-apps-script/FollowUpCore.gs'), 'utf8');
const context = { Date, Math, console, isFinite };
vm.createContext(context);
vm.runInContext(source, context, { filename: 'FollowUpCore.gs' });
const Core = context.FollowUpCore;
const today = '2026-07-21T12:00:00.000Z';
const evidence = [];
function test(name, fn) {
  try { fn(); evidence.push({case: name, result: 'passed'}); }
  catch (error) { evidence.push({case: name, result: 'failed', error: error.message}); throw error; }
}

test('filters future and terminal records', () => {
  const digest = Core.buildDigest([
    {'Lead ID':'L1','Status':'New','Next Action Date':'2026-07-20','Fit Score':40,'Company':'Due'},
    {'Lead ID':'L2','Status':'Closed','Next Action Date':'2026-07-01','Fit Score':99,'Company':'Closed'},
    {'Lead ID':'L3','Status':'New','Next Action Date':'2026-07-22','Fit Score':99,'Company':'Future'}
  ], [], {today});
  assert.equal(digest.items.length, 1);
  assert.equal(digest.items[0].record_id, 'L1');
});

test('normalises percentage-formatted probability', () => {
  const digest = Core.buildDigest([], [{
    'Opportunity ID':'O1','Stage':'Proposal','Next Step Date':'2026-07-20','Value €':1000,'Probability %':0.5,'Weighted Value €':'','Company ID':'C1'
  }], {today});
  assert.equal(digest.items[0].probability_pct, 50);
  assert.equal(digest.items[0].weighted_value_eur, 500);
});

test('orders critical commercial work first', () => {
  const digest = Core.buildDigest([
    {'Lead ID':'L1','Status':'New','Next Action Date':'2026-07-21','Fit Score':10,'Company':'Low'}
  ], [{
    'Opportunity ID':'O1','Stage':'Proposal','Next Step Date':'2026-07-14','Value €':2000,'Probability %':0.7,'Weighted Value €':1400,'Company ID':'C1'
  }], {today});
  assert.equal(digest.items[0].record_id, 'O1');
  assert.equal(digest.items[0].priority, 'critical');
});

test('groups by owner and applies fallback', () => {
  const digest = Core.buildDigest([
    {'Lead ID':'L1','Status':'New','Next Action Date':'2026-07-21','Owner':'Nikita'},
    {'Lead ID':'L2','Status':'New','Next Action Date':'2026-07-21','Owner':''}
  ], [], {today, fallbackOwner:'Default Owner'});
  assert.equal(digest.owners.Nikita, 1);
  assert.equal(digest.owners['Default Owner'], 1);
});

test('limit is deterministic and reports truncation', () => {
  const rows = [1,2,3].map(i => ({'Lead ID':'L'+i,'Status':'New','Next Action Date':'2026-07-20','Fit Score':i}));
  const digest = Core.buildDigest(rows, [], {today, limit:2});
  assert.equal(digest.total_due, 3);
  assert.equal(digest.displayed, 2);
  assert.equal(digest.truncated, true);
  assert.deepEqual(digest.items.map(item => item.record_id), ['L3','L2']);
});

test('log record contains only aggregate digest data', () => {
  const digest = Core.buildDigest([{'Lead ID':'L1','Status':'New','Next Action Date':'2026-07-21'}], [], {today});
  const log = Core.makeLogRecord({digest, owner:'Owner', timestamp:'2026-07-21T12:01:00Z'});
  assert.equal(log.Workflow, 'A02');
  assert.equal(log['Trigger Record'], 'A02-2026-07-21');
  assert.ok(log.Notes.includes('total_due=1'));
  assert.equal(Object.prototype.hasOwnProperty.call(log, 'Email'), false);
});

console.log(JSON.stringify({ok: true, tests: evidence}, null, 2));
