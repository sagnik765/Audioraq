import React, { useRef, useEffect, useState } from 'react';
import { usePlayer } from '../contexts/PlayerContext';
import { Play, Pause, SpeakerHigh, SpeakerSlash, SkipForward, SkipBack, X } from '@phosphor-icons/react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PlayerBar() {
  const {
    currentPodcast, isPlaying, progress, duration, volume,
    mediaRef, togglePlay, seek, setProgress, setDuration, setVolume, setIsPlaying
  } = usePlayer();

  const audioRef = useRef(null);
  const videoRef = useRef(null);
  const [showVideo, setShowVideo] = useState(false);
  const [currentPodcastState, setCurrentPodcastState] = useState(null);

  const isVideo = currentPodcast?.media_type === 'video';
  const activeRef = isVideo ? videoRef : audioRef;

  useEffect(() => {
    if (!currentPodcast) return;
    // Only reload if podcast actually changed
    if (currentPodcastState?.id === currentPodcast.id) {
      if (isPlaying && activeRef.current) {
        activeRef.current.play().catch(() => {});
      } else if (!isPlaying && activeRef.current) {
        activeRef.current.pause();
      }
      return;
    }
    setCurrentPodcastState(currentPodcast);
    setShowVideo(isVideo);

    const el = activeRef.current;
    if (!el) return;

    el.src = `${API}/podcasts/${currentPodcast.id}/stream`;
    el.volume = volume;
    el.load();

    const playPromise = el.play();
    if (playPromise) playPromise.catch(() => {});
  }, [currentPodcast, isPlaying, isVideo, volume, activeRef, currentPodcastState, setDuration]);

  useEffect(() => {
    const el = activeRef.current;
    if (!el) return;
    if (isPlaying) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [isPlaying, activeRef]);

  useEffect(() => {
    const el = activeRef.current;
    if (!el) return;
    el.volume = volume;
  }, [volume, activeRef]);

  const handleTimeUpdate = () => {
    const el = activeRef.current;
    if (el) setProgress(el.currentTime);
  };

  const handleLoadedMetadata = () => {
    const el = activeRef.current;
    if (el) setDuration(el.duration);
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setProgress(0);
  };

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const newTime = pct * duration;
    seek(newTime);
    if (activeRef.current) activeRef.current.currentTime = newTime;
  };

  const formatTime = (secs) => {
    if (!secs || isNaN(secs)) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const skipForward = () => {
    const el = activeRef.current;
    if (el) { el.currentTime = Math.min(el.currentTime + 15, duration); }
  };

  const skipBack = () => {
    const el = activeRef.current;
    if (el) { el.currentTime = Math.max(el.currentTime - 15, 0); }
  };

  if (!currentPodcast) return null;

  return (
    <>
      {/* Hidden audio element */}
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        style={{ display: 'none' }}
      />

      {/* Video modal */}
      {showVideo && isVideo && (
        <div className="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center p-4" data-testid="video-modal">
          <div className="relative max-w-4xl w-full">
            <button
              onClick={() => setShowVideo(false)}
              className="absolute -top-10 right-0 text-white hover:text-[#F5A623] transition-colors"
              data-testid="close-video-btn"
            >
              <X weight="bold" className="w-6 h-6" />
            </button>
            <video
              ref={videoRef}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={handleEnded}
              className="w-full rounded-xl"
              controls={false}
            />
          </div>
        </div>
      )}

      {/* Player Bar */}
      <div className="backdrop-blur-2xl bg-[#141417]/80 border-t border-[#27272A] fixed bottom-0 w-full z-50 shadow-[0_-8px_32px_rgba(0,0,0,0.4)]" data-testid="player-bar">
        {/* Progress bar */}
        <div
          className="h-1 bg-[#27272A] cursor-pointer group"
          onClick={handleSeek}
          data-testid="progress-bar"
        >
          <div
            className="h-full bg-[#F5A623] transition-all duration-100 relative"
            style={{ width: duration ? `${(progress / duration) * 100}%` : '0%' }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#F5A623] opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
          {/* Podcast Info */}
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className="w-10 h-10 rounded-lg bg-[#F5A623]/10 flex-shrink-0 flex items-center justify-center overflow-hidden">
              {currentPodcast.thumbnail_path ? (
                <img src={`${API}/podcasts/${currentPodcast.id}/thumbnail`} alt="" className="w-full h-full object-cover" />
              ) : (
                <Play weight="fill" className="w-4 h-4 text-[#F5A623]" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{currentPodcast.title}</p>
              <p className="text-xs text-[#8A8A93] truncate">{currentPodcast.podcaster_name}</p>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-4">
            <button onClick={skipBack} className="text-[#8A8A93] hover:text-white transition-colors" data-testid="skip-back-btn">
              <SkipBack weight="fill" className="w-5 h-5" />
            </button>
            <button
              onClick={togglePlay}
              className="w-10 h-10 rounded-full bg-[#F5A623] hover:bg-[#F7B84B] flex items-center justify-center transition-colors"
              data-testid="play-pause-btn"
            >
              {isPlaying ? (
                <Pause weight="fill" className="w-5 h-5 text-[#0A0A0B]" />
              ) : (
                <Play weight="fill" className="w-5 h-5 text-[#0A0A0B] ml-0.5" />
              )}
            </button>
            <button onClick={skipForward} className="text-[#8A8A93] hover:text-white transition-colors" data-testid="skip-forward-btn">
              <SkipForward weight="fill" className="w-5 h-5" />
            </button>
          </div>

          {/* Time */}
          <div className="hidden sm:flex items-center gap-2 text-xs text-[#8A8A93] min-w-[100px]">
            <span>{formatTime(progress)}</span>
            <span>/</span>
            <span>{formatTime(duration)}</span>
          </div>

          {/* Volume */}
          <div className="hidden md:flex items-center gap-2">
            <button
              onClick={() => setVolume(volume > 0 ? 0 : 0.8)}
              className="text-[#8A8A93] hover:text-white transition-colors"
              data-testid="mute-btn"
            >
              {volume > 0 ? <SpeakerHigh weight="fill" className="w-4 h-4" /> : <SpeakerSlash weight="fill" className="w-4 h-4" />}
            </button>
            <input
              type="range" min="0" max="1" step="0.05" value={volume}
              onChange={e => setVolume(parseFloat(e.target.value))}
              className="w-20 accent-[#F5A623]"
              data-testid="volume-slider"
            />
          </div>

          {/* Video toggle */}
          {isVideo && (
            <button
              onClick={() => setShowVideo(!showVideo)}
              className="text-[#8A8A93] hover:text-[#F5A623] text-xs font-medium transition-colors"
              data-testid="toggle-video-btn"
            >
              {showVideo ? 'Hide Video' : 'Show Video'}
            </button>
          )}
        </div>
      </div>
    </>
  );
}
