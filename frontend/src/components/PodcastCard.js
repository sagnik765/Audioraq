import React from 'react';
import { usePlayer } from '../contexts/PlayerContext';
import { Play, Headphones, Waveform } from '@phosphor-icons/react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PodcastCard({ podcast }) {
  const { playPodcast, currentPodcast } = usePlayer();
  const isActive = currentPodcast?.id === podcast.id;

  const thumbnailUrl = podcast.thumbnail_path
    ? `${API}/podcasts/${podcast.id}/thumbnail`
    : null;

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div
      className={`bg-[#141417] border rounded-xl overflow-hidden transition-all duration-300 hover:-translate-y-1 cursor-pointer group ${
        isActive ? 'border-[#F5A623] shadow-[0_0_20px_rgba(245,166,35,0.15)]' : 'border-[#27272A] hover:border-[#8A8A93]/50'
      }`}
      onClick={() => playPodcast(podcast)}
      data-testid={`podcast-card-${podcast.id}`}
    >
      {/* Thumbnail */}
      <div className="aspect-video relative bg-[#0A0A0B] overflow-hidden">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={podcast.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#F5A623]/10 to-[#141417]">
            <Headphones weight="duotone" className="w-12 h-12 text-[#F5A623]/40" />
          </div>
        )}
        {/* Play overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center">
          <div className={`w-12 h-12 rounded-full bg-[#F5A623] flex items-center justify-center transition-all ${
            isActive ? 'scale-100 opacity-100' : 'scale-75 opacity-0 group-hover:scale-100 group-hover:opacity-100'
          }`}>
            {isActive ? (
              <Waveform weight="bold" className="w-5 h-5 text-[#0A0A0B]" />
            ) : (
              <Play weight="fill" className="w-5 h-5 text-[#0A0A0B] ml-0.5" />
            )}
          </div>
        </div>
        {/* Media type badge */}
        <span className="absolute top-2 left-2 bg-[#27272A]/90 text-[10px] text-white px-2.5 py-0.5 rounded-full uppercase tracking-widest font-bold backdrop-blur-sm">
          {podcast.media_type || 'audio'}
        </span>
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="font-['Outfit'] text-base font-medium text-white truncate mb-1" title={podcast.title}>
          {podcast.title}
        </h3>
        <p className="text-xs text-[#8A8A93] mb-2 truncate">{podcast.podcaster_name}</p>
        {podcast.description && (
          <p className="text-xs text-[#8A8A93] line-clamp-2 mb-3 leading-relaxed">{podcast.description}</p>
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
              <Play weight="fill" className="w-3 h-3" />
              {podcast.play_count || 0}
            </span>
            <span>{formatDate(podcast.created_at)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
