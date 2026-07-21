/**
 * Stage 003 provider-runtime HTTP suite.
 *
 * Required Script Properties:
 *   SPREADSHEET_ID
 *   CONSENT_VERSION
 *   ACTIVE_SERVICE_CODES
 *   SYNTHETIC_ONLY=true
 *   WEB_APP_URL
 *
 * The target spreadsheet must be disposable and its title must start with:
 *   TEST — A01 Synthetic Intake —
 */
var ProviderStage003 = (function () {
  'use strict';

  var SHEETS = ['Companies', 'Contacts', 'Leads', 'Activities', 'Automation Log'];

  function run() {
    assertSyntheticGate_();
    var ss = SpreadsheetApp.openById(requiredProperty_('SPREADSHEET_ID'));
    assertDisposableSpreadsheet_(ss);
    assertSheetContracts_(ss);

    var initialCounts = countRows_(ss);
    var runId = 'stage003-' + Utilities.formatDate(new Date(), 'UTC', 'yyyyMMdd-HHmmss') + '-' + Utilities.getUuid().slice(0, 8);
    var consentVersion = requiredProperty_('CONSENT_VERSION');
    var serviceCode = requiredProperty_('ACTIVE_SERVICE_CODES').split(',')[0].trim();
    var evidence = {
      run_id: runId,
      started_at: new Date().toISOString(),
      synthetic_only: true,
      cases: [],
      initial_counts: initialCounts,
      cleanup: null,
      passed: false
    };

    try {
      var base = payload_(runId + '-new-0001', 'Synthetic Provider Lab', 'Primary Test', 'primary@provider.example.test', 'https://provider.example.test', serviceCode, consentVersion);
      evidence.cases.push(executeCase_(ss, 'new_submission', base, delta_(1, 1, 1, 1, 1), {ok: true, duplicate: false}));
      evidence.cases.push(executeCase_(ss, 'exact_retry', base, delta_(0, 0, 0, 0, 1), {ok: true, duplicate: true}));

      var second = payload_(runId + '-company-0002', 'Synthetic Provider Lab', 'Second Test', 'second@provider.example.test', 'https://provider.example.test', serviceCode, consentVersion);
      evidence.cases.push(executeCase_(ss, 'existing_company_new_contact', second, delta_(0, 1, 1, 1, 1), {ok: true, duplicate: false}));

      var existingContact = payload_(runId + '-contact-0003', 'Conflicting Synthetic Company', 'Second Test', 'second@provider.example.test', 'https://conflict.example.test', serviceCode, consentVersion);
      evidence.cases.push(executeCase_(ss, 'existing_contact', existingContact, delta_(0, 0, 1, 1, 1), {ok: true, duplicate: false}));

      var malformed = payload_(runId + '-invalid-email-0004', 'Synthetic Invalid Lab', 'Invalid Email', 'not-an-email', 'https://invalid-email.example.test', serviceCode, consentVersion);
      evidence.cases.push(executeCase_(ss, 'malformed_email', malformed, delta_(0, 0, 0, 0, 1), {ok: false, error: 'invalid_email'}));

      var missingCompany = payload_(runId + '-missing-company-0005', '', 'Missing Company', 'missing-company@provider.example.test', 'https://missing-company.example.test', serviceCode, consentVersion);
      evidence.cases.push(executeCase_(ss, 'missing_company', missingCompany, delta_(0, 0, 0, 0, 1), {ok: false, error: 'missing_company_name'}));

      var invalidService = payload_(runId + '-invalid-service-0006', 'Synthetic Invalid Service', 'Invalid Service', 'invalid-service@provider.example.test', 'https://invalid-service.example.test', 'NOT-ACTIVE', consentVersion);
      evidence.cases.push(executeCase_(ss, 'invalid_service', invalidService, delta_(0, 0, 0, 0, 1), {ok: false, error: 'invalid_service_code'}));

      var injectedFailure = payload_(runId + '-failure-0007', 'Synthetic Rollback Lab', 'Rollback Test', 'rollback@provider.example.test', 'https://rollback.example.test', serviceCode, consentVersion);
      injectedFailure.__test_failure_after_sheet = 'Contacts';
      evidence.cases.push(executeCase_(ss, 'injected_write_failure', injectedFailure, delta_(0, 0, 0, 0, 1), {ok: false, error: 'spreadsheet_write_failed'}));

      evidence.passed = evidence.cases.every(function (item) { return item.passed; });
      evidence.finished_at = new Date().toISOString();
      return evidence;
    } finally {
      evidence.cleanup = cleanupToCounts_(ss, initialCounts);
      evidence.finished_at = evidence.finished_at || new Date().toISOString();
      Logger.log(JSON.stringify(evidence));
    }
  }

  function payload_(submissionId, companyName, contactName, email, website, serviceCode, consentVersion) {
    return {
      submission_id: submissionId,
      company_name: companyName,
      contact_name: contactName,
      email: email,
      website: website,
      country: 'ES',
      phone: '',
      role: 'Synthetic tester',
      service_code: serviceCode,
      problem: 'Stage 003 provider-runtime synthetic test.',
      consent_version: consentVersion,
      preferred_language: 'en',
      source: 'Stage 003 provider suite',
      submitted_at: new Date().toISOString()
    };
  }

  function executeCase_(ss, name, payload, expectedDelta, expectedResponse) {
    var before = countRows_(ss);
    var response = post_(payload);
    Utilities.sleep(250);
    var after = countRows_(ss);
    var actualDelta = subtractCounts_(after, before);
    var deltaPass = sameCounts_(actualDelta, expectedDelta);
    var responsePass = matchesExpected_(response.body, expectedResponse);
    return {
      name: name,
      submission_id: payload.submission_id,
      response_code: response.code,
      response: response.body,
      expected_delta: expectedDelta,
      actual_delta: actualDelta,
      delta_passed: deltaPass,
      response_passed: responsePass,
      passed: deltaPass && responsePass
    };
  }

  function post_(payload) {
    var response = UrlFetchApp.fetch(requiredProperty_('WEB_APP_URL'), {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      followRedirects: true,
      headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()}
    });
    var text = response.getContentText();
    var body;
    try { body = JSON.parse(text); }
    catch (error) { body = {parse_error: true, raw_length: text.length}; }
    return {code: response.getResponseCode(), body: body};
  }

  function countRows_(ss) {
    var counts = {};
    SHEETS.forEach(function (name) {
      counts[name] = Math.max(0, requiredSheet_(ss, name).getLastRow() - 1);
    });
    return counts;
  }

  function subtractCounts_(after, before) {
    var result = {};
    SHEETS.forEach(function (name) { result[name] = Number(after[name] || 0) - Number(before[name] || 0); });
    return result;
  }

  function delta_(companies, contacts, leads, activities, logs) {
    return {
      Companies: companies,
      Contacts: contacts,
      Leads: leads,
      Activities: activities,
      'Automation Log': logs
    };
  }

  function sameCounts_(actual, expected) {
    return SHEETS.every(function (name) { return Number(actual[name]) === Number(expected[name]); });
  }

  function matchesExpected_(actual, expected) {
    return Object.keys(expected).every(function (key) { return actual && actual[key] === expected[key]; });
  }

  function cleanupToCounts_(ss, initialCounts) {
    var result = {started_at: new Date().toISOString(), sheets: {}, passed: true};
    SHEETS.forEach(function (name) {
      var sheet = requiredSheet_(ss, name);
      var targetLastRow = Number(initialCounts[name] || 0) + 1;
      var currentLastRow = sheet.getLastRow();
      var removed = 0;
      if (currentLastRow > targetLastRow) {
        removed = currentLastRow - targetLastRow;
        sheet.deleteRows(targetLastRow + 1, removed);
      }
      var finalCount = Math.max(0, sheet.getLastRow() - 1);
      var passed = finalCount === Number(initialCounts[name] || 0);
      result.sheets[name] = {removed: removed, final_count: finalCount, passed: passed};
      if (!passed) result.passed = false;
    });
    result.finished_at = new Date().toISOString();
    return result;
  }

  function assertDisposableSpreadsheet_(ss) {
    if (ss.getName().indexOf('TEST — A01 Synthetic Intake —') !== 0) {
      throw new Error('Refusing to test: spreadsheet title is not the disposable Stage 003 pattern.');
    }
  }

  function assertSyntheticGate_() {
    if (String(requiredProperty_('SYNTHETIC_ONLY')).toLowerCase() !== 'true') {
      throw new Error('Refusing to test: SYNTHETIC_ONLY must equal true.');
    }
  }

  function requiredProperty_(name) {
    var value = PropertiesService.getScriptProperties().getProperty(name);
    if (!value) throw new Error('Missing Script Property: ' + name);
    return value;
  }

  function requiredSheet_(ss, name) {
    var sheet = ss.getSheetByName(name);
    if (!sheet) throw new Error('Missing sheet: ' + name);
    return sheet;
  }

  return {run: run};
}());

function runProviderHttpSuite() {
  return ProviderStage003.run();
}
