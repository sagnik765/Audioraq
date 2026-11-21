# Optional direct API fallback: set up an Audioraq API key

The preferred workflow uses the local Audioraq MCP server. See [mcp-setup.md](mcp-setup.md) to connect it to Codex, Cursor, or another MCP client. Use this helper setup only if the user chooses direct API calls or the agent cannot handle MCP audio content.

The audio helper needs an Audioraq developer key in the environment of the process that runs it.

1. Sign in to Audioraq and create a developer key at https://www.audioraq.com/developers.
2. Configure the key as AUDIORAQ_API_KEY in the agent's own local environment or secret settings. Do not paste it into chat, store it in the skill folder, or add it to a shared .env file.
3. On Bash or Zsh, you can enter the key without echoing it or putting the value in shell history:

~~~sh
printf 'Audioraq API key: '
read -r -s AUDIORAQ_API_KEY
printf '\n'
export AUDIORAQ_API_KEY
~~~

Launch the agent from that same shell so child processes inherit the variable. A desktop agent launched separately may not inherit a shell variable; configure the agent's own process environment instead. Start a fresh agent session after setup if it was already running.

The public voice catalog does not require a key:

~~~sh
python scripts/audioraq_speech.py voices
~~~

If a key may have been exposed, revoke it from the Audioraq developer page and configure a replacement. Never ask an agent to display or send the key.
