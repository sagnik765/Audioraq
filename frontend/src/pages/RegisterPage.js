import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Eye, EyeSlash, Microphone, MicrophoneStage, User } from '@phosphor-icons/react';
import { useAuth } from '../contexts/AuthContext';
import { API } from '../lib/api';

const starterInterests = ['technology', 'business', 'self improvement'];

export default function RegisterPage() {
  const { register, getPendingSocialSignup, completeSocialSignup, cancelPendingSocialSignup } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(1);
  const [role, setRole] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [age, setAge] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showTitle, setShowTitle] = useState('');
  const [podcastDescription, setPodcastDescription] = useState('');
  const [selectedInterests, setSelectedInterests] = useState([]);
  const [interestOptions, setInterestOptions] = useState([]);
  const [promoCode, setPromoCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingSocial, setPendingSocial] = useState(null);
  const [loadingPendingSocial, setLoadingPendingSocial] = useState(false);
  const socialMode = searchParams.get('social') === '1';

  useEffect(() => {
    axios.get(`${API}/interests/options`).then((res) => {
      setInterestOptions(res.data.interests || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const incomingPromo = searchParams.get('promo') || searchParams.get('code') || searchParams.get('coupon');
    if (incomingPromo) {
      setPromoCode(incomingPromo.toUpperCase().replace(/[^A-Z0-9]/g, ''));
    }
  }, [searchParams]);

  useEffect(() => {
    let active = true;
    if (!socialMode) {
      setPendingSocial(null);
      setLoadingPendingSocial(false);
      return undefined;
    }

    setLoadingPendingSocial(true);
    getPendingSocialSignup().then((result) => {
      if (!active) return;
      if (!result.success) {
        setError(result.error || 'Your social sign-up session expired. Please try again.');
        setPendingSocial(null);
        return;
      }

      const social = result.data;
      setPendingSocial(social);
      setName((prev) => prev || social.name || '');
      setEmail(social.email || '');
      if (social.role_hint) {
        setRole((prev) => prev || social.role_hint);
      }
    }).finally(() => {
      if (active) setLoadingPendingSocial(false);
    });

    return () => {
      active = false;
    };
  }, [socialMode, getPendingSocialSignup]);

  const toggleInterest = (interest) => {
    setSelectedInterests((prev) => (
      prev.includes(interest) ? prev.filter((item) => item !== interest) : [...prev, interest]
    ));
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);
    const payload = {
      email,
      password,
      name,
      role,
      phone,
      age: role === 'user' && age !== '' ? Number(age) : null,
      interests: role === 'user' ? selectedInterests : [],
      podcast_description: role === 'podcaster' ? podcastDescription : '',
      show_title: role === 'podcaster' ? showTitle : '',
      promo_code: promoCode.trim(),
    };
    const result = socialMode
      ? await completeSocialSignup({
          name,
          role,
          phone,
          age: role === 'user' && age !== '' ? Number(age) : null,
          interests: role === 'user' ? selectedInterests : [],
          podcast_description: role === 'podcaster' ? podcastDescription : '',
          show_title: role === 'podcaster' ? showTitle : '',
          promo_code: promoCode.trim(),
        })
      : await register(payload);
    setLoading(false);
    if (result.success) {
      navigate(role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard');
    } else {
      setError(result.error);
    }
  };

  const progress = `${(step / 3) * 100}%`;
  const socialProviderLabel = pendingSocial?.provider ? `${pendingSocial.provider[0].toUpperCase()}${pendingSocial.provider.slice(1)}` : 'Social';

  const handleCancelSocial = async () => {
    await cancelPendingSocialSignup();
    navigate('/register', { replace: true });
  };

  if (socialMode && loadingPendingSocial) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (socialMode && !pendingSocial) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center p-6">
        <div className="w-full max-w-md rounded-3xl border border-[#27272A] bg-[#141417] p-8 text-center">
          <h1 className="font-['Outfit'] text-3xl font-bold text-white mb-3">Social sign-up expired</h1>
          <p className="text-[#8A8A93] mb-6">{error || 'Start the Google or Apple sign-up flow again to continue.'}</p>
          <button
            type="button"
            onClick={() => navigate('/register', { replace: true })}
            className="w-full bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3 transition-colors"
          >
            Back to sign up
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0B] flex" data-testid="register-page">
      <div className="hidden lg:block lg:w-1/2 relative">
        <img
          src="https://images.unsplash.com/photo-1617994452722-4145e196248b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTB8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMHNvdW5kJTIwd2F2ZSUyMGRhcmt8ZW58MHx8fHwxNzc0NzgxMzc0fDA&ixlib=rb-4.1.0&q=85"
          alt="Sound wave"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-[#0A0A0B]" />
      </div>

      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-md">
          <Link to="/" className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 rounded-xl bg-[#F5A623] flex items-center justify-center">
              <Microphone weight="bold" className="text-[#0A0A0B] w-5 h-5" />
            </div>
            <span className="font-['Outfit'] text-xl font-bold text-white tracking-tight">Audioraq</span>
          </Link>

          <div className="mb-8">
            <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-3">
              <span>Setup progress</span>
              <span>Step {step} of 3</span>
            </div>
            <div className="h-2 rounded-full bg-[#141417] border border-[#27272A] overflow-hidden">
              <div className="h-full bg-[#F5A623] transition-all duration-300" style={{ width: progress }} />
            </div>
          </div>

          {error && (
            <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg px-4 py-3 mb-6 text-sm text-[#EF4444]" data-testid="register-error">
              {error}
            </div>
          )}

          {step === 1 && (
            <div className="opacity-0 animate-fade-in-up">
              <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-2">
                {socialMode ? `Finish with ${socialProviderLabel}` : 'Join Audioraq'}
              </h1>
              <p className="text-[#8A8A93] mb-6">
                {socialMode
                  ? 'Your provider verified who you are. Now choose the Audioraq experience you want.'
                  : 'Choose the experience you want first. You can evolve from there later.'}
              </p>

              <div className="mb-8">
                {socialMode ? (
                  <div className="rounded-2xl border border-[#27272A] bg-[#141417] px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Connected account</p>
                    <p className="text-white font-medium">{pendingSocial?.email || email}</p>
                    <p className="text-sm text-[#8A8A93] mt-1">Signed in with {socialProviderLabel}. We only need your role-specific setup details now.</p>
                    <button
                      type="button"
                      onClick={handleCancelSocial}
                      className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors mt-3"
                    >
                      Start over
                    </button>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-[#27272A] bg-[#141417] px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Email account</p>
                    <p className="text-sm text-[#C7C7D1]">
                      Sign up with email to keep Audioraq onboarding simple and predictable.
                    </p>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 mb-8">
                <button
                  onClick={() => { setRole('user'); setStep(2); }}
                  className={`p-6 rounded-xl border transition-all text-left ${role === 'user' ? 'border-[#F5A623] bg-[#F5A623]/10' : 'border-[#27272A] bg-[#141417] hover:border-[#8A8A93]'}`}
                  data-testid="role-user-btn"
                >
                  <User weight="duotone" className="w-8 h-8 text-[#F5A623] mb-4" />
                  <h3 className="font-['Outfit'] text-lg font-medium text-white">Listener</h3>
                  <p className="text-xs text-[#8A8A93] mt-1">Build a home feed around your interests</p>
                </button>
                <button
                  onClick={() => { setRole('podcaster'); setStep(2); }}
                  className={`p-6 rounded-xl border transition-all text-left ${role === 'podcaster' ? 'border-[#F5A623] bg-[#F5A623]/10' : 'border-[#27272A] bg-[#141417] hover:border-[#8A8A93]'}`}
                  data-testid="role-podcaster-btn"
                >
                  <MicrophoneStage weight="duotone" className="w-8 h-8 text-[#F5A623] mb-4" />
                  <h3 className="font-['Outfit'] text-lg font-medium text-white">Podcaster</h3>
                  <p className="text-xs text-[#8A8A93] mt-1">Create a show and publish episodes</p>
                </button>
              </div>

              <p className="text-center text-sm text-[#8A8A93]">
                Already have an account?{' '}
                <Link to="/login" className="text-[#F5A623] hover:text-[#F7B84B] font-medium transition-colors" data-testid="register-login-link">
                  Sign In
                </Link>
              </p>
            </div>
          )}

          {step === 2 && (
            <div className="opacity-0 animate-fade-in-up">
              <h1 className="font-['Outfit'] text-3xl tracking-tight font-bold text-white mb-2">
                {socialMode
                  ? `Complete your ${socialProviderLabel} account`
                  : role === 'podcaster' ? 'Create your account' : 'Create your listener account'}
              </h1>
              <p className="text-[#8A8A93] mb-8">
                {socialMode
                  ? 'We already have your verified identity. Add the last product details and you are in.'
                  : 'This gets you through the door. We’ll shape the experience in the next step.'}
              </p>

              <div className="mb-6">
                {socialMode ? (
                  <div className="rounded-2xl border border-[#27272A] bg-[#141417] px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Using {socialProviderLabel}</p>
                    <p className="text-white font-medium">{pendingSocial?.email || email}</p>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-[#27272A] bg-[#141417] px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Secure sign up</p>
                    <p className="text-sm text-[#C7C7D1]">Use your email and password. Social sign-up has been removed from this flow.</p>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                    placeholder="Your full name"
                    required
                    data-testid="register-name-input"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={`w-full border rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none ${
                      socialMode
                        ? 'bg-[#141417] border-[#1F1F24] text-[#AFAFB7]'
                        : 'bg-[#0A0A0B] border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623]'
                    }`}
                    placeholder="you@example.com"
                    required
                    readOnly={socialMode}
                    data-testid="register-email-input"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Phone</label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                    placeholder="+1 (555) 000-0000"
                    data-testid="register-phone-input"
                  />
                </div>
                {role === 'user' && (
                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Age</label>
                    <input
                      type="number"
                      min="0"
                      max="120"
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                      className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                      placeholder="Your age"
                      data-testid="register-age-input"
                    />
                    <p className="text-xs text-[#8A8A93] mt-2">We use this to keep mature episodes out of underage listener accounts.</p>
                  </div>
                )}
                {!socialMode && (
                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Password</label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none pr-12"
                        placeholder="Create a password"
                        required
                        data-testid="register-password-input"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8A8A93] hover:text-white transition-colors"
                      >
                        {showPassword ? <EyeSlash size={20} /> : <Eye size={20} />}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-8">
                <button
                  onClick={() => setStep(1)}
                  className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                  data-testid="register-back-btn"
                >
                  Back
                </button>
                <button
                  onClick={() => {
                    if (!name || !email || (!socialMode && !password) || (role === 'user' && !age)) {
                      setError('Please fill all required fields');
                      return;
                    }
                    setError('');
                    setStep(3);
                  }}
                  className="flex-1 bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3 transition-colors"
                  data-testid="register-next-btn"
                >
                  Continue
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="opacity-0 animate-fade-in-up">
              {role === 'user' ? (
                <>
                  <h1 className="font-['Outfit'] text-3xl tracking-tight font-bold text-white mb-2">Shape your home feed</h1>
                  <p className="text-[#8A8A93] mb-6">Choose a few interests now. You can fine-tune them later in settings.</p>
                  <button
                    type="button"
                    onClick={() => setSelectedInterests(starterInterests)}
                    className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors mb-4"
                  >
                    Use starter picks
                  </button>
                  <div className="flex flex-wrap gap-2 mb-8 max-h-[300px] overflow-y-auto">
                    {interestOptions.map((interest) => (
                      <button
                        key={interest}
                        onClick={() => toggleInterest(interest)}
                        className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                          selectedInterests.includes(interest)
                            ? 'bg-[#F5A623] text-[#0A0A0B]'
                            : 'bg-[#141417] border border-[#27272A] text-[#8A8A93] hover:border-[#F5A623] hover:text-white'
                        }`}
                        data-testid={`interest-${interest.replace(/\s/g, '-')}`}
                      >
                        {interest}
                      </button>
                    ))}
                  </div>
                  <p className="text-sm text-[#8A8A93] mb-4">{selectedInterests.length} selected</p>
                </>
              ) : (
                <>
                  <h1 className="font-['Outfit'] text-3xl tracking-tight font-bold text-white mb-2">Create your show</h1>
                  <p className="text-[#8A8A93] mb-6">Set up the show identity listeners will discover first. You can edit it later.</p>
                  <div className="space-y-4">
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Title</label>
                      <input
                        type="text"
                        value={showTitle}
                        onChange={(e) => setShowTitle(e.target.value)}
                        className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                        placeholder="The name of your podcast"
                        data-testid="register-show-title"
                      />
                    </div>
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Description</label>
                      <textarea
                        value={podcastDescription}
                        onChange={(e) => setPodcastDescription(e.target.value)}
                        className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none min-h-[160px] resize-none"
                        placeholder="What is the show about, who is it for, and what kind of episodes will you publish?"
                        data-testid="register-podcast-description"
                      />
                    </div>
                  </div>
                </>
              )}

              <div className="mt-6 rounded-2xl border border-[#F5A623]/30 bg-[#F5A623]/10 px-4 py-4">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-1">Product Hunt promo</p>
                    <p className="text-sm text-[#EDE6D2]">Use <span className="font-semibold text-white">PODCASTAI</span> for a free AI podcast audit for two months.</p>
                  </div>
                  <span className="hidden sm:inline-flex rounded-full bg-[#0A0A0B] border border-[#F5A623]/30 px-3 py-1 text-xs font-semibold text-[#F5A623]">
                    Launch offer
                  </span>
                </div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Promo code</label>
                <input
                  type="text"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                  placeholder="PODCASTAI"
                  data-testid="register-promo-code"
                />
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setStep(2)}
                  className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                  data-testid="register-back-step3-btn"
                >
                  Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex-1 bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3 transition-colors disabled:opacity-50"
                  data-testid="register-submit-btn"
                >
                  {loading ? (socialMode ? 'Finishing account...' : 'Creating account...') : (socialMode ? `Finish with ${socialProviderLabel}` : 'Create Account')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
