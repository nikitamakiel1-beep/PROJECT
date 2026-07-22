import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const boardPath = path.join(root, 'apps/web/assets/model-evidence-board.json');
const modulePath = path.join(root, 'apps/web/assets/model-evidence-board.mjs');
const stylePath = path.join(root, 'apps/web/assets/model-evidence-board.css');

const board = JSON.parse(await fs.readFile(boardPath, 'utf8'));
const source = await fs.readFile(modulePath, 'utf8');
const style = await fs.readFile(stylePath, 'utf8');

function require(condition, message) {
  if (!condition) throw new Error(message);
}

require(board.promotion_permitted === false, 'demonstration board must prohibit promotion');
require(board.human_review_required === true, 'human review custody missing');
require(Array.isArray(board.cards) && board.cards.length >= 3, 'expected at least three evidence cards');
require(board.notice.toLowerCase().includes('synthetic'), 'synthetic notice missing');

const decisions = new Set();
for (const card of board.cards) {
  require(typeof card.candidate_id === 'string' && card.candidate_id.length > 0, 'candidate id missing');
  require(card.score >= 0 && card.score <= 1, `score out of range: ${card.candidate_id}`);
  require(card.rollback === 'verified' || card.rollback === 'blocked', `rollback state invalid: ${card.candidate_id}`);
  require(Array.isArray(card.route_debt), `route debt missing: ${card.candidate_id}`);
  require(Array.isArray(card.blockers), `blockers missing: ${card.candidate_id}`);
  require(Array.isArray(card.limitations) && card.limitations.length > 0, `limitations missing: ${card.candidate_id}`);
  require(Object.keys(card.axes).length === 8, `review axes incomplete: ${card.candidate_id}`);
  Object.values(card.axes).forEach(value => require(value >= 0 && value <= 1, `axis out of range: ${card.candidate_id}`));
  require(card.rollout.disagreement >= 0 && card.rollout.disagreement <= 1, 'disagreement out of range');
  require(card.rollout.abstention >= 0 && card.rollout.abstention <= 1, 'abstention out of range');
  require(card.rollout.incidents >= 0 && card.rollout.incidents <= 1, 'incident rate out of range');
  decisions.add(card.decision);
}

require(decisions.has('eligible_for_extended_shadow'), 'extended-shadow demonstration card missing');
require(decisions.has('human_review_required'), 'human-review demonstration card missing');
require(decisions.has('reject_or_rework'), 'rework demonstration card missing');
require(source.includes('Promotion disabled') && source.includes('Promoción desactivada'), 'bilingual disabled-promotion control missing');
require(source.includes('ensureSection') && source.includes('ensureStylesheet'), 'dynamic evidence-board mounting missing');
require(!source.includes('fetch("http') && !source.includes("fetch('http"), 'external endpoint found in evidence-board module');
require(style.includes('.model-evidence-card') && style.includes('@media (prefers-reduced-motion'), 'floating card or reduced-motion styles missing');

console.log(JSON.stringify({ ok: true, cards: board.cards.length, decisions: [...decisions].sort() }, null, 2));
