# Diktuy REST API

Use when MCP is not available: scripts, CI, backends, webhooks. The source of truth is the OpenAPI file
https://api.diktuy.ru/v1/docs/openapi.json (fetch it for exact schemas; the docs page itself is a JS app).

## Contents
- Auth and limits
- Endpoints
- Transcription flow
- Errors

## Auth and limits

- Base URL `https://api.diktuy.ru/v1`. Header `Authorization: Bearer $DIKTUY_API_KEY`.
- Keys look like `dk_live_` + 43 characters and are shown once, at https://diktuy.ru/dashboard/api. Up to 10 active keys.
- **Paid plans only** (Профи, Макс, Lifetime or a company seat); otherwise `403 plan_required`. Revoking a key or a plan
  change reaches the API within a minute.
- 60 requests per minute per key; see `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`.
- Cost: 1 credit per minute of audio, refunded on failure; audio without speech is free.

## Endpoints

| Method and path | What it does |
|---|---|
| `GET /me` | user, plan `{type: free\|pro\|max\|lifetime, active, expires_at}`, credits `{available, monthly_limit, monthly_used, purchased}` |
| `POST /transcriptions` | start a job by link: `{audio_url, language="auto", speakers=true, speaker_names?, summary="short", external_id?}`; 202 + `Location`. Up to 12 h and 2 GB. Send `Idempotency-Key` (kept 24 h). 10 per minute |
| `GET /transcriptions/{id}` | job and result; `?format=json\|text\|markdown\|srt\|vtt`. `409 not_ready`, `410 expired` (30 days) |
| `GET /transcriptions` | list: `limit` 1–100, `cursor`, `status` (comma-separated) → `{data, has_more, next_cursor}` |
| `PATCH /transcriptions/{id}/speakers` | `{"speakers": [{"id": 1, "name": "Анна"}]}` |
| `DELETE /transcriptions/{id}` | cancel (credits refunded) and delete the result; 204 |
| `POST /audio/transcriptions` | OpenAI-compatible multipart upload: `file`, `model?`, `language?`, `prompt?`, `response_format: json\|text\|srt\|vtt\|verbose_json`. Up to 25 MB and 30 min, 3 in parallel. Returns `credits_charged`, `credits_remaining` |
| `GET /meetings` | meetings synced from the desktop app (paid plans): `limit`, `cursor`; `started_at` is **UTC** |
| `GET /meetings/{id}` | one meeting: `segments`, `summary_texts`, `questions`; `?format=json\|text\|markdown` |
| `POST/GET /webhook-endpoints`, `DELETE …/{id}`, `POST …/{id}/test`, `GET …/{id}/deliveries` | up to 5 endpoints; events `transcription.completed`, `transcription.failed`, `meeting.created`, `meeting.updated`, `meeting.deleted`; secret `whsec_…` shown once, Standard Webhooks signatures |

`meetings/{id}` uses the same 32-hex id as MCP `meeting:<id>`.

## Transcription flow

```bash
curl -s https://api.diktuy.ru/v1/me -H "Authorization: Bearer $DIKTUY_API_KEY"   # balance first

curl -s https://api.diktuy.ru/v1/transcriptions \
  -H "Authorization: Bearer $DIKTUY_API_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"audio_url": "https://rutube.ru/video/…", "summary": "protocol"}'

curl -s "https://api.diktuy.ru/v1/transcriptions/$ID?format=markdown" -H "Authorization: Bearer $DIKTUY_API_KEY"
```

Poll every 30 s or use a `transcription.completed` webhook. Job `status`: `queued`, `processing`, `completed`, `failed`,
`cancelled`; at most 5 open jobs per account (`429 too_many_jobs`).

OpenAI SDK users can point `base_url` at `https://api.diktuy.ru/v1` and call `audio.transcriptions.create` with the
Diktuy key.

## Errors

RFC 9457 `application/problem+json`: `{type, title, status, detail, code, request_id}`; quote `request_id`
(also `X-Request-Id`) when writing to support@diktuy.ru.

| Status | `code` |
|---|---|
| 400 | `invalid_request`, `invalid_json` |
| 401 | `auth_required`, `invalid_key` |
| 402 | `insufficient_credits` |
| 403 | `plan_required`, `insufficient_scope` |
| 404 | `not_found` |
| 409 / 410 | `not_ready` / `expired` |
| 413 | `payload_too_large` (JSON > 1 MB, file > 25 MB) |
| 415 | `unsupported_media_type` |
| 422 | `bad_media`, `no_audio`, `too_long`, `link_unsupported`, `idempotency_mismatch`, `no_speakers`, `unknown_speaker` |
| 429 | `rate_limited`, `too_many_jobs` |
| 500 / 502 / 503 | `internal_error` / `transcription_failed` / `unavailable` |

Retry only 429 (after `RateLimit-Reset`) and 503. Never retry a `POST /transcriptions` without the same
`Idempotency-Key`.
