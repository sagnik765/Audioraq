# Connect the Audioraq MCP server

The local server lets an MCP-compatible agent discover Audioraq voices and render narration without copying API requests into a terminal. It runs over stdio on the developer's computer and calls the Audioraq API over HTTPS.

## Before setup

- Install Python 3.11 or later and [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- Create an Audioraq developer key at https://www.audioraq.com/developers. Speech generation needs the `audio:speech` scope.
- Make `AUDIORAQ_API_KEY` available to the MCP client process through its local environment or secret manager. Never put the key in chat, a committed project file, or the server command.

## Codex

Add this to `~/.codex/config.toml`:

~~~toml
[mcp_servers.audioraq]
command = "uvx"
args = [
  "--python", "3.11",
  "--from", "git+https://github.com/sagnik765/Audioraq.git#subdirectory=mcp-server",
  "audioraq-mcp",
]
env_vars = ["AUDIORAQ_API_KEY"]
~~~

Set `AUDIORAQ_API_KEY` in the environment available to Codex, then restart or reload the MCP connection.

## Cursor

Add this server entry to the user-level `~/.cursor/mcp.json`. Cursor supports `${env:NAME}` interpolation for environment values:

~~~json
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
~~~

Make the variable available to Cursor itself, then restart or reload the server. For another MCP client, use the same `uvx` command as a local stdio server and pass `AUDIORAQ_API_KEY` through its process environment.

## Tools

- `list_voices` returns the public voice catalog, defaults, and supported delivery profiles. It does not need a key.
- `create_speech` accepts narration text, a voice ID, MP3 or WAV format, and a delivery profile. It requires a key and returns metadata plus an MCP audio content block.

The documented default limit is 5,000 characters per request; the configured API limit is authoritative. The API is synchronous. Do not automatically retry a timeout because the first render may have completed.

## Troubleshooting

- If the server does not appear, verify `uvx` is on the agent's PATH and reload the MCP connection.
- If speech generation returns 401, check whether the key is missing, revoked, or lacks `audio:speech` scope.
- For 413, shorten the approved script or render separate sections in separate requests.
- For 429, follow `Retry-After`; do not retry in a loop.
- If the render times out, check Audioraq usage before submitting the text again.
