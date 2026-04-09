import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { usePlayer } from '../contexts/PlayerContext';
import { Pause, Play, SkipBack, SkipForward, SpeakerHigh, SpeakerSlash, X } from '@phosphor-icons/react';
import { API } from '../lib/api';

export default function PlayerBar() {
  const {
    currentPodcast,
    isPlaying,
    progress,
    duration,
    volume,
    mediaRef,
    togglePlay,
    seek,
    setProgress,
    setDuration,
    setVolume,
    setIsPlaying,
    queue,
    queueIndex,
    pendingStartTime,
    setPendingStartTime,
    playPodcast,
    playNextInQueue,
    playPreviousInQueue,
    removeFromQueue,
    clearQueue,
    dismissPlayer,
  } = usePlayer();

  const audioRef = useRef(null);
  const videoRef = useRef(null);
  const [showVideo, setShowVideo] = useState(false);
  const [showQueue, setShowQueue] = useState(false);
  const [currentPodcastState, setCurrentPodcastState] = useState(null);
  const trackedPlaybackIdRef = useRef('');
  const lastReportedProgressRef = useRef({ podcastId: '', seconds: 0 });

  const isVideo = currentPodcast?.media_type === 'video';
  const activeRef = isVideo ? videoRef : audioRef;
  const upcomingQueue = queue.slice(Math.max(0, queueIndex + 1));

  useEffect(() => {
    mediaRef.current = activeRef.current;
  }, [activeRef, mediaRef, currentPodcast]);

  useEffect(() => {
    if (!currentPodcast) return;
    if (currentPodcastState?.id === currentPodcast.id) {
      if (activeRef.current && !activeRef.current.src) {
        activeRef.current.src = `${API}/podcasts/${currentPodcast.id}/stream`;
        activeRef.current.load();
      }
      if (isPlaying && activeRef.current) {
        activeRef.current.play().catch(() => {});
      } else if (!isPlaying && activeRef.current) {
        activeRef.current.pause();
      }
      return;
    }

    setCurrentPodcastState(currentPodcast);
    trackedPlaybackIdRef.current = '';
    lastReportedProgressRef.current = { podcastId: currentPodcast.id, seconds: pendingStartTime || 0 };
    setShowVideo(isVideo);

    const el = activeRef.current;
    if (!el) return;

    el.src = `${API}/podcasts/${currentPodcast.id}/stream`;
    el.volume = volume;
    el.load();
    const playPromise = el.play();
    if (playPromise) playPromise.catch(() => {});
  }, [activeRef, currentPodcast, currentPodcastState, isPlaying, isVideo, pendingStartTime, volume]);

  useEffect(() => {
    const el = activeRef.current;
    if (!el) return;
    if (isPlaying) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, [activeRef, isPlaying]);

  useEffect(() => {
    const el = activeRef.current;
    if (!el) return;
    el.volume = volume;
  }, [activeRef, volume]);

  const reportProgress = (eventType, secondsOverride) => {
    if (!currentPodcast) return;
    const el = activeRef.current;
    const seconds = Math.max(0, Number.isFinite(secondsOverride) ? secondsOverride : (el?.currentTime || 0));
    const mediaDuration = Math.max(0, el?.duration || duration || currentPodcast.duration_seconds || 0);
    const lastReport = lastReportedProgressRef.current;
    const shouldSkip =
      eventType === 'progress' &&
      lastReport.podcastId === currentPodcast.id &&
      Math.abs(seconds - lastReport.seconds) < 10;

    if (shouldSkip) return;

    lastReportedProgressRef.current = { podcastId: currentPodcast.id, seconds };
    axios.post(`${API}/podcasts/${currentPodcast.id}/progress`, {
      progress_seconds: seconds,
      duration_seconds: mediaDuration,
      event_type: eventType,
    }, { withCredentials: true }).catch(() => {});
  };

  const handleTimeUpdate = () => {
    const el = activeRef.current;
    if (!el) return;
    setProgress(el.currentTime);
    reportProgress('progress', el.currentTime);
  };

  const handleLoadedMetadata = () => {
    const el = activeRef.current;
    if (!el) return;
    setDuration(el.duration);
    if (pendingStartTime > 0) {
      el.currentTime = Math.min(pendingStartTime, Math.max(el.duration - 1, 0));
      setProgress(el.currentTime);
      setPendingStartTime(0);
    }
  };

  const handleEnded = () => {
    const el = activeRef.current;
    const finishedAt = el?.duration || duration || progress;
    reportProgress('completed', finishedAt);
    if (!playNextInQueue()) {
      setIsPlaying(false);
      setProgress(finishedAt);
    }
  };

  const handleMediaPlay = () => {
    if (!currentPodcast) return;
    if (trackedPlaybackIdRef.current !== currentPodcast.id) {
      trackedPlaybackIdRef.current = currentPodcast.id;
      axios.post(`${API}/podcasts/${currentPodcast.id}/view`, {}, { withCredentials: true }).catch(() => {});
      reportProgress('started', progress);
    }
  };

  const handlePause = () => {
    reportProgress('pause');
  };

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const newTime = pct * duration;
    seek(newTime);
    if (activeRef.current) activeRef.current.currentTime = newTime;
    reportProgress('seek', newTime);
  };

  const formatTime = (secs) => {
    if (!secs || Number.isNaN(secs)) return '0:00';
    const mins = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    return `${mins}:${seconds.toString().padStart(2, '0')}`;
  };

  const handleSkipForward = () => {
    const el = activeRef.current;
    if (el) {
      el.currentTime = Math.min(el.currentTime + 15, duration);
      reportProgress('seek', el.currentTime);
    }
  };

  const handleSkipBack = () => {
    const el = activeRef.current;
    if (progress > 5 && el) {
      el.currentTime = Math.max(el.currentTime - 15, 0);
      reportProgress('seek', el.currentTime);
      return;
    }
    if (!playPreviousInQueue()) {
      seek(0);
    }
  };

  const handleDismiss = () => {
    reportProgress('pause');
    dismissPlayer();
  };

  if (!currentPodcast) return null;

  return (
    <>
      <audio
        ref={audioRef}
        onPlay={handleMediaPlay}
        onPause={handlePause}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        style={{ display: 'none' }}
      />

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
              onPlay={handleMediaPlay}
              onPause={handlePause}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={handleEnded}
              className="w-full rounded-xl"
              controls={false}
            />
          </div>
        </div>
      )}

      {showQueue && (
        <div className="fixed bottom-24 right-6 w-[360px] max-w-[calc(100vw-2rem)] z-50 bg-[#141417] border border-[#27272A] rounded-3xl shadow-[0_20px_60px_rgba(0,0,0,0.45)] overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#27272A]">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93]">Queue</p>
              <h3 className="font-['Outfit'] text-lg font-semibold text-white">Up next</h3>
            </div>
            <button
              onClick={clearQueue}
              className="text-xs text-[#F5A623] hover:text-[#F7B84B] transition-colors"
            >
              Clear queue
            </button>
          </div>
          <div className="max-h-[360px] overflow-y-auto px-4 py-3 space-y-2">
            {upcomingQueue.length > 0 ? (
              upcomingQueue.map((podcast) => (
                <div key={podcast.id} className="flex items-center gap-3 bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-3">
                  <button
                    type="button"
                    onClick={() => playPodcast(podcast, {
                      queueList: queue,
                      startIndex: queue.findIndex((item) => item.id === podcast.id),
                      startTime: podcast.resume_position_seconds || podcast.progress_seconds || 0,
                    })}
                    className="flex-1 text-left min-w-0"
                  >
                    <p className="text-sm text-white truncate">{podcast.title}</p>
                    <p className="text-xs text-[#8A8A93] truncate">{podcast.show_title || podcast.podcaster_name}</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFromQueue(podcast.id)}
                    className="text-[#8A8A93] hover:text-white transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))
            ) : (
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-2xl p-5 text-center">
                <p className="text-sm text-[#8A8A93]">Nothing queued yet. Use Play Next or Add to Queue from an episode.</p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="backdrop-blur-2xl bg-[#141417]/80 border-t border-[#27272A] fixed bottom-0 w-full z-50 shadow-[0_-8px_32px_rgba(0,0,0,0.4)]" data-testid="player-bar">
        <div className="h-1 bg-[#27272A] cursor-pointer group" onClick={handleSeek} data-testid="progress-bar">
          <div
            className="h-full bg-[#F5A623] transition-all duration-100 relative"
            style={{ width: duration ? `${(progress / duration) * 100}%` : '0%' }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#F5A623] opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className="w-10 h-10 rounded-lg bg-[#F5A623]/10 flex-shrink-0 flex items-center justify-center overflow-hidden">
              {(currentPodcast.thumbnail_path || currentPodcast.show_thumbnail_path || currentPodcast.external_thumbnail_url) ? (
                <img src={`${API}/podcasts/${currentPodcast.id}/thumbnail`} alt="" className="w-full h-full object-cover" />
              ) : (
                <Play weight="fill" className="w-4 h-4 text-[#F5A623]" />
              )}
            </div>
            <div className="min-w-0">
              <Link to={`/episodes/${currentPodcast.id}`} className="text-sm font-medium text-white truncate hover:text-[#F5A623] transition-colors block">
                {currentPodcast.title}
              </Link>
              <p className="text-xs text-[#8A8A93] truncate">{currentPodcast.show_title || currentPodcast.podcaster_name}</p>
              {currentPodcast.progress_percent > 0 && !currentPodcast.is_completed && (
                <p className="text-[11px] text-[#F5A623] truncate">Resume from {formatTime(currentPodcast.resume_position_seconds || currentPodcast.progress_seconds || 0)}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button onClick={handleSkipBack} className="text-[#8A8A93] hover:text-white transition-colors" data-testid="skip-back-btn">
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
            <button onClick={handleSkipForward} className="text-[#8A8A93] hover:text-white transition-colors" data-testid="skip-forward-btn">
              <SkipForward weight="fill" className="w-5 h-5" />
            </button>
          </div>

          <div className="hidden sm:flex items-center gap-2 text-xs text-[#8A8A93] min-w-[100px]">
            <span>{formatTime(progress)}</span>
            <span>/</span>
            <span>{formatTime(duration)}</span>
          </div>

          <div className="hidden md:flex items-center gap-2">
            <button
              onClick={() => setVolume(volume > 0 ? 0 : 0.8)}
              className="text-[#8A8A93] hover:text-white transition-colors"
              data-testid="mute-btn"
            >
              {volume > 0 ? <SpeakerHigh weight="fill" className="w-4 h-4" /> : <SpeakerSlash weight="fill" className="w-4 h-4" />}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-20 accent-[#F5A623]"
              data-testid="volume-slider"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowQueue((prev) => !prev)}
              className="text-xs text-[#8A8A93] hover:text-white transition-colors"
              data-testid="toggle-queue-btn"
            >
              Queue {upcomingQueue.length > 0 ? `(${upcomingQueue.length})` : ''}
            </button>

            {isVideo && (
              <button
                onClick={() => setShowVideo(!showVideo)}
                className="text-[#8A8A93] hover:text-[#F5A623] text-xs font-medium transition-colors"
                data-testid="toggle-video-btn"
              >
                {showVideo ? 'Hide Video' : 'Show Video'}
              </button>
            )}

            <button
              onClick={handleDismiss}
              className="text-[#8A8A93] hover:text-white transition-colors"
              data-testid="dismiss-player-btn"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
