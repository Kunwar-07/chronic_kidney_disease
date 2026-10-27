# Nephra backend

Standalone, dependency-free Node.js API with optional Supabase assessment storage for the existing CKD research project. All backend additions live in `backend/`. The frontend and ML files are unchanged. See [Supabase setup](SUPABASE.md) for the database migration, required configuration and authentication examples.

JavaScript is used because the project already exports its fitted models to JSON and provides a shared ML-owned JavaScript inference runtime. The API imports `ml/research/runtime.mjs` directly and reads the selected exports from `frontend/data/`. It does not retrain models, duplicate their scoring logic, load legacy pickles, or require Python dependencies.

## Run

Use Node.js 22.9 or newer. From the repository root:

```sh
cd backend
npm start
```

No `npm install` is necessary. The API listens at **http://127.0.0.1:8000**. Stop with Ctrl+C. `npm run dev` enables restart on source changes.

```sh
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/api/v1/models/screening
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H 'Content-Type: application/json' \
  --data-binary @examples/screening.json
```

The example contains synthetic fixture inputs. With the committed model it returns a probability of approximately `0.07142457936034693`, plus the model's threshold, explanations, quality flags, model/run identifiers and limitations. On Windows PowerShell use `curl.exe` for these commands.

## Frontend relationship

The existing frontend still runs using `cd frontend && npm run dev` and performs inference in browser memory. Adding this backend does **not** redirect its submissions to a server. Its existing privacy text and behavior therefore remain accurate. The API is ready for a separate client or a future, explicitly authorized frontend integration.

Prediction, validation and scenario endpoints process inputs in memory without saving them. With Supabase configured, authenticated callers can explicitly create, list, read and delete their own saved assessments. Supabase Auth manages accounts; this backend verifies user tokens with Supabase and forwards them to its REST API so row-level security applies. Request bodies, credentials and database responses are never logged. The optional explanation endpoint sends the submitted assessment inputs and computed research result to Gemini only when `GEMINI_API_KEY` is configured; otherwise it returns built-in educational guidance.

## API

All payloads are JSON. `GET /openapi.json` provides an OpenAPI 3.1 specification with input schemas generated from the loaded artifacts. Import this URL into an OpenAPI-compatible API client. Query parameters are accepted only for assessment history pagination; inputs belong in POST bodies.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| GET | `/ready` | Loaded model readiness and run ID |
| GET | `/openapi.json` | API specification |
| GET | `/api/v1/models` | Both selected model schemas and metadata |
| GET | `/api/v1/models/{task}` | Fields, units, categories, ranges, threshold and limitations |
| GET | `/api/v1/research` | Existing aggregate evaluation report |
| GET | `/api/v1/sources` | Existing source manifest |
| POST | `/api/v1/validate` | Validate inputs and return completeness/quality information |
| POST | `/api/v1/predict` | Run the selected model and explanations |
| POST | `/api/v1/scenarios` | Compare one hypothetical feature change |
| POST | `/api/v1/explanation` | Explain kidney-health context using Gemini or built-in fallback guidance |
| POST | `/api/v1/assessments` | Compute and save an assessment for the authenticated user |
| GET | `/api/v1/assessments?limit=20&offset=0` | List the authenticated user's saved assessment summaries |
| GET | `/api/v1/assessments/{id}` | Read a saved assessment owned by the authenticated user |
| DELETE | `/api/v1/assessments/{id}` | Delete a saved assessment owned by the authenticated user |

GET routes also support HEAD; recognized routes support OPTIONS. Model metadata excludes tree parameters. No filesystem or static frontend routes are served.

Prediction and validation requests have exactly this structure:

```json
{
  "task": "screening",
  "input": {"age": 56, "sex": 0, "bmi": 28.2, "diabetes": 0}
}
```

