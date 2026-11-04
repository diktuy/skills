# Personal setup

When: the user says «настрой Диктуй» / "set up Diktuy", or comes for the first time and `~/.diktuy-skill/preferences.md`
does not exist (offer it in one line after the first answer, don't force it). Optional: without it the skill uses
the defaults.

## 1. Check access

MCP: `get_account`. No MCP: `diktuy.py me` ([cli.md](cli.md)). Nothing works — [connect.md](connect.md) first.

## 2. Ask — one message, a numbered list

1. What for: meetings from the app / transcribing files and links / automations / everything?
2. How many credits may one transcription spend without asking? Default: always ask (SKILL.md, section 3).
3. Where to save transcripts? Default: the system temp folder.
4. Names, companies and terms that often come up in recordings (for correct spelling).
5. Regular meeting participants — to name speakers in link transcriptions.

«По умолчанию» and «пропусти» are fine answers.

## 3. Write `~/.diktuy-skill/preferences.md`

On Windows `C:\Users\<name>\.diktuy-skill\preferences.md`. It lives outside the skill folder, so updates keep it.

```markdown
# Диктуй — мои настройки

- Использую: встречи, расшифровка файлов
- Без вопроса тратить до: 30 кредитов за раз; пачки — всегда спрашивать
- Расшифровки сохранять в: ~/Documents/Расшифровки
- Словарь: Ромашка, Олег Смирнов, CRM, 1С
- Участники встреч: Иван Петров, Мария Соколова
- Язык записей: ru
```

How to apply: the folder → `--out` or where you save transcripts; the vocabulary → `add_dictionary_words` (MCP, asks
first) or `--prompt` of `transcribe`; participants → `speaker_names` / `--names`; language → `language`; the credit
threshold replaces «wait for a yes» up to that amount — batches and anything above it still need a yes.

## 4. Trim — only if asked

References load only when needed, so unused ones cost nothing. If the user still wants a smaller skill: delete
`references/automation.md` (no automations), `references/cli.md` and `scripts/` (MCP only), or `references/rest-api.md`
(no own code), and narrow the triggers in the `description` of SKILL.md. Warn that a skill update brings them back;
`preferences.md` stays.

## 5. Done

One line: what is set and a request to start with: «Что решили на последней встрече?», «Собери задачи за неделю»,
«Расшифруй это видео».
