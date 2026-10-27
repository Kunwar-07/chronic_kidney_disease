# Supabase setup

The backend supports explicit saved assessments in Supabase Postgres. The live `nephra-ckd` project is configured in this checkout's ignored `backend/.env`, and the migration has been applied. The website now has an entrance login/signup screen, persistent browser sessions with automatic token refresh, and automatic saving on assessment submission. ML files remain unchanged. The instructions below also explain how to configure another checkout.

## Details needed from you

Create or open your Supabase project and obtain these two values from the project's **Connect** dialog or **Settings → API Keys**:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_KEY
```

Copy `backend/.env.example` to `backend/.env` and fill them in locally. The file is ignored by Git. The legacy `anon` key can also be used as `SUPABASE_PUBLISHABLE_KEY`. Do not use a secret/service-role key: this integration deliberately keeps database row-level security active. No database password, database connection string, JWT signing secret or Supabase personal access token is needed.

Supabase distinguishes a project API key from a signed-in user's access token. The project URL and publishable key configure the backend. Each client calling a saved-assessment endpoint must additionally send its own **Supabase Auth access token** as `Authorization: Bearer <access_token>`. Keep session tokens private; do not paste them into chat or commit them.

Official references: [API keys](https://supabase.com/docs/guides/getting-started/api-keys), [REST API](https://supabase.com/docs/guides/api), [row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Create the table

1. In the Supabase project, open **SQL Editor → New query**.
2. Run the complete contents of [the migration](supabase/migrations/202610250001_assessments.sql) once. If a table named `public.assessments` already exists, review its schema first; this migration intentionally refuses to overwrite it.
3. Ensure the project's Data API is enabled and exposes the `public` schema.
4. Fill in the two environment values above and restart the backend with `npm start` from `backend/`.

The migration creates `public.assessments` with UUID IDs, the authenticated owner's user ID, pathway, normalized inputs, full model output, and creation time. An index supports user history ordered by timestamp and ID. The user's ID references `auth.users`; deleting the Supabase user also deletes their saved assessments.

Anonymous database access is revoked. Authenticated users can insert, read and delete their own records. Updates are not granted, and inserts cannot choose the record ID or creation time. RLS checks `auth.uid() = user_id` for every supported operation. The backend additionally filters reads/deletes by the verified user ID and never accepts an owner ID or result from the caller.

The backend calculates a fresh result before saving. These are user-owned research records, not tamper-proof clinical audit records: a user with a valid JWT can also reach the Supabase Data API directly and insert data permitted by their table grants and constraints.

## Sign in and verify

Use Supabase Auth to create/sign in a test user. Enable the sign-in method you want in the Supabase dashboard. Supabase's SDK or Auth API returns an `access_token` after successful sign-in; the project publishable key is not that token. The website handles this automatically; users need no Supabase dashboard account.

For a read-only connection check, temporarily set the test user's access token in your local environment or ignored `backend/.env`:

```dotenv
SUPABASE_TEST_ACCESS_TOKEN=YOUR_TEST_USER_ACCESS_TOKEN
```

Then, from `backend/`:

```sh
npm run db:check
```

The command verifies the token through Supabase Auth and reads at most one assessment for that user without printing it. It does not create records. Remove the temporary test token afterward. A successful check verifies connectivity and table read access, not every RLS policy. Token expiration produces a 401; sign in again or refresh the session using Supabase Auth.

## Save and retrieve assessments

Set `SUPABASE_TEST_ACCESS_TOKEN` in your shell to the signed-in test user's access token, then use the synthetic example from `backend/`:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/assessments \
  -H "Authorization: Bearer $SUPABASE_TEST_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/screening.json

curl 'http://127.0.0.1:8000/api/v1/assessments?limit=20&offset=0' \
  -H "Authorization: Bearer $SUPABASE_TEST_ACCESS_TOKEN"
```

`POST` returns 201 and the saved record including `id`. Use that ID for `GET /api/v1/assessments/{id}` or `DELETE /api/v1/assessments/{id}` with the same Authorization header. Deletion returns 204. A nonexistent record or another user's record returns 404. `limit` accepts 1–100, default 20; `offset` accepts 0–1000000, default 0. History returns newest-first summaries; fetch one record for full inputs/results. Offset pagination can shift when records are added or deleted between requests.

Before using real data, verify with **two test users**: save a synthetic assessment as A; confirm B's list excludes it and B gets 404 when reading/deleting its ID; confirm A can read and delete it. Also verify direct Data API queries with B's JWT cannot access A's record. Local mocked tests cannot verify deployed database policies.

Storage is explicit: `POST /api/v1/predict`, `/validate` and `/scenarios` never save anything, even when Supabase is configured. Only `POST /api/v1/assessments` persists health inputs/results. Missing or failed database configuration returns 503; the API does not claim a save succeeded on failure. If a connection fails after Supabase commits an insert, the outcome may be unknown; check history before retrying, since automatic deduplication is not implemented.

## Current verification scope

On 2026-10-25, the `nephra-ckd` project (`wftilcpezupeosiwqwam`, Mumbai) was connected and the migration was applied through Supabase SQL Editor. The publishable key and URL are stored locally in ignored `backend/.env` with file permissions 0600. No secret/service-role key or database password is stored by the backend.

Executed checks:

- All 28 backend tests passed.
- The live Supabase Auth endpoint responded successfully using the configured publishable key.
- The live Data API confirmed the assessments table exists and denied anonymous reads with PostgreSQL permission error `42501`.
- The configured backend produced predictions, required authentication for saved-assessment routes, and rejected an invalid user token through live Supabase Auth.
- [The live SQL ownership test](supabase/tests/ownership.sql) passed owner create/read/delete, cross-user read/insert/delete denial, update denial and anonymous-read denial. It used synthetic users inside a transaction and rolled back all test data.

The SQL policy test exercises real PostgreSQL permissions and RLS by switching roles and JWT claims. It does not authenticate real users through Supabase Auth. The live table contains an assessment from the website. Local automated tests cover persistent sessions, refresh, repeated saves after one login, and database failures.

[Live policy test screenshot](supabase-live-verification.png)


## Website login behavior

Sign in or create an account at the website entrance. Supabase Auth is the internal identity provider, not a separate dashboard login. Passwords are never saved in browser storage. Session tokens are kept in localStorage and refreshed before expiry; sign-out clears them and synchronizes across tabs. Existing tab sessions migrate on first reload. Clearing browser storage or revoking the session requires signing in again.

Authentication → Sign In / Providers → Confirm email is **off** in nephra-ckd (approved and applied October 25, 2026); new users enter immediately after signup. Keep passwords and row-level security enabled. For another project, apply the same setting if immediate signup is required.

Each valid Calculate and save submission creates a separate assessments row with the authenticated user ID, inputs, server-calculated result and timestamp. Success displays its database record ID. A failed save is visibly reported, never silently treated as success. The recent history shows the latest ten records. Hypothetical scenario adjustments are previews, not submitted assessments.
