const clamp = value => Math.max(0, Math.min(1, Number(value) || 0));

function softmax(values) {
  const maximum = Math.max(...values);
  const exponentials = values.map(value => Math.exp(Math.max(-40, Math.min(40, value - maximum))));
  const total = exponentials.reduce((sum, value) => sum + value, 0) || 1;
  return exponentials.map(value => value / total);
}

function seededRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function weights(seed, count, scale = 0.32) {
  const random = seededRandom(seed);
  return Array.from({ length: count }, () => (random() * 2 - 1) * scale);
}

function normalise(values) {
  const magnitude = Math.sqrt(values.reduce((sum, value) => sum + value * value, 0)) || 1;
  return values.map(value => value / magnitude);
}

const SERVICE_PROFILES = Object.freeze({
  IVA: [0.95, 0.34, 0.28, 0.42, 0.72, 0.62, 0.80, 0.38, 0.88, 0.82],
  CRM: [0.24, 0.98, 0.82, 0.78, 0.36, 0.48, 0.72, 0.78, 0.84, 0.90],
  IOP: [0.55, 0.48, 0.98, 0.70, 0.92, 0.82, 0.76, 0.54, 0.72, 0.86],
  OSP: [0.55, 0.48, 0.98, 0.70, 0.92, 0.82, 0.76, 0.54, 0.72, 0.86],
  WAB: [0.16, 0.72, 0.58, 0.88, 0.24, 0.42, 0.62, 0.94, 0.90, 0.82],
  ISS: [0.72, 0.84, 0.86, 0.76, 0.78, 0.74, 0.58, 0.72, 0.34, 0.70]
});

const RELATIONSHIP_GRAPH = Object.freeze({
  IVA: { IOP: 0.74, CRM: 0.34, ISS: 0.62 },
  CRM: { WAB: 0.66, IOP: 0.42, ISS: 0.78 },
  IOP: { IVA: 0.72, CRM: 0.46, ISS: 0.76 },
  WAB: { CRM: 0.72, IOP: 0.32, ISS: 0.54 },
  ISS: { IVA: 0.68, CRM: 0.80, IOP: 0.78, WAB: 0.58 }
});

const REASON_DIMENSIONS = Object.freeze([
  'visibility', 'follow_up', 'sales_message', 'contact_speed', 'international_readiness',
  'multilingual', 'low_complexity', 'automation', 'speed', 'profitability'
]);

function encodeAnswers(answers) {
  const goalMap = {
    visibility: [1, 0, 0, 0],
    follow_up: [0, 1, 0, 0],
    sales_message: [0, 0, 1, 0],
    contact_speed: [0, 0, 0, 1]
  };
  const goal = goalMap[answers.goal] || [0.25, 0.25, 0.25, 0.25];
  return [
    ...goal,
    clamp(answers.international_readiness),
    clamp(answers.multilingual_need),
    1 - clamp(answers.complexity_tolerance),
    clamp(answers.automation_priority),
    clamp(answers.urgency),
    1 - clamp(answers.budget_sensitivity)
  ];
}

function sequenceFromFeatures(features) {
  return [
    features.slice(0, 4),
    [features[4], features[5], features[6], features[7]],
    [features[8], features[9], features[2], features[1]]
  ];
}

function cnnEncode(sequence, seed) {
  const kernels = [
    weights(seed + 1, 8, 0.30),
    weights(seed + 2, 8, 0.30),
    weights(seed + 3, 8, 0.30),
    weights(seed + 4, 8, 0.30)
  ];
  const padded = [[0, 0, 0, 0], ...sequence, [0, 0, 0, 0]];
  return kernels.map((kernel, channel) => {
    let maximum = 0;
    for (let start = 0; start < padded.length - 1; start += 1) {
      let activation = (channel - 1.5) * 0.025;
      for (let offset = 0; offset < 2; offset += 1) {
        for (let feature = 0; feature < 4; feature += 1) {
          activation += padded[start + offset][feature] * kernel[offset * 4 + feature];
        }
      }
      maximum = Math.max(maximum, activation);
    }
    return maximum;
  });
}

