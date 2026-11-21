# Audioraq on Agensi: listing draft

## Name

Audioraq Text-to-Audio

## Summary

Turn approved scripts into paced MP3 or WAV narration from your agent with Audioraq.

## Description

Turn a podcast intro, article, explainer, tutorial, or video script into finished MP3 or WAV narration from your agent. Audioraq's audio pipeline adds sentence-aware pacing, pauses, edge padding, and mastering. Choose a named Audioraq voice and one of three delivery profiles: calm education, dialogue, or storytelling.

Connect the local Audioraq MCP server once, then use your agent to browse voices and render approved narration. The server returns an audio block and render metadata. It runs on your computer and uses Audioraq's API; you need an Audioraq developer key, but no separate voice-vendor accounts.

## Demo prompt

Render this approved intro as an MP3 using the `aman-warm-analyst` voice and `podcast-education-calm` profile: “A good idea deserves more than a wall of text. Turn this script into paced audio with Audioraq.” Save or return the audio as `audioraq-demo.mp3` in the output location I specify.

## What the buyer gets

- Agent tools to browse Audioraq voices and create narration through the local MCP server.
- Sentence-aware pacing, pauses, edge padding, and mastering in Audioraq's pipeline.
- MP3 or WAV output with voice, delivery profile, and available renderer/request metadata.
- Sensible defaults and a workflow that shows edited narration for approval before rendering.
- A self-contained direct API helper as an optional fallback when the user chooses it.

## Categories to select

1. Primary: Writing & Content
2. Also relevant: Workflow Automation or Image & Video, if multiple categories are available

## Tags

text-to-speech, text-to-audio, voiceover, podcast, narration, MP3, WAV, MCP, Audioraq

## Use cases

- Turn a reviewed podcast intro, outro, or episode segment into paced narration.
- Create an MP3 or WAV voiceover for a tutorial, presentation, or video.
- Prepare a selected article or explainer for spoken delivery.
- Choose an Audioraq voice and delivery profile for a story or lesson.

## Requirements and permissions

- Requires an Audioraq developer account and API key with `audio:speech` scope.
- Requires Python 3.11+, `uv`, and an MCP-compatible agent that can run a local stdio server.
- Network: outbound HTTPS to `www.audioraq.com` for speech generation; voice lookup is public.
- Environment: pass `AUDIORAQ_API_KEY` to the local server process; never paste it into chat or commit it.
- Narration is sent to Audioraq when the user requests a render. If the agent edits the script, it shows the exact text and gets approval first.
- The server does not open a public listener or automatically retry ambiguous timeouts.

## Known limitations

- Buyers need their own Audioraq developer key and local MCP setup. The API account usage is separate from any Agensi listing price.
- The API renders synchronously. Its documented default is 5,000 characters per request; the configured server limit is authoritative. Longer scripts need separate approved calls and audio results.
- The current v1 docs do not describe subtitle generation, long-form jobs, stitching, voice cloning, or separate speaker tracks.
- A dialogue profile does not generate separate speaker tracks. A delivery profile does not fact-check a script.
- The local MCP server returns standard MCP audio content. Saving it to a file depends on the connected agent's audio/file support; the skill must say so if the client cannot export it.

## FAQ

### What does it create?

Paced MP3 or WAV narration from user-provided or user-approved text.

### Does it prepare the script?

It can clean Markdown and make copy easier to read aloud. If the agent writes or materially changes narration, it shows the final text for approval before rendering.

### Do I need an Audioraq key?

Yes, for speech generation. Create a developer key at https://www.audioraq.com/developers and configure `AUDIORAQ_API_KEY` in the environment used by your MCP client. Do not paste it into chat. Voice lookup does not require a key.

### Can it render a full long-form episode in one request?

The API is synchronous and documents a 5,000-character default limit. Longer scripts require separate approved requests and separate audio results.

## Documentation links

- MCP installation: https://github.com/sagnik765/Audioraq/blob/main/docs/mcp-server.md
- API behavior: https://github.com/sagnik765/Audioraq/blob/main/docs/text-to-audio-api.md

## Pricing recommendation

Launch free while validating whether buyers can configure their key, connect the MCP server, complete their first render, and export the returned audio. The extra account and local setup steps are a barrier. Consider a one-time price after observing repeat use and buyer feedback. Public marketplace usage is not sales data and cannot establish an optimal price.

## Listing media

Upload the ZIP as the skill payload. After a real Audioraq render, add a short MP3 sample and a brief capture of the approval-to-audio flow if Agensi supports listing media. Do not present an unrendered or synthetic example as product proof.

## Upload steps

1. Sign in to Agensi and enable Creator Mode.
2. Open https://www.agensi.io/dashboard/submit and upload `audioraq-text-to-audio.zip`.
3. Use the listing fields above and review the required permissions and price.
4. Keep environment access limited to `AUDIORAQ_API_KEY` and network access limited to `www.audioraq.com`.
5. Add authentic listing media after making and listening to a real sample, then submit for review.

This is a prepared upload kit. It has not been submitted to Agensi.
