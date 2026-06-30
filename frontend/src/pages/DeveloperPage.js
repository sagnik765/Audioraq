import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  Code,
  Copy,
  Key,
  LockKey,
  Plus,
  SpeakerHigh,
  Trash,
  Waveform,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import { API } from '../lib/api';

const qualityProfiles = [
  ['podcast-education-calm', 'Calm education', 'Measured pacing for explainers and long-form narration.'],
  ['podcast-dialogue', 'Podcast dialogue', 'A little more movement for conversational delivery.'],
  ['podcast-storytelling', 'Storytelling', 'More expressive timing for narrative scripts.'],
];

function formatNumber(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return 'Never used';
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function CodeBlock({ children, label }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
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
      <pre className="overflow-x-auto p-5 text-sm leading-6 text-[#E4E4E7]"><code>{children}</code></pre>
    </div>
  );
}

export default function DeveloperPage() {
  const { user, loading } = useAuth();
  const [voices, setVoices] = useState([]);
  const [keys, setKeys] = useState([]);
  const [usage, setUsage] = useState(null);
  const [keyName, setKeyName] = useState('My application');
  const [creating, setCreating] = useState(false);
  const [revealedKey, setRevealedKey] = useState('');
  const [copiedKey, setCopiedKey] = useState(false);

  const endpoint = `${window.location.origin}/api/v1/audio/speech`;
  const curlExample = useMemo(() => `curl ${endpoint} \\
  -H "Authorization: Bearer $AUDIORAQ_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "input": "Welcome to a calmer way to turn ideas into audio.",
    "voice": "aman-warm-analyst",
    "format": "mp3",
    "quality_profile": "podcast-education-calm"
  }' \\
  --output audioraq-speech.mp3`, [endpoint]);

  const pythonExample = useMemo(() => `import os
import requests

response = requests.post(
    "${endpoint}",
    headers={"Authorization": f"Bearer {os.environ['AUDIORAQ_API_KEY']}"},
    json={
        "input": "Your text becomes finished, paced audio.",
        "voice": "samantha-warm-cohost",
        "format": "mp3",
        "quality_profile": "podcast-education-calm",
    },
)
response.raise_for_status()
open("speech.mp3", "wb").write(response.content)`, [endpoint]);

  const loadDeveloperData = async () => {
    if (!user) return;
    const [keyResponse, usageResponse] = await Promise.all([
      axios.get(`${API}/developer/api-keys`, { withCredentials: true }),
      axios.get(`${API}/developer/usage`, { withCredentials: true }),
    ]);
    setKeys(keyResponse.data.keys || []);
    setUsage(usageResponse.data || null);
  };

  useEffect(() => {
    axios.get(`${API}/v1/audio/voices`)
      .then(({ data }) => setVoices(data.data || []))
      .catch(() => setVoices([]));
  }, []);

  useEffect(() => {
    if (!loading && user) {
      loadDeveloperData().catch(() => toast.error('Could not load developer settings'));
    }
  }, [loading, user]); // eslint-disable-line react-hooks/exhaustive-deps

  const createKey = async (event) => {
    event.preventDefault();
    setCreating(true);
    try {
      const { data } = await axios.post(
        `${API}/developer/api-keys`,
        { name: keyName },
        { withCredentials: true },
      );
      setRevealedKey(data.key);
      setKeyName('My application');
      await loadDeveloperData();
      toast.success('API key created');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not create API key');
    } finally {
      setCreating(false);
    }
  };

  const revokeKey = async (keyId) => {
    if (!window.confirm('Revoke this API key? Requests using it will stop immediately.')) return;
    try {
      await axios.delete(`${API}/developer/api-keys/${keyId}`, { withCredentials: true });
      await loadDeveloperData();
      toast.success('API key revoked');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not revoke API key');
    }
  };

  const copyRevealedKey = async () => {
    await navigator.clipboard.writeText(revealedKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 1500);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white" data-testid="developer-page">
      <Navbar />

      <main>
        <section className="relative overflow-hidden border-b border-[#27272A]">
          <div className="absolute inset-0 opacity-40" style={{ background: 'radial-gradient(circle at 78% 22%, rgba(245,166,35,0.22), transparent 32%), radial-gradient(circle at 20% 75%, rgba(255,255,255,0.07), transparent 28%)' }} />
          <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-20 md:px-8 lg:grid-cols-[1.15fr_0.85fr] lg:px-12 lg:py-28">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#F5A623]/30 bg-[#F5A623]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-[#F5A623]">
                <Waveform className="h-4 w-4" /> Audioraq API
              </div>
              <h1 className="max-w-4xl font-['Outfit'] text-5xl font-bold leading-[0.96] tracking-[-0.04em] sm:text-6xl lg:text-7xl">
                Turn text into audio people can stay with.
              </h1>
              <p className="mt-7 max-w-2xl text-lg leading-8 text-[#A1A1AA]">
                One API call produces paced, mastered speech using Audioraq&apos;s podcast voice library. Built for explainers, articles, accessibility, product narration, and audio experiences.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                {user ? (
                  <a href="#api-keys" className="inline-flex items-center gap-2 rounded-full bg-[#F5A623] px-6 py-3 font-bold text-[#0A0A0B] hover:bg-[#F7B84B]">
                    Create an API key <ArrowRight className="h-4 w-4" />
                  </a>
                ) : (
                  <Link to="/register" className="inline-flex items-center gap-2 rounded-full bg-[#F5A623] px-6 py-3 font-bold text-[#0A0A0B] hover:bg-[#F7B84B]">
                    Get an API key <ArrowRight className="h-4 w-4" />
                  </Link>
                )}
                <a href="#quickstart" className="rounded-full border border-[#3F3F46] px-6 py-3 font-semibold text-white hover:border-[#71717A]">Read quickstart</a>
              </div>
            </div>

            <div className="self-end rounded-[2rem] border border-[#343438] bg-[#141417]/90 p-6 shadow-2xl shadow-black/40 backdrop-blur">
              <div className="mb-5 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-[0.2em] text-[#8A8A93]">POST /v1/audio/speech</span>
                <span className="rounded-full bg-[#22C55E]/10 px-2.5 py-1 text-xs font-semibold text-[#86EFAC]">Live</span>
              </div>
              <div className="space-y-3 font-mono text-sm">
                <p><span className="text-[#F5A623]">"input"</span><span className="text-[#71717A]">: </span><span className="text-[#E4E4E7]">"A voice worth listening to."</span></p>
                <p><span className="text-[#F5A623]">"voice"</span><span className="text-[#71717A]">: </span><span className="text-[#E4E4E7]">"aman-warm-analyst"</span></p>
                <p><span className="text-[#F5A623]">"format"</span><span className="text-[#71717A]">: </span><span className="text-[#E4E4E7]">"mp3"</span></p>
              </div>
              <div className="mt-6 flex items-center gap-3 border-t border-[#27272A] pt-5">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#F5A623] text-[#0A0A0B]"><SpeakerHigh weight="fill" className="h-5 w-5" /></div>
                <div>
                  <p className="font-semibold">Binary audio response</p>
                  <p className="text-sm text-[#8A8A93]">MP3 or WAV, ready to play</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-16 md:px-8 lg:px-12">
          <div className="grid gap-4 md:grid-cols-3">
            {[
              ['20 voices', 'Male and female voices across multiple accents and delivery styles.'],
              ['Podcast pacing', 'Sentence-aware pauses and edge padding prevent clipped or rushed speech.'],
              ['Privacy-minded', 'Usage logs count characters but never retain the submitted text.'],
            ].map(([title, body]) => (
              <div key={title} className="rounded-3xl border border-[#27272A] bg-[#141417] p-6">
                <p className="font-['Outfit'] text-xl font-semibold">{title}</p>
                <p className="mt-2 text-sm leading-6 text-[#8A8A93]">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="api-keys" className="mx-auto max-w-7xl scroll-mt-24 px-6 pb-20 md:px-8 lg:px-12">
          <div className="mb-8 flex items-end justify-between gap-5">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F5A623]">Developer access</p>
              <h2 className="mt-2 font-['Outfit'] text-3xl font-semibold">API keys and usage</h2>
            </div>
            <LockKey className="h-9 w-9 text-[#3F3F46]" />
          </div>

          {!loading && !user ? (
            <div className="rounded-3xl border border-[#F5A623]/25 bg-[#F5A623]/5 p-8">
              <h3 className="font-['Outfit'] text-2xl font-semibold">Sign up to issue your first key</h3>
              <p className="mt-2 max-w-2xl text-[#A1A1AA]">Keys are scoped to speech generation and can be revoked instantly from this page.</p>
              <div className="mt-6 flex gap-3">
                <Link to="/register" className="rounded-full bg-[#F5A623] px-5 py-2.5 font-bold text-[#0A0A0B]">Create account</Link>
                <Link to="/login" className="rounded-full border border-[#3F3F46] px-5 py-2.5 font-semibold">Sign in</Link>
              </div>
            </div>
          ) : user ? (
            <div className="grid gap-6 lg:grid-cols-[1fr_0.72fr]">
              <div className="rounded-3xl border border-[#27272A] bg-[#141417] p-6 md:p-8">
                {revealedKey && (
                  <div className="mb-7 rounded-2xl border border-[#F5A623]/30 bg-[#F5A623]/10 p-5">
                    <p className="font-semibold text-[#F8D48F]">Copy this key now. It will not be shown again.</p>
                    <div className="mt-3 flex gap-2">
                      <code className="min-w-0 flex-1 overflow-x-auto rounded-xl bg-[#09090B] px-4 py-3 text-sm text-white">{revealedKey}</code>
                      <button onClick={copyRevealedKey} className="rounded-xl bg-[#F5A623] px-4 text-[#0A0A0B]" aria-label="Copy API key">
                        {copiedKey ? <Check className="h-5 w-5" /> : <Copy className="h-5 w-5" />}
                      </button>
                    </div>
                  </div>
                )}

                <form onSubmit={createKey} className="flex flex-col gap-3 sm:flex-row">
                  <input
                    value={keyName}
                    onChange={(event) => setKeyName(event.target.value)}
                    maxLength={80}
                    className="min-w-0 flex-1 rounded-xl border border-[#343438] bg-[#0A0A0B] px-4 py-3 text-white outline-none focus:border-[#F5A623]"
                    placeholder="Key name"
                  />
                  <button disabled={creating} className="inline-flex items-center justify-center gap-2 rounded-full bg-[#F5A623] px-5 py-3 font-bold text-[#0A0A0B] disabled:opacity-50">
                    <Plus className="h-4 w-4" /> {creating ? 'Creating...' : 'Create key'}
                  </button>
                </form>

                <div className="mt-7 space-y-3">
                  {keys.length ? keys.map((apiKey) => (
                    <div key={apiKey.id} className="flex items-center gap-4 rounded-2xl border border-[#27272A] bg-[#0A0A0B] p-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#27272A]"><Key className="h-5 w-5 text-[#F5A623]" /></div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold">{apiKey.name}</p>
                        <p className="truncate font-mono text-xs text-[#71717A]">{apiKey.prefix}</p>
                      </div>
                      <div className="hidden text-right sm:block">
                        <p className="text-sm text-[#D4D4D8]">{formatNumber(apiKey.requests_count)} requests</p>
                        <p className="text-xs text-[#71717A]">{formatDate(apiKey.last_used_at)}</p>
                      </div>
                      <button onClick={() => revokeKey(apiKey.id)} className="rounded-lg p-2 text-[#71717A] hover:bg-[#EF4444]/10 hover:text-[#EF4444]" aria-label={`Revoke ${apiKey.name}`}>
                        <Trash className="h-5 w-5" />
                      </button>
                    </div>
                  )) : (
                    <p className="rounded-2xl border border-dashed border-[#343438] p-6 text-center text-sm text-[#71717A]">No active keys yet.</p>
                  )}
                </div>
              </div>

              <div className="rounded-3xl border border-[#27272A] bg-[#141417] p-6 md:p-8">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#8A8A93]">All-time usage</p>
                <div className="mt-6 grid grid-cols-2 gap-4">
                  {[
                    ['Requests', formatNumber(usage?.requests)],
                    ['Characters', formatNumber(usage?.characters)],
                    ['Audio data', `${(Number(usage?.output_bytes || 0) / 1048576).toFixed(1)} MB`],
                    ['Avg. latency', usage?.average_latency_ms ? `${formatNumber(usage.average_latency_ms)} ms` : 'No data'],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl bg-[#0A0A0B] p-4">
                      <p className="font-['Outfit'] text-2xl font-semibold">{value}</p>
                      <p className="mt-1 text-xs text-[#71717A]">{label}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-5 text-xs leading-5 text-[#71717A]">Your source text is not retained in Audioraq API usage records.</p>
              </div>
            </div>
          ) : null}
        </section>

        <section id="quickstart" className="border-y border-[#27272A] bg-[#111113] scroll-mt-20">
          <div className="mx-auto max-w-7xl px-6 py-20 md:px-8 lg:px-12">
            <div className="mb-10 max-w-2xl">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F5A623]">Quickstart</p>
              <h2 className="mt-2 font-['Outfit'] text-4xl font-semibold">Your first audio response</h2>
              <p className="mt-3 text-[#A1A1AA]">Send JSON, receive binary audio. Keep the API key on your server, never in browser code.</p>
            </div>
            <div className="grid gap-6 xl:grid-cols-2">
              <CodeBlock label="cURL">{curlExample}</CodeBlock>
              <CodeBlock label="Python">{pythonExample}</CodeBlock>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 py-20 md:px-8 lg:px-12">
          <div className="grid gap-12 lg:grid-cols-[0.65fr_1.35fr]">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#F5A623]">Voice library</p>
              <h2 className="mt-2 font-['Outfit'] text-3xl font-semibold">Choose the delivery, not just the gender.</h2>
              <p className="mt-4 text-sm leading-6 text-[#8A8A93]">Each ID maps to a stable Audioraq voice profile. Availability may use the best configured local or neural engine without changing your request contract.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {voices.map((voice) => (
                <div key={voice.id} className="rounded-2xl border border-[#27272A] bg-[#141417] p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold">{voice.name}</p>
                    <span className="rounded-full bg-[#27272A] px-2 py-0.5 text-[10px] uppercase tracking-wider text-[#A1A1AA]">{voice.gender}</span>
                  </div>
                  <p className="mt-1 text-xs text-[#F5A623]">{voice.style}</p>
                  <code className="mt-3 block break-all text-[11px] text-[#71717A]">{voice.id}</code>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 pb-24 md:px-8 lg:px-12">
          <div className="rounded-[2rem] border border-[#27272A] bg-[#141417] p-8 md:p-10">
            <div className="flex items-center gap-3"><Code className="h-6 w-6 text-[#F5A623]" /><h2 className="font-['Outfit'] text-2xl font-semibold">Request options</h2></div>
            <div className="mt-7 grid gap-4 md:grid-cols-3">
              {qualityProfiles.map(([id, title, body]) => (
                <div key={id} className="rounded-2xl bg-[#0A0A0B] p-5">
                  <p className="font-semibold">{title}</p>
                  <code className="mt-1 block text-xs text-[#F5A623]">{id}</code>
                  <p className="mt-3 text-sm leading-6 text-[#71717A]">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
