import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { usePlayer } from '../contexts/PlayerContext';
import { BookmarkSimple, Eye, EyeSlash, Headphones, Play, Star, Waveform } from '@phosphor-icons/react';
import { API } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { hidePodcast, restorePodcast, savePodcast, unsavePodcast } from '../lib/library';

export default function PodcastCard({ podcast, onHide, onSaveChange }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { playPodcast, currentPodcast, addToQueue, playNext } = usePlayer();
  const isActive = currentPodcast?.id === podcast.id;
  const isPlayable = podcast.is_playable !== false;
  const showListenerActions = user?.role === 'user' && podcast.publication_status !== 'draft';
  const [isSaved, setIsSaved] = useState(Boolean(podcast.is_saved));
  const [isHidden, setIsHidden] = useState(Boolean(podcast.is_hidden));

  const thumbnailUrl = `${API}/podcasts/${podcast.id}/thumbnail`;

  useEffect(() => {
    setIsSaved(Boolean(podcast.is_saved));
    setIsHidden(Boolean(podcast.is_hidden));
  }, [podcast.id, podcast.is_hidden, podcast.is_saved]);

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const handleSaveToggle = async (event) => {
    event.stopPropagation();

    if (!user) {
      toast.message('Create an account to save episodes for later.');
      navigate('/register');
      return;
    }

    const nextSaved = !isSaved;
    setIsSaved(nextSaved);

    try {
      if (nextSaved) {
        await savePodcast(podcast.id);
        toast.success('Saved for later');
      } else {
        await unsavePodcast(podcast.id);
        toast.success('Removed from saved');
      }
      onSaveChange?.(podcast.id, nextSaved);
    } catch (error) {
      setIsSaved(!nextSaved);
      toast.error(error.response?.data?.detail || 'Could not update saved state');
    }
  };

  const handleHideToggle = async (event) => {
    event.stopPropagation();

    if (!user) {
      toast.message('Create an account to tune recommendations.');
      navigate('/register');
      return;
    }

    const nextHidden = !isHidden;
    setIsHidden(nextHidden);
    if (nextHidden) {
      setIsSaved(false);
    }

    try {
      if (nextHidden) {
        await hidePodcast(podcast.id);
        toast.success('We will show less like this');
        onHide?.(podcast.id);
      } else {
        await restorePodcast(podcast.id);
        toast.success('Episode restored to your feed');
      }
    } catch (error) {
      setIsHidden(!nextHidden);
      setIsSaved(Boolean(podcast.is_saved));
      toast.error(error.response?.data?.detail || 'Could not update your feed preferences');
    }
  };

  const handleQueue = (event, mode) => {
    event.stopPropagation();
    if (mode === 'next') {
      playNext(podcast);
      toast.success('Added to play next');
      return;
    }
    addToQueue(podcast);
    toast.success('Added to queue');
  };

  if (isHidden) {
    return null;
  }

  return (
    <div
      className={`bg-[#141417] border rounded-xl overflow-hidden transition-all duration-300 hover:-translate-y-1 cursor-pointer group ${
        isActive ? 'border-[#F5A623] shadow-[0_0_20px_rgba(245,166,35,0.15)]' : 'border-[#27272A] hover:border-[#8A8A93]/50'
      }`}
      onClick={() => navigate(`/episodes/${podcast.id}`)}
      data-testid={`podcast-card-${podcast.id}`}
    >
      <div className="aspect-video relative bg-[#0A0A0B] overflow-hidden">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={podcast.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#F5A623]/10 to-[#141417]">
            <Headphones weight="duotone" className="w-12 h-12 text-[#F5A623]/40" />
          </div>
        )}

        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center">
          {isPlayable ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                playPodcast(podcast, {
                  startTime: podcast.resume_position_seconds || podcast.progress_seconds || 0,
                });
              }}
              className={`w-12 h-12 rounded-full bg-[#F5A623] flex items-center justify-center transition-all ${
                isActive ? 'scale-100 opacity-100' : 'scale-75 opacity-0 group-hover:scale-100 group-hover:opacity-100'
              }`}
              data-testid={`podcast-card-play-${podcast.id}`}
            >
              {isActive ? (
                <Waveform weight="bold" className="w-5 h-5 text-[#0A0A0B]" />
              ) : (
                <Play weight="fill" className="w-5 h-5 text-[#0A0A0B] ml-0.5" />
              )}
            </button>
          ) : (
            <div className="px-3 py-1.5 rounded-full bg-[#0A0A0B]/80 border border-[#27272A] text-[11px] uppercase tracking-[0.16em] font-semibold text-white">
              AI draft
            </div>
          )}
        </div>

        <span className="absolute top-2 left-2 bg-[#27272A]/90 text-[10px] text-white px-2.5 py-0.5 rounded-full uppercase tracking-widest font-bold backdrop-blur-sm">
          {podcast.publication_status === 'draft' ? 'draft' : (podcast.media_type || 'audio')}
        </span>
        {podcast.audience_rating === '18+' && (
          <span className="absolute top-2 right-2 bg-[#7C2D12]/90 text-[10px] text-white px-2.5 py-0.5 rounded-full uppercase tracking-widest font-bold backdrop-blur-sm">
            18+
          </span>
        )}
      </div>

      <div className="p-4">
        <p className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2 truncate">
          {podcast.show_title || podcast.podcaster_name}
        </p>
        <h3 className="font-['Outfit'] text-base font-medium text-white truncate mb-1" title={podcast.title}>
          {podcast.title}
        </h3>
        <p className="text-xs text-[#8A8A93] mb-2 truncate">{podcast.podcaster_name}</p>
        {podcast.recommendation_reason && (
          <p className="text-xs text-[#F5A623] mb-2 line-clamp-2">{podcast.recommendation_reason}</p>
        )}
        {podcast.description && (
          <p className="text-xs text-[#8A8A93] line-clamp-2 mb-3 leading-relaxed">{podcast.description}</p>
        )}
        {podcast.progress_percent > 0 && !podcast.is_completed && (
          <div className="mb-3">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.16em] text-[#8A8A93] mb-1">
              <span>Continue listening</span>
              <span>{Math.round(podcast.progress_percent)}%</span>
            </div>
            <div className="h-1.5 bg-[#27272A] rounded-full overflow-hidden">
              <div className="h-full bg-[#F5A623]" style={{ width: `${podcast.progress_percent}%` }} />
            </div>
          </div>
        )}
        {podcast.quality_signals?.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {podcast.quality_signals.slice(0, 2).map((signal) => (
              <span key={signal} className="bg-[#0A0A0B] border border-[#27272A] text-[10px] text-[#C7C7D1] px-2 py-0.5 rounded-full uppercase tracking-[0.16em]">
                {signal}
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            {podcast.category && (
              <span className="bg-[#27272A] text-[10px] text-white px-2.5 py-0.5 rounded-full uppercase tracking-widest font-bold">
                {podcast.category}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-[#8A8A93]">
            <span className="flex items-center gap-1">
              <Eye className="w-3 h-3" />
              {podcast.view_count || podcast.play_count || 0}
            </span>
            {podcast.rating_count > 0 && (
              <span className="flex items-center gap-1">
                <Star weight="fill" className="w-3 h-3 text-[#F5A623]" />
                {podcast.rating_average}
              </span>
            )}
            <span>{formatDate(podcast.created_at)}</span>
          </div>
        </div>
        {isPlayable && (
          <div className="flex items-center gap-2 mt-4 flex-wrap">
            <button
              type="button"
              onClick={(event) => handleQueue(event, 'next')}
              className="rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] bg-[#0A0A0B] border border-[#27272A] text-white hover:border-[#F5A623] transition-colors"
              data-testid={`podcast-next-${podcast.id}`}
            >
              Play next
            </button>
            <button
              type="button"
              onClick={(event) => handleQueue(event, 'queue')}
              className="rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93] hover:text-white hover:border-[#F5A623] transition-colors"
              data-testid={`podcast-queue-${podcast.id}`}
            >
              Queue
            </button>
          </div>
        )}
        {showListenerActions && (
          <div className="flex items-center gap-2 mt-4">
            <button
              type="button"
              onClick={handleSaveToggle}
              className={`rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] transition-colors ${
                isSaved
                  ? 'bg-[#F5A623] text-[#0A0A0B]'
                  : 'bg-[#0A0A0B] border border-[#27272A] text-white hover:border-[#F5A623]'
              }`}
              data-testid={`podcast-save-${podcast.id}`}
            >
              <span className="inline-flex items-center gap-1.5">
                <BookmarkSimple weight={isSaved ? 'fill' : 'regular'} className="w-3.5 h-3.5" />
                {isSaved ? 'Saved' : 'Save'}
              </span>
            </button>
            <button
              type="button"
              onClick={handleHideToggle}
              className="rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93] hover:text-white hover:border-[#F5A623] transition-colors"
              data-testid={`podcast-hide-${podcast.id}`}
            >
              <span className="inline-flex items-center gap-1.5">
                <EyeSlash className="w-3.5 h-3.5" />
                Not for me
              </span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
