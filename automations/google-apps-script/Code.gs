/**
 * Google Apps Script adapter for the pure IntakeCore contract.
 *
 * Script Properties required for synthetic testing:
 *   SPREADSHEET_ID
 *   CONSENT_VERSION
 *   ACTIVE_SERVICE_CODES   (comma separated, generated from schemas/services.json)
 *   SYNTHETIC_ONLY=true
 * Optional:
 *   OWNER_NAME
 */
function doPost(e) {
  var lock = LockService.getScriptLock();
  var payload = null;
  var ss = null;
  var snapshot = null;
  var retryCount = 0;
  var correlationId = '';
  var testFailureAfterSheet = '';
  try {
    lock.waitLock(15000);
    payload = parsePayload_(e);
    ss = SpreadsheetApp.openById(requiredProperty_('SPREADSHEET_ID'));
    assertSyntheticOnly_();
    testFailureAfterSheet = normaliseTestFailureSheet_(payload.__test_failure_after_sheet);
    assertSheetContracts_(ss);
    snapshot = readSnapshot_(ss);
    retryCount = countAttempts_(snapshot['Automation Log'], payload.submission_id);
    var options = contractOptions_();
    var plan = IntakeCore.preparePlan(payload, snapshot, options);
    correlationId = plan.correlation_id;

    if (plan.status === 'duplicate') {
      appendObject_(requiredSheet_(ss, 'Automation Log'), IntakeCore.makeLogRecord({
        status: 'duplicate', submission_id: plan.payload.submission_id,
        retry_count: plan.retry_count, correlation_id: plan.correlation_id,
        timestamp: new Date().toISOString(), owner: options.owner,
        notes: 'No operational rows changed.'
      }));
      return jsonResponse_({ok: true, duplicate: true, submission_id: plan.payload.submission_id, correlation_id: plan.correlation_id});
    }

    var writes = applyPlanTransaction_(ss, plan, testFailureAfterSheet);
    return jsonResponse_({
      ok: true, duplicate: false, submission_id: plan.payload.submission_id,
      correlation_id: plan.correlation_id, lead_id: plan.ids.lead,
      records_created: writes
    });
  } catch (err) {
    var code = safeErrorCode_(err);
    try {
      if (!ss) {
        var spreadsheetId = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
        if (spreadsheetId) ss = SpreadsheetApp.openById(spreadsheetId);
      }
      if (ss && ss.getSheetByName('Automation Log')) {
        var submissionId = payload && payload.submission_id ? String(payload.submission_id) : 'unresolved-' + Utilities.getUuid();
        if (!snapshot) snapshot = readSnapshotSafe_(ss);
        retryCount = countAttempts_(snapshot['Automation Log'] || [], submissionId);
        appendObject_(ss.getSheetByName('Automation Log'), IntakeCore.makeLogRecord({
          status: code.indexOf('missing_') === 0 || code.indexOf('invalid_') === 0 || code === 'consent_version_mismatch' ? 'rejected' : 'failed',
          submission_id: submissionId, retry_count: retryCount,
          correlation_id: correlationId || '', timestamp: new Date().toISOString(),
          owner: optionalProperty_('OWNER_NAME'), error_code: code,
          notes: 'Recoverable synthetic intake failure; no payload content retained.'
        }));
      }
    } catch (loggingError) {}
    return jsonResponse_({ok: false, error: code});
  } finally {
    try { lock.releaseLock(); } catch (ignored) {}
  }
}

function parsePayload_(e) {
  if (!e || !e.postData || !e.postData.contents) throw IntakeCore.contractError('missing_request_body', 'Missing request body.');
  try { return JSON.parse(e.postData.contents); }
  catch (error) { throw IntakeCore.contractError('invalid_json', 'Request body must contain valid JSON.'); }
}

function contractOptions_() {
  return {
    consentVersion: requiredProperty_('CONSENT_VERSION'),
    activeServiceCodes: requiredProperty_('ACTIVE_SERVICE_CODES').split(',').map(function (value) { return String(value).trim(); }).filter(String),
    owner: optionalProperty_('OWNER_NAME')
  };
}

function assertSyntheticOnly_() {
  if (String(requiredProperty_('SYNTHETIC_ONLY')).toLowerCase() !== 'true') {
    throw IntakeCore.contractError('synthetic_gate_closed', 'This deployment must remain synthetic-only during Stage 003.');
  }
}

function normaliseTestFailureSheet_(value) {
  var name = String(value || '').trim();
  if (!name) return '';
  if (['Companies','Contacts','Leads','Activities'].indexOf(name) === -1) {
    throw IntakeCore.contractError('invalid_test_failure_sheet', 'Synthetic failure injection sheet is invalid.');
  }
  return name;
}

