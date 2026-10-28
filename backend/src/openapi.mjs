import {TASKS} from './models.mjs';

export function buildOpenAPI(registry) {
  const ref = name => ({$ref: `#/components/schemas/${name}`});
  const content = schema => ({'application/json': {schema}});
  const errorResponses = Object.fromEntries([
    [400, 'Malformed JSON or request envelope'], [403, 'Origin or preflight rejected'],
    [401, 'Missing, invalid or expired Supabase user access token'],
    [408, 'Body read timed out'], [413, 'Body exceeds configured size limit'],
    [415, 'Unsupported content type or encoding'], [429, 'Rate limit exceeded; see Retry-After'],
    [500, 'Internal error'], [503, 'Database not configured or Supabase unavailable'],
  ].map(([code, description]) => [code, {description, content: content(ref('Error'))}]));
  const schemas = {
    Error: {type: 'object', required: ['status', 'error', 'request_id'], properties: {
      status: {const: 'error'}, request_id: {type: 'string', format: 'uuid'},
      error: {type: 'object', required: ['code', 'message'], properties: {code: {type: 'string'}, message: {type: 'string'}}},
    }},
    Quality: {type: 'object', required: ['feature', 'state', 'message'], properties: {
      feature: {type: 'string'}, state: {enum: ['observed', 'imputed', 'required', 'invalid', 'outside', 'unusual']}, message: {type: 'string'},
    }},
    Validation: {type: 'object', required: ['status', 'values', 'quality', 'errors', 'present'], properties: {
      status: {enum: ['ok', 'invalid']}, values: {type: 'object', additionalProperties: {type: ['number', 'null']}},
      quality: {type: 'array', items: ref('Quality')}, errors: {type: 'array', items: {type: 'string'}},
      present: {type: 'integer'}, stage: {enum: ['baseline', 'scenario']},
    }},
    Assessment: {type: 'object', required: ['status', 'task', 'model_version', 'run_id', 'model', 'label', 'probability', 'threshold', 'outcome', 'calibration', 'explanation_method', 'explanations', 'quality', 'present', 'total', 'limitations'], properties: {
      status: {const: 'ok'}, task: {enum: TASKS}, model_version: {type: 'string'}, run_id: {type: 'string'},
      model: {type: 'string'}, label: {type: 'string'}, probability: {type: 'number', minimum: 0, maximum: 1},
      threshold: {type: 'number', minimum: 0, maximum: 1}, outcome: {type: 'string'}, calibration: {type: 'string'},
      explanation_method: {type: 'string'}, limitations: {type: 'array', items: {type: 'string'}},
      present: {type: 'integer'}, total: {type: 'integer'}, quality: {type: 'array', items: ref('Quality')},
      explanations: {type: 'array', items: {type: 'object', required: ['feature', 'observed', 'reference', 'probability_difference'], properties: {
        feature: {type: 'string'}, observed: {type: 'number'}, reference: {type: 'number'}, probability_difference: {type: 'number'},
      }}},
    }},
    Scenario: {type: 'object', required: ['status', 'baseline', 'scenario', 'probability_difference', 'interpretation'], properties: {
      status: {const: 'ok'}, baseline: ref('Assessment'), scenario: ref('Assessment'),
      probability_difference: {type: 'number'}, interpretation: {type: 'string'},
    }},
    SavedAssessment: {type: 'object', required: ['id', 'user_id', 'created_at', 'task', 'input', 'result'], properties: {
      id: {type: 'string', format: 'uuid'}, user_id: {type: 'string', format: 'uuid'},
      created_at: {type: 'string', format: 'date-time'}, task: {enum: TASKS},
      input: {type: 'object', additionalProperties: {type: ['number', 'null']}}, result: ref('Assessment'),
    }},
    AssessmentPage: {type: 'object', required: ['assessments', 'limit', 'offset'], properties: {
      limit: {type: 'integer'}, offset: {type: 'integer'}, assessments: {type: 'array', items: {
        type: 'object', properties: {id: {type: 'string', format: 'uuid'}, created_at: {type: 'string', format: 'date-time'},
          task: {enum: TASKS}, model_version: {type: 'string'}, probability: {type: 'number'}},
      }},
    }},
  };
  for (const task of TASKS) {
    const artifact = registry.models[task];
    const properties = Object.fromEntries(artifact.features.map(name => {
      const field = artifact.fields[name];
      const schema = {type: field.required ? 'number' : ['number', 'null'], title: field.label,
        description: [field.unit, field.note].filter(Boolean).join('. ')};
      if (field.choices) schema.enum = [...Object.keys(field.choices).map(Number), ...(field.required ? [] : [null])];
      else Object.assign(schema, {minimum: field.min, maximum: field.max});
      return [name, schema];
    }));
    schemas[`${task}Input`] = {type: 'object', additionalProperties: false, properties,
      required: artifact.features.filter(name => artifact.fields[name].required),
      description: 'At least half of the inputs must be non-null. Systolic pressure must exceed diastolic when both are present. Biomarker additionally requires two secondary labs.'};
    schemas[`${task}Request`] = {type: 'object', additionalProperties: false, required: ['task', 'input'],
      properties: {task: {const: task}, input: ref(`${task}Input`)}};
    schemas[`${task}ScenarioRequest`] = {type: 'object', additionalProperties: false, required: ['task', 'input', 'changes'],
      properties: {task: {const: task}, input: ref(`${task}Input`), changes: {
        type: 'object', additionalProperties: false, minProperties: 1, maxProperties: 1, properties,
      }}};
  }
  const post = (summary, response, scenario = false) => ({summary,
    requestBody: {required: true, content: content({oneOf: TASKS.map(task => ref(`${task}${scenario ? 'ScenarioRequest' : 'Request'}`))})},
    responses: {'200': {description: 'Success', content: content(ref(response))},
      '422': {description: 'Model input validation failed', content: content(ref('Validation'))}, ...errorResponses}});
  const get = (summary, schema = {type: 'object'}) => ({summary, responses: {
    '200': {description: 'Success', content: content(schema)},
    '403': errorResponses[403], '429': errorResponses[429],
  }});
  const security = [{SupabaseUser: []}];
  const save = post('Compute and explicitly save an assessment for the signed-in user', 'SavedAssessment');
  save.responses['201'] = {...save.responses['200'], description: 'Assessment created'};
  delete save.responses['200'];
  save.security = security;
  const recordResponses = {
    ...errorResponses, '404': {description: 'Assessment missing or owned by another user', content: content(ref('Error'))},
  };
  return {openapi: '3.1.0', info: {title: 'Nephra Research API', version: '1.0.0',
    description: 'Research inference with optional authenticated Supabase assessment storage. POST /predict does not save data. Single-visit marker estimates; not diagnosis or future progression.'},
  servers: [{url: '/'}], paths: {
    '/health': {get: get('Process liveness')}, '/ready': {get: get('Models loaded and startup checks passed')},
    '/openapi.json': {get: get('This API specification')},
    '/api/v1/config': {get: get('Public browser configuration: Supabase URL and publishable key only')},
    '/api/v1/models': {get: get('Model metadata, feature fields, units, ranges and limitations')},
    '/api/v1/models/{task}': {get: {...get('Metadata for one pathway'), parameters: [{name: 'task', in: 'path', required: true, schema: {enum: TASKS}}],
      responses: {...get('').responses, '404': {description: 'Unknown pathway', content: content(ref('Error'))}}}},
    '/api/v1/research': {get: get('Existing aggregate evaluation report')},
    '/api/v1/sources': {get: get('Existing data source manifest', {})},
    '/api/v1/validate': {post: post('Validate inputs without running inference', 'Validation')},
    '/api/v1/predict': {post: post('Run the selected fitted model and its explanations', 'Assessment')},
    '/api/v1/scenarios': {post: post('Compare a single-feature hypothetical change', 'Scenario', true)},
    '/api/v1/explanation': {post: post('Generate a cautious kidney-health explanation with a deterministic fallback', 'Explanation')},
    '/api/v1/assessments': {post: save, get: {
      ...get('List the signed-in user’s saved assessments'), security,
      parameters: [
        {name: 'limit', in: 'query', schema: {type: 'integer', minimum: 1, maximum: 100, default: 20}},
        {name: 'offset', in: 'query', schema: {type: 'integer', minimum: 0, maximum: 1000000, default: 0}},
      ], responses: {...errorResponses, '200': {description: 'Newest first; summary fields only', content: content(ref('AssessmentPage'))}},
    }},
    '/api/v1/assessments/{id}': {
      parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'string', format: 'uuid'}}],
      get: {summary: 'Read one of the signed-in user’s assessments', security,
        responses: {...recordResponses, '200': {description: 'Saved assessment', content: content(ref('SavedAssessment'))}}},
      delete: {summary: 'Delete one of the signed-in user’s assessments', security,
        responses: {...recordResponses, '204': {description: 'Deleted'}}},
    },
  }, components: {schemas: {...schemas,
    Explanation: {type: 'object', required: ['source', 'title', 'body'], properties: {
      source: {enum: ['gemini', 'fallback']}, model: {type: ['string', 'null']},
      title: {type: 'string'}, body: {type: 'string'},
    }},
  }, securitySchemes: {
    SupabaseUser: {type: 'http', scheme: 'bearer', bearerFormat: 'Supabase access JWT',
      description: 'A signed-in user access token, not a Supabase project API key.'},
  }}};
}
