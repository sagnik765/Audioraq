import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../lib/api';

const providerConfig = [
  { id: 'google', label: 'Google' },
  { id: 'apple', label: 'Apple' },
];

function SocialButton({ provider, available, intent, roleHint }) {
  const label = provider.label;

  const handleClick = () => {
    if (!available) return;
    const params = new URLSearchParams({
      intent,
      return_origin: window.location.origin,
    });
    if (roleHint) {
      params.set('role_hint', roleHint);
    }
    window.location.assign(`${API}/auth/oauth/${provider.id}/start?${params.toString()}`);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!available}
      className={`w-full rounded-xl px-4 py-3 transition-colors text-sm font-medium ${
        available
          ? 'bg-[#141417] hover:bg-[#1B1B20] border border-[#27272A] text-white'
          : 'bg-[#101013] border border-[#1F1F24] text-[#6E6E77] cursor-not-allowed'
      }`}
      data-testid={`${provider.id}-${intent}-btn`}
    >
      Continue with {label}{available ? '' : ' (setup pending)'}
    </button>
  );
}

export default function SocialAuthButtons({ context = 'sign in', roleHint = '' }) {
  const [providers, setProviders] = useState({ google: false, apple: false });
  const [loading, setLoading] = useState(true);
  const intent = context.toLowerCase().includes('up') ? 'register' : 'login';

  useEffect(() => {
    let active = true;
    axios.get(`${API}/auth/social/providers`).then(({ data }) => {
      if (!active) return;
      setProviders({
        google: Boolean(data?.google),
        apple: Boolean(data?.apple),
      });
    }).catch(() => {
      if (!active) return;
      setProviders({ google: false, apple: false });
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  const hasAnyProvider = providers.google || providers.apple;

  return (
    <div className="space-y-3">
      {providerConfig.map((provider) => (
        <SocialButton
          key={provider.id}
          provider={provider}
          available={providers[provider.id]}
          intent={intent}
          roleHint={roleHint}
        />
      ))}
      {!loading && !hasAnyProvider && (
        <p className="text-xs text-[#8A8A93]">
          Email auth is live. Google and Apple turn on automatically once their server credentials are connected.
        </p>
      )}
      <div className="flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-[#8A8A93]">
        <div className="h-px flex-1 bg-[#27272A]" />
        <span>or use email</span>
        <div className="h-px flex-1 bg-[#27272A]" />
      </div>
    </div>
  );
}
