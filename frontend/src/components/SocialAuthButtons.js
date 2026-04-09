import React from 'react';
import { toast } from 'sonner';

function SocialButton({ provider, context }) {
  return (
    <button
      type="button"
      onClick={() => toast.message(`${provider} ${context} will work once OAuth credentials are connected.`)}
      className="w-full bg-[#141417] hover:bg-[#1B1B20] border border-[#27272A] text-white rounded-xl px-4 py-3 transition-colors text-sm font-medium"
      data-testid={`${provider.toLowerCase()}-${context.replace(/\s+/g, '-')}-btn`}
    >
      Continue with {provider}
    </button>
  );
}

export default function SocialAuthButtons({ context = 'sign in' }) {
  return (
    <div className="space-y-3">
      <SocialButton provider="Google" context={context} />
      <SocialButton provider="Apple" context={context} />
      <div className="flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-[#8A8A93]">
        <div className="h-px flex-1 bg-[#27272A]" />
        <span>or use email</span>
        <div className="h-px flex-1 bg-[#27272A]" />
      </div>
    </div>
  );
}
