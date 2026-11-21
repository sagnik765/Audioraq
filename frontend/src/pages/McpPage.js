import React, { useState } from 'react';
import { ArrowRight, Check, Copy, Key, Plug, Waveform } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import Navbar from '../components/Navbar';

const endpoint = 'https://www.audioraq.com/mcp';

const codexConfig = `[mcp_servers.audioraq]
url = "${endpoint}"
bearer_token_env_var = "AUDIORAQ_API_KEY"`;

const cursorConfig = `{
  "mcpServers": {
    "audioraq": {
      "url": "${endpoint}",
      "headers": {
        "Authorization": "Bearer \${env:AUDIORAQ_API_KEY}"
      }
    }
  }
}`;

function ConfigBlock({ label, value }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Could not copy configuration');
    }
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-[#2E2E32] bg-[#09090B]">
      <div className="flex items-center justify-between border-b border-[#27272A] px-4 py-2.5">
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8A8A93]">{label}</span>
        <button onClick={copy} className="flex items-center gap-1.5 text-xs text-[#A1A1AA] hover:text-white">
          {copied ? <Check className="h-4 w-4 text-[#22C55E]" /> : <Copy className="h-4 w-4" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-5 text-sm leading-6 text-[#E4E4E7]"><code>{value}</code></pre>
    </div>
  );
}

export default function McpPage() {
  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white" data-testid="mcp-page">
      <Navbar />
      <main>
        <section className="relative overflow-hidden border-b border-[#27272A]">
          <div className="absolute inset-0 opacity-40" style={{ background: 'radial-gradient(circle at 78% 22%, rgba(245,166,35,0.22), transparent 32%), radial-gradient(circle at 20% 75%, rgba(255,255,255,0.07), transparent 28%)' }} />
          <div className="relative mx-auto max-w-7xl px-6 py-20 md:px-8 lg:px-12 lg:py-28">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#F5A623]/30 bg-[#F5A623]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-[#F5A623]">
              <Plug className="h-4 w-4" /> Audioraq MCP
            </div>
            <h1 className="max-w-4xl font-['Outfit'] text-5xl font-bold leading-[0.96] tracking-[-0.04em] sm:text-6xl lg:text-7xl">
              Give your agent an audio studio.
            </h1>
            <p className="mt-7 max-w-3xl text-lg leading-8 text-[#A1A1AA]">
              Connect to Audioraq’s hosted Model Context Protocol server. Your agent can browse the voice library and turn approved scripts into paced, mastered MP3 or WAV audio—using Audioraq’s voice and delivery profiles.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/developers#api-keys" className="inline-flex items-center gap-2 rounded-full bg-[#F5A623] px-6 py-3 font-bold text-[#0A0A0B] hover:bg-[#F7B84B]">
                Create an API key <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#connect" className="rounded-full border border-[#3F3F46] px-6 py-3 font-semibold text-white hover:border-[#71717A]">Connect an agent</a>
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-7xl gap-4 px-6 py-12 md:grid-cols-3 md:px-8 lg:px-12">
          {[
            ['list_voices', 'Explore Audioraq voices and supported delivery profiles.'],
            ['create_speech', 'Render approved narration as MP3 or WAV.'],
            ['Paced audio', 'Sentence-aware pauses, edge padding, and mastering.'],
          ].map(([title, body]) => (
            <div key={title} className="rounded-3xl border border-[#27272A] bg-[#141417] p-6">
              <p className="font-['Outfit'] text-xl font-semibold">{title}</p>
              <p className="mt-2 text-sm leading-6 text-[#8A8A93]">{body}</p>
            </div>
          ))}
        </section>

        <section id="connect" className="mx-auto max-w-7xl scroll-mt-24 px-6 pb-20 md:px-8 lg:px-12">
          <div className="mb-8 max-w-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F5A623]">Connect once</p>
            <h2 className="mt-2 font-['Outfit'] text-3xl font-semibold">Hosted endpoint</h2>
            <p className="mt-3 leading-7 text-[#A1A1AA]">Use the endpoint below with an Audioraq developer key. The hosted server checks the key on each connection request. Speech requests use your key’s existing usage and rate limits.</p>
          </div>

          <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="rounded-3xl border border-[#27272A] bg-[#141417] p-6 md:p-8">
              <div className="flex items-start gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#F5A623] text-[#0A0A0B]"><Waveform weight="fill" className="h-5 w-5" /></div>
                <div>
                  <p className="font-semibold">Streamable HTTP</p>
                  <code className="mt-2 block break-all rounded-lg bg-[#09090B] px-3 py-2 text-sm text-[#F5A623]">{endpoint}</code>
                </div>
              </div>
              <div className="mt-6 flex items-start gap-3 border-t border-[#27272A] pt-5">
                <Key className="mt-0.5 h-4 w-4 shrink-0 text-[#F5A623]" />
                <p className="text-sm leading-6 text-[#A1A1AA]">Use an Audioraq developer key with the <code className="text-[#E4E4E7]">audio:speech</code> scope. Keep it in your agent’s environment or secret manager; don’t paste it into a shared config or chat.</p>
              </div>
              <p className="mt-5 text-xs leading-5 text-[#71717A]">This hosted endpoint accepts Audioraq API keys as static bearer credentials. It does not use an OAuth sign-in flow.</p>
            </div>

            <div className="space-y-5">
              <ConfigBlock label="Codex · ~/.codex/config.toml" value={codexConfig} />
              <ConfigBlock label="Cursor · ~/.cursor/mcp.json" value={cursorConfig} />
            </div>
          </div>

          <div className="mt-8 rounded-3xl border border-[#27272A] bg-[#111113] p-6 md:p-8">
            <h3 className="font-['Outfit'] text-xl font-semibold">Before rendering</h3>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-[#A1A1AA]">
              <li>• Approve the exact narration before your agent sends it to Audioraq.</li>
              <li>• The API is synchronous and defaults to a 5,000-character request limit.</li>
              <li>• Use the returned MCP audio content or save it with your agent’s supported audio handling.</li>
              <li>• If a render times out, check usage before retrying; the first request may have completed.</li>
            </ul>
            <Link to="/developers" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[#F5A623] hover:text-[#F7B84B]">API keys and developer guide <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </section>
      </main>
    </div>
  );
}
