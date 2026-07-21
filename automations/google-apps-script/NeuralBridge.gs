function runNeuralShadowExport() {
  var lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    assertA06SyntheticGate_();
    var ss = openA06Spreadsheet_();
    assertA06DisposableSpreadsheet_(ss);
    var salt = requiredA06Property_('NEURAL_PSEUDONYM_SALT');
    var tables = {
      Leads: readA06Table_(requiredA06Sheet_(ss, 'Leads')),
      Companies: readA06Table_(requiredA06Sheet_(ss, 'Companies')),
      Contacts: readA06Table_(requiredA06Sheet_(ss, 'Contacts')),
      Services: readA06Table_(requiredA06Sheet_(ss, 'Services')),
      Activities: readA06Table_(requiredA06Sheet_(ss, 'Activities')),
      Opportunities: readA06Table_(requiredA06Sheet_(ss, 'Opportunities'))
    };
    var packages = NeuralBridgeCore.buildPackages(tables, {
      syntheticOnly: true,
      today: optionalA06Date_('A06_TODAY_OVERRIDE') || new Date(),
      pseudonymize: function (namespace, value) {
        return String(namespace).toUpperCase() + '-' + hmacA06Hex_(namespace + '|' + value, salt).slice(0, 16).toUpperCase();
      },
      hashHex: sha256A06Hex_,
      hashBytes: sha256A06Bytes_
    });
    var queue = ensureA06Queue_(ss);
    var result = upsertA06Packages_(queue, packages);
    appendA06Log_(ss, {
      workflow: 'A06',
      trigger: 'A06-' + Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'),
      action: 'Build PII-free neural shadow packages',
      result: 'accepted',
      notes: 'created=' + result.created + '; unchanged=' + result.unchanged + '; eligible=' + packages.length
    });
    return {ok: true, created: result.created, unchanged: result.unchanged, eligible: packages.length, package_ids: result.packageIds};
  } catch (error) {
    return {ok: false, error: safeA06Error_(error)};
  } finally {
    try { lock.releaseLock(); } catch (ignored) {}
  }
}

function importNeuralShadowDecision(decisionJson) {
  var lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    assertA06SyntheticGate_();
    var ss = openA06Spreadsheet_();
    assertA06DisposableSpreadsheet_(ss);
    var queue = requiredA06Sheet_(ss, 'Neural Shadow Queue');
    var decision = typeof decisionJson === 'string' ? JSON.parse(decisionJson) : decisionJson;
    var rows = readA06TableWithRows_(queue);
    var match = rows.filter(function (entry) { return String(entry.record['Package ID']) === String(decision.package_id); })[0];
    if (!match) throw new Error('package_not_found');
    var expectedPackage = JSON.parse(String(match.record['Export JSON'] || '{}'));
    NeuralBridgeCore.validateDecision(decision, expectedPackage);
    var headers = headerMapA06_(queue);
    queue.getRange(match.row, headers['Decision Digest']).setValue(String(decision.decision_digest));
    queue.getRange(match.row, headers['Decision JSON']).setValue(JSON.stringify(decision));
    queue.getRange(match.row, headers.Status).setValue('Decision Ready');
    queue.getRange(match.row, headers['Review Status']).setValue(decision.execution_policy && decision.execution_policy.bounded_auto_eligible ? 'AUTO_ELIGIBLE' : 'REVIEW_REQUIRED');
    queue.getRange(match.row, headers.Notes).setValue('Imported in neural shadow mode; external communication disabled.');
    appendA06Log_(ss, {
      workflow: 'A06',
      trigger: String(decision.package_id),
      action: 'Import neural shadow decision',
      result: 'accepted',
      notes: 'decision_digest=' + String(decision.decision_digest).slice(0, 16)
    });
    return {ok: true, package_id: decision.package_id, status: 'Decision Ready'};
  } catch (error) {
    return {ok: false, error: safeA06Error_(error)};
  } finally {
    try { lock.releaseLock(); } catch (ignored) {}
  }
}