function requiredProperty_(name) {
  var value = PropertiesService.getScriptProperties().getProperty(name);
  if (!value) throw IntakeCore.contractError('missing_property_' + name.toLowerCase(), 'Missing Script Property: ' + name);
  return value;
}

function optionalProperty_(name) {
  return PropertiesService.getScriptProperties().getProperty(name) || '';
}

function requiredSheet_(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) throw IntakeCore.contractError('missing_sheet_' + name.toLowerCase().replace(/\s+/g, '_'), 'Missing sheet: ' + name);
  return sheet;
}

function readTable_(sheet) {
  var lastColumn = sheet.getLastColumn();
  var lastRow = sheet.getLastRow();
  if (lastColumn < 1 || lastRow < 1) return [];
  var headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0].map(String);
  if (lastRow < 2) return [];
  return sheet.getRange(2, 1, lastRow - 1, lastColumn).getValues().map(function (values) {
    var record = {};
    headers.forEach(function (header, index) { record[header] = values[index]; });
    return record;
  });
}

function readSnapshot_(ss) {
  var snapshot = {};
  Object.keys(IntakeCore.HEADERS).forEach(function (name) { snapshot[name] = readTable_(requiredSheet_(ss, name)); });
  return snapshot;
}

function readSnapshotSafe_(ss) {
  var snapshot = {};
  Object.keys(IntakeCore.HEADERS).forEach(function (name) {
    var sheet = ss.getSheetByName(name);
    snapshot[name] = sheet ? readTable_(sheet) : [];
  });
  return snapshot;
}

function assertSheetContracts_(ss) {
  Object.keys(IntakeCore.HEADERS).forEach(function (name) {
    var sheet = requiredSheet_(ss, name);
    var expected = IntakeCore.HEADERS[name];
    var actual = sheet.getRange(1, 1, 1, expected.length).getValues()[0].map(String);
    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
      throw IntakeCore.contractError('sheet_contract_mismatch_' + name.toLowerCase().replace(/\s+/g, '_'), 'Sheet header contract mismatch: ' + name);
    }
  });
}

function countAttempts_(logs, submissionId) {
  return (logs || []).filter(function (row) { return String(row['Trigger Record']) === String(submissionId); }).length;
}

function appendObject_(sheet, record) {
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  var row = headers.map(function (header) { return Object.prototype.hasOwnProperty.call(record, header) ? record[header] : ''; });
  sheet.appendRow(row);
  return sheet.getLastRow();
}

function applyPlanTransaction_(ss, plan, testFailureAfterSheet) {
  var appended = [];
  var counts = {Companies: 0, Contacts: 0, Leads: 0, Activities: 0, 'Automation Log': 0};
  try {
    ['Companies','Contacts','Leads','Activities'].forEach(function (name) {
      var sheet = requiredSheet_(ss, name);
      (plan.records[name] || []).forEach(function (record) {
        var row = appendObject_(sheet, record);
        appended.push({sheet: sheet, row: row});
        counts[name] += 1;
      });
      if (testFailureAfterSheet === name) {
        throw IntakeCore.contractError('synthetic_injected_write_failure', 'Synthetic provider failure injected after ' + name + '.');
      }
    });
    var logSheet = requiredSheet_(ss, 'Automation Log');
    var logRow = appendObject_(logSheet, IntakeCore.makeLogRecord({
      status: 'accepted', submission_id: plan.payload.submission_id,
      retry_count: plan.retry_count, correlation_id: plan.correlation_id,
      timestamp: new Date().toISOString(), owner: contractOptions_().owner,
      notes: 'company=' + plan.ids.company + '; contact=' + plan.ids.contact + '; lead=' + plan.ids.lead + '; activity=' + plan.ids.activity + (plan.warnings.length ? '; warnings=' + plan.warnings.join(',') : '')
    }));
    appended.push({sheet: logSheet, row: logRow});
    counts['Automation Log'] += 1;
    return counts;
  } catch (error) {
    for (var i = appended.length - 1; i >= 0; i -= 1) {
      try { appended[i].sheet.deleteRow(appended[i].row); } catch (rollbackError) {}
    }
    throw IntakeCore.contractError('spreadsheet_write_failed', 'Spreadsheet write failed and appended rows were rolled back.');
  }
}

function safeErrorCode_(error) {
  var code = error && error.code ? String(error.code) : 'internal_error';
  return /^[a-z0-9_]+$/.test(code) ? code : 'internal_error';
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
