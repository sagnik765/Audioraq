import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';

const starterInterests = ['technology', 'business', 'self improvement'];

function formatDateTime(value) {
  if (!value) return 'Not set';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

const creatorGrowthPlays = [
  {
    title: 'Turn every episode into one clear promise',
    body: 'Before publishing, write the listener outcome in one sentence. This improves titles, thumbnails, show notes, and social posts.',
  },
  {
    title: 'Use proof-of-work instead of hype',
    body: 'Share one episode page, one quality signal, and one creator lesson. This makes Audioraq feel credible without fake urgency.',
  },
  {
    title: 'Ask for feedback at the right moment',
    body: 'After a listener saves, rates, or finishes an episode, ask what would make the next episode more useful.',
  },
];

const listenerBenefits = [
  'Personal home feed shaped by interests, saved episodes, and followed shows.',
  'Save for later, queue episodes, and resume unfinished listens.',
  'Sharper recommendations with quality, trust, likes, ratings, and view signals.',
];

export default function SettingsPage() {
  const { user, checkAuth, updateInterests } = useAuth();
  const { currentPodcast } = usePlayer();
  const canManageShowIdentity = user?.role === 'podcaster';
  const canSeeCreatorTools = user?.role === 'podcaster' || user?.role === 'admin';

  const [interestOptions, setInterestOptions] = useState([]);
  const [selectedInterests, setSelectedInterests] = useState([]);
  const [shows, setShows] = useState([]);
  const [activeShowId, setActiveShowId] = useState('');
  const [showTitle, setShowTitle] = useState('');
  const [showDescription, setShowDescription] = useState('');
  const [showCategory, setShowCategory] = useState('general');
  const [saving, setSaving] = useState(false);
  const [promoCode, setPromoCode] = useState('PODCASTAI');
  const [promoSubmitting, setPromoSubmitting] = useState(false);

  const auditPromo = user?.promo_entitlements?.ai_podcast_audit || {};

  useEffect(() => {
    setSelectedInterests(user?.interests || []);
  }, [user]);

  useEffect(() => {
    axios.get(`${API}/interests/options`).then((res) => {
      setInterestOptions(res.data.interests || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!canManageShowIdentity) return;
    axios.get(`${API}/shows/my`, { withCredentials: true }).then((res) => {
      const nextShows = res.data.shows || [];
      setShows(nextShows);
      if (nextShows[0]) {
        setActiveShowId(nextShows[0].id);
        setShowTitle(nextShows[0].title || '');
        setShowDescription(nextShows[0].description || '');
        setShowCategory(nextShows[0].category || 'general');
      }
    }).catch(() => {});
  }, [canManageShowIdentity, user]);

  useEffect(() => {
    const activeShow = shows.find((show) => show.id === activeShowId);
    if (!activeShow) return;
    setShowTitle(activeShow.title || '');
    setShowDescription(activeShow.description || '');
    setShowCategory(activeShow.category || 'general');
  }, [activeShowId, shows]);

  const toggleInterest = (interest) => {
    setSelectedInterests((prev) => (
      prev.includes(interest) ? prev.filter((item) => item !== interest) : [...prev, interest]
    ));
  };

  const handleSaveInterests = async () => {
    setSaving(true);
    const result = await updateInterests(selectedInterests);
    setSaving(false);
    if (result.success) {
      toast.success('Interests updated');
      checkAuth();
    } else {
      toast.error(result.error || 'Failed to update interests');
    }
  };

  const handleSaveShow = async (event) => {
    event.preventDefault();
    if (!activeShowId) {
      toast.error('Create a show first from Creator Studio');
      return;
    }
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('title', showTitle);
      formData.append('description', showDescription);
      formData.append('category', showCategory);
      await axios.put(`${API}/shows/${activeShowId}`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Show settings updated');
      checkAuth();
      const refreshed = await axios.get(`${API}/shows/my`, { withCredentials: true });
      setShows(refreshed.data.shows || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update show');
    } finally {
      setSaving(false);
    }
  };

  const handleRedeemPromo = async (event) => {
    event.preventDefault();
    if (!promoCode.trim()) {
      toast.error('Enter a promo code first');
      return;
    }
    setPromoSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/promos/redeem`, { code: promoCode.trim() }, { withCredentials: true });
      toast.success(data.message || 'Promo code applied');
      checkAuth();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not apply promo code');
    } finally {
      setPromoSubmitting(false);
    }
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="settings-page">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 md:px-8 lg:px-12 py-10 space-y-8">
        <div>
          <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-1">Settings</h1>
          <p className="text-[#8A8A93]">
            {canSeeCreatorTools
              ? 'Tune the parts of Audioraq that improve creator activation, trust, and repeat listening.'
              : 'Tune your interests so Audioraq becomes a sharper listening home.'}
          </p>
        </div>

        <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-6 md:p-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Launch Promo</p>
              <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Free AI podcast audit</h2>
              <p className="text-sm text-[#8A8A93] max-w-2xl">
                Product Hunt users can use <span className="text-white font-semibold">PODCASTAI</span> to unlock two months of AI podcast audit access for creator strategy, positioning, episode ideas, and quality guidance.
              </p>
              {auditPromo.active ? (
                <div className="mt-4 inline-flex flex-wrap gap-2 rounded-2xl border border-[#22C55E]/30 bg-[#22C55E]/10 px-4 py-3 text-sm text-[#BBF7D0]">
                  <span className="font-semibold">Active</span>
                  <span>Expires {formatDateTime(auditPromo.expires_at)}</span>
                  <span>{auditPromo.days_remaining || 0} days remaining</span>
                </div>
              ) : (
                <p className="text-xs text-[#71717A] mt-3">Activation is instant and does not slow down podcast creation.</p>
              )}
            </div>

            <form onSubmit={handleRedeemPromo} className="w-full lg:max-w-sm">
              <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Promo code</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                  className="min-w-0 flex-1 bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none"
                  placeholder="PODCASTAI"
                  data-testid="settings-promo-code"
                />
                <button
                  type="submit"
                  disabled={promoSubmitting || auditPromo.active}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors disabled:opacity-50"
                  data-testid="settings-promo-submit"
                >
                  {auditPromo.active ? 'Applied' : promoSubmitting ? 'Applying...' : 'Apply'}
                </button>
              </div>
            </form>
          </div>
        </section>

        {canSeeCreatorTools && (
          <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-7">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Manual Marketing System</p>
                <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Grow without connecting social accounts</h2>
                <p className="text-sm text-[#8A8A93] max-w-3xl">
                  For cybersecurity reasons, Audioraq now keeps social publishing manual. The platform should help you decide what to say and what proof to show, while you stay in control of posting from LinkedIn or Instagram.
                </p>
              </div>
              <Link
                to="/dashboard/podcaster"
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors text-center"
              >
                Open Creator Studio
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {creatorGrowthPlays.map((play) => (
                <div key={play.title} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                  <h3 className="font-['Outfit'] text-lg font-semibold text-white mb-2">{play.title}</h3>
                  <p className="text-sm text-[#8A8A93] leading-relaxed">{play.body}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {canManageShowIdentity && (
          <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="mb-7">
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Show Identity</p>
              <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Make the show easy to trust before playback</h2>
              <p className="text-sm text-[#8A8A93]">
                Strong titles, categories, and descriptions improve discovery, listener confidence, and the quality of AI-generated episode strategy.
              </p>
            </div>

            <div className="flex flex-wrap gap-3 mb-8">
              {shows.map((show) => (
                <button
                  key={show.id}
                  type="button"
                  onClick={() => setActiveShowId(show.id)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    activeShowId === show.id
                      ? 'bg-[#F5A623] text-[#0A0A0B]'
                      : 'bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93] hover:text-white hover:border-[#F5A623]'
                  }`}
                >
                  {show.title}
                </button>
              ))}
              {!shows.length && (
                <Link to="/dashboard/podcaster" className="text-sm text-[#F5A623] hover:text-[#F7B84B]">
                  Create your first show in Creator Studio
                </Link>
              )}
            </div>

            {shows.length > 0 && (
              <form onSubmit={handleSaveShow} className="space-y-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Title</label>
                  <input
                    type="text"
                    value={showTitle}
                    onChange={(e) => setShowTitle(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Category</label>
                  <input
                    type="text"
                    value={showCategory}
                    onChange={(e) => setShowCategory(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Description</label>
                  <textarea
                    value={showDescription}
                    onChange={(e) => setShowDescription(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none min-h-[160px] resize-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Show Settings'}
                </button>
              </form>
            )}
          </section>
        )}

        {!canSeeCreatorTools && (
          <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="mb-6">
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Why Sign In Matters</p>
              <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Make Audioraq remember what you care about</h2>
              <p className="text-sm text-[#8A8A93]">Public browsing is open, but the product gets better when it can learn from your listening choices.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {listenerBenefits.map((benefit) => (
                <div key={benefit} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                  <p className="text-sm text-[#C7C7D1] leading-relaxed">{benefit}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
          <div className="flex items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-1">Your interests</h2>
              <p className="text-sm text-[#8A8A93]">These shape recommendations, topic filters, and the home feed.</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedInterests(starterInterests)}
              className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors"
            >
              Use starter picks
            </button>
          </div>

          <div className="flex flex-wrap gap-2 mb-4">
            {interestOptions.map((interest) => (
              <button
                key={interest}
                type="button"
                onClick={() => toggleInterest(interest)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  selectedInterests.includes(interest)
                    ? 'bg-[#F5A623] text-[#0A0A0B]'
                    : 'bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93] hover:text-white hover:border-[#F5A623]'
                }`}
              >
                {interest}
              </button>
            ))}
          </div>
          <p className="text-sm text-[#8A8A93] mb-6">{selectedInterests.length} selected</p>
          <button
            type="button"
            onClick={handleSaveInterests}
            disabled={saving}
            className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Interests'}
          </button>
        </section>
      </main>
    </div>
  );
}