function applyBoundedNeuralOpportunities() {
  var lock = LockService.getScriptLock();
  lock.waitLock(15000);
  var rollback = [];
  try {
    assertA06SyntheticGate_();
    if (String(requiredA06Property_('A03_AUTONOMY_MODE')).toLowerCase() !== 'bounded_auto') throw new Error('bounded_auto_mode_required');
    if (String(requiredA06Property_('A03_BOUNDED_WRITE_ENABLED')).toLowerCase() !== 'true') throw new Error('bounded_write_gate_closed');
    var ss = openA06Spreadsheet_();
    assertA06DisposableSpreadsheet_(ss);
    var queue = requiredA06Sheet_(ss, 'Neural Shadow Queue');
    var opportunities = requiredA06Sheet_(ss, 'Opportunities');
    var leads = requiredA06Sheet_(ss, 'Leads');
    var queueRows = readA06TableWithRows_(queue);
    var opportunityRows = readA06Table_(opportunities);
    var opportunityIds = {};
    opportunityRows.forEach(function (row) { opportunityIds[String(row['Opportunity ID'])] = true; });
    var leadRows = readA06TableWithRows_(leads);
    var leadsById = {};
    leadRows.forEach(function (entry) { leadsById[String(entry.record['Lead ID'])] = entry; });
    var opportunityHeaders = readA06Headers_(opportunities);
    var leadHeaderMap = headerMapA06_(leads);
    var queueHeaderMap = headerMapA06_(queue);
    var applied = [];

    queueRows.forEach(function (entry) {
      if (String(entry.record.Status) !== 'Decision Ready') return;
      if (String(entry.record['Review Status']) !== 'AUTO_ELIGIBLE') return;
      var decision = JSON.parse(String(entry.record['Decision JSON'] || '{}'));
      var expectedPackage = JSON.parse(String(entry.record['Export JSON'] || '{}'));
      NeuralBridgeCore.validateDecision(decision, expectedPackage);
      var prediction = decision.prediction || {};
      if (Number(prediction.confidence || 0) < 0.72) return;
      if (Number(prediction.uncertainty || 1) > 0.28) return;
      var action = decision.proposed_internal_action || {};
      var opportunityId = String(action.opportunity_ref || '');
      if (!opportunityId || opportunityIds[opportunityId]) {
        queue.getRange(entry.row, queueHeaderMap['Review Status']).setValue('DUPLICATE_PRESERVED');
        return;
      }
      var leadId = String(entry.record['Lead ID'] || '');
      var leadEntry = leadsById[leadId];
      if (!leadEntry) throw new Error('lead_mapping_not_found');
      if (String(leadEntry.record['Opportunity ID'] || '')) {
        queue.getRange(entry.row, queueHeaderMap['Review Status']).setValue('EXISTING_LINK_PRESERVED');
        return;
      }
      var record = {
        'Opportunity ID': opportunityId,
        'Company ID': String(entry.record['Company ID'] || ''),
        'Contact ID': String(entry.record['Contact ID'] || ''),
        'Service Code': String(decision.service_code || ''),
        'Stage': 'Qualified',
        'Value €': Number(action.value_eur || 0),
        'Probability %': Number(action.probability_pct || 0),
        'Weighted Value €': Number(action.weighted_value_eur || 0),
        'Created Date': new Date().toISOString(),
        'Expected Close': '',
        'Won/Lost Date': '',
        'Loss Reason': '',
        'Proposal URL': '',
        'Invoice Status': 'Not issued',
        'Payment Date': '',
        'Delivery Status': 'Not started',
        'Linear Issue': '',
        'Client Folder URL': '',
        'Owner': String(leadEntry.record.Owner || ''),
        'Next Step': 'Human review of neural shadow evidence',
        'Next Step Date': new Date().toISOString(),
        'Notes': 'lead_id=' + leadId + '; package_id=' + String(decision.package_id) + '; decision_digest=' + String(decision.decision_digest) + '; bounded_auto=true'
      };
      var appendedRow = opportunities.getLastRow() + 1;
      opportunities.appendRow(opportunityHeaders.map(function (header) { return Object.prototype.hasOwnProperty.call(record, header) ? record[header] : ''; }));
      rollback.push({type: 'delete_row', sheet: opportunities, row: appendedRow});
      var oldOpportunityId = leadEntry.record['Opportunity ID'] || '';
      leads.getRange(leadEntry.row, leadHeaderMap['Opportunity ID']).setValue(opportunityId);
      rollback.push({type: 'restore_cell', sheet: leads, row: leadEntry.row, column: leadHeaderMap['Opportunity ID'], value: oldOpportunityId});
      queue.getRange(entry.row, queueHeaderMap.Status).setValue('Applied');
      queue.getRange(entry.row, queueHeaderMap['Review Status']).setValue('AUTO_APPLIED');
      queue.getRange(entry.row, queueHeaderMap['Applied At']).setValue(new Date().toISOString());
      opportunityIds[opportunityId] = true;
      applied.push(opportunityId);
    });

    appendA06Log_(ss, {
      workflow: 'A03',
      trigger: 'A03-' + Utilities.formatDate(new Date(), 'UTC', 'yyyy-MM-dd'),
      action: 'Apply bounded neural Opportunity plans',
      result: 'accepted',
      notes: 'applied=' + applied.length + '; external_messages=0'
    });
    return {ok: true, applied: applied.length, opportunity_ids: applied};
  } catch (error) {
    rollbackA06_(rollback);
    return {ok: false, error: safeA06Error_(error)};
  } finally {
    try { lock.releaseLock(); } catch (ignored) {}
  }
}

