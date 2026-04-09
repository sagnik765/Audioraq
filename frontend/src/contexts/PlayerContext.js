import React, { createContext, useContext, useEffect, useRef, useState } from 'react';

const PlayerContext = createContext(null);
const STORAGE_KEY = 'audioraq-player-state-v3';

function readStoredState() {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function PlayerProvider({ children }) {
  const stored = readStoredState();
  const [currentPodcast, setCurrentPodcast] = useState(stored?.currentPodcast || null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(stored?.progress || 0);
  const [duration, setDuration] = useState(stored?.duration || 0);
  const [volume, setVolume] = useState(stored?.volume ?? 0.8);
  const [queue, setQueue] = useState(stored?.queue || (stored?.currentPodcast ? [stored.currentPodcast] : []));
  const [queueIndex, setQueueIndex] = useState(stored?.queueIndex ?? (stored?.currentPodcast ? 0 : -1));
  const [pendingStartTime, setPendingStartTime] = useState(stored?.progress || 0);
  const mediaRef = useRef(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        currentPodcast,
        progress,
        duration,
        volume,
        queue,
        queueIndex,
      }));
    } catch {
      // Ignore persistence failures.
    }
  }, [currentPodcast, duration, progress, queue, queueIndex, volume]);

  const playPodcast = (podcast, options = {}) => {
    if (!podcast) return;

    const startTime = options.startTime ?? podcast.resume_position_seconds ?? podcast.progress_seconds ?? 0;
    const queueList = options.queueList || [podcast];
    const startIndex = options.startIndex ?? Math.max(0, queueList.findIndex((item) => item.id === podcast.id));

    setQueue(queueList);
    setQueueIndex(startIndex);
    setCurrentPodcast({ ...podcast, resume_position_seconds: startTime });
    setPendingStartTime(startTime);
    setProgress(startTime);
    setDuration(options.duration ?? podcast.duration_seconds ?? 0);
    setIsPlaying(true);
  };

  const playCollection = (podcasts, startIndex = 0, options = {}) => {
    if (!Array.isArray(podcasts) || podcasts.length === 0) return;
    const safeIndex = Math.min(Math.max(0, startIndex), podcasts.length - 1);
    playPodcast(podcasts[safeIndex], {
      ...options,
      queueList: podcasts,
      startIndex: safeIndex,
    });
  };

  const togglePlay = () => {
    setIsPlaying((prev) => !prev);
  };

  const seek = (time) => {
    setProgress(time);
    setPendingStartTime(time);
    if (mediaRef.current) {
      mediaRef.current.currentTime = time;
    }
  };

  const addToQueue = (podcast) => {
    if (!podcast) return;
    setQueue((prev) => {
      if (currentPodcast?.id === podcast.id) return prev.length ? prev : [podcast];
      if (prev.some((item) => item.id === podcast.id)) return prev;
      return [...prev, podcast];
    });
  };

  const playNext = (podcast) => {
    if (!podcast) return;
    if (currentPodcast?.id === podcast.id) return;
    setQueue((prev) => {
      const withoutItem = prev.filter((item) => item.id !== podcast.id);
      if (queueIndex < 0) {
        const rest = withoutItem.filter((item) => item.id !== currentPodcast?.id);
        const nextQueue = currentPodcast ? [currentPodcast, podcast, ...rest] : [podcast, ...withoutItem];
        setQueueIndex(0);
        return nextQueue;
      }
      const nextQueue = [...withoutItem];
      nextQueue.splice(queueIndex + 1, 0, podcast);
      return nextQueue;
    });
  };

  const removeFromQueue = (podcastId) => {
    setQueue((prev) => {
      const removedIndex = prev.findIndex((item) => item.id === podcastId);
      const nextQueue = prev.filter((item) => item.id !== podcastId);
      setQueueIndex((prevIndex) => {
        if (!nextQueue.length) return -1;
        if (removedIndex === -1) return prevIndex;
        if (removedIndex < prevIndex) return prevIndex - 1;
        return Math.min(prevIndex, nextQueue.length - 1);
      });
      return nextQueue;
    });
  };

  const clearQueue = () => {
    if (currentPodcast) {
      setQueue([currentPodcast]);
      setQueueIndex(0);
      return;
    }
    setQueue([]);
    setQueueIndex(-1);
  };

  const playNextInQueue = () => {
    if (queueIndex + 1 >= queue.length) {
      setIsPlaying(false);
      return false;
    }
    const nextIndex = queueIndex + 1;
    playPodcast(queue[nextIndex], {
      queueList: queue,
      startIndex: nextIndex,
      startTime: queue[nextIndex]?.resume_position_seconds || queue[nextIndex]?.progress_seconds || 0,
    });
    return true;
  };

  const playPreviousInQueue = () => {
    if (queueIndex <= 0) return false;
    const prevIndex = queueIndex - 1;
    playPodcast(queue[prevIndex], {
      queueList: queue,
      startIndex: prevIndex,
      startTime: queue[prevIndex]?.resume_position_seconds || queue[prevIndex]?.progress_seconds || 0,
    });
    return true;
  };

  const dismissPlayer = () => {
    setCurrentPodcast(null);
    setIsPlaying(false);
    setProgress(0);
    setDuration(0);
    setPendingStartTime(0);
  };

  return (
    <PlayerContext.Provider value={{
      currentPodcast,
      isPlaying,
      progress,
      duration,
      volume,
      mediaRef,
      queue,
      queueIndex,
      pendingStartTime,
      playPodcast,
      playCollection,
      togglePlay,
      seek,
      addToQueue,
      playNext,
      removeFromQueue,
      clearQueue,
      playNextInQueue,
      playPreviousInQueue,
      dismissPlayer,
      setProgress,
      setDuration,
      setVolume,
      setIsPlaying,
      setPendingStartTime,
    }}>
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
}
