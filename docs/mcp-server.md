# Audioraq MCP Server

The Audioraq MCP server lets an AI coding agent use Audioraq's text-to-audio product through two tools: `list_voices` and `create_speech`. It runs locally as an MCP stdio process and calls Audioraq's existing versioned API over HTTPS. It does not expose a public MCP endpoint or open a local network port.

## Requirements

- Python 3.11 or later
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- An Audioraq account and developer key from <https://www.audioraq.com/developers>
- An MCP-compatible agent that can run a local stdio server

## Install from GitHub

Use this command as the local server executable in your agent configuration:

```text
uvx --python 3.11 --from "git+https://github.com/sagnik765/Audioraq.git#subdirectory=mcp-server" audioraq-mcp
```

The source is built from the `mcp-server` subdirectory. You do not need to install the Audioraq web application or its database dependencies.

### Codex

Add this to `~/.codex/config.toml`. Set `AUDIORAQ_API_KEY` in the environment available to Codex; `env_vars` forwards that existing value to the server process without putting the key in the config file.

```toml
[mcp_servers.audioraq]
command = "uvx"
args = [
  "--python", "3.11",
  "--from", "git+https://github.com/sagnik765/Audioraq.git#subdirectory=mcp-server",
  "audioraq-mcp",
]
env_vars = ["AUDIORAQ_API_KEY"]
```

### Cursor

Add the following server to your user-level `~/.cursor/mcp.json` and make sure `AUDIORAQ_API_KEY` is available to Cursor's process. Cursor supports `${env:NAME}` interpolation in stdio server environment values.

```json
{
  "mcpServers": {
    "audioraq": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--python", "3.11",
        "--from", "git+https://github.com/sagnik765/Audioraq.git#subdirectory=mcp-server",
        "audioraq-mcp"
      ],
      "env": {
        "AUDIORAQ_API_KEY": "${env:AUDIORAQ_API_KEY}"
      }
    }
  }
}
```

For other MCP clients, configure the same command as a local stdio server and pass `AUDIORAQ_API_KEY` through the process environment. Keep API keys in user-level configuration or a secret store; do not commit them to project configuration.

## Tools

### `list_voices`

Returns Audioraq's current public voice catalog, defaults, and supported delivery profiles. It does not require an API key.

### `create_speech`

Creates paced MP3 or WAV narration through Audioraq. It requires `AUDIORAQ_API_KEY` and accepts:

| Input | Default | Meaning |
|---|---|---|
| `text` | required | Narration approved by the user |
| `voice` | `aman-warm-analyst` | Stable Audioraq voice ID |
| `output_format` | `mp3` | `mp3` or `wav` |
| `quality_profile` | `podcast-education-calm` | `podcast-education-calm`, `podcast-dialogue`, or `podcast-storytelling` |

The response contains a text block with request metadata and an MCP audio block with the MP3/WAV bytes. Clients that support audio content can play or save the returned result. The current API is synchronous; its configured character limit applies.

## Security and behavior

- The key is read from `AUDIORAQ_API_KEY` for each speech request, sent as a bearer token only to `https://www.audioraq.com`, and never printed by the server.
- The server refuses redirects and omits raw API error bodies from tool errors.
- It does not write local files, start a network listener, or retain narration.
- Narration is sent to Audioraq when `create_speech` is called. Usage records store operational metadata, not the submitted text, per the [API documentation](text-to-audio-api.md).
- It does not retry ambiguous timeouts automatically. The first request may have completed.
- The API key must include the `audio:speech` scope. Keys created on the Audioraq Developers page receive that scope.

## Troubleshooting

- **Tool server does not appear:** confirm `uvx` is on the client's PATH, save the client config, and restart or reload the MCP connection.
- **`AUDIORAQ_API_KEY` missing:** set the variable in the client process environment and reconnect.
- **HTTP 401:** create a new developer key or replace the revoked key.
- **HTTP 413:** shorten the narration or make separate calls for separate sections.
- **HTTP 429:** follow the returned `Retry-After` value; do not loop retries.
- **Timeout:** check Audioraq usage before asking the agent to submit the text again.

## Development

From the repository root:

```bash
uv run --project mcp-server audioraq-mcp
```

The process waits silently on stdin/stdout for its MCP host. Do not print logs to stdout; stdio is the protocol transport.
