import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Microphone, Eye, EyeSlash, User, MicrophoneStage } from '@phosphor-icons/react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1=role, 2=details, 3=interests/description
  const [role, setRole] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [podcastDescription, setPodcastDescription] = useState('');
  const [selectedInterests, setSelectedInterests] = useState([]);
  const [interestOptions, setInterestOptions] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    axios.get(`${API}/interests/options`).then(res => {
      setInterestOptions(res.data.interests || []);
    }).catch(() => {});
  }, []);

  const toggleInterest = (interest) => {
    setSelectedInterests(prev =>
      prev.includes(interest) ? prev.filter(i => i !== interest) : [...prev, interest]
    );
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);
    const result = await register({
      email, password, name, role, phone,
      interests: role === 'user' ? selectedInterests : [],
      podcast_description: role === 'podcaster' ? podcastDescription : ''
    });
    setLoading(false);
    if (result.success) {
      navigate(role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard');
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] flex" data-testid="register-page">
      {/* Left - Image */}
      <div className="hidden lg:block lg:w-1/2 relative">
        <img
          src="https://images.unsplash.com/photo-1617994452722-4145e196248b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTB8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMHNvdW5kJTIwd2F2ZSUyMGRhcmt8ZW58MHx8fHwxNzc0NzgxMzc0fDA&ixlib=rb-4.1.0&q=85"
          alt="Sound wave"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-[#0A0A0B]" />
      </div>

      {/* Right - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-md">
          <Link to="/" className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 rounded-xl bg-[#F5A623] flex items-center justify-center">
              <Microphone weight="bold" className="text-[#0A0A0B] w-5 h-5" />
            </div>
            <span className="font-['Outfit'] text-xl font-bold text-white tracking-tight">Podlyzer</span>
          </Link>

          {error && (
            <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg px-4 py-3 mb-6 text-sm text-[#EF4444]" data-testid="register-error">
              {error}
            </div>
          )}

          {/* Step 1: Role Selection */}
          {step === 1 && (
            <div className="opacity-0 animate-fade-in-up">
              <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-2">Join Podlyzer</h1>
              <p className="text-[#8A8A93] mb-8">Are you here to listen or create?</p>

              <div className="grid grid-cols-2 gap-4 mb-8">
                <button
                  onClick={() => { setRole('user'); setStep(2); }}
                  className={`p-6 rounded-xl border transition-all text-left ${role === 'user' ? 'border-[#F5A623] bg-[#F5A623]/10' : 'border-[#27272A] bg-[#141417] hover:border-[#8A8A93]'}`}
                  data-testid="role-user-btn"
                >
                  <User weight="duotone" className="w-8 h-8 text-[#F5A623] mb-4" />
                  <h3 className="font-['Outfit'] text-lg font-medium text-white">Listener</h3>
                  <p className="text-xs text-[#8A8A93] mt-1">Discover and play podcasts</p>
                </button>
                <button
                  onClick={() => { setRole('podcaster'); setStep(2); }}
                  className={`p-6 rounded-xl border transition-all text-left ${role === 'podcaster' ? 'border-[#F5A623] bg-[#F5A623]/10' : 'border-[#27272A] bg-[#141417] hover:border-[#8A8A93]'}`}
                  data-testid="role-podcaster-btn"
                >
                  <MicrophoneStage weight="duotone" className="w-8 h-8 text-[#F5A623] mb-4" />
                  <h3 className="font-['Outfit'] text-lg font-medium text-white">Podcaster</h3>
                  <p className="text-xs text-[#8A8A93] mt-1">Upload and share your content</p>
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

          {/* Step 2: Account Details */}
          {step === 2 && (
            <div className="opacity-0 animate-fade-in-up">
              <h1 className="font-['Outfit'] text-3xl tracking-tight font-bold text-white mb-2">
                {role === 'podcaster' ? 'Create your podcaster account' : 'Create your account'}
              </h1>
              <p className="text-[#8A8A93] mb-8">Fill in your details to get started</p>

              <div className="space-y-4">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Name</label>
                  <input
                    type="text" value={name} onChange={e => setName(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                    placeholder="Your full name" required data-testid="register-name-input"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Email</label>
                  <input
                    type="email" value={email} onChange={e => setEmail(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                    placeholder="you@example.com" required data-testid="register-email-input"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Phone</label>
                  <input
                    type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                    placeholder="+1 (555) 000-0000" data-testid="register-phone-input"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Password</label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                      className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none pr-12"
                      placeholder="Create a password" required data-testid="register-password-input"
                    />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8A8A93] hover:text-white transition-colors">
                      {showPassword ? <EyeSlash size={20} /> : <Eye size={20} />}
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex gap-3 mt-8">
                <button onClick={() => setStep(1)}
                  className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                  data-testid="register-back-btn">
                  Back
                </button>
                <button
                  onClick={() => {
                    if (!name || !email || !password) { setError('Please fill all required fields'); return; }
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

          {/* Step 3: Interests or Podcast Description */}
          {step === 3 && (
            <div className="opacity-0 animate-fade-in-up">
              {role === 'user' ? (
                <>
                  <h1 className="font-['Outfit'] text-3xl tracking-tight font-bold text-white mb-2">What interests you?</h1>
                  <p className="text-[#8A8A93] mb-6">Select topics to personalize your recommendations</p>
                  <div className="flex flex-wrap gap-2 mb-8 max-h-[300px] overflow-y-auto">
                    {interestOptions.map(interest => (
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
                  {selectedInterests.length > 0 && (
                    <p className="text-sm text-[#8A8A93] mb-4">{selectedInterests.length} selected</p>
                  )}
                </>
              ) : (
                <>
                  <h1 className="font-['Outfit'] text-3xl tracking-tight font-bold text-white mb-2">Tell us about your podcast</h1>
                  <p className="text-[#8A8A93] mb-6">Describe what your podcast is about. We'll extract keywords to help listeners find you.</p>
                  <textarea
                    value={podcastDescription}
                    onChange={e => setPodcastDescription(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none min-h-[160px] resize-none"
                    placeholder="e.g., A weekly show exploring the latest in AI, machine learning, and how technology shapes our future..."
                    data-testid="register-podcast-description"
                  />
                </>
              )}

              <div className="flex gap-3 mt-6">
                <button onClick={() => setStep(2)}
                  className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                  data-testid="register-back-step3-btn">
                  Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex-1 bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3 transition-colors disabled:opacity-50"
                  data-testid="register-submit-btn"
                >
                  {loading ? 'Creating account...' : 'Create Account'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
