# Connect to Audioraq MCP

Audioraq hosts a Streamable HTTP MCP server at `https://www.audioraq.com/mcp`. A local Python server is not required.

## Before setup

- Create an Audioraq developer key at https://www.audioraq.com/developers. Speech generation requires the `audio:speech` scope.
- Set `AUDIORAQ_API_KEY` in the environment available to your MCP client or use its secret manager.
- The hosted endpoint accepts Audioraq API keys as static bearer credentials; it does not use OAuth sign-in. Do not put the key in a shared project file or paste it into chat.

## Codex

Set the environment variable before starting/restarting Codex, then add this to `~/.codex/config.toml`:

~~~toml
[mcp_servers.audioraq]
url = "https://www.audioraq.com/mcp"
bearer_token_env_var = "AUDIORAQ_API_KEY"
~~~

## Cursor

Make the variable available to the Cursor process and add this entry to `~/.cursor/mcp.json`:

~~~json
{
  "mcpServers": {
    "audioraq": {
      "url": "https://www.audioraq.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:AUDIORAQ_API_KEY}"
      }
    }
  }
}
~~~

## Other MCP clients

Connect to the endpoint over Streamable HTTP and configure the request header `Authorization: Bearer <Audioraq API key>`. The server checks the key and `audio:speech` scope on each MCP request. Speech rendering uses the existing API rate limit and usage tracking.

## Local stdio alternative

The repository also includes a local stdio server for MCP clients that cannot use a hosted endpoint or when a user prefers local execution. See <https://github.com/sagnik765/Audioraq/blob/main/mcp-server/README.md>.

## Troubleshooting

- If the server does not appear, check that the MCP client supports Streamable HTTP and reload the server connection.
- If the server returns 401, check that `AUDIORAQ_API_KEY` is available to the client and that the key is active with `audio:speech` scope.
- For 413, shorten the approved narration or render separate sections.
- For 429, follow `Retry-After`; do not retry in a loop.
- If a render times out, check Audioraq usage before submitting the same text again.
