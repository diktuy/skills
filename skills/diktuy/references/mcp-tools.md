# Diktuy MCP tools

13 tools. Read-only ones are marked `ro`; the rest change data but never delete it. Dates are `YYYY-MM-DD` in Moscow
time, `date_to` inclusive. Every response is JSON; text fields are in Russian.

## Contents
- Search and read: `search`, `fetch`, `list_meetings`, `get_meeting`, `search_transcripts`, `list_tasks`, `list_dictations`
- Account: `get_account`
- Transcription: `transcribe_url`, `get_transcription_status`
- Changes: `rename_meeting`, `set_speaker_names`, `add_dictionary_words`
- Errors

## Search and read

**`search(query)`** `ro` — across meetings, dictations, files and bot recordings. Up to 10 results, no pagination.
Returns `{results: [{id, title, url, date, snippet, time?, shared?}]}`. Same shape as ChatGPT deep research.

**`fetch(id)`** `ro` — one item in full: `{id, title, text, url, metadata}`. Text is cut at 100 000 characters.

**`list_meetings(date_from?, date_to?, scope="all", limit=20, cursor?)`** `ro`
- `scope`: `all` — own meetings, meetings shared in the company and bot recordings; `mine` — own; `company` — shared.
- `limit` 1–100. Returns `{meetings: [...], next_cursor}`; `next_cursor` is present only when the page is full.

**`get_meeting(id, part="overview", offset=0, max_chars=40000)`** `ro` — `id` is `meeting:…` or `recording:…`.
- `overview` — title, date, duration, participants, which summaries exist, `expires_at` for link recordings.
- `summary` — the summaries «Кратко», «Протокол», «Задачи» and the user's own questions with answers.
- `transcript` — replies `[HH:MM:SS] Speaker: text` from `offset`; returns `next_offset` (`null` at the end) and
  `total_segments`. `max_chars` 1 000–150 000.
- `all` — everything, may come back with `truncated: true`.

**`search_transcripts(query, meeting_id?, date_from?, date_to?, limit=20)`** `ro` — the exact place in a conversation.
Returns `{hits: [{id, title, date, time, speaker, text}]}`; `time` is the offset from the start of the recording.

**`list_tasks(date_from?, date_to?, limit=20)`** `ro` — action items from meeting summaries.
Returns `{meetings: [{id, title, date, tasks, from}]}`; `from` is «Задачи» or «Протокол» when there is no tasks summary.

**`list_dictations(kind="all", query?, date_from?, date_to?, limit=20, cursor?)`** `ro` — dictations and transcribed
files from the desktop app. `kind`: `all`, `dictation`, `file`. With `query` there is no cursor. Needs a Diktuy account;
on the free plan the list is empty because the app keeps history on the computer.

## Account

**`get_account()`** `ro` — `{now, name, email, plan, paid, telegram_linked, minutes_left, company, limits}`.
- `now` — current time in Moscow; use it for «сегодня», «на этой неделе».
- `minutes_left` — the credit balance (1 credit = 1 minute of transcription by link).
- `plan`: `free`, `pro` (Профи), `unlimited` (Макс), `lifetime`.

## Transcription

**`transcribe_url(url, summary="short", speakers=true, language="auto")`** — starts a job and returns at once:
`{job_id, status: "queued", id: "recording:<job_id>"}`.
- `url`: https only. VK Video (vk.com, vkvideo.ru, vk.ru), Rutube, Yandex Disk (disk.yandex.ru/.com, yadi.sk,
  disk.360.yandex.ru), Google Drive, or a direct link to mp3, m4a, wav, ogg, opus, flac, aac, mp4, mov, webm, mkv and
  other common audio and video formats. **YouTube is refused.**
- `summary`: `short`, `protocol`, `tasks`, `none`. `language`: `auto`, `ru`, `en`.
- Cost: 1 credit per minute, `max(1, round(seconds / 60))`, charged once the length is known; refunded if the job fails
  or is cancelled. Zero balance — refused at once. Not enough for the whole recording — the job fails with
  `insufficient_credits`; there is no partial transcript.
- At most 5 open jobs per account (shared with the REST API); one runs at a time, the rest wait.
- Signed in with the bot URL (no account): paid from the bot's trial minutes.

**`get_transcription_status(job_id)`** `ro` — `job_id` is the bare UUID.
Returns `{job_id, status, stage, progress, eta_seconds, duration, id?, error?}`.
`status` goes `queued` → `downloading` → … → `done` / `failed` / `cancelled`; `stage` is a Russian label for the user.
On `done`, open `get_meeting("recording:<job_id>")`. Usually a few minutes; results are kept 30 days.

## Changes (confirm with the user first)

**`rename_meeting(id, title)`** — `title` up to 200 characters; empty restores the automatic title. Only the user's
own meetings.

**`set_speaker_names(id, names)`** — `recording:…` only (bot and link recordings). `names` maps the speaker number to a
name: `{"0": "Анна", "1": "Олег"}`. «Участник 1» is key `"0"`. Name up to 60 characters; empty removes it.
Speaker names in desktop-app meetings are changed in the app only (sync would overwrite them).

**`add_dictionary_words(words)`** — 1–200 words (names, terms, brands as they should be written), each up to 100
characters, up to 2 000 in the dictionary, duplicates ignored case-insensitively. Paid plans only. Returns
`{added, total}`.

## Errors (text comes from the server, in Russian)

| Message starts with | Meaning |
|---|---|
| «Нужен аккаунт Диктуй» | signed in with the bot URL; this tool needs an account |
| «На бесплатном тарифе — 50 запросов в сутки» | free daily limit reached; next calls work after 24 h from the earliest |
| «Слишком много запросов подряд» | paid limit 120 per minute; wait a minute |
| «На балансе нет минут» | top up at https://diktuy.ru/dashboard/billing |
| «Уже 5 записей в работе» | wait for a job to finish |
| «YouTube не отдаёт записи» | YouTube is not supported; ask for another link or a file |
| «Не получилось. Попробуйте ещё раз через минуту.» | temporary server error; one retry after a minute |