`task` is `screening` or `biomarker`. Feature values must be finite JSON numbers or `null`; numeric strings, booleans and blank strings are rejected. Omitted optional features are imputed by the ML runtime. The original model validation rules are preserved: age and sex are required, at least half the pathway's inputs must be supplied, the biomarker pathway needs two secondary labs, and systolic pressure must exceed diastolic pressure when both are present. Unknown features and invalid ranges/categories are rejected. Use the metadata endpoints for exact feature names and units; no new medical rules are introduced.

For hypothetical exploration, POST the same envelope to `/api/v1/scenarios` with one additional property:

```json
{
  "task": "screening",
  "input": {"age": 56, "sex": 0, "bmi": 28.2, "diabetes": 0},
  "changes": {"bmi": 35}
}
```

The response includes complete `baseline` and `scenario` assessments plus `probability_difference` (scenario minus baseline, on the 0–1 probability scale). These are model behavior comparisons, not causal effects or treatment advice. The existing single-visit research outcome and limitations are included in every successful assessment.

## Errors

Successful operations return HTTP 200, except creation (201 with a Location header) and deletion (204). A model input failure returns HTTP 422 with `status: "invalid"`, `errors`, `quality`, normalized `values` and `present`. Scenario validation failures also identify `stage` as `baseline` or `scenario`.

Protocol errors use this envelope:

```json
{
  "status": "error",
  "error": {"code": "invalid_task", "message": "task must be screening or biomarker."},
  "request_id": "server-generated UUID"
}
```

| Status | Meaning |
| --- | --- |
| 400 | Malformed JSON, invalid envelope/types or query parameters |
| 401 | Missing, invalid or expired Supabase user access token |
| 403 | Origin or CORS preflight not allowed |
| 404 | Unknown route/pathway |
| 405 | Unsupported HTTP method; see `Allow` |
| 408 | Body read timeout |
| 413 | Request body too large |
| 415 | Unsupported content type or compressed body |
| 422 | ML input validation failure |
| 429 | Rate limit reached; see `Retry-After` in seconds |
| 500 | Unexpected internal failure; no stack trace or input is returned |
| 503 | Supabase is unconfigured, unavailable, or its setup is incomplete |

Responses include `X-Request-Id`, `Cache-Control: no-store` and content-type protection. Invalid HTTP framing/header errors may be rejected directly by Node before the JSON handler runs.

## Configuration

Optionally copy `.env.example` to `.env` in `backend/`. Environment variables take precedence. `.env` is ignored by Git.

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | Listening port |
| `CORS_ORIGINS` | `http://127.0.0.1:4173,http://localhost:4173` | Exact comma-separated browser origins; empty disables cross-origin access |
| `MAX_BODY_BYTES` | `16384` | Maximum JSON body size, including chunked requests |
| `BODY_TIMEOUT_MS` | `10000` | Maximum time to read a POST body |
| `RATE_LIMIT_MAX` | `60` | Requests per socket address per window |
| `RATE_LIMIT_WINDOW_MS` | `60000` | Rate-limit window |
| `MODEL_DATA_DIR` | repository `frontend/data` | Trusted local directory containing both model JSONs, `report.json` and `sources.json` |
| `SUPABASE_URL` | empty | Supabase project URL; required with publishable key to enable storage |
| `SUPABASE_PUBLISHABLE_KEY` | empty | Publishable key (legacy anon also accepted); admin keys rejected |
| `SUPABASE_TIMEOUT_MS` | `10000` | Timeout for each Supabase request |
| `GEMINI_API_KEY` | empty | Optional Gemini API key; keep it server-side and never expose it to the frontend |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model used for concise explanations; override if your account exposes another supported model |
| `GEMINI_TIMEOUT_MS` | `8000` | Maximum time allowed for a Gemini request |

If Gemini is unset, rate-limited, overloaded, times out, or returns an unusable response, `/api/v1/explanation` automatically returns the deterministic built-in guidance with `"source": "fallback"`. Gemini responses are constrained to educational context: they must not diagnose, promise kidney recovery, or prescribe medication changes. The UI labels the source so users can distinguish Gemini text from the fallback.

