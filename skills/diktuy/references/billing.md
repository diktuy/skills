# Plans, credits and limits

Prices change; read them at https://diktuy.ru/pricing instead of quoting numbers from here.

## What costs credits

| Action | Cost |
|---|---|
| Reading anything through MCP or REST | free (only call limits apply) |
| `transcribe_url` / `POST /v1/transcriptions` / `POST /v1/audio/transcriptions` | 1 credit per minute of audio, rounded, at least 1; refunded on failure; no speech — free |
| Renaming, speaker names, dictionary words | free |

Inside the desktop app cloud transcription and AI summaries have their own rates (see the pricing page); recording and
transcribing on the computer is free on every plan.

## Plans as the tools report them

| `get_account.plan` / `/v1/me plan.type` | Name | Notes |
|---|---|---|
| `free` | Бесплатный | one-time welcome credits; 50 MCP calls per 24 h; app meetings, dictations and files are not on the server; no REST API |
| `pro` | Профи | monthly credits; history synced; REST API |
| `unlimited` (MCP) / `max` (REST) | Макс | more monthly credits; same features |
| `lifetime` | — | older lifetime accounts |

A company seat (plan «Бизнес») also opens the REST API. Extra credits are sold in packs that don't expire.

## Before spending

1. `get_account` (or `GET /v1/me`) → balance.
2. If the length is known, say the expected cost: «запись 47 минут — спишется около 47 кредитов, на балансе 120».
3. Wait for a yes. Then start once and poll.

## When something runs out

- «На балансе нет минут» / `402 insufficient_credits` — top up at https://diktuy.ru/dashboard/billing or wait for the
  monthly credits. Don't retry.
- «50 запросов в сутки» — the free limit; it frees up 24 h after the earliest call. Paid plans have no daily limit.
- `403 plan_required` — the REST API needs a paid plan; the MCP server still works.
- Empty meetings on the free plan — meetings stay on the computer. Suggest the bot (@DiktuyMeetBot) or a link
  transcription, or a paid plan for sync.

## Tokens of the user's model

The second bill — and the one that surprises people. Everything a tool returned stays in the context and is sent to
the model again **on every following step**: a 25k-token transcript plus 20 more steps of work is about 500k input
tokens. Caching makes it cheaper, not free.

Measured on real meetings (Russian speech, 2–4 speakers):

| What | Characters | Tokens |
|---|---|---|
| «Кратко» + «Задачи» + «Протокол» of a 25-minute meeting | ~7k | 2–3k |
| Lines of a one-hour meeting (text) | 50–60k | 15–30k |
| One hour in markdown (summaries + timed lines) | 55–65k | 16–33k |
| One hour in JSON | 80–120k | 25–50k |

The spread is the tokenizer: one token is 2 to 3.5 characters of Russian text.

How to keep it low:
1. **Summary first** — `get_meeting(part="summary")` / `meeting <ref> --summary` answers «что решили» 5–10 times
   cheaper than the transcript.
2. **Then search** — `search_transcripts` / `diktuy.py search` returns only the matching lines with time.
3. **Full text only when the task needs it**, page by page (`offset`, default `max_chars`), or into a file with
   `--out` and read the needed part. The script writes anything over 12k characters to a file by itself.
4. **JSON only for code.** People and summaries need text or markdown.
5. **Heavy reading** (a two-hour meeting, tasks from five meetings) — if the agent can run subagents, read there and
   bring back the result.
6. After a heavy transcript, offer to continue in a new conversation with the result.

If the user asks why so many tokens — explain the re-sending and show the table.
