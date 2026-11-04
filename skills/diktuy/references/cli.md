# Diktuy without MCP: the `diktuy.py` script

Use when the MCP server is not connected but the user has an API key (paid plan): Codex in a sandbox, Gemini CLI,
OpenCode, Kimi, a server, a cron job, or a user who prefers no MCP. One Python 3.8+ file, standard library only,
Windows, macOS and Linux. Output and errors are in Russian.

```bash
python3 <this skill folder>/scripts/diktuy.py <command>    # Windows: python or py
```

Every command has `-h`. Below `diktuy.py` means the line above.

## Contents
- Key
- Meetings: find, summaries, tasks, search, full text
- Transcription: file, folder, link, speakers, cancel
- Webhooks
- What the script does for you

## Key

- `diktuy.py me` first: plan, credits, key scopes. «Ключа API нет» → the user creates a key at
  https://diktuy.ru/dashboard/api (paid plans only) and runs `diktuy.py login` **in their own terminal**: the input
  is hidden, the key is checked and saved to `~/.diktuy-skill/api-key` (owner-only). Never take the key in chat.
- Servers and CI: `DIKTUY_API_KEY` instead of the file. `diktuy.py logout` removes the saved key.
- `401 invalid_key` — revoked or mistyped: new key, `login` again. `403 plan_required` — the key works on Профи,
  Макс and company seats only; on the free plan use MCP ([connect.md](connect.md)).

## Meetings (free)

```bash
diktuy.py meetings --since 3d                  # date, length, speakers, ready summaries, id, title
diktuy.py meeting last --summary               # «Кратко», «Протокол», «Задачи» — answer «what was decided» from here
diktuy.py meeting 28.10 --summary tasks        # one summary
diktuy.py meeting <ref> --questions            # the user's own questions to the meeting and the answers
diktuy.py tasks --since 7d                     # «Задачи» of every meeting in the period + meetings without them
diktuy.py search "сроки поставки" --since 30d  # speakers, lines, summaries, questions; [HH:MM:SS] of each hit
diktuy.py search "договор|контракт" --regex --since all
diktuy.py meeting <ref> --format text --out <file>   # full transcript to a file, then read only the part you need
```

- `<ref>`: `last`, a list number (`1` = latest), part of a date or title (`28.10`, `Zoom`), or the full id. Several
  matches — the script lists them; ask the user.
- The REST API has no search; `search` opens each meeting in the period, one request each (60 per minute per key):
  narrow long histories with `--since`. Without `--regex` it matches from the start of a word.
- `meeting` formats: `markdown` (default: summaries + lines with time), `text` (lines only), `json` (for code).
- No meeting yet — it is still being transcribed in the app (wait a minute), the app is signed in to another account,
  or it was deleted. Meetings are read-only here: renaming, speakers and summaries are changed in the app.

## Transcription (1 credit per minute)

Before any of these: `me`, say the expected cost and the balance, wait for yes (SKILL.md, section 3).

| Recording | Command |
|---|---|
| File up to 25 MB and 30 min, text only | `transcribe <file>` — text right away, nothing stored on the server |
| Longer, bigger, needs speakers or a summary, VK Video / Rutube | `submit <url>` — a queued job, up to 12 h and 2 GB |

```bash
diktuy.py transcribe voice.ogg --prompt "Ромашка, Олег Смирнов, CRM"   # names and terms, up to 500 chars
diktuy.py transcribe lecture.m4a --format srt --out lecture.srt         # also vtt, verbose_json, --words
diktuy.py transcribe voices/ --out-dir texts/                           # a folder or "*.ogg": one result per file
diktuy.py submit "<url>" --summary protocol --names "Иван Петров,Мария" --wait --out meeting.md
diktuy.py submit "<url>" --format srt --wait --out video.srt
diktuy.py jobs                                  # status, length, credits
diktuy.py job <id> --wait --format text --out t.txt   # any format of a finished job, any number of times, free
diktuy.py speakers <id> 0=Иван 1=Мария          # 0 is «Участник 1»; empty name restores the label
diktuy.py cancel <id> --yes                     # cancels or DELETES the result for good — only after the user's yes
```

- Every `transcribe` call is charged again: pick the format once (`verbose_json` gives text and timestamps).
- Longer than 30 min without a link: `ffmpeg -i long.m4a -f segment -segment_time 1740 -c copy part_%02d.m4a`, then
  the folder (no speakers this way). Over 25 MB: `ffmpeg -i in.mp4 -vn -ac 1 -b:a 48k out.ogg`.
- Links must open without signing in (Yandex Disk «Поделиться», Google Drive «Anyone with the link»). Some sites
  refuse server downloads — `download_failed`, no credits spent: upload to Yandex Disk or Google Drive instead.
- `--wait` on a long recording can outlast the agent's command timeout: `submit` without `--wait`, then
  `job <id> --wait` later.

## Webhooks (free)

```bash
diktuy.py webhooks add https://n8n.example.ru/webhook/diktuy --events meeting.created,transcription.completed
diktuy.py webhooks list | test <id> | deliveries <id>
diktuy.py webhooks delete <id> --yes            # only after the user's yes
```

The `whsec_…` secret is shown once: it goes straight to the receiving server. Recipes — [automation.md](automation.md).

## What the script does for you

- Output longer than 12 000 characters goes to a file (`DIKTUY_OUT` or the system temp folder, `--out` to choose);
  the agent sees the first 1 500 characters, the path and a token estimate. `--full` turns this off — avoid it.
- Waits out `429` and `503` (`Retry-After`) and retries only requests that cannot charge twice.
- Prints the error code, the server's explanation and a hint `→ …` to pass on to the user. Exit code 1 on API
  errors, 2 when `--yes` is missing.
- After a transcription: «списано N, осталось M».