## Deploy as a Vercel folder upload

The repository root is prepared for Vercel's dashboard folder upload. Do not upload `.env` files or API keys. In Vercel, choose **Add New → Project → Import Third-Party → Upload** (or the dashboard's folder upload option), select the repository root, and deploy with the detected settings:

- Framework preset: **Other**
- Build command: `npm run build`
- Output directory: `frontend/dist`
- Node.js version: **22.x**

Add these environment variables in the Vercel project settings for **Production**, **Preview**, and **Development** as needed:

```text
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_MS=8000
CORS_ORIGINS=https://your-project.vercel.app
```

If saved assessments are required, also add `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_TIMEOUT_MS`. Apply the Supabase migration before using account features. `MODEL_DATA_DIR` is normally unnecessary because the deployment uses the committed `frontend/data` exports.

The catch-all function at `api/[...path].mjs` serves the existing `/health`, `/ready`, `/openapi.json`, and `/api/v1/*` routes. The frontend uses same-origin API requests on Vercel, so no frontend URL change is required. After changing environment variables, redeploy; Vercel functions do not read local `.env` files.

Relative `MODEL_DATA_DIR` paths resolve from the process working directory; absolute paths are recommended. The default resolves relative to the backend source, independent of the current working directory. Exports are loaded once at startup; restart after updating them. Startup fails if exports cannot be parsed, schemas/model selection/run versions disagree, or reference inference fails. Only use trusted, locally managed exports.

Liveness/readiness and preflight requests are exempt from rate limiting. Forwarded IP headers are deliberately ignored. Behind a reverse proxy the built-in limiter sees the proxy's socket address, so configure per-client limits at that proxy. The limiter is per process, resets on restart and is not a distributed quota.

Inference and metadata routes remain public; saved-assessment routes require Supabase user authentication. CORS is a browser policy, not authentication. A network deployment needs TLS and appropriate operational controls before accepting sensitive data. This implementation does not claim production clinical readiness. Inference runs synchronously using the existing small model exports; benchmark representative traffic before scaling it beyond local use. `/ready` checks model readiness and reports database configuration as `disabled` or `configured_unverified`; use `npm run db:check` with a test user token to verify actual database connectivity.

## Verification

```sh
npm run check
npm test
```

Tests use actual localhost HTTP requests and the existing synthetic parity fixtures. They cover both pathways' prediction parity with the ML runtime and Python-exported expected values, validation gates, imputation/range warnings, scenarios, strict payload handling, metadata/research delivery, CORS, methods, body limits/timeouts, rate-limit recovery, startup failures, OpenAPI references, and the server entry point's startup/shutdown. No training or patient data is required. Tests require permission to listen on loopback ports.

Supabase tests mock the remote HTTP boundary while exercising the real API and adapter. They check token verification, ownership filters, authenticated CRUD, pagination, failure sanitization, timeouts and disabled configuration. They do not execute PostgreSQL or prove deployed RLS policies; apply the migration and verify against your project before using saved assessments.

## Files

```text
backend/
  src/config.mjs       Environment parsing and defaults
  src/models.mjs       Trusted export loading and ML runtime adapter
  src/openapi.mjs      Artifact-derived API specification
  src/app.mjs          HTTP routing, input handling and safeguards
  src/server.mjs       Process startup and graceful shutdown
  src/supabase.mjs     Supabase Auth/REST adapter using caller JWTs
  src/errors.mjs       Shared sanitized API errors
  supabase/migrations/ Assessment table, grants and ownership policies
  scripts/             Live database connection check
  tests/api.test.mjs   HTTP integration and model parity tests
  examples/            Synthetic request example
```

Run this folder inside the repository: it depends on the existing ML runtime and exported data through read-only imports/reads. For packaging, include `backend/`, `ml/research/runtime.mjs`, and the four JSON exports in `frontend/data/`, or point `MODEL_DATA_DIR` at the corresponding trusted exports.
