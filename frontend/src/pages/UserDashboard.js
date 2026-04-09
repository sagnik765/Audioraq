import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { BookmarkSimple, Broadcast, Fire, MagnifyingGlass, Sparkle } from '@phosphor-icons/react';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import ShowCard from '../components/ShowCard';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';
import { authRequest } from '../lib/library';

function upsertById(items, item) {
  const withoutItem = items.filter((entry) => entry.id !== item.id);
  return [item, ...withoutItem];
}

export default function UserDashboard() {
  const { user } = useAuth();
  const { currentPodcast } = usePlayer();
  const [recommended, setRecommended] = useState([]);
  const [trending, setTrending] = useState([]);
  const [recentEpisodes, setRecentEpisodes] = useState([]);
  const [continueListening, setContinueListening] = useState([]);
  const [listeningHistory, setListeningHistory] = useState([]);
  const [suggestedShows, setSuggestedShows] = useState([]);
  const [followedShows, setFollowedShows] = useState([]);
  const [followedEpisodes, setFollowedEpisodes] = useState([]);
  const [savedEpisodes, setSavedEpisodes] = useState([]);
  const [recMethod, setRecMethod] = useState('');
  const [recommendationSort, setRecommendationSort] = useState('smart');
  const [loading, setLoading] = useState(true);

  const removeEpisodeEverywhere = useCallback((podcastId) => {
    const removeById = (items) => items.filter((item) => item.id !== podcastId);
    setRecommended(removeById);
    setTrending(removeById);
    setRecentEpisodes(removeById);
    setContinueListening(removeById);
    setListeningHistory(removeById);
    setFollowedEpisodes(removeById);
    setSavedEpisodes(removeById);
  }, []);

  const handleSaveStateChange = useCallback((podcast, nextSaved) => {
    setSavedEpisodes((prev) => {
      if (!nextSaved) {
        return prev.filter((item) => item.id !== podcast.id);
      }
      return upsertById(prev, { ...podcast, is_saved: true }).slice(0, 4);
    });
  }, []);

  const handleShowFollowChange = useCallback((showId, nextFollowing, showData) => {
    const normalizedShow = {
      ...showData,
      is_following: nextFollowing,
    };

    setSuggestedShows((prev) => {
      if (nextFollowing) {
        return prev.filter((show) => show.id !== showId);
      }
      return upsertById(prev, normalizedShow).slice(0, 4);
    });

    setFollowedShows((prev) => {
      if (nextFollowing) {
        return upsertById(prev, normalizedShow).slice(0, 4);
      }
      return prev.filter((show) => show.id !== showId);
    });

    if (!nextFollowing) {
      setFollowedEpisodes((prev) => prev.filter((episode) => episode.show_id !== showId));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchHome() {
      setLoading(true);
      try {
        const [
          recRes,
          trendRes,
          recentRes,
          continueRes,
          historyRes,
          showsRes,
          followingShowsRes,
          followingEpisodesRes,
          savedRes,
        ] = await Promise.all([
          axios.get(
            `${API}/recommendations${recommendationSort !== 'smart' ? `?sort=${encodeURIComponent(recommendationSort)}` : ''}`,
            authRequest,
          ).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/trending`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/podcasts?sort=recent&limit=8`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/listening/continue?limit=4`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/listening/history?limit=6`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/shows?limit=4`, authRequest).catch(() => ({ data: { shows: [] } })),
          axios.get(`${API}/shows/following?limit=4`, authRequest).catch(() => ({ data: { shows: [] } })),
          axios.get(`${API}/podcasts?following_only=true&sort=recent&limit=8`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/podcasts/saved?limit=4`, authRequest).catch(() => ({ data: { podcasts: [] } })),
        ]);

        if (!cancelled) {
          const followed = followingShowsRes.data.shows || [];
          const followedIds = new Set(followed.map((show) => show.id));

          setRecommended(recRes.data.podcasts || []);
          setRecMethod(recRes.data.method || '');
          setTrending(trendRes.data.podcasts || []);
          setRecentEpisodes(recentRes.data.podcasts || []);
          setContinueListening(continueRes.data.podcasts || []);
          setListeningHistory(historyRes.data.podcasts || []);
          setFollowedShows(followed);
          setFollowedEpisodes(followingEpisodesRes.data.podcasts || []);
          setSavedEpisodes(savedRes.data.podcasts || []);
          setSuggestedShows((showsRes.data.shows || []).filter((show) => !followedIds.has(show.id)).slice(0, 4));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchHome();
    return () => { cancelled = true; };
  }, [recommendationSort]);

  const displayName = user?.name?.split(' ')[0] || 'there';
  const visibleInterests = user?.interests?.slice(0, 3) || [];

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="user-dashboard">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 md:p-10 mb-10 overflow-hidden relative">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(245,166,35,0.12),transparent_35%)]" />
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8">
            <div className="max-w-2xl">
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-3">Your Home Feed</p>
              <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-3">
                Welcome back, {displayName}
              </h1>
              <p className="text-[#8A8A93] leading-relaxed mb-5">
                Audioraq is shaping this feed around the shows you follow, the episodes you save, and the topics you told us matter.
              </p>
              {visibleInterests.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm text-white mb-3">
                    Picked for you because you chose {visibleInterests.join(', ')}.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {visibleInterests.map((interest) => (
                      <span key={interest} className="px-3 py-1 rounded-full bg-[#0A0A0B] border border-[#27272A] text-xs text-[#8A8A93]">
                        {interest}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                to="/browse"
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors inline-flex items-center gap-2"
              >
                <MagnifyingGlass className="w-5 h-5" />
                Explore Browse
              </Link>
              <Link
                to="/settings"
                className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
              >
                Refine Interests
              </Link>
            </div>
          </div>
        </section>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {(followedShows.length === 0 || savedEpisodes.length === 0) && (
              <section className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-12">
                {followedShows.length === 0 && (
                  <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-6">
                    <div className="flex items-center gap-3 mb-3">
                      <Broadcast className="w-5 h-5 text-[#F5A623]" />
                      <h2 className="font-['Outfit'] text-xl font-semibold text-white">Follow a few shows</h2>
                    </div>
                    <p className="text-sm text-[#8A8A93] mb-5">
                      Following turns Audioraq into a real listening home instead of a one-off browse session. Start with a few strong shows and new releases will land here automatically.
                    </p>
                    <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                      Find shows to follow
                    </Link>
                  </div>
                )}

                {savedEpisodes.length === 0 && (
                  <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-6">
                    <div className="flex items-center gap-3 mb-3">
                      <BookmarkSimple className="w-5 h-5 text-[#F5A623]" />
                      <h2 className="font-['Outfit'] text-xl font-semibold text-white">Build your listen-later shelf</h2>
                    </div>
                    <p className="text-sm text-[#8A8A93] mb-5">
                      Save episodes the moment you discover them. That keeps good long-form finds from disappearing before you have time to actually listen.
                    </p>
                    <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                      Save a few episodes
                    </Link>
                  </div>
                )}
              </section>
            )}

            {followedEpisodes.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Broadcast className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">New from shows you follow</h2>
                  </div>
                  <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                    Browse more
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {followedEpisodes.map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {continueListening.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <BookmarkSimple className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">Continue listening</h2>
                  </div>
                  <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                    Find more
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {continueListening.map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {recommended.length > 0 && (
              <section className="mb-12">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                  <div className="flex items-center gap-3">
                    <Sparkle weight="duotone" className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">Recommended for you</h2>
                    {recMethod && (
                      <span className="bg-[#27272A] text-[10px] text-white px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                        {recMethod === 'ai' ? 'AI Powered' : recMethod}
                      </span>
                    )}
                  </div>
                  <select
                    value={recommendationSort}
                    onChange={(event) => setRecommendationSort(event.target.value)}
                    className="bg-[#0A0A0B] border border-[#27272A] rounded-full px-4 py-2 text-sm text-white outline-none"
                  >
                    <option value="smart">Smart mix</option>
                    <option value="highest_rated">Highest rated</option>
                    <option value="most_viewed">Most viewed</option>
                  </select>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {recommended.slice(0, 8).map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {savedEpisodes.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <BookmarkSimple className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">Saved for later</h2>
                  </div>
                  <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                    Find more
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {savedEpisodes.map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {followedShows.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Broadcast className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">Shows you are following</h2>
                  </div>
                  <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                    Discover more
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                  {followedShows.map((show) => (
                    <ShowCard key={show.id} show={show} onFollowChange={handleShowFollowChange} />
                  ))}
                </div>
              </section>
            )}

            {suggestedShows.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Sparkle weight="duotone" className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">Shows worth following</h2>
                  </div>
                  <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                    See all
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                  {suggestedShows.map((show) => (
                    <ShowCard key={show.id} show={show} onFollowChange={handleShowFollowChange} />
                  ))}
                </div>
              </section>
            )}

            {recentEpisodes.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Sparkle weight="duotone" className="text-[#F5A623] w-5 h-5" />
                    <h2 className="font-['Outfit'] text-xl font-semibold text-white">Fresh episodes</h2>
                  </div>
                  <Link to="/browse" className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                    Browse all
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {recentEpisodes.map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {trending.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <Fire weight="duotone" className="text-[#F5A623] w-5 h-5" />
                  <h2 className="font-['Outfit'] text-xl font-semibold text-white">Trending now</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {trending.slice(0, 4).map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {listeningHistory.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <Fire weight="duotone" className="text-[#F5A623] w-5 h-5" />
                  <h2 className="font-['Outfit'] text-xl font-semibold text-white">Listening history</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {listeningHistory.map((podcast) => (
                    <PodcastCard
                      key={podcast.id}
                      podcast={podcast}
                      onHide={removeEpisodeEverywhere}
                      onSaveChange={(_, nextSaved) => handleSaveStateChange(podcast, nextSaved)}
                    />
                  ))}
                </div>
              </section>
            )}

            {!recommended.length && !recentEpisodes.length && !followedEpisodes.length && !savedEpisodes.length && !continueListening.length && !listeningHistory.length && (
              <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-12 text-center">
                <h3 className="font-['Outfit'] text-xl font-semibold text-white mb-2">Your feed is just getting started</h3>
                <p className="text-[#8A8A93] mb-6">
                  Browse a few shows, save a few episodes, and tell Audioraq what does not fit. That is how the home feed starts feeling intentional.
                </p>
                <div className="flex items-center justify-center gap-3 flex-wrap">
                  <Link to="/settings" className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors">
                    Update interests
                  </Link>
                  <Link to="/browse" className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors">
                    Browse shows
                  </Link>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
