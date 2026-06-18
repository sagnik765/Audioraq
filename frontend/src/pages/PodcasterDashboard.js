import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Broadcast, CloudArrowUp, Microphone, PencilSimple, Play, Plus, Trash } from '@phosphor-icons/react';
import { toast } from 'sonner';
import AIPodcastCreator from '../components/AIPodcastCreator';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';
import { displayAIText } from '../lib/displayText';

const categories = [
  'general', 'technology', 'science', 'business', 'health', 'education',
  'entertainment', 'sports', 'politics', 'music', 'comedy', 'true crime',
  'history', 'philosophy', 'art', 'gaming', 'finance', 'travel', 'food',
];

export default function PodcasterDashboard() {
  const { user, checkAuth } = useAuth();
  const { currentPodcast } = usePlayer();
  const [shows, setShows] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [selectedShowId, setSelectedShowId] = useState('');
  const [showAICreator, setShowAICreator] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [showCreateShow, setShowCreateShow] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [savingShow, setSavingShow] = useState(false);
  const [rssImporting, setRssImporting] = useState(false);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [strategyRefreshing, setStrategyRefreshing] = useState(false);
  const [showStrategy, setShowStrategy] = useState(null);
  const [aiSeedBrief, setAiSeedBrief] = useState(null);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('general');
  const [file, setFile] = useState(null);
  const [thumbnail, setThumbnail] = useState(null);
  const [autoGenerateEpisodeThumbnail, setAutoGenerateEpisodeThumbnail] = useState(true);
  const [episodeNumber, setEpisodeNumber] = useState('');
  const [seasonNumber, setSeasonNumber] = useState('');
  const [publishMode, setPublishMode] = useState('upload');
  const [audienceRating, setAudienceRating] = useState('all_ages');

  const [showTitle, setShowTitle] = useState('');
  const [showDescription, setShowDescription] = useState('');
  const [showCategory, setShowCategory] = useState('general');
  const [showThumbnail, setShowThumbnail] = useState(null);
  const [autoGenerateShowThumbnail, setAutoGenerateShowThumbnail] = useState(true);
  const [rssFeedUrl, setRssFeedUrl] = useState('');
  const [aiDraftApplied, setAiDraftApplied] = useState(null);

  const fetchStudio = useCallback(async () => {
    setLoading(true);
    try {
      const analyticsUrl = `${API}/creator/analytics${selectedShowId ? `?show_id=${encodeURIComponent(selectedShowId)}` : ''}`;
      const [showsRes, episodesRes, analyticsRes] = await Promise.all([
        axios.get(`${API}/shows/my`, { withCredentials: true }),
        axios.get(`${API}/podcasts/my`, { withCredentials: true }),
        axios.get(analyticsUrl, { withCredentials: true }).catch(() => ({ data: null })),
      ]);
      const nextShows = showsRes.data.shows || [];
      setShows(nextShows);
      setEpisodes(episodesRes.data.podcasts || []);
      setAnalytics(analyticsRes.data || null);
      if (!selectedShowId && nextShows[0]) {
        setSelectedShowId(nextShows[0].id);
      }
    } catch {
      toast.error('Failed to load Creator Studio');
    } finally {
      setLoading(false);
    }
  }, [selectedShowId]);

  useEffect(() => {
    fetchStudio();
  }, [fetchStudio]);

  const visibleEpisodes = selectedShowId ? episodes.filter((episode) => episode.show_id === selectedShowId) : episodes;
  const activeShow = shows.find((show) => show.id === selectedShowId) || shows[0] || null;
  const auditPromo = user?.promo_entitlements?.ai_podcast_audit || {};

  const totalPlays = episodes.reduce((sum, episode) => sum + (episode.play_count || 0), 0);

  const fetchShowStrategy = useCallback(async (showId, { refresh = false } = {}) => {
    if (!showId) {
      setShowStrategy(null);
      return;
    }

    if (refresh) {
      setStrategyRefreshing(true);
    } else {
      setStrategyLoading(true);
    }

    try {
      const { data } = await axios.get(`${API}/shows/${showId}/ai-strategy${refresh ? '?refresh=true' : ''}`, {
        withCredentials: true,
      });
      setShowStrategy(data || null);
    } catch (error) {
      if (refresh) {
        toast.error(error.response?.data?.detail || 'Could not refresh show strategy');
      } else {
        setShowStrategy(null);
      }
    } finally {
      setStrategyLoading(false);
      setStrategyRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedShowId) {
      setShowStrategy(null);
      return;
    }
    fetchShowStrategy(selectedShowId);
  }, [fetchShowStrategy, selectedShowId]);

  const resetUploadForm = () => {
    setTitle('');
    setDescription('');
    setCategory('general');
    setFile(null);
    setThumbnail(null);
    setAutoGenerateEpisodeThumbnail(true);
    setEpisodeNumber('');
    setSeasonNumber('');
    setAudienceRating('all_ages');
    setPublishMode('upload');
    setAiDraftApplied(null);
  };

  const notifyEpisodeOutcome = (episode, actionLabel) => {
    if (episode.publication_status === 'draft' && !episode.is_playable) {
      toast.success(`${actionLabel} created as an AI draft in your studio.`);
      if (episode.moderation_summary) {
        toast.message(displayAIText(episode.moderation_summary));
      }
      return;
    }
    if (episode.moderation_status === 'blocked') {
      toast.message('Safety review flagged this episode. It is saved in Studio but hidden from listeners.');
      return;
    }
    if (episode.moderation_status === 'review' && episode.moderation_summary) {
      toast.message(`Safety review: ${displayAIText(episode.moderation_summary)}`);
    } else {
      toast.success(actionLabel);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (publishMode === 'upload' && !file) {
      toast.error('Please select an episode file');
      return;
    }
    if (publishMode === 'ai' && !aiDraftApplied?.id) {
      toast.error('Generate an AI episode package first');
      return;
    }
    if (publishMode === 'upload' && aiDraftApplied?.id && file && !file.type.startsWith('audio/')) {
      toast.error('Create with AI supports audio-only publishing. Use regular Publish Episode for recorded video uploads.');
      return;
    }
    if (!selectedShowId) {
      toast.error('Create a show first');
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('show_id', selectedShowId);
      formData.append('title', title);
      formData.append('description', description);
      formData.append('category', category);
      formData.append('audience_rating', audienceRating);
      if (aiDraftApplied?.id) formData.append('ai_draft_id', aiDraftApplied.id);
      if (thumbnail) formData.append('thumbnail', thumbnail);
      formData.append('auto_generate_thumbnail', autoGenerateEpisodeThumbnail ? 'true' : 'false');
      if (episodeNumber) formData.append('episode_number', episodeNumber);
      if (seasonNumber) formData.append('season_number', seasonNumber);
      if (publishMode === 'upload') {
        formData.append('file', file);
      }

      const endpoint = publishMode === 'upload' ? `${API}/podcasts/upload` : `${API}/podcasts/ai-create`;
      const { data } = await axios.post(endpoint, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      notifyEpisodeOutcome(data, publishMode === 'upload' ? 'Episode published' : 'AI audio episode published');
      resetUploadForm();
      setShowUpload(false);
      fetchStudio();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Publish failed');
    } finally {
      setUploading(false);
    }
  };

  const handleCreateShow = async (e) => {
    e.preventDefault();
    setSavingShow(true);
    try {
      const formData = new FormData();
      formData.append('title', showTitle);
      formData.append('description', showDescription);
      formData.append('category', showCategory);
      if (showThumbnail) formData.append('thumbnail', showThumbnail);
      formData.append('auto_generate_thumbnail', autoGenerateShowThumbnail ? 'true' : 'false');
      const res = await axios.post(`${API}/shows`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Show created');
      setShowCreateShow(false);
      setShowTitle('');
      setShowDescription('');
      setShowCategory('general');
      setShowThumbnail(null);
      setAutoGenerateShowThumbnail(true);
      setSelectedShowId(res.data.id);
      fetchStudio();
      checkAuth();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create show');
    } finally {
      setSavingShow(false);
    }
  };

  const handleImportRss = async (event) => {
    event.preventDefault();
    if (!rssFeedUrl.trim()) {
      toast.error('Enter an RSS feed URL first');
      return;
    }

    setRssImporting(true);
    try {
      const { data } = await axios.post(`${API}/shows/import-rss`, {
        feed_url: rssFeedUrl.trim(),
        show_id: selectedShowId || '',
        import_limit: 12,
      }, { withCredentials: true });
      toast.success(`Imported ${data.imported_count || 0} episodes from RSS`);
      setRssFeedUrl('');
      setSelectedShowId(data.show_id || selectedShowId);
      fetchStudio();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'RSS import failed');
    } finally {
      setRssImporting(false);
    }
  };

  const handleDeleteEpisode = async (episodeId, event) => {
    event.stopPropagation();
    if (!window.confirm('Delete this episode?')) return;
    try {
      await axios.delete(`${API}/podcasts/${episodeId}`, { withCredentials: true });
      toast.success('Episode deleted');
      fetchStudio();
    } catch {
      toast.error('Failed to delete episode');
    }
  };

  const beginEditEpisode = (episode, event) => {
    event.stopPropagation();
    setEditingEpisode({
      id: episode.id,
      title: episode.title,
      description: episode.description || '',
      category: episode.category || 'general',
      audience_rating: episode.audience_rating || 'all_ages',
      show_id: episode.show_id || selectedShowId,
      episode_number: episode.episode_number || '',
      season_number: episode.season_number || '',
      thumbnail: null,
      auto_generate_thumbnail: false,
    });
  };

  const handleSaveEpisode = async (e) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append('title', editingEpisode.title);
      formData.append('description', editingEpisode.description);
      formData.append('category', editingEpisode.category);
      formData.append('audience_rating', editingEpisode.audience_rating || 'all_ages');
      formData.append('show_id', editingEpisode.show_id);
      if (editingEpisode.episode_number) formData.append('episode_number', editingEpisode.episode_number);
      if (editingEpisode.season_number) formData.append('season_number', editingEpisode.season_number);
      if (editingEpisode.thumbnail) formData.append('thumbnail', editingEpisode.thumbnail);
      formData.append('auto_generate_thumbnail', editingEpisode.auto_generate_thumbnail ? 'true' : 'false');

      await axios.put(`${API}/podcasts/${editingEpisode.id}`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Episode updated');
      setEditingEpisode(null);
      fetchStudio();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update episode');
    }
  };

  const handleApplyAIDraft = (draft) => {
    setSelectedShowId(draft.show_id || selectedShowId);
    setTitle(draft.publish_prefill?.title || draft.generation?.episode_title || '');
    setDescription(draft.publish_prefill?.description || draft.generation?.suggested_description || '');
    setCategory(draft.publish_prefill?.category || draft.recommended_category || activeShow?.category || 'general');
    setAiDraftApplied(draft);
    setPublishMode('ai');
    setShowUpload(true);
    setShowAICreator(false);
    toast.success('AI draft applied. AI-created episodes are audio-only; recorded video still belongs in regular Publish Episode.');
    setTimeout(() => {
      document.querySelector('[data-testid="upload-podcast-form"]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const handleGenerateShowThumbnail = async (showId) => {
    try {
      const { data } = await axios.post(`${API}/shows/${showId}/thumbnail/generate`, {}, { withCredentials: true });
      setShows((prev) => prev.map((show) => (show.id === showId ? data : show)));
      toast.success('Show thumbnail created');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not create show thumbnail');
    }
  };

  const handleGenerateEpisodeThumbnail = async (episodeId) => {
    try {
      const { data } = await axios.post(`${API}/podcasts/${episodeId}/thumbnail/generate`, {}, { withCredentials: true });
      setEpisodes((prev) => prev.map((episode) => (episode.id === episodeId ? data : episode)));
      toast.success('Episode thumbnail created');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not create episode thumbnail');
    }
  };

  const handleUseStrategyIdea = (idea) => {
    if (!idea?.ai_seed) {
      toast.error('That idea is missing an AI Studio seed.');
      return;
    }
    setAiSeedBrief(JSON.parse(JSON.stringify(idea.ai_seed)));
    setShowAICreator(true);
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="podcaster-dashboard">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-10">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Creator Studio</p>
            <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-2">
              Run your show, not just uploads
            </h1>
            <p className="text-[#8A8A93]">Manage show identity, publish episodes, and keep your catalog organized in Audioraq.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => {
                setAiSeedBrief(null);
                setShowAICreator(true);
              }}
              className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors inline-flex items-center gap-2"
              data-testid="ai-toggle-btn"
            >
              <PencilSimple className="w-5 h-5" />
              Create with AI
            </button>
            <button
              onClick={() => setShowCreateShow((prev) => !prev)}
              className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors inline-flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              Create Show
            </button>
            <button
              onClick={() => setShowUpload((prev) => !prev)}
              className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors inline-flex items-center gap-2"
              data-testid="upload-toggle-btn"
            >
              <CloudArrowUp weight="bold" className="w-5 h-5" />
              Publish Episode
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4 mb-10">
          {[
            { label: 'Shows', value: shows.length, icon: <Broadcast weight="duotone" className="w-6 h-6 text-[#F5A623]" /> },
            { label: 'Episodes', value: episodes.length, icon: <Microphone weight="duotone" className="w-6 h-6 text-[#F5A623]" /> },
            { label: 'Total Plays', value: totalPlays, icon: <Play weight="duotone" className="w-6 h-6 text-[#F5A623]" /> },
            { label: 'Saved', value: analytics?.overview?.saved_count || 0, icon: <Plus className="w-6 h-6 text-[#F5A623]" /> },
            { label: 'Avg Completion', value: `${analytics?.overview?.avg_completion_rate || 0}%`, icon: <PencilSimple className="w-6 h-6 text-[#F5A623]" /> },
          ].map((stat) => (
            <div key={stat.label} className="bg-[#141417] border border-[#27272A] rounded-xl p-6 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#F5A623]/10 flex items-center justify-center">{stat.icon}</div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93]">{stat.label}</p>
                <p className="font-['Outfit'] text-2xl font-bold text-white">{stat.value}</p>
              </div>
            </div>
          ))}
        </div>

        <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 mb-10">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-6">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Show Manager</p>
              <h2 className="font-['Outfit'] text-2xl font-semibold text-white">Show > Season > Episode organization</h2>
              <p className="text-sm text-[#8A8A93] mt-1">
                Keep each show branded, then publish episodes into seasons with AI Agents quality status attached.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreateShow(true)}
              className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors inline-flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              New Show
            </button>
          </div>

          {shows.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {shows.map((show) => (
                <div
                  key={show.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedShowId(show.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedShowId(show.id);
                    }
                  }}
                  className={`text-left rounded-2xl border p-5 transition-all ${
                    selectedShowId === show.id
                      ? 'border-[#F5A623] bg-[#F5A623]/10'
                      : 'border-[#27272A] bg-[#0A0A0B] hover:border-[#8A8A93]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-[0.18em] text-[#F5A623] mb-1">{show.category || 'general'}</p>
                      <h3 className="font-['Outfit'] text-lg font-semibold text-white truncate">{show.title}</h3>
                    </div>
                    <span className="text-xs text-[#8A8A93] whitespace-nowrap">{show.episode_count || 0} episodes</span>
                  </div>
                  <p className="text-sm text-[#8A8A93] line-clamp-2 mb-4">{show.description || 'Add a show description so listeners know what to expect.'}</p>
                  <div className="flex flex-wrap gap-2 mb-4">
                    {(show.quality_signals || ['Ready for episodes']).slice(0, 3).map((signal) => (
                      <span key={signal} className="bg-[#141417] border border-[#27272A] rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-[#C7C7D1]">
                        {signal}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs text-[#8A8A93]">{show.total_play_count || 0} plays</span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleGenerateShowThumbnail(show.id);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          event.stopPropagation();
                          handleGenerateShowThumbnail(show.id);
                        }
                      }}
                      className="text-xs text-[#F5A623] hover:text-[#F7B84B] transition-colors"
                    >
                      Create thumbnail
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-8 text-center">
              <p className="text-[#8A8A93] mb-4">Create a show first, then add seasons and episodes under it.</p>
              <button
                type="button"
                onClick={() => setShowCreateShow(true)}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors"
              >
                Create Show
              </button>
            </div>
          )}
        </section>

        <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 mb-10">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-6">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">AI Strategist</p>
              <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">What this show should publish next</h2>
              <p className="text-sm text-[#8A8A93] max-w-3xl">
                This is the creator-side AI layer that actually matters: it reads the show, recent episodes, and listener signals, then turns that into concrete next-episode moves you can send straight into AI Studio.
              </p>
              {auditPromo.active && (
                <p className="mt-3 inline-flex rounded-full border border-[#22C55E]/30 bg-[#22C55E]/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#BBF7D0]">
                  PODCASTAI audit active · {auditPromo.days_remaining || 0} days left
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  setAiSeedBrief(null);
                  setShowAICreator(true);
                }}
                disabled={!activeShow}
                className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors disabled:opacity-40"
              >
                Open AI Studio
              </button>
              <button
                type="button"
                onClick={() => fetchShowStrategy(selectedShowId, { refresh: true })}
                disabled={!selectedShowId || strategyRefreshing}
                className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors disabled:opacity-40"
              >
                {strategyRefreshing ? 'Refreshing...' : 'Refresh Strategy'}
              </button>
            </div>
          </div>

          {!activeShow ? (
            <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 text-center">
              <p className="text-sm text-[#8A8A93]">Select or create a show first so Audioraq can generate a strategy that is specific to a real catalog.</p>
            </div>
          ) : strategyLoading && !showStrategy ? (
            <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6">
              <p className="text-sm text-[#8A8A93]">Reading the show, recent episodes, and listener signals...</p>
            </div>
          ) : showStrategy ? (
            <>
              <div className="grid grid-cols-1 xl:grid-cols-[0.92fr_1.08fr] gap-6 mb-6">
                <div className="space-y-4">
                  <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Positioning</p>
                    <p className="text-sm text-white leading-relaxed">{showStrategy.positioning}</p>
                  </div>
                  <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Audience promise</p>
                    <p className="text-sm text-[#C7C7D1] leading-relaxed">{showStrategy.audience_promise}</p>
                  </div>
                  <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">Title starters</p>
                    <div className="flex flex-wrap gap-2">
                      {(showStrategy.title_starters || []).map((titleStarter) => (
                        <span key={titleStarter} className="bg-[#141417] border border-[#27272A] rounded-full px-3 py-1.5 text-xs text-white">
                          {titleStarter}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">What is working</p>
                    <div className="space-y-3">
                      {(showStrategy.what_is_working || []).map((item) => (
                        <div key={item} className="border border-[#27272A] rounded-xl px-3 py-3">
                          <p className="text-sm text-white leading-relaxed">{item}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">Underused angles</p>
                    <div className="space-y-3">
                      {(showStrategy.underused_angles || []).map((item) => (
                        <div key={item} className="border border-[#27272A] rounded-xl px-3 py-3">
                          <p className="text-sm text-[#C7C7D1] leading-relaxed">{item}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5 mb-6">
                <div className="flex items-center justify-between gap-4 mb-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Next AI-ready ideas</p>
                    <h3 className="font-['Outfit'] text-xl font-semibold text-white">High-leverage episodes to create next</h3>
                  </div>
                  <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93]">
                    Provider: {showStrategy.provider || 'deterministic'}
                  </p>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {(showStrategy.next_episode_ideas || []).map((idea) => (
                    <div key={`${idea.title}-${idea.format}`} className="bg-[#141417] border border-[#27272A] rounded-2xl p-5">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div>
                          <h4 className="font-['Outfit'] text-lg font-semibold text-white mb-1">{idea.title}</h4>
                          <p className="text-xs uppercase tracking-[0.18em] text-[#F5A623]">{idea.format} · optimize for {idea.optimize_for}</p>
                        </div>
                      </div>
                      <p className="text-sm text-white leading-relaxed mb-3">{idea.angle}</p>
                      <p className="text-sm text-[#8A8A93] leading-relaxed mb-3">{idea.why_now}</p>
                      <div className="bg-[#0A0A0B] border border-[#27272A] rounded-xl px-3 py-3 mb-4">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Desired outcome</p>
                        <p className="text-sm text-[#C7C7D1]">{idea.desired_outcome}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleUseStrategyIdea(idea)}
                        className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors"
                      >
                        Use in Create with AI
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">Growth moves</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {(showStrategy.growth_moves || []).map((move) => (
                    <div key={move} className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                      <p className="text-sm text-[#C7C7D1] leading-relaxed">{move}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-6 text-center">
              <p className="text-sm text-[#8A8A93]">Audioraq could not generate a strategy for this show yet. Try refreshing once the show has a title, description, and at least one episode.</p>
            </div>
          )}
        </section>

        <Dialog open={showAICreator} onOpenChange={setShowAICreator}>
          <DialogContent className="max-w-6xl bg-[#0A0A0B] border border-[#27272A] text-white p-0 overflow-hidden">
            <div className="max-h-[86vh] overflow-y-auto px-6 py-6 md:px-8">
              <AIPodcastCreator
                shows={shows}
                selectedShowId={selectedShowId}
                onSelectShow={setSelectedShowId}
                activeShow={activeShow}
                onApplyDraft={handleApplyAIDraft}
                seedBrief={aiSeedBrief}
              />
            </div>
          </DialogContent>
        </Dialog>

        <section className="grid grid-cols-1 xl:grid-cols-[1.15fr_0.85fr] gap-6 mb-10">
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-3">Creator Concierge</p>
            <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-3">
              {episodes.length ? 'Keep the show polished after publishing' : 'Launch the first strong version of your show'}
            </h2>
            <p className="text-sm text-[#8A8A93] mb-6">
              Audioraq works best when every show feels intentional. These are the highest-leverage steps to improve discoverability and listening completion.
            </p>
            <div className="space-y-3">
              {[
                { label: 'Create a show', done: shows.length > 0 },
                { label: 'Write a show description', done: Boolean(activeShow?.description) },
                { label: 'Add show artwork', done: Boolean(activeShow?.thumbnail_path || activeShow?.external_thumbnail_url) },
                { label: 'Publish the first episode', done: episodes.length > 0 },
                { label: 'Use season or episode numbering', done: episodes.some((episode) => episode.season_number || episode.episode_number) },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between gap-4 bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-3">
                  <span className="text-sm text-white">{item.label}</span>
                  <span className={`text-xs uppercase tracking-[0.18em] font-semibold ${item.done ? 'text-[#F5A623]' : 'text-[#8A8A93]'}`}>
                    {item.done ? 'Done' : 'Next'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-3">RSS Import</p>
            <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-3">Bring in an existing catalog</h2>
            <p className="text-sm text-[#8A8A93] mb-6">
              If your show already lives elsewhere, import the feed and keep Audioraq focused on episodes, metadata, and discovery instead of manual re-entry. The workflow now supports three creation lanes: RSS import, direct file publishing, and AI-assisted planning.
            </p>
            <form onSubmit={handleImportRss} className="space-y-4">
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Feed URL</label>
                <input
                  type="url"
                  value={rssFeedUrl}
                  onChange={(e) => setRssFeedUrl(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  placeholder="https://example.com/feed.xml"
                />
              </div>
              <button
                type="submit"
                disabled={rssImporting}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
              >
                {rssImporting ? 'Importing...' : 'Import RSS Feed'}
              </button>
            </form>
          </div>
        </section>

        {showCreateShow && (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 mb-8">
            <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-6">Create a Show</h2>
            <form onSubmit={handleCreateShow} className="space-y-5">
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Title</label>
                <input
                  type="text"
                  value={showTitle}
                  onChange={(e) => setShowTitle(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  required
                />
              </div>
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Category</label>
                <select
                  value={showCategory}
                  onChange={(e) => setShowCategory(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                >
                  {categories.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Description</label>
                <textarea
                  value={showDescription}
                  onChange={(e) => setShowDescription(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none min-h-[140px] resize-none"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Artwork</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setShowThumbnail(e.target.files[0])}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 file:mr-4 file:rounded-full file:border-0 file:bg-[#27272A] file:text-white file:font-medium file:px-4 file:py-1 file:text-sm"
                  />
                  <p className="text-xs text-[#8A8A93] mt-2">Upload custom cover art if you already have it.</p>
                </div>
                <label className="rounded-2xl border border-[#27272A] bg-[#0A0A0B] px-4 py-4 flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoGenerateShowThumbnail}
                    onChange={(e) => setAutoGenerateShowThumbnail(e.target.checked)}
                    className="mt-1 accent-[#F5A623]"
                  />
                  <span>
                    <span className="block text-sm font-semibold text-white">Create artwork automatically</span>
                    <span className="block text-xs text-[#8A8A93] mt-1">Audioraq will generate a branded show thumbnail from the title and category if no custom file is uploaded.</span>
                  </span>
                </label>
              </div>
              <button
                type="submit"
                disabled={savingShow}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
              >
                {savingShow ? 'Creating...' : 'Create Show'}
              </button>
            </form>
          </div>
        )}

        {showUpload && (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 mb-8" data-testid="upload-podcast-form">
            <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-6">Publish Episode</h2>
            <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4 mb-6">
              <p className="text-xs uppercase tracking-[0.18em] text-[#F5A623] mb-2">Fast AI Agents gate</p>
              <p className="text-sm text-[#C7C7D1]">
                Clean episodes use Audioraq's local fast-path safety and quality checks first, then publish. Risky packages still escalate before they reach listeners.
              </p>
            </div>
            {aiDraftApplied && (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4 mb-6">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">AI draft applied</p>
                <p className="text-sm text-white mb-2">{aiDraftApplied.generation?.episode_title || aiDraftApplied.publish_prefill?.title}</p>
                <p className="text-sm text-[#8A8A93]">
                  Title, description, and category were prefilled from your AI episode package. Create with AI is audio-only, and AI Agents will attach a quality report before publishing.
                </p>
                {aiDraftApplied.quality_review && (
                  <p className="text-xs text-[#F5A623] mt-3">
                    AI Agents score: {aiDraftApplied.quality_review.quality_score}/100 · {aiDraftApplied.quality_review.status}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setAiDraftApplied(null);
                    setPublishMode('upload');
                    toast.message('AI draft cleared. Regular uploads can use audio or video.');
                  }}
                  className="text-xs text-[#C7C7D1] hover:text-white underline underline-offset-4 mt-3"
                >
                  Clear AI draft and publish a recorded file instead
                </button>
              </div>
            )}
            {aiDraftApplied && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
                <button
                  type="button"
                  onClick={() => setPublishMode('upload')}
                  className={`rounded-2xl border px-4 py-4 text-left transition-all ${
                    publishMode === 'upload'
                      ? 'border-[#F5A623] bg-[#F5A623]/10'
                      : 'border-[#27272A] bg-[#0A0A0B] hover:border-[#8A8A93]'
                  }`}
                >
                  <p className="text-sm font-semibold text-white mb-1">Upload final audio</p>
                  <p className="text-xs text-[#8A8A93]">Publish this AI-created episode with an audio file and optional thumbnail.</p>
                </button>
                <button
                  type="button"
                  onClick={() => setPublishMode('ai')}
                  className={`rounded-2xl border px-4 py-4 text-left transition-all ${
                    publishMode === 'ai'
                      ? 'border-[#F5A623] bg-[#F5A623]/10'
                      : 'border-[#27272A] bg-[#0A0A0B] hover:border-[#8A8A93]'
                  }`}
                >
                  <p className="text-sm font-semibold text-white mb-1">Create rendered AI audio</p>
                  <p className="text-xs text-[#8A8A93]">Render a playable audio episode from the generated script, then attach the AI Agents review.</p>
                </button>
              </div>
            )}
            <form onSubmit={handleUpload} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show</label>
                  <select
                    value={selectedShowId}
                    onChange={(e) => setSelectedShowId(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                    data-testid="upload-show-select"
                  >
                    {shows.map((show) => <option key={show.id} value={show.id}>{show.title}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Title</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                    required
                    data-testid="upload-title-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                    data-testid="upload-category-select"
                  >
                    {categories.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Audience</label>
                  <select
                    value={audienceRating}
                    onChange={(e) => setAudienceRating(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  >
                    <option value="all_ages">All ages</option>
                    <option value="18+">Mature 18+</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Season</label>
                  <input
                    type="number"
                    value={seasonNumber}
                    onChange={(e) => setSeasonNumber(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Episode</label>
                  <input
                    type="number"
                    value={episodeNumber}
                    onChange={(e) => setEpisodeNumber(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Episode Notes</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none min-h-[120px] resize-none"
                  data-testid="upload-description-textarea"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {publishMode === 'upload' && (
                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Episode File</label>
                    <input
                      type="file"
                      accept={aiDraftApplied ? 'audio/*' : 'audio/*,video/*'}
                      onChange={(e) => setFile(e.target.files[0])}
                      className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 file:mr-4 file:rounded-full file:border-0 file:bg-[#F5A623] file:text-[#0A0A0B] file:font-bold file:px-4 file:py-1 file:text-sm"
                      data-testid="upload-file-input"
                    />
                    <p className="text-xs text-[#8A8A93] mt-2">
                      {aiDraftApplied
                        ? 'AI-created episodes only accept audio here. To publish a recorded video, clear this AI draft and use Publish Episode normally.'
                        : 'Recorded uploads can be audio or audio + video.'}
                    </p>
                  </div>
                )}
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Episode Thumbnail</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setThumbnail(e.target.files[0])}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 file:mr-4 file:rounded-full file:border-0 file:bg-[#27272A] file:text-white file:font-medium file:px-4 file:py-1 file:text-sm"
                    data-testid="upload-thumbnail-input"
                  />
                  <label className="flex items-start gap-3 mt-3 text-sm text-[#C7C7D1] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoGenerateEpisodeThumbnail}
                      onChange={(e) => setAutoGenerateEpisodeThumbnail(e.target.checked)}
                      className="mt-1 accent-[#F5A623]"
                    />
                    <span>
                      <span className="block text-white">Create thumbnail automatically</span>
                      <span className="block text-xs text-[#8A8A93] mt-1">If no file is uploaded, Audioraq generates category-aware artwork for this episode.</span>
                    </span>
                  </label>
                </div>
              </div>

              {publishMode === 'ai' && (
                <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">AI draft outcome</p>
                  <p className="text-sm text-[#C7C7D1]">
                    This renders an audio-only episode from the AI package, publishes it as playable audio, and stores the generated script package, safety review, and AI Agents quality report.
                  </p>
                </div>
              )}

              <button
                type="submit"
                disabled={uploading}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
                data-testid="upload-submit-btn"
              >
                {uploading ? 'Publishing...' : publishMode === 'upload' ? 'Publish Episode' : 'Create AI Audio Episode'}
              </button>
            </form>
          </div>
        )}

        {editingEpisode && (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 mb-8">
            <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-6">Edit Episode</h2>
            <form onSubmit={handleSaveEpisode} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <input
                  type="text"
                  value={editingEpisode.title}
                  onChange={(e) => setEditingEpisode((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                />
                <select
                  value={editingEpisode.show_id}
                  onChange={(e) => setEditingEpisode((prev) => ({ ...prev, show_id: e.target.value }))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                >
                  {shows.map((show) => <option key={show.id} value={show.id}>{show.title}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
                <select
                  value={editingEpisode.category}
                  onChange={(e) => setEditingEpisode((prev) => ({ ...prev, category: e.target.value }))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                >
                  {categories.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
                <select
                  value={editingEpisode.audience_rating}
                  onChange={(e) => setEditingEpisode((prev) => ({ ...prev, audience_rating: e.target.value }))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                >
                  <option value="all_ages">All ages</option>
                  <option value="18+">Mature 18+</option>
                </select>
                <input
                  type="number"
                  value={editingEpisode.season_number}
                  onChange={(e) => setEditingEpisode((prev) => ({ ...prev, season_number: e.target.value }))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  placeholder="Season"
                />
                <input
                  type="number"
                  value={editingEpisode.episode_number}
                  onChange={(e) => setEditingEpisode((prev) => ({ ...prev, episode_number: e.target.value }))}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  placeholder="Episode"
                />
              </div>
              <textarea
                value={editingEpisode.description}
                onChange={(e) => setEditingEpisode((prev) => ({ ...prev, description: e.target.value }))}
                className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none min-h-[120px] resize-none"
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Replace Thumbnail</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setEditingEpisode((prev) => ({ ...prev, thumbnail: e.target.files[0] }))}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 file:mr-4 file:rounded-full file:border-0 file:bg-[#27272A] file:text-white file:font-medium file:px-4 file:py-1 file:text-sm"
                  />
                </div>
                <label className="rounded-2xl border border-[#27272A] bg-[#0A0A0B] px-4 py-4 flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingEpisode.auto_generate_thumbnail}
                    onChange={(e) => setEditingEpisode((prev) => ({ ...prev, auto_generate_thumbnail: e.target.checked }))}
                    className="mt-1 accent-[#F5A623]"
                  />
                  <span>
                    <span className="block text-sm font-semibold text-white">Regenerate from metadata</span>
                    <span className="block text-xs text-[#8A8A93] mt-1">Create fresh episode artwork from the title, show, and category.</span>
                  </span>
                </label>
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => setEditingEpisode(null)} className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors">
                  Cancel
                </button>
                <button type="submit" className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors">
                  Save Episode
                </button>
              </div>
            </form>
          </div>
        )}

        {analytics && (
          <section className="grid grid-cols-1 xl:grid-cols-[0.9fr_1.1fr] gap-6 mb-10">
            <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
              <div className="flex items-center justify-between gap-4 mb-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Audience Insight</p>
                  <h2 className="font-['Outfit'] text-2xl font-semibold text-white">What listeners are doing</h2>
                </div>
                <span className="text-sm text-[#8A8A93]">{analytics.overview?.listener_count || 0} listeners</span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                {[
                  { label: 'Shows', value: analytics.overview?.show_count || 0 },
                  { label: 'Episodes', value: analytics.overview?.episode_count || 0 },
                  { label: 'Total Plays', value: analytics.overview?.total_plays || 0 },
                  { label: 'Saved', value: analytics.overview?.saved_count || 0 },
                ].map((item) => (
                  <div key={item.label} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">{item.label}</p>
                    <p className="font-['Outfit'] text-2xl font-semibold text-white">{item.value}</p>
                  </div>
                ))}
              </div>

              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">Top listener interests</p>
                {analytics.listener_interests?.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {analytics.listener_interests.map((item) => (
                      <span key={item.interest} className="px-3 py-1 rounded-full bg-[#141417] border border-[#27272A] text-xs text-white">
                        {item.interest} ({item.count})
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[#8A8A93]">Interest insights will appear as listening activity builds.</p>
                )}
              </div>
            </div>

            <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
              <div className="flex items-center justify-between gap-4 mb-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Episode Performance</p>
                  <h2 className="font-['Outfit'] text-2xl font-semibold text-white">Completion and saves</h2>
                </div>
                <span className="text-sm text-[#8A8A93]">{analytics.overview?.avg_completion_rate || 0}% avg completion</span>
              </div>

              <div className="space-y-3">
                {(analytics.episodes || []).slice(0, 6).map((episode) => (
                  <div key={episode.id} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div className="min-w-0">
                        <p className="text-sm text-white truncate">{episode.title}</p>
                        <p className="text-xs text-[#8A8A93] truncate">{episode.show_title}</p>
                      </div>
                      <span className="text-xs text-[#F5A623] whitespace-nowrap">{episode.play_count} plays</span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      <div>
                        <p className="text-[#8A8A93] uppercase tracking-[0.16em] mb-1">Saved</p>
                        <p className="text-white">{episode.saved_count}</p>
                      </div>
                      <div>
                        <p className="text-[#8A8A93] uppercase tracking-[0.16em] mb-1">Started</p>
                        <p className="text-white">{episode.started_count}</p>
                      </div>
                      <div>
                        <p className="text-[#8A8A93] uppercase tracking-[0.16em] mb-1">Completion</p>
                        <p className="text-white">{episode.completion_rate}%</p>
                      </div>
                    </div>
                  </div>
                ))}
                {!analytics.episodes?.length && (
                  <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5 text-center">
                    <p className="text-sm text-[#8A8A93]">Performance analytics will populate after the first listening sessions.</p>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        <section>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-1">Published Episodes</h2>
              <p className="text-sm text-[#8A8A93]">Filter by show, edit metadata, and keep each show cleanly organized.</p>
            </div>
            <select
              value={selectedShowId}
              onChange={(e) => setSelectedShowId(e.target.value)}
              className="bg-[#141417] border border-[#27272A] rounded-full px-4 py-2 text-sm text-white outline-none"
            >
              <option value="">All Shows</option>
              {shows.map((show) => <option key={show.id} value={show.id}>{show.title}</option>)}
            </select>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : visibleEpisodes.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {visibleEpisodes.map((episode) => (
                <div key={episode.id} className="relative group">
                  <PodcastCard podcast={episode} />
                  <div className="absolute top-3 right-3 flex gap-2 z-10">
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        handleGenerateEpisodeThumbnail(episode.id);
                      }}
                      className="bg-[#0A0A0B]/85 hover:bg-[#0A0A0B] text-white rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity"
                      data-testid={`generate-thumbnail-${episode.id}`}
                    >
                      <Plus weight="bold" className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(event) => beginEditEpisode(episode, event)}
                      className="bg-[#0A0A0B]/85 hover:bg-[#0A0A0B] text-white rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity"
                      data-testid={`edit-podcast-${episode.id}`}
                    >
                      <PencilSimple weight="bold" className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(event) => handleDeleteEpisode(episode.id, event)}
                      className="bg-[#EF4444]/85 hover:bg-[#EF4444] text-white rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity"
                      data-testid={`delete-podcast-${episode.id}`}
                    >
                      <Trash weight="bold" className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-12 text-center">
              <Broadcast weight="duotone" className="w-12 h-12 text-[#8A8A93] mx-auto mb-4" />
              <h3 className="font-['Outfit'] text-lg font-medium text-white mb-2">No episodes here yet</h3>
              <p className="text-sm text-[#8A8A93] mb-6">
                {shows.length > 0 ? 'Create momentum by publishing the first episode for this show.' : 'Create your first show, then publish the first episode.'}
              </p>
              <div className="flex justify-center gap-3 flex-wrap">
                <button
                  onClick={() => setShowCreateShow(true)}
                  className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                >
                  Create Show
                </button>
                <button
                  onClick={() => setShowAICreator(true)}
                  className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                >
                  Create with AI
                </button>
                <button
                  onClick={() => setShowUpload(true)}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors"
                >
                  Publish Episode
                </button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
