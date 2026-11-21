# Audioraq MCP Server

Local Model Context Protocol server for Audioraq's developer text-to-audio API. It runs over stdio, exposes `list_voices` and `create_speech`, and returns audio as a standard MCP audio content block.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- An Audioraq developer key created at <https://www.audioraq.com/developers>

## Run from GitHub

Configure your MCP client to run:

```text
uvx --python 3.11 --from "git+https://github.com/sagnik765/Audioraq.git#subdirectory=mcp-server" audioraq-mcp
```

Pass `AUDIORAQ_API_KEY` to the local server process through the MCP client's environment configuration. The key is sent only to `www.audioraq.com` for speech requests. `list_voices` is public and does not need a key.

See [`docs/mcp-server.md`](../docs/mcp-server.md) for Codex and Cursor setup, key handling, and tool details.