function openA06Spreadsheet_() {
  var id = optionalA06Property_('SPREADSHEET_ID');
  return id ? SpreadsheetApp.openById(id) : SpreadsheetApp.getActiveSpreadsheet();
}

function assertA06SyntheticGate_() {
  if (String(requiredA06Property_('SYNTHETIC_ONLY')).toLowerCase() !== 'true') throw new Error('synthetic_gate_closed');
}

function assertA06DisposableSpreadsheet_(ss) {
  if (!ss || ss.getName().indexOf('TEST —') !== 0) throw new Error('disposable_spreadsheet_required');
}

function requiredA06Property_(name) {
  var value = PropertiesService.getScriptProperties().getProperty(name);
  if (!value) throw new Error('missing_property_' + name.toLowerCase());
  return value;
}

function optionalA06Property_(name) {
  return PropertiesService.getScriptProperties().getProperty(name) || '';
}

function optionalA06Date_(name) {
  var value = optionalA06Property_(name);
  if (!value) return null;
  var parsed = new Date(value);
  if (isNaN(parsed.getTime())) throw new Error('invalid_date_override');
  return parsed;
}

function requiredA06Sheet_(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) throw new Error('missing_sheet_' + name.toLowerCase().replace(/\s+/g, '_'));
  return sheet;
}

function readA06Headers_(sheet) {
  if (sheet.getLastColumn() < 1) return [];
  return sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
}

function readA06Table_(sheet) {
  return readA06TableWithRows_(sheet).map(function (entry) { return entry.record; });
}

function readA06TableWithRows_(sheet) {
  var headers = readA06Headers_(sheet);
  if (!headers.length || sheet.getLastRow() < 2) return [];
  return sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues().map(function (values, index) {
    var record = {};
    headers.forEach(function (header, column) { record[header] = values[column]; });
    return {row: index + 2, record: record};
  });
}

function headerMapA06_(sheet) {
  var map = {};
  readA06Headers_(sheet).forEach(function (header, index) { map[header] = index + 1; });
  return map;
}

