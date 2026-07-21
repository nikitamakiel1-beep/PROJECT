function runDailyFollowUpDigest() {
  var lock = LockService.getScriptLock();
  lock.waitLock(15000);
  var ss = null;
  var digestSheet = null;
  var digestSnapshot = null;
  var digestSheetCreated = false;
  try {
    assertA02SyntheticGate_();
    ss = openA02Spreadsheet_();
    assertA02DisposableSpreadsheet_(ss);
    var leads = readA02Table_(requiredA02Sheet_(ss, 'Leads'));
    var opportunities = readA02Table_(requiredA02Sheet_(ss, 'Opportunities'));
    var logs = readA02Table_(requiredA02Sheet_(ss, 'Automation Log'));
    var options = {
      today: optionalA02Property_('A02_TODAY_OVERRIDE') || new Date(),
      fallbackOwner: optionalA02Property_('OWNER_NAME') || 'Unassigned',
      limit: Number(optionalA02Property_('A02_LIMIT') || 100)
    };
    var digest = FollowUpCore.buildDigest(leads, opportunities, options);
    var priorAttempts = logs.filter(function (row) {
      return String(row['Workflow']) === 'A02' && String(row['Trigger Record']) === digest.trigger_record;
    });
    if (priorAttempts.some(function (row) { return String(row['Result']) === 'accepted'; })) {
      return {ok: true, duplicate: true, digest: sanitiseA02Result_(digest)};
    }

    digestSheet = ss.getSheetByName('Follow-up Digest');
    digestSheetCreated = !digestSheet;
    if (!digestSheet) digestSheet = ss.insertSheet('Follow-up Digest');
    digestSnapshot = snapshotA02Sheet_(digestSheet);
    writeA02Digest_(digestSheet, digest);

    appendA02Object_(requiredA02Sheet_(ss, 'Automation Log'), FollowUpCore.makeLogRecord({
      digest: digest,
      result: 'accepted',
      retry_count: priorAttempts.length,
      timestamp: new Date().toISOString(),
      owner: options.fallbackOwner
    }));
    return {ok: true, duplicate: false, digest: sanitiseA02Result_(digest)};
  } catch (error) {
    if (ss && digestSheet) {
      try {
        if (digestSheetCreated) ss.deleteSheet(digestSheet);
        else restoreA02Sheet_(digestSheet, digestSnapshot);
      } catch (rollbackError) {}
    }
    if (ss && ss.getSheetByName('Automation Log')) {
      try {
        var fallbackDigest = {trigger_record: 'A02-unresolved', displayed: 0, total_due: 0, counts: {critical: 0, high: 0, due: 0}};
        appendA02Object_(ss.getSheetByName('Automation Log'), FollowUpCore.makeLogRecord({
          digest: fallbackDigest,
          result: 'failed',
          error: safeA02Error_(error),
          retry_count: 0,
          timestamp: new Date().toISOString(),
          owner: optionalA02Property_('OWNER_NAME')
        }));
      } catch (loggingError) {}
    }
    return {ok: false, error: safeA02Error_(error)};
  } finally {
    try { lock.releaseLock(); } catch (ignored) {}
  }
}

function runWeekdayDailyFollowUpDigest() {
  var day = new Date().getDay();
  if (day === 0 || day === 6) return {ok: true, skipped: true, reason: 'weekend'};
  return runDailyFollowUpDigest();
}

function openA02Spreadsheet_() {
  var id = optionalA02Property_('SPREADSHEET_ID');
  return id ? SpreadsheetApp.openById(id) : SpreadsheetApp.getActiveSpreadsheet();
}

function assertA02SyntheticGate_() {
  if (String(requiredA02Property_('SYNTHETIC_ONLY')).toLowerCase() !== 'true') {
    throw new Error('synthetic_gate_closed');
  }
}

function assertA02DisposableSpreadsheet_(ss) {
  if (!ss || ss.getName().indexOf('TEST —') !== 0) throw new Error('disposable_spreadsheet_required');
}

function requiredA02Property_(name) {
  var value = PropertiesService.getScriptProperties().getProperty(name);
  if (!value) throw new Error('missing_property_' + name.toLowerCase());
  return value;
}

function optionalA02Property_(name) {
  return PropertiesService.getScriptProperties().getProperty(name) || '';
}

function requiredA02Sheet_(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) throw new Error('missing_sheet_' + name.toLowerCase().replace(/\s+/g, '_'));
  return sheet;
}

function readA02Table_(sheet) {
  var lastColumn = sheet.getLastColumn();
  var lastRow = sheet.getLastRow();
  if (lastColumn < 1 || lastRow < 2) return [];
  var headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0].map(String);
  return sheet.getRange(2, 1, lastRow - 1, lastColumn).getValues().map(function (values) {
    var record = {};
    headers.forEach(function (header, index) { record[header] = values[index]; });
    return record;
  });
}

function writeA02Digest_(sheet, digest) {
  var headers = ['Priority', 'Record Type', 'Record ID', 'Company / Company ID', 'Owner', 'Due Date', 'Days Overdue', 'Next Action', 'Value €', 'Probability %', 'Weighted Value €', 'Source Sheet'];
  var rows = digest.items.map(function (item) {
    return [item.priority, item.record_type, item.record_id, item.company, item.owner, item.due_date, item.days_overdue, item.next_action, item.value_eur, item.probability_pct, item.weighted_value_eur, item.source_sheet];
  });
  sheet.clearContents();
  sheet.getRange(1, 1, 1, 4).setValues([['Digest Date', digest.digest_date, 'Total Due', digest.total_due]]);
  sheet.getRange(2, 1, 1, 6).setValues([['Displayed', digest.displayed, 'Critical', digest.counts.critical, 'High', digest.counts.high]]);
  sheet.getRange(4, 1, 1, headers.length).setValues([headers]);
  if (rows.length) sheet.getRange(5, 1, rows.length, headers.length).setValues(rows);
  sheet.setFrozenRows(4);
  sheet.autoResizeColumns(1, headers.length);
}

function appendA02Object_(sheet, record) {
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  sheet.appendRow(headers.map(function (header) { return Object.prototype.hasOwnProperty.call(record, header) ? record[header] : ''; }));
}

function snapshotA02Sheet_(sheet) {
  var lastRow = sheet.getLastRow();
  var lastColumn = sheet.getLastColumn();
  return {
    rows: lastRow,
    columns: lastColumn,
    values: lastRow && lastColumn ? sheet.getRange(1, 1, lastRow, lastColumn).getValues() : []
  };
}

function restoreA02Sheet_(sheet, snapshot) {
  sheet.clearContents();
  if (snapshot && snapshot.values && snapshot.values.length) {
    sheet.getRange(1, 1, snapshot.rows, snapshot.columns).setValues(snapshot.values);
  }
}

function sanitiseA02Result_(digest) {
  return {
    digest_date: digest.digest_date,
    trigger_record: digest.trigger_record,
    total_due: digest.total_due,
    displayed: digest.displayed,
    truncated: digest.truncated,
    counts: digest.counts,
    owners: digest.owners
  };
}

function safeA02Error_(error) {
  var value = error && error.message ? String(error.message) : 'internal_error';
  return /^[a-z0-9_]+$/.test(value) ? value : 'internal_error';
}
