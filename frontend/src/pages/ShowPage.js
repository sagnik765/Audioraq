import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowLeft, Broadcast, Play, UsersThree } from '@phosphor-icons/react';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { displayAIText } from '../lib/displayText';
import { followShow, unfollowShow, authRequest } from '../lib/library';

export default function ShowPage() {
  const { showId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { currentPodcast, playCollection } = usePlayer();
  const [show, setShow] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchShow() {
      setLoading(true);
      try {
        const [showRes, episodesRes] = await Promise.all([
          axios.get(`${API}/shows/${showId}`, authRequest),
          axios.get(`${API}/shows/${showId}/episodes`, authRequest),
        ]);
        if (!cancelled) {
          setShow(showRes.data);
          setEpisodes(episodesRes.data.podcasts || []);
        }
      } catch {
        if (!cancelled) {
          setShow(false);
          setEpisodes([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchShow();
    return () => { cancelled = true; };
  }, [showId]);

  if (loading) {
    return (
      <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`}>
        <Navbar />
        <div className="flex items-center justify-center py-32">
          <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!show) {
    return (
      <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`}>
        <Navbar />
        <main className="max-w-5xl mx-auto px-6 md:px-8 lg:px-12 py-12">
          <Link to="/browse" className="inline-flex items-center gap-2 text-sm text-[#8A8A93] hover:text-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to browse
          </Link>
          <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-12 text-center">
            <h1 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Show not found</h1>
            <p className="text-[#8A8A93]">It may have been removed or is no longer available.</p>
          </div>
        </main>
      </div>
    );
  }

  const thumbnailUrl = `${API}/shows/${show.id}/thumbnail`;
  const latestEpisode = episodes[0];
  const isOwnShow = Boolean(user && show.podcaster_id === user.id);
  const seasonGroups = Object.entries(
    episodes.reduce((groups, episode) => {
      const seasonKey = episode.season_number ? `Season ${episode.season_number}` : 'Episodes';
      groups[seasonKey] = groups[seasonKey] || [];
      groups[seasonKey].push(episode);
      return groups;
    }, {}),
  ).map(([label, seasonEpisodes]) => ({
    label,
    episodes: [...seasonEpisodes].sort((a, b) => {
      const aNumber = Number(a.episode_number || 0);
      const bNumber = Number(b.episode_number || 0);
      if (aNumber && bNumber) return aNumber - bNumber;
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    }),
  })).sort((a, b) => {
    if (a.label === 'Episodes') return 1;
    if (b.label === 'Episodes') return -1;
    return Number(b.label.replace(/\D/g, '') || 0) - Number(a.label.replace(/\D/g, '') || 0);
  });

  const handleFollowToggle = async () => {
    if (!user) {
      toast.message('Create an account to follow shows and build a personal listening home.');
      navigate('/register');
      return;
    }
    if (isOwnShow) return;
    const nextFollowing = !show.is_following;
    setShow((prev) => ({
      ...prev,
      is_following: nextFollowing,
      follower_count: Math.max(0, (prev?.follower_count || 0) + (nextFollowing ? 1 : -1)),
    }));

    try {
      if (nextFollowing) {
        await followShow(show.id);
        toast.success('Show followed');
      } else {
        await unfollowShow(show.id);
        toast.success('Show unfollowed');
      }
    } catch (error) {
      setShow((prev) => ({
        ...prev,
        is_following: !nextFollowing,
        follower_count: Math.max(0, (prev?.follower_count || 0) + (nextFollowing ? -1 : 1)),
      }));
      toast.error(error.response?.data?.detail || 'Could not update follow status');
    }
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="show-page">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 md:px-8 lg:px-12 py-10">
        <Link to="/browse" className="inline-flex items-center gap-2 text-sm text-[#8A8A93] hover:text-white transition-colors mb-8">
          <ArrowLeft className="w-4 h-4" />
          Back to browse
        </Link>

        <section className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-8 mb-12">
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl overflow-hidden">
            <div className="aspect-[16/11] bg-[#0A0A0B]">
              {thumbnailUrl ? (
                <img src={thumbnailUrl} alt={show.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-[#F5A623]/15 to-[#141417] flex items-center justify-center">
                  <Broadcast weight="duotone" className="w-16 h-16 text-[#F5A623]/50" />
                </div>
              )}
            </div>
          </div>

          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="flex items-center gap-2 mb-4">
              <span className="bg-[#27272A] text-[10px] text-white px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                show
              </span>
              <span className="bg-[#F5A623]/10 text-[#F5A623] text-[10px] px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                {show.category || 'general'}
              </span>
            </div>

            <h1 className="font-['Outfit'] text-3xl md:text-4xl tracking-tight font-bold text-white mb-3">{show.title}</h1>
            <p className="text-sm text-[#8A8A93] mb-6">Hosted by {show.podcaster_name}</p>

            <p className="text-sm text-[#C7C7D1] leading-relaxed whitespace-pre-wrap mb-8">
              {show.description || 'This show is getting set up right now.'}
            </p>

            {show.quality_signals?.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-6">
                {show.quality_signals.map((signal) => (
                  <span key={signal} className="px-3 py-1 rounded-full bg-[#0A0A0B] border border-[#27272A] text-xs uppercase tracking-[0.18em] text-[#C7C7D1]">
                    {displayAIText(signal)}
                  </span>
                ))}
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[
                { label: 'Episodes', value: show.episode_count || episodes.length || 0 },
                { label: 'Followers', value: show.follower_count || 0 },
                { label: 'Plays', value: show.total_play_count || 0 },
                { label: 'Rhythm', value: show.cadence_label || (show.latest_episode_at ? new Date(show.latest_episode_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'New') },
              ].map((stat) => (
                <div key={stat.label} className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-1">{stat.label}</p>
                  <p className="font-['Outfit'] text-xl font-semibold text-white">{stat.value}</p>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-3">
              {latestEpisode && (
                <button
                  onClick={() => {
                    if (!user) {
                      toast.message('Create a free account to play full episodes and keep your listening history.');
                      navigate('/register');
                      return;
                    }
                    playCollection(episodes, 0, {
                      startTime: latestEpisode.resume_position_seconds || latestEpisode.progress_seconds || 0,
                    });
                  }}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
                  data-testid="show-play-latest-btn"
                >
                  <Play weight="fill" className="w-5 h-5" />
                  {user ? 'Play Latest Episode' : 'Sign up to play'}
                </button>
              )}
              <button
                onClick={handleFollowToggle}
                className={`font-bold rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors ${
                  isOwnShow
                    ? 'bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93]'
                    : show.is_following
                      ? 'bg-[#0A0A0B] border border-[#F5A623]/50 text-white hover:border-[#F5A623]'
                      : 'bg-[#0A0A0B] border border-[#27272A] text-white hover:border-[#F5A623]'
                }`}
                disabled={isOwnShow}
                data-testid="show-follow-toggle"
              >
                <UsersThree className="w-5 h-5" />
                {isOwnShow ? 'You run this show' : show.is_following ? 'Following this show' : user ? 'Follow show' : 'Sign up to follow'}
              </button>
            </div>

            {!user && (
              <div className="mt-6 rounded-2xl border border-[#27272A] bg-[#0A0A0B] px-4 py-4">
                <p className="text-sm text-white mb-1">Members can follow this show, play full episodes, save listens, and get new releases in Home.</p>
                <Link to="/register" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                  Create your listener account
                </Link>
              </div>
            )}
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-['Outfit'] text-2xl font-semibold text-white">Episodes</h2>
            <p className="text-sm text-[#8A8A93]">{episodes.length} published</p>
          </div>

          {episodes.length > 0 ? (
            <div className="space-y-10">
              {seasonGroups.map((group) => (
                <div key={group.label}>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-['Outfit'] text-lg font-semibold text-white">{group.label}</h3>
                    <span className="text-sm text-[#8A8A93]">{group.episodes.length} episodes</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    {group.episodes.map((episode) => (
                      <PodcastCard
                        key={episode.id}
                        podcast={episode}
                        onHide={(hiddenId) => setEpisodes((prev) => prev.filter((item) => item.id !== hiddenId))}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-10 text-center">
              <p className="text-[#8A8A93]">This show does not have published episodes yet.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