function graphPropagate(baseScores, activeCodes) {
  const canonical = code => code === 'OSP' ? 'IOP' : code;
  const scores = Object.fromEntries(activeCodes.map(code => [canonical(code), baseScores[canonical(code)] || 0]));
  const propagated = { ...scores };
  for (const [source, neighbours] of Object.entries(RELATIONSHIP_GRAPH)) {
    if (!(source in scores)) continue;
    for (const [target, weight] of Object.entries(neighbours)) {
      if (!(target in scores)) continue;
      propagated[target] += scores[source] * weight * 0.16;
    }
  }
  return propagated;
}

function profileScore(features, serviceCode) {
  const profile = SERVICE_PROFILES[serviceCode] || SERVICE_PROFILES[serviceCode === 'OSP' ? 'IOP' : serviceCode];
  if (!profile) return 0;
  return features.reduce((sum, value, index) => sum + value * profile[index], 0) / features.length;
}

function memberScores(features, activeCodes, seed) {
  const temporal = cnnEncode(sequenceFromFeatures(features), seed);
  const temporalSignal = temporal.reduce((sum, value) => sum + value, 0) / temporal.length;
  const random = weights(seed + 100, activeCodes.length * 3, 0.11);
  const base = {};
  activeCodes.forEach((rawCode, index) => {
    const code = rawCode === 'OSP' ? 'IOP' : rawCode;
    const direct = profileScore(features, code);
    const adjustment = random[index * 3] * features[4] + random[index * 3 + 1] * features[7] + random[index * 3 + 2] * temporalSignal;
    base[code] = Math.max(0.001, direct + temporalSignal * 0.18 + adjustment);
  });
  return graphPropagate(base, activeCodes);
}

function reasonIndexes(features, serviceCode) {
  const code = serviceCode === 'OSP' ? 'IOP' : serviceCode;
  const profile = SERVICE_PROFILES[code] || Array(10).fill(0);
  return features
    .map((value, index) => ({ index, score: value * profile[index] }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map(item => REASON_DIMENSIONS[item.index]);
}

export function recommendServices(answers, services, options = {}) {
  if (!Array.isArray(services) || services.length === 0) throw new Error('services_required');
  const active = services.filter(service => service.status === 'active');
  if (!active.length) throw new Error('active_services_required');
  const features = encodeAnswers(answers);
  const activeCodes = [...new Set(active.map(service => service.code === 'OSP' ? 'IOP' : service.code))];
  const seeds = options.seeds || [113, 227, 389, 557, 761];
  const memberDistributions = seeds.map(seed => {
    const raw = memberScores(features, activeCodes, seed);
    const probabilities = softmax(activeCodes.map(code => raw[code] * 4.2));
    return Object.fromEntries(activeCodes.map((code, index) => [code, probabilities[index]]));
  });
  const means = {};
  const variances = {};
  for (const code of activeCodes) {
    const values = memberDistributions.map(distribution => distribution[code]);
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
    means[code] = mean;
    variances[code] = variance;
  }
  const ranked = activeCodes
    .map(code => {
      const source = active.find(service => (service.code === 'OSP' ? 'IOP' : service.code) === code);
      const uncertainty = clamp(Math.sqrt(variances[code]) * 4.5);
      return {
        code,
        source_code: source?.code || code,
        probability: means[code],
        fit_pct: Math.round(means[code] * 100),
        confidence: clamp(1 - uncertainty),
        uncertainty,
        reasons: reasonIndexes(features, code),
        price_eur: Number(source?.price_eur || 0),
        delivery_days: Number(source?.delivery_days || 0)
      };
    })
    .sort((a, b) => b.probability - a.probability);
  const probabilityGap = ranked.length > 1 ? ranked[0].probability - ranked[1].probability : ranked[0].probability;
  return {
    model_version: 'web-neural-recommender-shadow-v0.1',
    local_only: true,
    features,
    recommendations: ranked,
    confidence: clamp(0.55 + probabilityGap * 1.8),
    requires_human_review: true
  };
}

export const recommenderContract = Object.freeze({
  model_version: 'web-neural-recommender-shadow-v0.1',
  feature_count: 10,
  cnn_sequence_shape: [3, 4],
  graph_nodes: ['IVA', 'CRM', 'IOP', 'WAB', 'ISS'],
  local_only: true,
  personal_data_required: false,
  automatic_purchase: false,
  automatic_contact: false
});
