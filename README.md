# Diktuy Skills

Скилл и MCP-сервер [Диктуй](https://diktuy.ru) для ИИ-ассистентов: Claude, Claude Code, ChatGPT, Codex, Cursor,
VS Code и других. Ассистент ищет по вашим встречам, расшифровкам и диктовкам, собирает решения и задачи, находит,
кто что сказал и когда, и расшифровывает ссылки на видео.

```bash
npx skills add diktuy/skills
```

[English below](#english)

## Что умеет

- «Что решили на планёрке во вторник?» — решения и задачи по выжимке встречи
- «Найди, где Олег говорил про сроки поставки» — реплика, кто сказал и время `[ЧЧ:ММ:СС]`
- «Собери задачи со всех встреч за неделю» — по людям, со сроками
- «Расшифруй вебинар по ссылке на Rutube и выпиши главное» — VK Видео, Rutube, Яндекс Диск, Google Диск, файл
- «Найди в моих диктовках письмо поставщику»

Скилл учит ассистента работать с Диктуй правильно: сначала спросить, прежде чем списывать кредиты, не просить ключ в
чате, понимать московское время, формат id и лимиты тарифов. Сам доступ к данным даёт MCP-сервер
`https://mcp.diktuy.ru/mcp` со входом через аккаунт Диктуй.

## Установка

**Любой агент** (Claude Code, Codex, Cursor, Copilot и ещё 70+, установщик сам найдёт их на компьютере):

```bash
npx skills add diktuy/skills
```

Затем подключите сервер в своей программе — команды в [connect.md](skills/diktuy/references/connect.md).

**Claude Code** — плагин сразу со скиллом и сервером:

```
/plugin marketplace add diktuy/skills
/plugin install diktuy@diktuy
```

Потом `/mcp` → Diktuy → войти в аккаунт.

**Codex**

```bash
npx skills add diktuy/skills -a codex
codex mcp add diktuy --url https://mcp.diktuy.ru/mcp
codex mcp login diktuy
```

**Cursor** — `npx skills add diktuy/skills -a cursor` и сервер в `~/.cursor/mcp.json`:

```json
{ "mcpServers": { "diktuy": { "url": "https://mcp.diktuy.ru/mcp" } } }
```

**Claude (claude.ai)** — [Диктуй в каталоге Claude](https://claude.ai/directory/connectors/diktuy).
Скилл: Customize → Skills → Add → Upload skill, ZIP папки `skills/diktuy`.

**ChatGPT** — Плагины → Добавить → Добавить пользовательский сервер MCP. Нужен тариф Pro, Business или Enterprise.

## Вход и ключи

- По умолчанию — вход через аккаунт Диктуй, без ключей. Отключить: [кабинет → API](https://diktuy.ru/dashboard/api).
- **Без MCP** — по ключу API (платные тарифы): в скилле есть скрипт `scripts/diktuy.py` на Python без зависимостей.
  Встречи, поиск, задачи за неделю, расшифровка файла, папки или ссылки, уведомления. Ключ сохраняется командой
  `python scripts/diktuy.py login` в вашем терминале, для серверов и CI — переменная `DIKTUY_API_KEY`. Подходит, если
  программа не умеет MCP, агент работает в песочнице или не хочется держать сервер в каждом разговоре.
  Команды — [cli.md](skills/diktuy/references/cli.md).
- REST API: `https://api.diktuy.ru/v1`, [OpenAPI](https://api.diktuy.ru/v1/docs/openapi.json); n8n, Make,
  Битрикс24 — [automation.md](skills/diktuy/references/automation.md).

## Настройка под себя

Скажите ассистенту «Настрой Диктуй». Он спросит, для чего вам Диктуй, сколько кредитов можно тратить без вопроса,
куда сохранять расшифровки, какие имена и термины звучат в записях, и запишет ответы в
`~/.diktuy-skill/preferences.md`. Файл лежит вне папки скилла, обновления его не трогают.

## Цены и лимиты

MCP есть на всех тарифах Диктуй. Чтение бесплатно, расшифровка по ссылке — 1 кредит за минуту записи. На бесплатном
тарифе 50 запросов ассистента в сутки, встречи из приложения видны на платных тарифах. Подробнее —
[diktuy.ru/pricing](https://diktuy.ru/pricing) и [billing.md](skills/diktuy/references/billing.md).

Второй счёт — токены вашей нейросети. Час встречи — 15–30 тыс. токенов, и они уходят модели заново с каждым
следующим шагом ассистента. Поэтому скилл сначала берёт выжимку, потом поиск, а полный текст читает частями или
сохраняет в файл. Замеры — в [billing.md](skills/diktuy/references/billing.md).

## Состав

| Файл | Зачем |
|---|---|
| [skills/diktuy/SKILL.md](skills/diktuy/SKILL.md) | сам скилл: порядок подключения, деньги, инструменты, сценарии |
| [references/connect.md](skills/diktuy/references/connect.md) | подключение в каждой программе |
| [references/mcp-tools.md](skills/diktuy/references/mcp-tools.md) | 13 инструментов сервера |
| [references/cli.md](skills/diktuy/references/cli.md) | без MCP: скрипт `scripts/diktuy.py` по ключу API |
| [references/rest-api.md](skills/diktuy/references/rest-api.md) | REST API для своего кода |
| [references/automation.md](skills/diktuy/references/automation.md) | уведомления, n8n, Make, Битрикс24 |
| [references/billing.md](skills/diktuy/references/billing.md) | тарифы, кредиты, лимиты, токены |
| [references/setup.md](skills/diktuy/references/setup.md) | «Настрой Диктуй»: настройки под себя |
| [evals/evals.json](evals/evals.json) | проверочные сценарии |
| `.claude-plugin/`, `.mcp.json`, `agents/openai.yaml` | плагин Claude Code и манифест Codex |

Вопросы: [support@diktuy.ru](mailto:support@diktuy.ru), Telegram [@diktuy_help](https://t.me/diktuy_help).

---

## English

Agent skill and remote MCP server for [Diktuy](https://diktuy.ru), a meeting recorder and voice dictation app for
Windows and macOS with a Telegram bot. The assistant searches your meetings, transcripts and dictations, collects
decisions and action items, finds who said what and when, and transcribes VK Video, Rutube, Yandex Disk, Google Drive
or direct file links. Data is in Russian; the skill works in any language.

```bash
npx skills add diktuy/skills
```

- Claude Code: `/plugin marketplace add diktuy/skills`, then `/plugin install diktuy@diktuy`, then `/mcp` to sign in.
- Codex: `codex mcp add diktuy --url https://mcp.diktuy.ru/mcp` and `codex mcp login diktuy`.
- Cursor, VS Code and others: see [connect.md](skills/diktuy/references/connect.md).
- Claude.ai: [Diktuy in the Claude directory](https://claude.ai/directory/connectors/diktuy).

Sign-in is OAuth with a Diktuy account (no keys). For headless use on paid plans, put an API key in `DIKTUY_API_KEY`; REST API at
`https://api.diktuy.ru/v1` ([OpenAPI](https://api.diktuy.ru/v1/docs/openapi.json)). Reading is free; transcription
costs 1 credit per minute of audio. Free plan: 50 assistant calls per day.

Without MCP, the bundled `scripts/diktuy.py` (Python 3.8+, no dependencies) does the same with an API key —
[cli.md](skills/diktuy/references/cli.md). An hour of meeting is 15–30k tokens of your model's context, so the skill
reads summaries first and pages through transcripts. Say «Настрой Диктуй» ("set up Diktuy") to save personal
preferences in `~/.diktuy-skill/preferences.md`.

License: MIT.
