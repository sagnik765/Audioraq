---
name: Audioraq Text-to-Audio
description: Turn approved scripts into paced MP3 or WAV narration with Audioraq. Uses the local Audioraq MCP server for voice discovery and rendering; requires an Audioraq developer key.
summary: Create paced MP3 or WAV narration with Audioraq from your agent.
version: 1.1.0
tags:
  - text-to-speech
  - voiceover
  - podcast
  - audio
  - mcp
keywords:
  - Audioraq MCP
  - text to audio
  - text to speech
  - podcast narration
  - voiceover
  - MP3
  - WAV
use_cases:
  - Render a podcast intro, episode segment, or explainer as paced MP3 or WAV narration.
  - Prepare a technical article or video script for spoken delivery.
  - Choose an Audioraq voice and delivery profile for narration.
docs_url: https://github.com/sagnik765/Audioraq/blob/main/docs/mcp-server.md
---

# Audioraq Text-to-Audio

Use Audioraq from your agent to turn approved narration into MP3 or WAV audio. Audioraq applies sentence-aware pacing, pauses, edge padding, and mastering, with named voice profiles and three delivery profiles: calm education, dialogue, and storytelling. The local Audioraq MCP server makes voice lookup and rendering available as agent tools.

## Requirements and data handling

- The user needs an Audioraq account and developer API key from https://www.audioraq.com/developers.
- The agent needs the local Audioraq MCP server configured, Python 3.11+, `uv`, and an MCP client that supports local stdio servers. Follow [references/mcp-setup.md](references/mcp-setup.md).
- `list_voices` is a public lookup. `create_speech` sends the narration to Audioraq and requires `AUDIORAQ_API_KEY` with the `audio:speech` scope.
- The server reads the key from its process environment. Never ask the user to paste it into chat, print it, or commit it to project files.
- For a selected source file, read only that file and send only the approved narration. Do not scan folders or include unrelated file contents, metadata, or secrets.
- Do not overwrite an existing audio file. Use the client's supported audio export or file-writing flow and choose an unused path, or ask before replacing a file.
- Audioraq's API documentation says usage records keep character counts and operational metadata, not submitted text. See [the API reference](https://github.com/sagnik765/Audioraq/blob/main/docs/text-to-audio-api.md) for current service behavior.

If the MCP tools are unavailable, explain that the server needs to be installed and connected, then point to the setup guide. Do not silently switch to the direct API helper. The helper is an optional fallback only when the user chooses it; see [references/setup.md](references/setup.md).

## Workflow

1. Use the user's final script as written. If they provide notes, rough copy, or Markdown, prepare speech-ready narration while preserving facts, names, figures, and intent. Expand dates or abbreviations only when the spoken form is clear.
2. Avoid a preference interview when the request is clear. Default to MP3, `aman-warm-analyst`, and `podcast-education-calm`. Use `podcast-dialogue` for conversational copy and `podcast-storytelling` for narrative copy. These profiles shape delivery; they do not create separate speakers or clone voices.
3. Use `list_voices` if the user asks to compare voices or supplies an unclear voice ID. Show a few relevant options, not the whole catalog unless requested.
4. If you drafted or materially edited the narration, show the exact final text and get approval before rendering. A direct request to convert specific text authorizes sending that text. Before the first render, make clear that the approved narration will be sent to Audioraq.
5. The documented default input limit is 5,000 characters, but the configured server limit is authoritative. Do not silently shorten or split longer text. Offer an edit or separately approved sections; each section uses a separate request and produces a separate audio result.
6. Call `create_speech` once per approved result, passing the exact narration, voice, `output_format`, and `quality_profile`. Do not automatically retry an ambiguous timeout; the first request may have completed.
7. Return or save the audio content from the MCP result using the client’s supported audio handling. Report the format, voice, profile, byte size, and available Audioraq request or renderer metadata. If the client cannot save returned audio, explain that limitation instead of claiming a file was created.
8. Do not claim the audio was fact-checked, captioned, or quality-scored. Audioraq shapes audio delivery; it does not validate the script's claims.

## MCP tools

- `list_voices`: returns Audioraq's public voice catalog, defaults, and supported delivery profiles; no key required.
- `create_speech`: renders narration through Audioraq and returns metadata plus an MCP audio content block; requires `AUDIORAQ_API_KEY`.

The server runs locally over stdio, connects to Audioraq over HTTPS, does not open a network listener, refuses redirects, omits raw API error bodies, and does not automatically retry requests. See [references/mcp-setup.md](references/mcp-setup.md) for client setup and [references/api-reference.md](references/api-reference.md) for API limits and errors.

## Optional direct API helper

Use the bundled standard-library helper only if the user explicitly chooses the direct API fallback or their agent cannot receive MCP audio content. It accepts text or stdin, reads no source files, and refuses to overwrite an output file by default.

~~~text
python scripts/audioraq_speech.py speech \
  --text "A short approved narration goes here." \
  --voice aman-warm-analyst \
  --format mp3 \
  --quality-profile podcast-education-calm \
  --output ./audioraq-narration.mp3
~~~

For longer narration, pass the approved text through standard input instead of a shell argument. Consult [references/setup.md](references/setup.md) for fallback setup and [references/api-reference.md](references/api-reference.md) for API behavior.

## Limits and recovery

- The v1 API is synchronous. Long-form jobs, callbacks, audio stitching, subtitles, voice cloning, and separate speaker tracks are not documented v1 features.
- The documented 5,000-character limit is a default and may be configured differently; the API response is authoritative.
- On 400, refresh the voice list and correct the option. On 401, tell the user the key is missing, invalid, or revoked and point to local key setup. On 413, ask whether to shorten the narration or render separate sections. On 429, respect `Retry-After` and do not loop retries.
- Treat an ambiguous timeout as an unknown result. Do not submit the same narration again automatically because the first render may have completed.
