# Connecting Diktuy

Server: `https://mcp.diktuy.ru/mcp` (Streamable HTTP). Two ways to sign in:

- **Diktuy account (OAuth)** — default. The app opens a Diktuy window «Разрешить», the user signs in at diktuy.ru.
  Works on every Diktuy plan. Disconnect any time at https://diktuy.ru/dashboard/api («Отключить»).
- **API key** — `Authorization: Bearer dk_live_…`, key from https://diktuy.ru/dashboard/api. For headless setups.
  Keys can be created on paid plans only; on the free plan sign in with the account. Keep the key in the
  `DIKTUY_API_KEY` environment variable.

Don't configure both for one server: in Claude Code an `Authorization` header turns OAuth off.

## Claude (claude.ai, desktop, mobile)

Customize → Connectors → Add → Add custom connector → name `Diktuy`, URL `https://mcp.diktuy.ru/mcp` → Connect.
The free Claude plan allows one custom connector. Claude's interface is in English.

## ChatGPT

Plugins → + → Add custom MCP server (in Russian UI: Плагины → Добавить → Добавить пользовательский сервер MCP),
URL `https://mcp.diktuy.ru/mcp`, authentication OAuth. Custom MCP servers need ChatGPT Pro (read-only tools),
Business or Enterprise; Plus and Free refuse them.

## Claude Code

```bash
claude mcp add --transport http diktuy https://mcp.diktuy.ru/mcp            # this project
claude mcp add --transport http --scope user diktuy https://mcp.diktuy.ru/mcp  # all projects
```

Then run `/mcp` inside Claude Code and sign in (or `claude mcp login diktuy` from the shell).

With a key instead of OAuth:

```bash
claude mcp add --transport http diktuy https://mcp.diktuy.ru/mcp \
  --header "Authorization: Bearer $DIKTUY_API_KEY"
```

## Codex

```bash
codex mcp add diktuy --url https://mcp.diktuy.ru/mcp
codex mcp login diktuy
```

With a key: `codex mcp add diktuy --url https://mcp.diktuy.ru/mcp --bearer-token-env-var DIKTUY_API_KEY`.
Restart Codex after adding.

## Cursor

`~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

```json
{
  "mcpServers": {
    "diktuy": { "url": "https://mcp.diktuy.ru/mcp" }
  }
}
```

Cursor offers to sign in. With a key, add `"headers": { "Authorization": "Bearer ${env:DIKTUY_API_KEY}" }`.

## VS Code (Copilot)

`.vscode/mcp.json`:

```json
{
  "inputs": [
    { "type": "promptString", "id": "diktuy-key", "description": "Diktuy API key", "password": true }
  ],
  "servers": {
    "diktuy": {
      "type": "http",
      "url": "https://mcp.diktuy.ru/mcp",
      "headers": { "Authorization": "Bearer ${input:diktuy-key}" }
    }
  }
}
```

## Other MCP clients

Any client with remote Streamable HTTP and OAuth 2.1 (dynamic client registration or client ID metadata documents)
works with the URL alone. Otherwise pass the API key as a Bearer header.

## No account, only the Telegram bot

Send `/mcp` to @DiktuyMeetBot: it returns a personal URL with a token. Treat it like a password. The assistant then
sees bot recordings only.

## Check the connection

Call `get_account`. It returns the plan, the credit balance (`minutes_left`) and `now` in Moscow time.
- «Нужен аккаунт Диктуй…» — signed in with the bot URL; account-only tools are unavailable.
- 401 — the key was revoked or mistyped, or the account disconnected assistants in the dashboard. Sign in again.
