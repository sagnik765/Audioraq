import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowLeft, BookmarkSimple, Broadcast, Eye, EyeSlash, Heart, Play, Star } from '@phosphor-icons/react';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import {
  authRequest,
  clearPodcastRating,
  followShow,
  hidePodcast,
  likePodcast,
  ratePodcast,
  restorePodcast,
  savePodcast,
  unfollowShow,
  unlikePodcast,
  unsavePodcast,
} from '../lib/library';

export default function EpisodeDetailPage() {
  const { podcastId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { currentPodcast, playPodcast, addToQueue, playNext } = usePlayer();
  const [episode, setEpisode] = useState(null);
  const [related, setRelated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accessRestricted, setAccessRestricted] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function fetchEpisode() {
      setLoading(true);
      try {
        const [episodeRes, relatedRes] = await Promise.all([
          axios.get(`${API}/podcasts/${podcastId}`, authRequest),
          axios.get(`${API}/podcasts/${podcastId}/related`, authRequest).catch(() => ({ data: { podcasts: [] } })),
        ]);
        if (!cancelled) {
          setAccessRestricted(false);
          setEpisode(episodeRes.data);
          setRelated(relatedRes.data.podcasts || []);
        }
      } catch (error) {
        if (!cancelled) {
          setAccessRestricted(error.response?.status === 403);
          setEpisode(false);
          setRelated([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchEpisode();
    return () => { cancelled = true; };
  }, [podcastId]);

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

  if (!episode) {
    return (
      <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`}>
        <Navbar />
        <main className="max-w-5xl mx-auto px-6 md:px-8 lg:px-12 py-12">
          <Link to="/browse" className="inline-flex items-center gap-2 text-sm text-[#8A8A93] hover:text-white transition-colors mb-8">
            <ArrowLeft className="w-4 h-4" />
            Back to browse
          </Link>
          <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-12 text-center">
            <h1 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">{accessRestricted ? 'Episode restricted' : 'Episode not found'}</h1>
            <p className="text-[#8A8A93]">
              {accessRestricted ? 'This episode is currently restricted for your account.' : 'It may have been removed or is no longer available.'}
            </p>
          </div>
        </main>
      </div>
    );
  }

  const thumbnailUrl = (episode.thumbnail_path || episode.show_thumbnail_path || episode.external_thumbnail_url) ? `${API}/podcasts/${episode.id}/thumbnail` : null;
  const isOwnShow = Boolean(user && episode.podcaster_id === user.id);
  const canEngage = user?.role === 'user' && episode.publication_status !== 'draft';
  const canPlayEpisode = episode.is_playable !== false;

  const handleSaveToggle = async () => {
    if (!user) return;
    const nextSaved = !episode.is_saved;
    setEpisode((prev) => ({ ...prev, is_saved: nextSaved }));
    try {
      if (nextSaved) {
        await savePodcast(episode.id);
        toast.success('Saved for later');
      } else {
        await unsavePodcast(episode.id);
        toast.success('Removed from saved');
      }
    } catch (error) {
      setEpisode((prev) => ({ ...prev, is_saved: !nextSaved }));
      toast.error(error.response?.data?.detail || 'Could not update saved state');
    }
  };

  const handleHideToggle = async () => {
    if (!user) return;
    const nextHidden = !episode.is_hidden;
    setEpisode((prev) => ({ ...prev, is_hidden: nextHidden, is_saved: nextHidden ? false : prev.is_saved }));
    try {
      if (nextHidden) {
        await hidePodcast(episode.id);
        setRelated((prev) => prev.filter((item) => item.id !== episode.id));
        toast.success('We will show less like this');
      } else {
        await restorePodcast(episode.id);
        toast.success('Episode restored to your feed');
      }
    } catch (error) {
      setEpisode((prev) => ({ ...prev, is_hidden: !nextHidden, is_saved: episode.is_saved }));
      toast.error(error.response?.data?.detail || 'Could not update your feed preferences');
    }
  };

  const handleFollowToggle = async () => {
    if (!user || isOwnShow || !episode.show_id) return;
    const nextFollowing = !episode.is_following_show;
    setEpisode((prev) => ({
      ...prev,
      is_following_show: nextFollowing,
      show: prev.show ? { ...prev.show, is_following: nextFollowing, follower_count: Math.max(0, (prev.show.follower_count || 0) + (nextFollowing ? 1 : -1)) } : prev.show,
    }));

    try {
      if (nextFollowing) {
        await followShow(episode.show_id);
        toast.success('Show followed');
      } else {
        await unfollowShow(episode.show_id);
        toast.success('Show unfollowed');
      }
    } catch (error) {
      setEpisode((prev) => ({
        ...prev,
        is_following_show: !nextFollowing,
        show: prev.show ? { ...prev.show, is_following: !nextFollowing, follower_count: Math.max(0, (prev.show.follower_count || 0) + (nextFollowing ? -1 : 1)) } : prev.show,
      }));
      toast.error(error.response?.data?.detail || 'Could not update follow status');
    }
  };

  const handleLikeToggle = async () => {
    if (!user) {
      toast.message('Create an account to like episodes and rate them later.');
      navigate('/register');
      return;
    }
    const nextLiked = !episode.is_liked;
    setEpisode((prev) => ({ ...prev, is_liked: nextLiked, like_count: Math.max(0, (prev.like_count || 0) + (nextLiked ? 1 : -1)) }));
    try {
      const response = nextLiked ? await likePodcast(episode.id) : await unlikePodcast(episode.id);
      setEpisode((prev) => ({ ...prev, like_count: response.like_count ?? prev.like_count }));
    } catch (error) {
      setEpisode((prev) => ({ ...prev, is_liked: !nextLiked, like_count: Math.max(0, (prev.like_count || 0) + (nextLiked ? -1 : 1)) }));
      toast.error(error.response?.data?.detail || 'Could not update like');
    }
  };

  const handleRating = async (nextRating) => {
    if (!user) {
      toast.message('Create an account to leave ratings.');
      navigate('/register');
      return;
    }
    const previousRating = episode.viewer_rating || 0;
    const shouldClear = previousRating === nextRating;
    setEpisode((prev) => ({ ...prev, viewer_rating: shouldClear ? 0 : nextRating }));
    try {
      const response = shouldClear
        ? await clearPodcastRating(episode.id)
        : await ratePodcast(episode.id, nextRating);
      setEpisode((prev) => ({
        ...prev,
        viewer_rating: response.viewer_rating ?? (shouldClear ? 0 : nextRating),
        rating_average: response.rating_average ?? prev.rating_average,
        rating_count: response.rating_count ?? prev.rating_count,
      }));
      toast.success(shouldClear ? 'Rating cleared' : 'Rating saved');
    } catch (error) {
      setEpisode((prev) => ({ ...prev, viewer_rating: previousRating }));
      toast.error(error.response?.data?.detail || 'Could not update rating');
    }
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="episode-detail-page">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 md:px-8 lg:px-12 py-10">
        <Link to="/browse" className="inline-flex items-center gap-2 text-sm text-[#8A8A93] hover:text-white transition-colors mb-8">
          <ArrowLeft className="w-4 h-4" />
          Back to browse
        </Link>

        <section className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-8 mb-12">
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl overflow-hidden">
            <div className="aspect-video bg-[#0A0A0B]">
              {thumbnailUrl ? (
                <img src={thumbnailUrl} alt={episode.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-[#F5A623]/15 to-[#141417] flex items-center justify-center">
                  <Play weight="fill" className="w-16 h-16 text-[#F5A623]/40" />
                </div>
              )}
            </div>
          </div>

          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="flex items-center gap-2 mb-4">
              <span className="bg-[#27272A] text-[10px] text-white px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                {episode.publication_status === 'draft' ? 'draft' : (episode.media_type || 'audio')}
              </span>
              {episode.category && (
                <span className="bg-[#F5A623]/10 text-[#F5A623] text-[10px] px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                  {episode.category}
                </span>
              )}
              {episode.audience_rating === '18+' && (
                <span className="bg-[#7C2D12]/20 text-[#FDBA74] text-[10px] px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                  18+
                </span>
              )}
            </div>

            <h1 className="font-['Outfit'] text-3xl md:text-4xl tracking-tight font-bold text-white mb-3">
              {episode.title}
            </h1>

            <div className="space-y-2 mb-6">
              <Link
                to={`/shows/${episode.show_id}`}
                className="inline-flex items-center gap-2 text-[#F5A623] hover:text-[#F7B84B] transition-colors"
              >
                <Broadcast className="w-4 h-4" />
                {episode.show_title || episode.podcaster_name}
              </Link>
              <p className="text-sm text-[#8A8A93]">Hosted by {episode.podcaster_name}</p>
            </div>

            {episode.recommendation_reason && (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-3 mb-6">
                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-1">Why this is here</p>
                <p className="text-sm text-white">{episode.recommendation_reason}</p>
              </div>
            )}

            <p className="text-sm text-[#C7C7D1] leading-relaxed whitespace-pre-wrap mb-8">
              {episode.description || 'No episode notes yet.'}
            </p>

            <div className="grid grid-cols-3 gap-3 mb-6">
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Views</p>
                <p className="font-['Outfit'] text-2xl font-semibold text-white">{episode.view_count || episode.play_count || 0}</p>
              </div>
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Likes</p>
                <p className="font-['Outfit'] text-2xl font-semibold text-white">{episode.like_count || 0}</p>
              </div>
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Rating</p>
                <p className="font-['Outfit'] text-2xl font-semibold text-white">
                  {episode.rating_count > 0 ? `${episode.rating_average} / 5` : 'Unrated'}
                </p>
              </div>
            </div>

            {episode.moderation_summary && (isOwnShow || user?.role === 'admin') && (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4 mb-6">
                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-1">Safety review</p>
                <p className="text-sm text-white mb-2">{episode.moderation_summary}</p>
                <p className="text-xs text-[#8A8A93] uppercase tracking-[0.16em]">
                  Status: {episode.moderation_status || 'clear'}
                </p>
              </div>
            )}

            {episode.progress_percent > 0 && !episode.is_completed && (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4 mb-6">
                <div className="flex items-center justify-between text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">
                  <span>Continue listening</span>
                  <span>{Math.round(episode.progress_percent)}%</span>
                </div>
                <div className="h-2 bg-[#27272A] rounded-full overflow-hidden">
                  <div className="h-full bg-[#F5A623]" style={{ width: `${episode.progress_percent}%` }} />
                </div>
              </div>
            )}

            {episode.quality_signals?.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-6">
                {episode.quality_signals.map((signal) => (
                  <span key={signal} className="px-3 py-1 rounded-full bg-[#0A0A0B] border border-[#27272A] text-xs uppercase tracking-[0.18em] text-[#C7C7D1]">
                    {signal}
                  </span>
                ))}
              </div>
            )}

            {episode.is_hidden && (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-3 mb-6">
                <p className="text-sm text-white">This episode is hidden from your recommendations and browse feed.</p>
              </div>
            )}

            <div className="flex flex-wrap gap-3 mb-6">
              {canPlayEpisode ? (
                <button
                  onClick={() => playPodcast(episode, {
                    startTime: episode.resume_position_seconds || episode.progress_seconds || 0,
                  })}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
                  data-testid="episode-play-btn"
                >
                  <Play weight="fill" className="w-5 h-5" />
                  {episode.progress_percent > 0 && !episode.is_completed ? 'Resume Episode' : 'Play Episode'}
                </button>
              ) : (
                <div className="bg-[#0A0A0B] border border-[#27272A] text-white rounded-full px-6 py-3 inline-flex items-center gap-2">
                  <Play className="w-5 h-5" />
                  AI draft only
                </div>
              )}
              <Link
                to={`/shows/${episode.show_id}`}
                className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
              >
                <Broadcast className="w-5 h-5" />
                Visit Show
              </Link>
              {canPlayEpisode && (
                <>
                  <button
                    onClick={() => {
                      playNext(episode);
                      toast.success('Added to play next');
                    }}
                    className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
                    data-testid="episode-play-next-btn"
                  >
                    <Play className="w-5 h-5" />
                    Play Next
                  </button>
                  <button
                    onClick={() => {
                      addToQueue(episode);
                      toast.success('Added to queue');
                    }}
                    className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
                    data-testid="episode-queue-btn"
                  >
                    <Play className="w-5 h-5" />
                    Add to Queue
                  </button>
                </>
              )}
              {canEngage && (
                <>
                  <button
                    onClick={handleSaveToggle}
                    className={`rounded-full px-6 py-3 inline-flex items-center gap-2 font-bold transition-colors ${
                      episode.is_saved
                        ? 'bg-[#F5A623] text-[#0A0A0B]'
                        : 'bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white'
                    }`}
                    data-testid="episode-save-btn"
                  >
                    <BookmarkSimple weight={episode.is_saved ? 'fill' : 'regular'} className="w-5 h-5" />
                    {episode.is_saved ? 'Saved' : 'Save for later'}
                  </button>
                  <button
                    onClick={handleHideToggle}
                    className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
                    data-testid="episode-hide-btn"
                  >
                    <EyeSlash className="w-5 h-5" />
                    {episode.is_hidden ? 'Restore to feed' : 'Not interested'}
                  </button>
                  {!isOwnShow && (
                    <button
                      onClick={handleFollowToggle}
                      className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 inline-flex items-center gap-2 transition-colors"
                      data-testid="episode-follow-show-btn"
                    >
                      <Broadcast className="w-5 h-5" />
                      {episode.is_following_show ? 'Following show' : 'Follow show'}
                    </button>
                  )}
                </>
              )}
            </div>

            {canEngage && (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl px-4 py-4 mb-6">
                <div className="flex flex-wrap items-center gap-3 justify-between">
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={handleLikeToggle}
                      className={`rounded-full px-4 py-2 inline-flex items-center gap-2 transition-colors ${
                        episode.is_liked
                          ? 'bg-[#F5A623] text-[#0A0A0B]'
                          : 'bg-[#141417] border border-[#27272A] text-white hover:border-[#F5A623]'
                      }`}
                    >
                      <Heart weight={episode.is_liked ? 'fill' : 'regular'} className="w-4 h-4" />
                      {episode.is_liked ? 'Liked' : 'Like'}
                    </button>
                    <div className="flex items-center gap-2 text-sm text-[#8A8A93]">
                      <Eye className="w-4 h-4" />
                      <span>{episode.view_count || episode.play_count || 0} views</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {[1, 2, 3, 4, 5].map((rating) => (
                      <button
                        key={rating}
                        type="button"
                        onClick={() => handleRating(rating)}
                        className={`w-9 h-9 rounded-full inline-flex items-center justify-center transition-colors ${
                          (episode.viewer_rating || 0) >= rating
                            ? 'bg-[#F5A623] text-[#0A0A0B]'
                            : 'bg-[#141417] border border-[#27272A] text-white hover:border-[#F5A623]'
                        }`}
                      >
                        <Star weight={(episode.viewer_rating || 0) >= rating ? 'fill' : 'regular'} className="w-4 h-4" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {episode.keywords?.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {episode.keywords.slice(0, 8).map((keyword) => (
                  <span key={keyword} className="px-3 py-1 rounded-full bg-[#0A0A0B] border border-[#27272A] text-xs text-[#8A8A93]">
                    {keyword}
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-['Outfit'] text-2xl font-semibold text-white">More to hear next</h2>
            {episode.show_id && (
              <Link to={`/shows/${episode.show_id}`} className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors">
                View full show
              </Link>
            )}
          </div>

          {related.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {related.map((item) => (
                <PodcastCard
                  key={item.id}
                  podcast={item}
                  onHide={(hiddenId) => setRelated((prev) => prev.filter((entry) => entry.id !== hiddenId))}
                />
              ))}
            </div>
          ) : (
            <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-10 text-center">
              <p className="text-[#8A8A93]">More episodes will show up here as this show grows.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
