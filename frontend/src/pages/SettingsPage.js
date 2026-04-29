import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';

const starterInterests = ['technology', 'business', 'self improvement'];

const emptyOverview = {
  connected_accounts: 0,
  published_posts: 0,
  queued_posts: 0,
  failed_posts: 0,
  recent_success_rate: 0,
};

function formatDateTime(value) {
  if (!value) return 'Not set';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function providerLabel(provider) {
  return provider === 'linkedin' ? 'LinkedIn' : 'Instagram';
}

export default function SettingsPage() {
  const { user, checkAuth, updateInterests } = useAuth();
  const { currentPodcast } = usePlayer();
  const canManagePublishing = user?.role === 'podcaster' || user?.role === 'admin';
  const canManageShowIdentity = user?.role === 'podcaster';

  const [interestOptions, setInterestOptions] = useState([]);
  const [selectedInterests, setSelectedInterests] = useState([]);
  const [shows, setShows] = useState([]);
  const [activeShowId, setActiveShowId] = useState('');
  const [showTitle, setShowTitle] = useState('');
  const [showDescription, setShowDescription] = useState('');
  const [showCategory, setShowCategory] = useState('general');
  const [saving, setSaving] = useState(false);

  const [socialLoading, setSocialLoading] = useState(false);
  const [socialSubmitting, setSocialSubmitting] = useState(false);
  const [socialProviders, setSocialProviders] = useState({});
  const [socialAccounts, setSocialAccounts] = useState([]);
  const [socialPosts, setSocialPosts] = useState([]);
  const [socialAnalytics, setSocialAnalytics] = useState({ overview: emptyOverview, by_provider: {}, recent_posts: [] });

  const [manualProvider, setManualProvider] = useState('linkedin');
  const [manualAccessToken, setManualAccessToken] = useState('');
  const [manualRefreshToken, setManualRefreshToken] = useState('');
  const [manualOrganizationId, setManualOrganizationId] = useState('');
  const [manualOrganizationName, setManualOrganizationName] = useState('');
  const [manualPageId, setManualPageId] = useState('');
  const [manualInstagramAccountId, setManualInstagramAccountId] = useState('');
  const [manualAccountName, setManualAccountName] = useState('');

  const [postProvider, setPostProvider] = useState('linkedin');
  const [postAccountId, setPostAccountId] = useState('');
  const [postHeadline, setPostHeadline] = useState('');
  const [postCaption, setPostCaption] = useState('');
  const [postCta, setPostCta] = useState('Follow Audioraq for more AI-first podcast workflows.');
  const [postLinkUrl, setPostLinkUrl] = useState('https://www.audioraq.com');
  const [postHashtags, setPostHashtags] = useState('#audioraq #podcasting #aiforcreators');
  const [postScheduledAt, setPostScheduledAt] = useState('');
  const [postAssetUrl, setPostAssetUrl] = useState('');
  const [useGeneratedCard, setUseGeneratedCard] = useState(true);

  const availableAccounts = useMemo(
    () => socialAccounts.filter((account) => account.provider === postProvider),
    [socialAccounts, postProvider],
  );
  const manualTokenSupported = useMemo(
    () => Object.values(socialProviders || {}).some((details) => details?.manual_token_supported),
    [socialProviders],
  );

  const loadSocialPublishing = useCallback(async () => {
    if (!canManagePublishing) return;
    setSocialLoading(true);
    try {
      const [providersRes, accountsRes, analyticsRes, postsRes] = await Promise.all([
        axios.get(`${API}/social/providers`, { withCredentials: true }),
        axios.get(`${API}/social/accounts`, { withCredentials: true }),
        axios.get(`${API}/social/analytics`, { withCredentials: true }),
        axios.get(`${API}/social/posts`, { withCredentials: true }),
      ]);
      setSocialProviders(providersRes.data || {});
      setSocialAccounts(accountsRes.data.accounts || []);
      setSocialAnalytics(analyticsRes.data || { overview: emptyOverview, by_provider: {}, recent_posts: [] });
      setSocialPosts(postsRes.data.posts || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not load social publishing settings');
    } finally {
      setSocialLoading(false);
    }
  }, [canManagePublishing]);

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

  useEffect(() => {
    if (!canManagePublishing) return;
    loadSocialPublishing();
  }, [canManagePublishing, loadSocialPublishing]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const success = params.get('social_success');
    const error = params.get('social_error');
    if (success) toast.success(success);
    if (error) toast.error(error);
    if (success || error) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (!availableAccounts.length) {
      setPostAccountId('');
      return;
    }
    if (!availableAccounts.some((account) => account.id === postAccountId)) {
      setPostAccountId(availableAccounts[0].id);
    }
  }, [availableAccounts, postAccountId]);

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

  const handleSaveShow = async (e) => {
    e.preventDefault();
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

  const handleOAuthConnect = (provider) => {
    const returnOrigin = encodeURIComponent(window.location.origin);
    window.location.href = `${API}/social/oauth/${provider}/start?return_origin=${returnOrigin}`;
  };

  const handleManualConnect = async (event) => {
    event.preventDefault();
    if (!manualAccessToken.trim()) {
      toast.error('Paste an access token first');
      return;
    }
    setSocialSubmitting(true);
    try {
      await axios.post(`${API}/social/connect/manual`, {
        provider: manualProvider,
        access_token: manualAccessToken.trim(),
        refresh_token: manualRefreshToken.trim(),
        organization_id: manualOrganizationId.trim(),
        organization_name: manualOrganizationName.trim(),
        page_id: manualPageId.trim(),
        instagram_account_id: manualInstagramAccountId.trim(),
        account_name: manualAccountName.trim(),
      }, { withCredentials: true });
      toast.success(`${providerLabel(manualProvider)} connected`);
      setManualAccessToken('');
      setManualRefreshToken('');
      setManualOrganizationId('');
      setManualOrganizationName('');
      setManualPageId('');
      setManualInstagramAccountId('');
      setManualAccountName('');
      loadSocialPublishing();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Manual connect failed');
    } finally {
      setSocialSubmitting(false);
    }
  };

  const handleDisconnectAccount = async (accountId) => {
    setSocialSubmitting(true);
    try {
      await axios.delete(`${API}/social/accounts/${accountId}`, { withCredentials: true });
      toast.success('Connected social account removed');
      loadSocialPublishing();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not remove connected social account');
    } finally {
      setSocialSubmitting(false);
    }
  };

  const resetPostComposer = () => {
    setPostHeadline('');
    setPostCaption('');
    setPostScheduledAt('');
    setPostAssetUrl('');
    setUseGeneratedCard(true);
  };

  const handleCreatePost = async (mode) => {
    if (!postAccountId) {
      toast.error('Connect a social account first');
      return;
    }
    if (!postHeadline.trim()) {
      toast.error('Add a headline first');
      return;
    }

    setSocialSubmitting(true);
    try {
      await axios.post(`${API}/social/posts`, {
        provider: postProvider,
        social_account_id: postAccountId,
        headline: postHeadline.trim(),
        caption: postCaption.trim(),
        cta: postCta.trim(),
        link_url: postLinkUrl.trim(),
        hashtags: postHashtags.split(/[\s,]+/).filter(Boolean),
        scheduled_at: postScheduledAt ? new Date(postScheduledAt).toISOString() : '',
        asset_url: postAssetUrl.trim(),
        use_generated_card: useGeneratedCard,
        status: mode === 'queue' ? 'queued' : 'draft',
        publish_now: mode === 'publish',
        source: 'audioraq_marketing_agent',
      }, { withCredentials: true });
      toast.success(
        mode === 'publish'
          ? `${providerLabel(postProvider)} post published`
          : mode === 'queue'
            ? 'Post queued for publishing'
            : 'Social draft saved',
      );
      resetPostComposer();
      loadSocialPublishing();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save social post');
    } finally {
      setSocialSubmitting(false);
    }
  };

  const handlePublishQueued = async () => {
    setSocialSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/social/queue/process`, {}, { withCredentials: true });
      toast.success(`Processed ${data.processed_count || 0} queued social posts`);
      loadSocialPublishing();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not process the publish queue');
    } finally {
      setSocialSubmitting(false);
    }
  };

  const handlePublishOne = async (postId) => {
    setSocialSubmitting(true);
    try {
      await axios.post(`${API}/social/posts/${postId}/publish`, {}, { withCredentials: true });
      toast.success('Post published');
      loadSocialPublishing();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not publish post');
    } finally {
      setSocialSubmitting(false);
    }
  };

  const handleDeletePost = async (postId) => {
    setSocialSubmitting(true);
    try {
      await axios.delete(`${API}/social/posts/${postId}`, { withCredentials: true });
      toast.success('Post removed');
      loadSocialPublishing();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not remove post');
    } finally {
      setSocialSubmitting(false);
    }
  };

  const providerCounts = useMemo(() => {
    const counts = {};
    socialAccounts.forEach((account) => {
      counts[account.provider] = (counts[account.provider] || 0) + 1;
    });
    return counts;
  }, [socialAccounts]);

  const overview = socialAnalytics?.overview || emptyOverview;

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="settings-page">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 md:px-8 lg:px-12 py-10 space-y-8">
        <div>
          <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-1">Settings</h1>
          <p className="text-[#8A8A93]">
            {canManagePublishing
              ? canManageShowIdentity
                ? 'Manage your show identity, publishing defaults, and Audioraq social distribution.'
                : 'Manage Audioraq social distribution and publishing operations.'
              : 'Refine your interests to improve the home feed.'}
          </p>
        </div>

        {canManagePublishing ? (
          <>
            {canManageShowIdentity && (
              <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
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
              </div>

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
              </div>
            )}

            <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 space-y-8">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Social Publishing</p>
                  <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Connect Audioraq to LinkedIn and Instagram</h2>
                  <p className="text-sm text-[#8A8A93] max-w-3xl">
                    This turns the marketing agent into a real publishing system. OAuth is the required production-safe path for connecting provider accounts.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handlePublishQueued}
                  disabled={socialSubmitting || socialLoading}
                  className="bg-[#0A0A0B] border border-[#F5A623] text-[#F5A623] hover:bg-[#F5A623] hover:text-[#0A0A0B] rounded-full px-5 py-3 font-semibold transition-colors disabled:opacity-50"
                >
                  Process Queue
                </button>
              </div>

              <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Connected</p>
                  <p className="text-3xl font-bold text-white">{overview.connected_accounts}</p>
                </div>
                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Published</p>
                  <p className="text-3xl font-bold text-white">{overview.published_posts}</p>
                </div>
                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Queued</p>
                  <p className="text-3xl font-bold text-white">{overview.queued_posts}</p>
                </div>
                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#8A8A93] mb-2">Success Rate</p>
                  <p className="text-3xl font-bold text-white">{overview.recent_success_rate}%</p>
                </div>
              </div>

              <div className="grid lg:grid-cols-2 gap-6">
                {['linkedin', 'instagram'].map((provider) => {
                  const details = socialProviders?.[provider] || {};
                  const connectedCount = providerCounts[provider] || 0;
                  return (
                    <div key={provider} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="font-['Outfit'] text-xl font-semibold text-white">{providerLabel(provider)}</h3>
                          <p className="text-sm text-[#8A8A93] mt-1">
                            {details.configured
                              ? 'OAuth connect is ready on this server.'
                              : 'OAuth is not configured yet on this server. Manual token connect still works.'}
                          </p>
                        </div>
                        <span className="text-xs uppercase tracking-[0.2em] text-[#F5A623]">
                          {connectedCount} connected
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => handleOAuthConnect(provider)}
                          disabled={!details.oauth_supported || socialSubmitting}
                          className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors disabled:opacity-40"
                        >
                          Connect with OAuth
                        </button>
                        {details.manual_token_supported && (
                          <button
                            type="button"
                            onClick={() => setManualProvider(provider)}
                            className="bg-[#151518] border border-[#27272A] text-white rounded-full px-5 py-3 font-semibold"
                          >
                            Use Manual Token
                          </button>
                        )}
                      </div>
                      <div className="text-xs text-[#8A8A93] leading-relaxed">
                        Required scopes:
                        <span className="text-white"> {(details.scopes || []).join(', ') || 'not available yet'}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
                {manualTokenSupported && (
                <form onSubmit={handleManualConnect} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Manual Token Connect</p>
                    <h3 className="font-['Outfit'] text-xl font-semibold text-white mb-1">Fallback when OAuth app setup is not ready</h3>
                    <p className="text-sm text-[#8A8A93]">Paste a valid provider token and the account identifiers if autodiscovery does not find the right profile.</p>
                  </div>

                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Provider</label>
                    <select
                      value={manualProvider}
                      onChange={(e) => setManualProvider(e.target.value)}
                      className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                    >
                      <option value="linkedin">LinkedIn</option>
                      <option value="instagram">Instagram</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Access Token</label>
                    <textarea
                      value={manualAccessToken}
                      onChange={(e) => setManualAccessToken(e.target.value)}
                      className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none min-h-[120px] resize-none"
                      placeholder="Paste a valid provider access token"
                    />
                  </div>

                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Refresh Token (Optional)</label>
                    <input
                      type="text"
                      value={manualRefreshToken}
                      onChange={(e) => setManualRefreshToken(e.target.value)}
                      className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                    />
                  </div>

                  {manualProvider === 'linkedin' ? (
                    <>
                      <div>
                        <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Organization ID (Optional)</label>
                        <input
                          type="text"
                          value={manualOrganizationId}
                          onChange={(e) => setManualOrganizationId(e.target.value)}
                          className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                          placeholder="Used if the token cannot auto-discover the Company Page"
                        />
                      </div>
                      <div>
                        <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Organization Name (Optional)</label>
                        <input
                          type="text"
                          value={manualOrganizationName}
                          onChange={(e) => setManualOrganizationName(e.target.value)}
                          className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Facebook Page ID (Optional)</label>
                        <input
                          type="text"
                          value={manualPageId}
                          onChange={(e) => setManualPageId(e.target.value)}
                          className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                        />
                      </div>
                      <div>
                        <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Instagram Account ID (Optional)</label>
                        <input
                          type="text"
                          value={manualInstagramAccountId}
                          onChange={(e) => setManualInstagramAccountId(e.target.value)}
                          className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                        />
                      </div>
                      <div>
                        <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Account Name (Optional)</label>
                        <input
                          type="text"
                          value={manualAccountName}
                          onChange={(e) => setManualAccountName(e.target.value)}
                          className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                        />
                      </div>
                    </>
                  )}

                  <button
                    type="submit"
                    disabled={socialSubmitting}
                    className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
                  >
                    {socialSubmitting ? 'Connecting...' : 'Connect Account'}
                  </button>
                </form>
                )}

                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Connected Accounts</p>
                    <h3 className="font-['Outfit'] text-xl font-semibold text-white">Current publishing targets</h3>
                  </div>
                  <div className="space-y-3">
                    {!socialAccounts.length && (
                      <div className="text-sm text-[#8A8A93] border border-dashed border-[#27272A] rounded-2xl p-4">
                        No social accounts are connected yet.
                      </div>
                    )}
                    {socialAccounts.map((account) => (
                      <div key={account.id} className="border border-[#27272A] rounded-2xl p-4 bg-[#141417]">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-white font-semibold">{account.account_name || account.username || account.account_id}</p>
                            <p className="text-sm text-[#8A8A93]">
                              {providerLabel(account.provider)}
                              {account.username ? ` @${account.username}` : ''}
                            </p>
                            <p className="text-xs text-[#71717A] mt-2">
                              Token preview: {account.token_preview || 'stored securely'}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDisconnectAccount(account.id)}
                            disabled={socialSubmitting}
                            className="text-sm text-[#F97316] hover:text-[#FB923C] transition-colors"
                          >
                            Disconnect
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-6">
                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Marketing Agent Composer</p>
                    <h3 className="font-['Outfit'] text-xl font-semibold text-white">Queue or publish directly from Audioraq</h3>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Provider</label>
                      <select
                        value={postProvider}
                        onChange={(e) => setPostProvider(e.target.value)}
                        className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      >
                        <option value="linkedin">LinkedIn</option>
                        <option value="instagram">Instagram</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Connected Account</label>
                      <select
                        value={postAccountId}
                        onChange={(e) => setPostAccountId(e.target.value)}
                        className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      >
                        {!availableAccounts.length && <option value="">Connect an account first</option>}
                        {availableAccounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.account_name || account.username || account.account_id}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Headline</label>
                    <input
                      type="text"
                      value={postHeadline}
                      onChange={(e) => setPostHeadline(e.target.value)}
                      className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      placeholder="What are we saying in this post?"
                    />
                  </div>

                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Caption</label>
                    <textarea
                      value={postCaption}
                      onChange={(e) => setPostCaption(e.target.value)}
                      className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none min-h-[160px] resize-none"
                      placeholder="Add the detailed body copy here"
                    />
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">CTA</label>
                      <input
                        type="text"
                        value={postCta}
                        onChange={(e) => setPostCta(e.target.value)}
                        className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Link URL</label>
                      <input
                        type="text"
                        value={postLinkUrl}
                        onChange={(e) => setPostLinkUrl(e.target.value)}
                        className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      />
                    </div>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Hashtags</label>
                      <input
                        type="text"
                        value={postHashtags}
                        onChange={(e) => setPostHashtags(e.target.value)}
                        className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Schedule (Optional)</label>
                      <input
                        type="datetime-local"
                        value={postScheduledAt}
                        onChange={(e) => setPostScheduledAt(e.target.value)}
                        className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Asset URL (Optional)</label>
                    <input
                      type="text"
                      value={postAssetUrl}
                      onChange={(e) => setPostAssetUrl(e.target.value)}
                      className="w-full bg-[#141417] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      placeholder="Instagram requires an image. Leave this blank to use an auto-generated Audioraq card."
                    />
                  </div>

                  <label className="flex items-center gap-3 text-sm text-[#D4D4D8]">
                    <input
                      type="checkbox"
                      checked={useGeneratedCard}
                      onChange={(e) => setUseGeneratedCard(e.target.checked)}
                    />
                    Generate an Audioraq social card automatically when needed
                  </label>

                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => handleCreatePost('publish')}
                      disabled={socialSubmitting}
                      className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors disabled:opacity-50"
                    >
                      Publish Now
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCreatePost('queue')}
                      disabled={socialSubmitting}
                      className="bg-[#0A0A0B] border border-[#F5A623] text-[#F5A623] hover:bg-[#F5A623] hover:text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors disabled:opacity-50"
                    >
                      Queue Post
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCreatePost('draft')}
                      disabled={socialSubmitting}
                      className="bg-[#151518] border border-[#27272A] text-white font-semibold rounded-full px-5 py-3 transition-colors disabled:opacity-50"
                    >
                      Save Draft
                    </button>
                  </div>
                </div>

                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Recent Posts</p>
                    <h3 className="font-['Outfit'] text-xl font-semibold text-white">Queue visibility for the marketing agent</h3>
                  </div>
                  <div className="space-y-3 max-h-[640px] overflow-y-auto pr-1">
                    {!socialPosts.length && (
                      <div className="text-sm text-[#8A8A93] border border-dashed border-[#27272A] rounded-2xl p-4">
                        No social drafts or queued posts yet.
                      </div>
                    )}
                    {socialPosts.map((post) => (
                      <div key={post.id} className="border border-[#27272A] rounded-2xl p-4 bg-[#141417]">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0">
                            <p className="text-white font-semibold mb-1">{post.headline}</p>
                            <p className="text-sm text-[#8A8A93] mb-2">
                              {providerLabel(post.provider)} · {post.status}
                            </p>
                            <p className="text-xs text-[#71717A]">
                              Scheduled: {formatDateTime(post.scheduled_at)} · Published: {formatDateTime(post.published_at)}
                            </p>
                            {post.failure_reason && (
                              <p className="text-xs text-[#F97316] mt-2">{post.failure_reason}</p>
                            )}
                          </div>
                          <img
                            src={post.card_image_url}
                            alt={`${post.headline} social card`}
                            className="w-20 h-20 rounded-2xl object-cover border border-[#27272A]"
                          />
                        </div>
                        <div className="flex flex-wrap gap-3 mt-4">
                          {post.status !== 'published' && (
                            <button
                              type="button"
                              onClick={() => handlePublishOne(post.id)}
                              disabled={socialSubmitting}
                              className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors"
                            >
                              Publish now
                            </button>
                          )}
                          <a
                            href={post.card_image_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm text-[#8A8A93] hover:text-white transition-colors"
                          >
                            Preview card
                          </a>
                          <button
                            type="button"
                            onClick={() => handleDeletePost(post.id)}
                            disabled={socialSubmitting}
                            className="text-sm text-[#F97316] hover:text-[#FB923C] transition-colors"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-1">Your interests</h2>
                <p className="text-sm text-[#8A8A93]">These shape the recommendations on your home feed.</p>
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
          </div>
        )}
      </main>
    </div>
  );
}
