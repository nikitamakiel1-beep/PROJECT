var FollowUpCore = (function () {
  'use strict';

  var PRIORITY_RANK = {critical: 0, high: 1, due: 2};
  var TERMINAL_LEAD = ['closed', 'lost', 'converted', 'disqualified'];
  var TERMINAL_OPPORTUNITY = ['won', 'lost', 'closed'];

  function text_(value) { return value == null ? '' : String(value).trim(); }
  function number_(value) {
    var parsed = Number(value);
    return isFinite(parsed) ? parsed : 0;
  }
  function date_(value) {
    if (!value) return null;
    var parsed = value instanceof Date ? new Date(value.getTime()) : new Date(String(value));
    if (isNaN(parsed.getTime())) return null;
    parsed.setHours(0, 0, 0, 0);
    return parsed;
  }
  function isoDate_(value) {
    var parsed = date_(value);
    return parsed ? parsed.toISOString().slice(0, 10) : '';
  }
  function daysOverdue_(today, due) {
    return Math.floor((today.getTime() - due.getTime()) / 86400000);
  }
  function isTerminal_(value, terminal) {
    return terminal.indexOf(text_(value).toLowerCase()) !== -1;
  }
  function priority_(days, commercialScore) {
    if (days >= 7 || commercialScore >= 120) return 'critical';
    if (days >= 3 || commercialScore >= 70) return 'high';
    return 'due';
  }
  function owner_(value, fallback) { return text_(value) || fallback || 'Unassigned'; }

  function leadItem_(row, today, fallbackOwner) {
    if (isTerminal_(row['Status'], TERMINAL_LEAD)) return null;
    var due = date_(row['Next Action Date']);
    if (!due || due.getTime() > today.getTime()) return null;
    var days = daysOverdue_(today, due);
    var fit = number_(row['Fit Score']);
    var score = days * 10 + fit;
    return {
      priority: priority_(days, score),
      record_type: 'Lead',
      record_id: text_(row['Lead ID']),
      company: text_(row['Company']),
      owner: owner_(row['Owner'], fallbackOwner),
      due_date: isoDate_(due),
      days_overdue: days,
      next_action: text_(row['Next Action']) || 'Review lead',
      value_eur: 0,
      probability_pct: 0,
      weighted_value_eur: 0,
      commercial_score: score,
      source_sheet: 'Leads'
    };
  }

  function opportunityItem_(row, today, fallbackOwner) {
    if (isTerminal_(row['Stage'], TERMINAL_OPPORTUNITY)) return null;
    var due = date_(row['Next Step Date']);
    if (!due || due.getTime() > today.getTime()) return null;
    var days = daysOverdue_(today, due);
    var value = number_(row['Value €']);
    var probability = number_(row['Probability %']);
    var weighted = number_(row['Weighted Value €']) || value * probability;
    var score = days * 10 + probability + Math.min(weighted / 100, 50);
    return {
      priority: priority_(days, score),
      record_type: 'Opportunity',
      record_id: text_(row['Opportunity ID']),
      company: text_(row['Company ID']),
      owner: owner_(row['Owner'], fallbackOwner),
      due_date: isoDate_(due),
      days_overdue: days,
      next_action: text_(row['Next Step']) || 'Review opportunity',
      value_eur: value,
      probability_pct: probability,
      weighted_value_eur: weighted,
      commercial_score: score,
      source_sheet: 'Opportunities'
    };
  }

  function compare_(a, b) {
    return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] ||
      b.commercial_score - a.commercial_score ||
      b.days_overdue - a.days_overdue ||
      a.due_date.localeCompare(b.due_date) ||
      a.record_type.localeCompare(b.record_type) ||
      a.record_id.localeCompare(b.record_id);
  }

  function buildDigest(leads, opportunities, options) {
    options = options || {};
    var today = date_(options.today || new Date());
    if (!today) throw new Error('invalid_today');
    var fallbackOwner = text_(options.fallbackOwner) || 'Unassigned';
    var limit = Math.max(1, Math.min(500, Number(options.limit) || 100));
    var items = [];
    (leads || []).forEach(function (row) {
      var item = leadItem_(row, today, fallbackOwner);
      if (item) items.push(item);
    });
    (opportunities || []).forEach(function (row) {
      var item = opportunityItem_(row, today, fallbackOwner);
      if (item) items.push(item);
    });
    items.sort(compare_);
    var totalItems = items.length;
    items = items.slice(0, limit);
    var counts = {critical: 0, high: 0, due: 0, Lead: 0, Opportunity: 0};
    var owners = {};
    items.forEach(function (item) {
      counts[item.priority] += 1;
      counts[item.record_type] += 1;
      owners[item.owner] = (owners[item.owner] || 0) + 1;
    });
    return {
      digest_date: isoDate_(today),
      trigger_record: 'A02-' + isoDate_(today),
      total_due: totalItems,
      displayed: items.length,
      truncated: totalItems > items.length,
      counts: counts,
      owners: owners,
      items: items
    };
  }

  function makeLogRecord(input) {
    return {
      'Log ID': input.log_id || ('LOG-A02-' + String(input.digest.trigger_record).replace(/[^A-Za-z0-9-]/g, '')),
      'Timestamp': input.timestamp || new Date().toISOString(),
      'Workflow': 'A02',
      'Trigger Record': input.digest.trigger_record,
      'Action': 'Build internal overdue follow-up digest',
      'Result': input.result || 'accepted',
      'Error': input.error || '',
      'Retry Count': Number(input.retry_count || 0),
      'Owner': input.owner || '',
      'Source System': 'CRM',
      'Destination System': 'Follow-up Digest',
      'Notes': 'displayed=' + input.digest.displayed + '; total_due=' + input.digest.total_due + '; critical=' + input.digest.counts.critical + '; high=' + input.digest.counts.high + '; due=' + input.digest.counts.due
    };
  }

  return {buildDigest: buildDigest, makeLogRecord: makeLogRecord};
}());
