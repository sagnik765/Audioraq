import React, { createContext, useContext, useState, useRef, useCallback } from 'react';
import axios from 'axios';

const PlayerContext = createContext(null);
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function PlayerProvider({ children }) {
  const [currentPodcast, setCurrentPodcast] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const mediaRef = useRef(null);

  const playPodcast = useCallback(async (podcast) => {
    setCurrentPodcast(podcast);
    setIsPlaying(true);
    setProgress(0);
    // Record view
    try {
      await axios.post(`${API}/podcasts/${podcast.id}/view`, {}, { withCredentials: true });
    } catch { /* ignore for unauthenticated */ }
  }, []);

  const togglePlay = useCallback(() => {
    setIsPlaying(prev => !prev);
  }, []);

  const seek = useCallback((time) => {
    setProgress(time);
    if (mediaRef.current) {
      mediaRef.current.currentTime = time;
    }
  }, []);

  return (
    <PlayerContext.Provider value={{
      currentPodcast, isPlaying, progress, duration, volume,
      mediaRef, playPodcast, togglePlay, seek, setProgress,
      setDuration, setVolume, setIsPlaying
    }}>
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used within PlayerProvider");
  return ctx;
}
