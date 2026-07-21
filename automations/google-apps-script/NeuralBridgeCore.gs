var NeuralBridgeCore = (function () {
  'use strict';

  var PACKAGE_VERSION = 'neural-provider-package-v1';
  var SERVICE_ALIASES = {OSP: 'IOP'};

  function text_(value) {
    return value === null || value === undefined ? '' : String(value).trim();
  }

  function number_(value, fallback) {
    var parsed = Number(value);
    return isFinite(parsed) ? parsed : (fallback === undefined ? 0 : fallback);
  }

  function clip_(value) {
    return Math.max(0, Math.min(1, number_(value, 0)));
  }

  function bool_(value) {
    if (value === true) return true;
    return ['true', 'yes', '1', 'active', 'accepted', 'recorded'].indexOf(text_(value).toLowerCase()) >= 0;
  }

  function canonicalService_(value) {
    var code = text_(value).toUpperCase();
    return SERVICE_ALIASES[code] || code;
  }

  function parseDate_(value) {
    if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value.getTime())) return value;
    var parsed = new Date(value);
    return isNaN(parsed.getTime()) ? null : parsed;
  }

  function daysSince_(value, today) {
    var parsed = parseDate_(value);
    if (!parsed) return 999;
    return Math.max(0, Math.floor((today.getTime() - parsed.getTime()) / 86400000));
  }

  function daysOverdue_(value, today) {
    var parsed = parseDate_(value);
    if (!parsed) return 0;
    return Math.max(0, Math.floor((today.getTime() - parsed.getTime()) / 86400000));
  }

  function stableStringify_(value) {
    if (value === null || typeof value !== 'object') return JSON.stringify(value);
    if (Array.isArray(value)) return '[' + value.map(stableStringify_).join(',') + ']';
    return '{' + Object.keys(value).sort().map(function (key) {
      return JSON.stringify(key) + ':' + stableStringify_(value[key]);
    }).join(',') + '}';
  }

  function indexBy_(rows, field, normalizer) {
    var index = {};
    (rows || []).forEach(function (row) {
      var raw = row[field];
      var key = normalizer ? normalizer(raw) : text_(raw);
      if (key && !Object.prototype.hasOwnProperty.call(index, key)) index[key] = row;
    });
    return index;
  }

  function serviceIndex_(rows) {
    var index = {};
    (rows || []).forEach(function (row) {
      var raw = text_(row['Service Code'] || row.code).toUpperCase();
      var canonical = canonicalService_(raw);
      if (raw) index[raw] = row;
      if (canonical) index[canonical] = row;
    });
    return index;
  }

  function serviceActive_(service) {
    if (!service) return false;
    var status = text_(service.status || service.Status).toLowerCase();
    return status === 'active' || bool_(service.Active || service.active);
  }

  function servicePrice_(service) {
    if (!service) return 0;
    var keys = ['price_eur', 'Standard Price €', 'standard_price_eur', 'Beta Price €'];
    for (var i = 0; i < keys.length; i += 1) {
      if (Object.prototype.hasOwnProperty.call(service, keys[i])) {
        var value = number_(service[keys[i]], -1);
        if (value >= 0) return value;
      }
    }
    return 0;
  }

  function serviceAutomation_(service) {
    var value = service && (service.automation_target_pct || service['Automation Target %'] || service.automation_pct);
    return clip_(number_(value, 0) / 100);
  }

  function serviceDelivery_(service) {
    return Math.max(0, number_(service && (service.delivery_days || service['Delivery Days']), 0));
  }

  function consent_(contact, lead) {
    var value = (text_(contact && contact['Consent Status']) + ' ' + text_(lead && lead['Consent Basis'])).toLowerCase();
    return ['accepted', 'recorded', 'authorised', 'requested', 'assessment'].some(function (token) {
      return value.indexOf(token) >= 0;
    }) ? 1 : 0;
  }

  function activityFeatures_(activity, today) {
    var days = daysSince_(activity.Date, today);
    var outcome = (text_(activity.Outcome) + ' ' + text_(activity.Summary)).toLowerCase();
    var type = text_(activity['Activity Type']).toLowerCase();
    var channel = text_(activity.Channel).toLowerCase();
    var positive = ['positive', 'interested', 'replied', 'accepted', 'meeting'].some(function (token) { return outcome.indexOf(token) >= 0; }) ? 1 : 0;
    var response = ['reply', 'replied', 'response', 'answered'].some(function (token) { return outcome.indexOf(token) >= 0; }) ? 1 : 0;
    var meeting = outcome.indexOf('meeting') >= 0 || type.indexOf('meeting') >= 0 || type.indexOf('call') >= 0 ? 1 : 0;
    var direct = ['email', 'phone', 'video', 'meeting', 'whatsapp'].indexOf(channel) >= 0 ? 1 : 0;
    var duration = clip_(number_(activity['Duration Minutes'], 0) / 60);
    var recency = Math.exp(-Math.min(days, 365) / 45);
    return [recency, positive, response, meeting, direct, duration];
  }

  function relationship_(contact, activities) {
    var raw = number_(contact && contact['Relationship Strength'], -1);
    if (raw >= 0) return clip_(raw > 1 ? raw / 100 : raw);
    var positive = (activities || []).reduce(function (sum, activity) {
      return sum + activityFeatures_(activity, new Date())[1];
    }, 0);
    return clip_(0.12 + (activities || []).length * 0.06 + positive * 0.09);
  }

  function hashedTextVector_(text, hashBytes, size) {
    var vector = [];
    for (var i = 0; i < size; i += 1) vector.push(0);
    var tokens = text_(text).toLowerCase().match(/[a-zA-ZÀ-ÿ0-9]{2,}/g) || [];
    tokens.forEach(function (token) {
      var digest = hashBytes(token);
      var bucket = digest[0] % size;
      var sign = digest[1] % 2 ? -1 : 1;
      vector[bucket] += sign * (1 + Math.min(token.length, 12) / 12);
    });
    var norm = Math.sqrt(vector.reduce(function (sum, value) { return sum + value * value; }, 0)) || 1;
    return vector.map(function (value) { return value / norm; });
  }

  function matchingActivities_(activities, lead, contact) {
    var companyId = text_(lead['Company ID']);
    var contactId = text_(lead['Contact ID']);
    return (activities || []).filter(function (activity) {
      if (contactId && text_(activity['Contact ID']) === contactId) return true;
      if (companyId && text_(activity['Company ID']) === companyId) return true;
      return false;
    }).sort(function (left, right) {
      var leftDate = parseDate_(left.Date);
      var rightDate = parseDate_(right.Date);
      return (leftDate ? leftDate.getTime() : 0) - (rightDate ? rightDate.getTime() : 0);
    }).slice(-20);
  }

  function existingOpportunity_(lead, serviceCode, opportunities) {
    var linked = text_(lead['Opportunity ID']);
    var leadId = text_(lead['Lead ID']);
    return (opportunities || []).some(function (opportunity) {
      if (linked && text_(opportunity['Opportunity ID']) === linked) return true;
      var notes = text_(opportunity.Notes);
      return notes.indexOf('lead_id=' + leadId) >= 0 && canonicalService_(opportunity['Service Code']) === serviceCode;
    });
  }

  function featurePackage_(lead, company, contact, service, activities, options) {
    var today = options.today;
    var fit = clip_(number_(lead['Fit Score'], 0) / 100);
    var relationship = relationship_(contact, activities);
    var consent = consent_(contact, lead);
    var qualified = text_(lead.Status).toLowerCase() === 'qualified' ? 1 : 0;
    var active = serviceActive_(service) ? 1 : 0;
    var price = servicePrice_(service);
    var automation = serviceAutomation_(service);
    var delivery = serviceDelivery_(service);
    var sinceContact = daysSince_(lead['Last Contact'] || (contact && contact['Last Contact']), today);
    var overdue = daysOverdue_(lead['Next Action Date'], today);
    var websitePresent = text_((company && company.Website) || lead.Website) ? 1 : 0;
    var internationalFit = number_(company && company['International Fit'], fit * 100);
    internationalFit = clip_(internationalFit > 1 ? internationalFit / 100 : internationalFit);
    var tabular = [
      fit, relationship, consent, qualified, active, clip_(price / 1000), automation,
      clip_(delivery / 30), clip_(activities.length / 20), clip_(sinceContact / 120),
      clip_(overdue / 30), clip_((websitePresent + internationalFit) / 2)
    ];
    var narrative = [
      lead.Notes, lead['Next Action'], company && company.Sector, company && company.Subsector,
      company && company.Notes, service && (service.name || service['Service Name'])
    ].map(text_).filter(Boolean).join(' ');
    var textVector = hashedTextVector_(narrative, options.hashBytes, 8);
    var activitySequence = activities.map(function (activity) { return activityFeatures_(activity, today); });
    var graphNodes = [
      [1, 0, 0, 0, internationalFit, websitePresent],
      [0, 1, 0, 0, relationship, consent],
      [0, 0, 1, 0, fit, qualified],
      [0, 0, 0, 1, clip_(price / 1000), automation]
    ];
    var adjacency = [[0,1,1,0],[1,0,1,0],[1,1,0,1],[0,0,1,0]];
    var activitySignal = clip_(activities.length / 8);
    var conversion = clip_(0.08 + fit * 0.42 + qualified * 0.22 + consent * 0.08 + active * 0.08 + activitySignal * 0.12);
    var urgency = clip_(overdue / 14 + (qualified ? 0.15 : 0));
    var churn = clip_(sinceContact / 120 - relationship * 0.35);
    var relationshipPrior = clip_(relationship * 0.72 + activitySignal * 0.18 + consent * 0.10);
    var actions = [0.05, 0.08, 0.22, 0.50, 0.15];
    if (!active || fit < 0.60) actions = [0.34, 0.26, 0.10, 0.02, 0.28];
    else if (!qualified) actions = [0.12, 0.18, 0.38, 0.05, 0.27];
    else if (consent < 1) actions = [0.10, 0.42, 0.20, 0.03, 0.25];
    return {
      features: {
        tabular: tabular,
        text_vector: textVector,
        activity_sequence: activitySequence,
        graph_nodes: graphNodes,
        adjacency: adjacency,
        focus_index: 2
      },
      priors: {
        conversion: conversion,
        relationship: relationshipPrior,
        urgency: urgency,
        churn: churn,
        actions: actions
      }
    };
  }

  function buildPackages(tables, options) {
    options = options || {};
    if (options.syntheticOnly !== true) throw new Error('synthetic_gate_closed');
    if (typeof options.pseudonymize !== 'function') throw new Error('pseudonymizer_required');
    if (typeof options.hashHex !== 'function' || typeof options.hashBytes !== 'function') throw new Error('hash_functions_required');
    var today = options.today instanceof Date ? options.today : new Date();
    var companies = indexBy_(tables.Companies || [], 'Company ID');
    var contacts = indexBy_(tables.Contacts || [], 'Contact ID');
    var services = serviceIndex_(tables.Services || []);
    var activities = tables.Activities || [];
    var opportunities = tables.Opportunities || [];
    var output = [];

    (tables.Leads || []).forEach(function (lead) {
      if (text_(lead.Status).toLowerCase() !== 'qualified') return;
      if (number_(lead['Fit Score'], 0) < 60) return;
      var leadId = text_(lead['Lead ID']);
      var companyId = text_(lead['Company ID']);
      var contactId = text_(lead['Contact ID']);
      var serviceCode = canonicalService_(lead['Service Interest']);
      if (!leadId || !companyId || !contactId || !serviceCode) return;
      var service = services[serviceCode] || services[text_(lead['Service Interest']).toUpperCase()];
      if (!serviceActive_(service) || servicePrice_(service) <= 0) return;
      if (existingOpportunity_(lead, serviceCode, opportunities)) return;
      var company = companies[companyId] || {};
      var contact = contacts[contactId] || {};
      var relatedActivities = matchingActivities_(activities, lead, contact);
      var featureBundle = featurePackage_(lead, company, contact, service, relatedActivities, {
        today: today,
        hashBytes: options.hashBytes
      });
      var leadRef = options.pseudonymize('lead', leadId);
      var companyRef = options.pseudonymize('company', companyId);
      var contactRef = options.pseudonymize('contact', contactId);
      var packageId = 'NPKG-' + options.hashHex([leadRef, serviceCode, today.toISOString().slice(0, 10)].join('|')).slice(0, 12).toUpperCase();
      var digestPayload = {
        package_id: packageId,
        lead_ref: leadRef,
        company_ref: companyRef,
        contact_ref: contactRef,
        service_code: serviceCode,
        service_price_eur: servicePrice_(service),
        features: featureBundle.features,
        priors: featureBundle.priors
      };
      var featureDigest = options.hashHex(stableStringify_(digestPayload));
      var neuralPackage = {
        package_version: PACKAGE_VERSION,
        synthetic_only: true,
        package_id: packageId,
        lead_ref: leadRef,
        company_ref: companyRef,
        contact_ref: contactRef,
        service_code: serviceCode,
        service_price_eur: servicePrice_(service),
        features: featureBundle.features,
        priors: featureBundle.priors,
        feature_digest: featureDigest
      };
      output.push({
        package: neuralPackage,
        internal: {
          lead_id: leadId,
          company_id: companyId,
          contact_id: contactId,
          service_code: serviceCode
        }
      });
    });
    return output;
  }

  function validateDecision(decision, expectedPackage) {
    if (!decision || decision.decision_version !== 'neural-provider-decision-v1') throw new Error('decision_version_invalid');
    if (text_(decision.package_id) !== text_(expectedPackage.package_id)) throw new Error('decision_package_mismatch');
    if (text_(decision.feature_digest) !== text_(expectedPackage.feature_digest)) throw new Error('decision_feature_digest_mismatch');
    if (!decision.decision_digest || !/^[a-f0-9]{64}$/i.test(String(decision.decision_digest))) throw new Error('decision_digest_invalid');
    if (!decision.execution_policy || decision.execution_policy.mutation_permitted !== false) throw new Error('shadow_mutation_policy_invalid');
    if (decision.execution_policy.external_communication_permitted !== false) throw new Error('external_communication_policy_invalid');
    return true;
  }

  return {
    PACKAGE_VERSION: PACKAGE_VERSION,
    canonicalService: canonicalService_,
    stableStringify: stableStringify_,
    buildPackages: buildPackages,
    validateDecision: validateDecision
  };
}());
