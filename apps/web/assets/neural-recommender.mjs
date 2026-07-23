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

function mean(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function variance(values) {
  if (values.length < 2) return 0;
  const centre = mean(values);
  return mean(values.map(value => (value - centre) ** 2));
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

const NEXT_STEP_LIBRARY = Object.freeze({
  IVA: ['define_target_market', 'audit_priority_pages', 'apply_30_day_fixes'],
  CRM: ['consolidate_leads', 'define_pipeline_ownership', 'activate_follow_up_rhythm'],
  IOP: ['select_primary_audience', 'collect_commercial_proof', 'draft_bilingual_one_pager']
});

function canonicalCode(code) {
  return code === 'OSP' ? 'IOP' : code;
}

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

function needProgression(features) {
  return [
    features.slice(0, 4),
    [features[4], features[5], features[6], features[7]],
    [features[8], features[9], (features[0] + features[2]) / 2, (features[1] + features[3]) / 2]
  ];
}

function serviceEconomics(service) {
  const price = Number(service?.price_eur || 0);
  const delivery = Number(service?.delivery_days || 0);
  const automation = Number(service?.automation_target_pct || 0) / 100;
  const hours = Number(service?.estimated_hours || 0);
  return [
    clamp(1 - price / 700),
    clamp(1 - delivery / 12),
    clamp(automation),
    clamp(1 - hours / 10)
  ];
}

function buildNeedTensor(features, service, serviceCode) {
  const code = canonicalCode(serviceCode);
  const profile = SERVICE_PROFILES[code] || Array(10).fill(0);
  const need = needProgression(features);
  const economics = serviceEconomics(service);
  const servicePlane = [
    profile.slice(0, 4),
    profile.slice(4, 8),
    [profile[8], profile[9], economics[1], economics[0]]
  ];
  const interactionPlane = need.map((row, rowIndex) => row.map((value, columnIndex) => {
    const serviceValue = servicePlane[rowIndex][columnIndex];
    const crossAxis = (features[(rowIndex * 3 + columnIndex) % features.length] + economics[columnIndex]) / 2;
    return clamp(Math.sqrt(Math.max(0, value * serviceValue)) * 0.72 + crossAxis * 0.28);
  }));
  return [need, servicePlane, interactionPlane];
}

function convolution3D(tensor, seed, channels = 8) {
  if (tensor.length !== 3 || tensor.some(plane => plane.length !== 3 || plane.some(row => row.length !== 4))) {
    throw new Error('invalid_multidimensional_tensor');
  }
  const embeddings = [];
  for (let channel = 0; channel < channels; channel += 1) {
    const kernel = weights(seed + channel * 17, 8, 0.28);
    const activations = [];
    for (let depth = 0; depth <= 1; depth += 1) {
      for (let row = 0; row <= 1; row += 1) {
        for (let column = 0; column <= 2; column += 1) {
          let activation = (channel - (channels - 1) / 2) * 0.012;
          let index = 0;
          for (let kd = 0; kd < 2; kd += 1) {
            for (let kr = 0; kr < 2; kr += 1) {
              for (let kc = 0; kc < 2; kc += 1) {
                activation += tensor[depth + kd][row + kr][column + kc] * kernel[index];
                index += 1;
              }
            }
          }
          activations.push(Math.max(0, activation));
        }
      }
    }
    embeddings.push(Math.max(...activations), mean(activations), Math.sqrt(variance(activations)));
  }
  const depthSummary = tensor.map(plane => mean(plane.flat()));
  const progressionSummary = [0, 1, 2].map(row => mean(tensor.flatMap(plane => plane[row])));
  const featureGroupSummary = [0, 1, 2, 3].map(column => mean(tensor.flatMap(plane => plane.map(row => row[column]))));
  return [...embeddings, ...depthSummary, ...progressionSummary, ...featureGroupSummary];
}

function latentProjection(latent, seed) {
  const projectionWeights = weights(seed + 900, latent.length, 0.18);
  const weighted = latent.reduce((sum, value, index) => sum + value * projectionWeights[index], 0);
  const energy = Math.sqrt(mean(latent.map(value => value * value)));
  return Math.max(0, weighted / Math.sqrt(latent.length) + energy * 0.72);
}

function profileScore(features, serviceCode) {
  const profile = SERVICE_PROFILES[canonicalCode(serviceCode)];
  if (!profile) return 0;
  return mean(features.map((value, index) => value * profile[index]));
}

function economicAlignment(features, service) {
  const economics = serviceEconomics(service);
  return mean([
    economics[0] * features[9],
    economics[1] * features[8],
    economics[2] * features[7],
    economics[3] * features[6]
  ]);
}

function graphAttention(baseScores, activeCodes) {
  const codes = activeCodes.map(canonicalCode);
  let state = Object.fromEntries(codes.map(code => [code, baseScores[code] || 0]));
  for (let layer = 0; layer < 2; layer += 1) {
    const next = { ...state };
    for (const target of codes) {
      const incoming = [];
      for (const source of codes) {
        const relation = RELATIONSHIP_GRAPH[source]?.[target] || 0;
        if (relation <= 0) continue;
        const attentionLogit = relation * (0.65 + state[source] * 0.35 + state[target] * 0.15);
        incoming.push({ source, relation, attentionLogit });
      }
      if (!incoming.length) continue;
      const attention = softmax(incoming.map(item => item.attentionLogit));
      const message = incoming.reduce((sum, item, index) => sum + attention[index] * state[item.source] * item.relation, 0);
      next[target] = state[target] * 0.90 + message * 0.10;
    }
    state = next;
  }
  return state;
}

function memberScores(features, activeServices, seed) {
  const base = {};
  for (const service of activeServices) {
    const code = canonicalCode(service.code);
    const tensor = buildNeedTensor(features, service, code);
    const latent = convolution3D(tensor, seed + code.charCodeAt(0));
    const tensorSignal = latentProjection(latent, seed + code.charCodeAt(code.length - 1));
    const direct = profileScore(features, code);
    const economics = economicAlignment(features, service);
    const perturbation = weights(seed + code.length * 131, 3, 0.025);
    base[code] = Math.max(0.001,
      direct * 0.72 +
      tensorSignal * 0.14 +
      economics * 0.14 +
      perturbation[0] * features[4] +
      perturbation[1] * features[7] +
      perturbation[2] * features[8]
    );
  }
  return graphAttention(base, activeServices.map(service => service.code));
}

function reasonIndexes(features, serviceCode) {
  const profile = SERVICE_PROFILES[canonicalCode(serviceCode)] || Array(10).fill(0);
  return features
    .map((value, index) => ({ index, score: value * profile[index] }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map(item => REASON_DIMENSIONS[item.index]);
}

function connectedPath(ranked) {
  if (!ranked.length) return [];
  const top = ranked[0].code;
  const neighbours = Object.entries(RELATIONSHIP_GRAPH[top] || {})
    .filter(([code]) => ranked.some(item => item.code === code))
    .sort((a, b) => b[1] - a[1]);
  const next = neighbours[0]?.[0] || ranked[1]?.code || null;
  return next ? [top, next] : [top];
}

function buildNextSteps(topCode, ranked, features) {
  const core = NEXT_STEP_LIBRARY[topCode] || ['confirm_problem', 'review_scope', 'prepare_inputs'];
  const path = connectedPath(ranked);
  const steps = core.map((action, index) => ({
    order: index + 1,
    phase: index === 0 ? 'evidence' : index === 1 ? 'build' : 'activate',
    action,
    autonomous_internal: index < 2,
    human_gate: index === 2,
    depends_on: index === 0 ? [] : [core[index - 1]]
  }));
  if (path.length > 1) {
    steps.push({
      order: steps.length + 1,
      phase: 'connect',
      action: 'evaluate_connected_service',
      service_code: path[1],
      autonomous_internal: true,
      human_gate: true,
      depends_on: [core[core.length - 1]]
    });
  }
  if (features[8] >= 0.75) {
    steps.unshift({
      order: 0,
      phase: 'triage',
      action: 'protect_urgent_scope',
      autonomous_internal: true,
      human_gate: false,
      depends_on: []
    });
  }
  return steps;
}

export function recommendServices(answers, services, options = {}) {
  if (!Array.isArray(services) || services.length === 0) throw new Error('services_required');
  const active = services.filter(service => service.status === 'active');
  if (!active.length) throw new Error('active_services_required');
  const features = encodeAnswers(answers);
  const canonicalServices = active.filter((service, index, list) =>
    list.findIndex(item => canonicalCode(item.code) === canonicalCode(service.code)) === index
  );
  const activeCodes = canonicalServices.map(service => canonicalCode(service.code));
  const seeds = options.seeds || [113, 227, 389, 557, 761, 887, 997];
  const memberDistributions = seeds.map(seed => {
    const raw = memberScores(features, canonicalServices, seed);
    const probabilities = softmax(activeCodes.map(code => raw[code] * 5.0));
    return Object.fromEntries(activeCodes.map((code, index) => [code, probabilities[index]]));
  });
  const means = {};
  const variances = {};
  for (const code of activeCodes) {
    const values = memberDistributions.map(distribution => distribution[code]);
    means[code] = mean(values);
    variances[code] = variance(values);
  }
  const ranked = activeCodes
    .map(code => {
      const source = canonicalServices.find(service => canonicalCode(service.code) === code);
      const uncertainty = clamp(Math.sqrt(variances[code]) * 5.2);
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
  const topService = canonicalServices.find(service => canonicalCode(service.code) === ranked[0].code);
  const topTensor = buildNeedTensor(features, topService, ranked[0].code);
  const latent = convolution3D(topTensor, 2026);
  return {
    model_version: 'web-multidimensional-neural-fabric-shadow-v0.2',
    local_only: true,
    features,
    tensor_shape: [3, 3, 4],
    latent_dimensions: latent.length,
    latent_summary: {
      mean: mean(latent),
      energy: Math.sqrt(mean(latent.map(value => value * value))),
      maximum: Math.max(...latent)
    },
    recommendations: ranked,
    confidence: clamp(0.54 + probabilityGap * 1.9 + (1 - mean(Object.values(variances))) * 0.08),
    connected_path: connectedPath(ranked),
    next_steps: buildNextSteps(ranked[0].code, ranked, features),
    requires_human_review: true
  };
}

export const recommenderContract = Object.freeze({
  model_version: 'web-multidimensional-neural-fabric-shadow-v0.2',
  feature_count: 10,
  tensor_shape: [3, 3, 4],
  convolution_dimensions: 3,
  convolution_kernel: [2, 2, 2],
  convolution_channels: 8,
  ensemble_size: 7,
  graph_layers: 2,
  graph_nodes: ['IVA', 'CRM', 'IOP', 'WAB', 'ISS'],
  local_only: true,
  personal_data_required: false,
  automatic_purchase: false,
  automatic_contact: false,
  automatic_crm_write: false,
  online_learning: false
});
