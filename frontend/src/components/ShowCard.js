import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Broadcast, PlayCircle, UsersThree, Waveform } from '@phosphor-icons/react';
import { API } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { followShow, unfollowShow } from '../lib/library';

export default function ShowCard({ show, onFollowChange }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [isFollowing, setIsFollowing] = useState(Boolean(show.is_following));
  const [followerCount, setFollowerCount] = useState(show.follower_count || 0);
  const isOwnShow = Boolean(user && show.podcaster_id === user.id);
  const thumbnailUrl = `${API}/shows/${show.id}/thumbnail`;

  useEffect(() => {
    setIsFollowing(Boolean(show.is_following));
    setFollowerCount(show.follower_count || 0);
  }, [show.follower_count, show.id, show.is_following]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'New show';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const handleFollowToggle = async (event) => {
    event.stopPropagation();

    if (!user) {
      toast.message('Create an account to follow shows and shape your home feed.');
      navigate('/register');
      return;
    }

    if (isOwnShow) {
      return;
    }

    const nextFollowing = !isFollowing;
    const nextFollowerCount = Math.max(0, followerCount + (nextFollowing ? 1 : -1));
    setIsFollowing(nextFollowing);
    setFollowerCount(nextFollowerCount);

    try {
      if (nextFollowing) {
        await followShow(show.id);
        toast.success('Show followed');
      } else {
        await unfollowShow(show.id);
        toast.success('Show unfollowed');
      }
      onFollowChange?.(show.id, nextFollowing, {
        ...show,
        is_following: nextFollowing,
        follower_count: nextFollowerCount,
      });
    } catch (error) {
      setIsFollowing(!nextFollowing);
      setFollowerCount(followerCount);
      toast.error(error.response?.data?.detail || 'Could not update follow status');
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/shows/${show.id}`)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          navigate(`/shows/${show.id}`);
        }
      }}
      className="w-full text-left bg-[#141417] border border-[#27272A] rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:border-[#8A8A93]/50 group cursor-pointer"
      data-testid={`show-card-${show.id}`}
    >
      <div className="aspect-[16/9] bg-[#0A0A0B] relative overflow-hidden">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={show.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#F5A623]/15 to-[#141417]">
            <Broadcast weight="duotone" className="w-14 h-14 text-[#F5A623]/50" />
          </div>
        )}
        <div className="absolute top-3 left-3 bg-[#27272A]/90 text-[10px] text-white px-2.5 py-1 rounded-full uppercase tracking-widest font-bold">
          {show.category || 'show'}
        </div>
      </div>

      <div className="p-5">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <h3 className="font-['Outfit'] text-lg font-semibold text-white mb-1 line-clamp-1">{show.title}</h3>
            <p className="text-xs text-[#8A8A93]">{show.podcaster_name}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-[#F5A623] opacity-0 group-hover:opacity-100 transition-opacity">
              <Waveform weight="duotone" className="w-5 h-5" />
            </div>
            {user && (
              <button
                type="button"
                onClick={handleFollowToggle}
                className={`rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] transition-colors ${
                  isOwnShow
                    ? 'bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93]'
                    : isFollowing
                      ? 'bg-[#F5A623] text-[#0A0A0B]'
                      : 'bg-[#0A0A0B] border border-[#27272A] text-white hover:border-[#F5A623]'
                }`}
                data-testid={`show-follow-${show.id}`}
              >
                {isOwnShow ? 'Your Show' : isFollowing ? 'Following' : 'Follow'}
              </button>
            )}
          </div>
        </div>

        <p className="text-sm text-[#8A8A93] leading-relaxed line-clamp-3 min-h-[60px]">
          {show.description || 'A new show ready for its first audience.'}
        </p>

        {show.quality_signals?.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {show.quality_signals.slice(0, 3).map((signal) => (
              <span key={signal} className="px-2.5 py-1 rounded-full bg-[#0A0A0B] border border-[#27272A] text-[10px] uppercase tracking-[0.16em] text-[#C7C7D1]">
                {signal}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mt-5 text-xs text-[#8A8A93]">
          <div className="flex items-center gap-4 flex-wrap">
            <span className="flex items-center gap-1">
              <PlayCircle weight="fill" className="w-3.5 h-3.5" />
              {show.episode_count || 0} episodes
            </span>
            <span className="flex items-center gap-1">
              <UsersThree weight="duotone" className="w-3.5 h-3.5" />
              {followerCount} followers
            </span>
            <span>{show.total_play_count || 0} plays</span>
          </div>
          <span>{show.cadence_label || formatDate(show.latest_episode_at || show.created_at)}</span>
        </div>
      </div>
    </div>
  );
}