function ensureA06Queue_(ss) {
  var sheet = ss.getSheetByName('Neural Shadow Queue');
  if (!sheet) sheet = ss.insertSheet('Neural Shadow Queue');
  var headers = ['Package ID', 'Created', 'Lead ID', 'Company ID', 'Contact ID', 'Service Code', 'Feature Digest', 'Status', 'Export JSON', 'Decision Digest', 'Decision JSON', 'Review Status', 'Applied At', 'Notes'];
  if (sheet.getLastRow() === 0) sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  var current = readA06Headers_(sheet);
  if (current.join('|') !== headers.join('|')) throw new Error('neural_queue_header_mismatch');
  sheet.setFrozenRows(1);
  return sheet;
}

function upsertA06Packages_(sheet, packages) {
  var existing = {};
  readA06TableWithRows_(sheet).forEach(function (entry) { existing[String(entry.record['Package ID'])] = entry; });
  var created = 0;
  var unchanged = 0;
  var ids = [];
  packages.forEach(function (item) {
    var neuralPackage = item.package;
    ids.push(neuralPackage.package_id);
    var match = existing[neuralPackage.package_id];
    if (match) {
      if (String(match.record['Feature Digest']) !== String(neuralPackage.feature_digest)) throw new Error('package_id_feature_collision');
      unchanged += 1;
      return;
    }
    sheet.appendRow([
      neuralPackage.package_id,
      new Date().toISOString(),
      item.internal.lead_id,
      item.internal.company_id,
      item.internal.contact_id,
      item.internal.service_code,
      neuralPackage.feature_digest,
      'Export Ready',
      JSON.stringify(neuralPackage),
      '', '', 'PENDING', '',
      'PII-free package; raw mapping retained only inside this spreadsheet.'
    ]);
    created += 1;
  });
  return {created: created, unchanged: unchanged, packageIds: ids};
}

function appendA06Log_(ss, input) {
  var sheet = requiredA06Sheet_(ss, 'Automation Log');
  var headers = readA06Headers_(sheet);
  var timestamp = new Date().toISOString();
  var record = {
    'Log ID': 'LOG-' + sha256A06Hex_([input.workflow, input.trigger, timestamp].join('|')).slice(0, 12).toUpperCase(),
    'Timestamp': timestamp,
    'Workflow': input.workflow,
    'Trigger Record': input.trigger,
    'Action': input.action,
    'Result': input.result,
    'Error': '',
    'Retry Count': 0,
    'Owner': optionalA06Property_('OWNER_NAME') || 'Unassigned',
    'Source System': 'CRM',
    'Destination System': 'Neural shadow queue',
    'Notes': input.notes
  };
  sheet.appendRow(headers.map(function (header) { return Object.prototype.hasOwnProperty.call(record, header) ? record[header] : ''; }));
}

function rollbackA06_(operations) {
  for (var index = operations.length - 1; index >= 0; index -= 1) {
    var item = operations[index];
    try {
      if (item.type === 'delete_row') item.sheet.deleteRow(item.row);
      if (item.type === 'restore_cell') item.sheet.getRange(item.row, item.column).setValue(item.value);
    } catch (ignored) {}
  }
}

function sha256A06Bytes_(value) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(value), Utilities.Charset.UTF_8).map(function (byte) { return byte < 0 ? byte + 256 : byte; });
}

function sha256A06Hex_(value) {
  return sha256A06Bytes_(value).map(function (byte) { return ('0' + byte.toString(16)).slice(-2); }).join('');
}

function hmacA06Hex_(value, secret) {
  return Utilities.computeHmacSha256Signature(String(value), String(secret), Utilities.Charset.UTF_8).map(function (byte) {
    var normalized = byte < 0 ? byte + 256 : byte;
    return ('0' + normalized.toString(16)).slice(-2);
  }).join('');
}

function safeA06Error_(error) {
  var value = error && error.message ? String(error.message) : 'internal_error';
  return /^[a-z0-9_]+$/.test(value) ? value : 'internal_error';
}
