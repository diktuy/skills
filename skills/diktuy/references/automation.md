# Automations: webhooks, n8n, Make, Bitrix24, own code

For users who wire Diktuy into their processes: a new meeting → tasks in a CRM, a call recording by link → a protocol
in the deal, a voice message → text. REST API, paid plans; one API key per integration, so revoking one breaks
nothing else. Endpoints and errors — [rest-api.md](rest-api.md).

## Contents
- Webhooks
- n8n
- Make
- Bitrix24
- Own code

## Webhooks

Diktuy POSTs to the user's URL when something is ready — no polling.

| Event | When |
|---|---|
| `transcription.completed` / `transcription.failed` | a link transcription is done or failed |
| `meeting.created` / `meeting.updated` / `meeting.deleted` | a desktop-app meeting appeared, changed (names, summary, title) or was deleted |
| `webhook.test` | sent by the test call |

Meeting events come only for meetings recorded after the endpoint was added. Set up with
`diktuy.py webhooks add <url>` ([cli.md](cli.md)) or `POST /v1/webhook-endpoints`. The `whsec_…` secret is shown
once: put it in the receiver's environment, never in a repository.

The body carries only the id; fetch the content with a second request:

```json
{"type": "transcription.completed", "timestamp": "…",
 "data": {"id": "…", "object": "transcription", "status": "completed", "external_id": "deal-42", "duration_seconds": 1834.6}}
```

For meeting events `data.id` goes to `GET /v1/meetings/{id}`.

Receiver rules:
- Answer 2xx within 15 seconds, do the work after. Otherwise retries: 1 min, 5 min, 30 min, 2 h, 5 h, 10 h, 10 h.
  A `410` answer or 5 days without a single success disables the endpoint.
- The same event can arrive twice — deduplicate by the `webhook-id` header.
- Verify the Standard Webhooks signature on the raw body before parsing:

```js
// Node.js: npm install standardwebhooks
import { Webhook } from "standardwebhooks";
const event = new Webhook(process.env.DIKTUY_WEBHOOK_SECRET).verify(rawBody, headers); // throws on a bad signature
```

```python
# Python: pip install standardwebhooks
from standardwebhooks.webhooks import Webhook
event = Webhook(os.environ["DIKTUY_WEBHOOK_SECRET"]).verify(raw_body, headers)
```

## n8n

1. **Webhook** node: POST, Respond — Immediately. Its Production URL goes to `webhooks add`.
2. **IF** node: `{{ $json.body.type }}` equals `meeting.created` (or `transcription.completed`).
3. **HTTP Request** node: GET `https://api.diktuy.ru/v1/meetings/{{ $json.body.data.id }}?format=markdown`
   (link jobs: `/v1/transcriptions/{{ $json.body.data.id }}?format=markdown`), auth via Credentials → Header Auth,
   `Authorization: Bearer dk_live_…`.
4. Then anywhere: Telegram, mail, Google Sheets, a CRM, an AI node for a custom summary.

Transcribe a link from n8n: HTTP Request POST `https://api.diktuy.ru/v1/transcriptions`, JSON
`{"audio_url": "…", "summary": "protocol", "external_id": "…"}`; the result arrives as `transcription.completed`.

## Make

**Webhooks → Custom webhook** gives the URL for `webhooks add`. **HTTP → Make a request** calls the API with
`Authorization: Bearer dk_live_…` and a JSON body.

## Bitrix24

Through n8n, Make or an own handler:
- call or meeting recording → `POST /v1/transcriptions` with `external_id` = deal id → `transcription.completed` →
  the protocol as a deal comment (`crm.timeline.comment.add` via a Bitrix24 inbound webhook);
- `meeting.created` → the «Задачи» summary → tasks (`tasks.task.add`).

## Own code

File transcription is OpenAI-compatible — their SDKs work with a different base URL and key:

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.diktuy.ru/v1", api_key=os.environ["DIKTUY_API_KEY"])
print(client.audio.transcriptions.create(model="whisper-1", file=open("voice.ogg", "rb")).text)
```

Links go through the queue: `POST /v1/transcriptions` → 202 with `id` → the webhook or `GET /v1/transcriptions/{id}`
until `completed` → `?format=text|markdown|srt|vtt`. Send `Idempotency-Key` so a retried request does not start a
second job.
