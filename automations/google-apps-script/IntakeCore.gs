/**
 * Pure intake contract shared by Google Apps Script and the local synthetic harness.
 * This file deliberately avoids SpreadsheetApp, PropertiesService and browser APIs.
 */
var IntakeCore = (function () {
  'use strict';

  var REQUIRED_FIELDS = [
    'submission_id', 'company_name', 'contact_name', 'email',
    'service_code', 'consent_version'
  ];

  var HEADERS = {
    Companies: ['Company ID','Company Name','Website','Sector','Subsector','Country','Region','Employees','Revenue Band','Export Status','Target Markets','Languages','Digital Maturity','International Fit','Last Researched','Source URLs','Google Business URL','LinkedIn URL','Owner','Notes'],
    Contacts: ['Contact ID','Company ID','Full Name','Role','Email','Phone','LinkedIn','Preferred Channel','Language','Consent Status','Consent Date','Last Contact','Next Contact','Owner','Relationship Strength','Notes'],
    Leads: ['Lead ID','Created Date','Company','Contact Name','Role','Email','Phone','Website','Country','Source','Consent Basis','Service Interest','Fit Score','Status','Last Contact','Next Action Date','Next Action','Owner','Notes','Company ID','Contact ID','Opportunity ID'],
    Activities: ['Activity ID','Date','Company ID','Contact ID','Opportunity ID','Activity Type','Channel','Summary','Outcome','Next Action','Next Action Date','Owner','Source / Link','Duration Minutes','Billable','Notes'],
    'Automation Log': ['Log ID','Timestamp','Workflow','Trigger Record','Action','Result','Error','Retry Count','Owner','Source System','Destination System','Notes']
  };

  function trim(value) { return String(value == null ? '' : value).trim(); }
  function normalise(value) { return trim(value).toLowerCase().replace(/\s+/g, ' '); }
  function normaliseEmail(value) { return normalise(value); }

  function normaliseWebsite(value) {
    var raw = trim(value);
    if (!raw) return '';
    var host = raw.replace(/^[a-z][a-z0-9+.-]*:\/\//i, '').split(/[\/?#]/)[0].toLowerCase();
    if (host.indexOf('@') !== -1) host = host.split('@').pop();
    host = host.replace(/:\d+$/, '').replace(/^www\./, '');
    if (!host || /\s/.test(host) || !/^[a-z0-9.-]+$/.test(host) || host.indexOf('.') === -1 || /^\.|\.$|\.\./.test(host)) {
      throw contractError('invalid_website', 'Website must be a valid hostname or URL.');
    }
    return host;
  }

  function contractError(code, message) {
    var error = new Error(message);
    error.code = code;
    return error;
  }

  function stableHash(input) {
    var text = String(input);
    var hash = 2166136261;
    for (var i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return ('00000000' + (hash >>> 0).toString(16).toUpperCase()).slice(-8);
  }

  function stableId(prefix, input) { return prefix + '-' + stableHash(input); }

  function validatePayload(payload, options) {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw contractError('invalid_payload', 'Payload must be a JSON object.');
    }
    REQUIRED_FIELDS.forEach(function (key) {
      if (!trim(payload[key])) throw contractError('missing_' + key, 'Missing required field: ' + key);
    });
    if (trim(payload.submission_id).length < 8) {
      throw contractError('invalid_submission_id', 'submission_id must contain at least eight characters.');
    }
    if (trim(payload.company_name).length < 2 || trim(payload.contact_name).length < 2) {
      throw contractError('invalid_name', 'Company and contact names must contain at least two characters.');
    }
    var email = normaliseEmail(payload.email);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      throw contractError('invalid_email', 'Email format is invalid.');
    }
    var consentVersion = trim(options.consentVersion);
    if (!consentVersion || trim(payload.consent_version) !== consentVersion) {
      throw contractError('consent_version_mismatch', 'Consent version does not match the configured version.');
    }
    var allowed = options.activeServiceCodes || [];
    if (allowed.indexOf(trim(payload.service_code)) === -1) {
      throw contractError('invalid_service_code', 'Service code is not active or supported.');
    }
    if (trim(payload.problem).length > 3000) {
      throw contractError('problem_too_long', 'Problem description exceeds 3000 characters.');
    }
    if (payload.preferred_language && ['en','es','ca','other'].indexOf(trim(payload.preferred_language)) === -1) {
      throw contractError('invalid_language', 'Preferred language is unsupported.');
    }
    return sanitisePayload(payload);
  }

  function sanitisePayload(payload) {
    var submittedAt = trim(payload.submitted_at);
    var timestamp = submittedAt && !isNaN(Date.parse(submittedAt)) ? new Date(submittedAt).toISOString() : new Date().toISOString();
    return {
      submission_id: trim(payload.submission_id),
      company_name: trim(payload.company_name),
      contact_name: trim(payload.contact_name),
      email: normaliseEmail(payload.email),
      website: trim(payload.website),
      website_key: normaliseWebsite(payload.website),
      country: trim(payload.country),
      phone: trim(payload.phone),
      role: trim(payload.role),
      service_code: trim(payload.service_code),
      problem: trim(payload.problem),
      consent_version: trim(payload.consent_version),
      preferred_language: trim(payload.preferred_language) || 'en',
      source: trim(payload.source) || 'Website assessment',
      submitted_at: timestamp
    };
  }

  function recordValue(record, key) { return record && record[key] != null ? record[key] : ''; }
  function findBy(records, predicate) {
    for (var i = 0; i < records.length; i += 1) if (predicate(records[i])) return records[i];
    return null;
  }

  function companyKeyFromRecord(record) {
    var website = trim(recordValue(record, 'Website'));
    if (website) {
      try { return 'web:' + normaliseWebsite(website); } catch (ignored) {}
    }
    return 'name:' + normalise(recordValue(record, 'Company Name'));
  }

  function companyKeyFromPayload(payload) {
    return payload.website_key ? 'web:' + payload.website_key : 'name:' + normalise(payload.company_name);
  }

  function hasSuccessfulSubmission(logs, submissionId) {
    return !!findBy(logs, function (row) {
      return trim(recordValue(row, 'Trigger Record')) === submissionId &&
        ['accepted','duplicate'].indexOf(normalise(recordValue(row, 'Result'))) !== -1;
    });
  }

  function nextRetryCount(logs, submissionId) {
    var count = 0;
    logs.forEach(function (row) {
      if (trim(recordValue(row, 'Trigger Record')) === submissionId) count += 1;
    });
    return count;
  }

  function preparePlan(rawPayload, snapshot, options) {
    var payload = validatePayload(rawPayload, options);
    var logs = snapshot['Automation Log'] || [];
    var retryCount = nextRetryCount(logs, payload.submission_id);
    var correlationId = 'A01-' + stableHash(payload.submission_id);
    var ids = {
      company: stableId('COM', companyKeyFromPayload(payload)),
      contact: stableId('CON', payload.email),
      lead: stableId('LEAD', payload.submission_id),
      activity: stableId('ACT', payload.submission_id)
    };

    if (hasSuccessfulSubmission(logs, payload.submission_id)) {
      return {
        status: 'duplicate', payload: payload, retry_count: retryCount,
        correlation_id: correlationId, ids: ids,
        records: {Companies: [], Contacts: [], Leads: [], Activities: []},
        warnings: []
      };
    }

    var companies = snapshot.Companies || [];
    var contacts = snapshot.Contacts || [];
    var leads = snapshot.Leads || [];
    var activities = snapshot.Activities || [];
    var contact = findBy(contacts, function (row) { return normaliseEmail(recordValue(row, 'Email')) === payload.email; });
    var company = null;
    var warnings = [];

    if (contact) {
      ids.contact = trim(recordValue(contact, 'Contact ID')) || ids.contact;
      var linkedCompanyId = trim(recordValue(contact, 'Company ID'));
      company = findBy(companies, function (row) { return trim(recordValue(row, 'Company ID')) === linkedCompanyId; });
      if (company) ids.company = trim(recordValue(company, 'Company ID')) || ids.company;
      if (company && companyKeyFromRecord(company) !== companyKeyFromPayload(payload)) {
        warnings.push('existing_contact_company_precedence');
      }
    }

    if (!company) {
      var submittedCompanyKey = companyKeyFromPayload(payload);
      company = findBy(companies, function (row) { return companyKeyFromRecord(row) === submittedCompanyKey; });
      if (company) ids.company = trim(recordValue(company, 'Company ID')) || ids.company;
    }

    var existingLead = findBy(leads, function (row) { return trim(recordValue(row, 'Lead ID')) === ids.lead; });
    var existingActivity = findBy(activities, function (row) { return trim(recordValue(row, 'Activity ID')) === ids.activity; });
    var nextActionDate = new Date(new Date(payload.submitted_at).getTime() + 24 * 60 * 60 * 1000).toISOString();
    var records = {Companies: [], Contacts: [], Leads: [], Activities: []};

    if (!company) {
      records.Companies.push({
        'Company ID': ids.company,
        'Company Name': payload.company_name,
        'Website': payload.website,
        'Country': payload.country,
        'Languages': payload.preferred_language,
        'Source URLs': payload.website,
        'Notes': 'Created by synthetic A01 intake; correlation=' + correlationId
      });
    }

    if (!contact) {
      records.Contacts.push({
        'Contact ID': ids.contact,
        'Company ID': ids.company,
        'Full Name': payload.contact_name,
        'Role': payload.role,
        'Email': payload.email,
        'Phone': payload.phone,
        'Preferred Channel': 'Email',
        'Language': payload.preferred_language,
        'Consent Status': 'Assessment consent recorded',
        'Consent Date': payload.submitted_at,
        'Next Contact': nextActionDate,
        'Notes': 'consent=' + payload.consent_version + '; correlation=' + correlationId
      });
    }

    if (!existingLead) {
      records.Leads.push({
        'Lead ID': ids.lead,
        'Created Date': payload.submitted_at,
        'Company': payload.company_name,
        'Contact Name': payload.contact_name,
        'Role': payload.role,
        'Email': payload.email,
        'Phone': payload.phone,
        'Website': payload.website,
        'Country': payload.country,
        'Source': payload.source,
        'Consent Basis': 'Website assessment — ' + payload.consent_version,
        'Service Interest': payload.service_code,
        'Status': 'New',
        'Next Action Date': nextActionDate,
        'Next Action': 'Review synthetic submission',
        'Owner': options.owner || '',
        'Notes': payload.problem + (payload.problem ? '\n' : '') + 'submission_id=' + payload.submission_id + '; correlation=' + correlationId,
        'Company ID': ids.company,
        'Contact ID': ids.contact
      });
    }

    if (!existingActivity) {
      records.Activities.push({
        'Activity ID': ids.activity,
        'Date': payload.submitted_at,
        'Company ID': ids.company,
        'Contact ID': ids.contact,
        'Activity Type': 'Lead intake',
        'Channel': 'Website',
        'Summary': 'Synthetic assessment received',
        'Outcome': 'Lead record prepared',
        'Next Action': 'Review submission',
        'Next Action Date': nextActionDate,
        'Owner': options.owner || '',
        'Source / Link': payload.submission_id,
        'Duration Minutes': 0,
        'Billable': false,
        'Notes': 'correlation=' + correlationId
      });
    }

    return {
      status: 'accepted', payload: payload, retry_count: retryCount,
      correlation_id: correlationId, ids: ids, records: records, warnings: warnings
    };
  }

  function makeLogRecord(context) {
    var status = context.status;
    var submissionId = context.submission_id || 'unresolved';
    var correlationId = context.correlation_id || ('A01-' + stableHash(submissionId));
    var retryCount = Number(context.retry_count || 0);
    var timestamp = context.timestamp || new Date().toISOString();
    return {
      'Log ID': stableId('LOG', submissionId + ':' + retryCount + ':' + status),
      'Timestamp': timestamp,
      'Workflow': 'A01',
      'Trigger Record': submissionId,
      'Action': 'Synthetic website intake',
      'Result': status,
      'Error': context.error_code || '',
      'Retry Count': retryCount,
      'Owner': context.owner || '',
      'Source System': 'Website assessment',
      'Destination System': 'CRM',
      'Notes': 'correlation=' + correlationId + (context.notes ? '; ' + context.notes : '')
    };
  }

  return {
    HEADERS: HEADERS,
    normalise: normalise,
    normaliseEmail: normaliseEmail,
    normaliseWebsite: normaliseWebsite,
    stableId: stableId,
    validatePayload: validatePayload,
    preparePlan: preparePlan,
    makeLogRecord: makeLogRecord,
    contractError: contractError
  };
}());
