# Audioraq MCP Server

Audioraq hosts a Streamable HTTP MCP endpoint at:

```text
https://www.audioraq.com/mcp
```

Connect an MCP client using an Audioraq developer key as a bearer credential. The hosted server exposes `list_voices` and `create_speech` through the existing Audioraq text-to-audio API. It is part of the deployed FastAPI application; no local Python process is needed for the hosted connection.

## Requirements

- An Audioraq account and developer API key from <https://www.audioraq.com/developers>
- An MCP client that supports Streamable HTTP and custom authorization headers
- A key with the `audio:speech` scope (keys created on the Developers page receive it)

The hosted endpoint accepts Audioraq keys as static bearer credentials. It does not implement OAuth sign-in or OAuth discovery. Store the key in the agent's local environment or secret manager; do not paste it into chat, commit it, or put it in a shared config file.

## Connect from Codex

Set `AUDIORAQ_API_KEY` in the environment available to Codex. Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.audioraq]
url = "https://www.audioraq.com/mcp"
bearer_token_env_var = "AUDIORAQ_API_KEY"
```

Reload MCP servers in Codex. The `bearer_token_env_var` field supplies the environment value as the HTTP bearer token.

## Connect from Cursor

Make `AUDIORAQ_API_KEY` available to the Cursor process and add this server to `~/.cursor/mcp.json`:

```json
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
```

Reload the server in Cursor. For another MCP client, connect to the same endpoint over Streamable HTTP and set `Authorization: Bearer <Audioraq API key>`.

## Tools

### `list_voices`

Returns Audioraq's public voice catalog, default voice, and supported delivery profiles. The hosted MCP endpoint still requires a valid Audioraq key before any MCP request is served.

### `create_speech`

Creates paced MP3 or WAV narration and returns request metadata plus an MCP audio content block. Inputs:

| Input | Default | Meaning |
|---|---|---|
| `text` | required | User-approved narration |
| `voice` | `aman-warm-analyst` | Stable Audioraq voice ID |
| `output_format` | `mp3` | `mp3` or `wav` |
| `quality_profile` | `podcast-education-calm` | `podcast-education-calm`, `podcast-dialogue`, or `podcast-storytelling` |

Speech generation uses the connected key's existing rate limit and usage records. The API is synchronous; its configured character limit applies (5,000 characters by default). The server does not write audio files to the user's machine; use the MCP client's audio export or file workflow.

## Security and behavior

- The endpoint validates the opaque API key against Audioraq's existing developer-key store and scope on every MCP HTTP request. Revoked keys stop working.
- HTTPS terminates at Audioraq's Caddy proxy. The MCP server passes the key only to the app's loopback text-to-audio API route for speech rendering.
- The MCP tool never prints or returns the key, writes local files, or retries an ambiguous timeout automatically.
- Raw API error bodies are omitted. On 401, check that the key is active; on 413, shorten the narration or split it into separately approved sections; on 429, respect `Retry-After`.
- The API documentation says usage records keep character counts and operational metadata, not submitted narration: [Text-to-Audio API Reference](text-to-audio-api.md).

## Local stdio alternative

For clients or environments that require a local process, the repository also includes a stdio MCP server under `mcp-server/`. Its install command and client configuration are in [`mcp-server/README.md`](../mcp-server/README.md). Both transports expose the same two tools and use the same Audioraq developer key.

The hosted server uses the official [MCP Python SDK Streamable HTTP transport](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/asgi.md) and its bearer-token verification interface. Hosted transport behavior is documented by the [MCP Python SDK](https://py.sdk.modelcontextprotocol.io/).
