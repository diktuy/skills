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
