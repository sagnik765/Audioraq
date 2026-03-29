import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import { Sparkle, Fire, MagnifyingGlass, Sliders } from '@phosphor-icons/react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function UserDashboard() {
  const { user } = useAuth();
  const { currentPodcast } = usePlayer();
  const [recommended, setRecommended] = useState([]);
  const [trending, setTrending] = useState([]);
  const [allPodcasts, setAllPodcasts] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [recMethod, setRecMethod] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [recRes, trendRes, allRes] = await Promise.all([
        axios.get(`${API}/recommendations`, { withCredentials: true }).catch(() => ({ data: { podcasts: [] } })),
        axios.get(`${API}/trending`).catch(() => ({ data: { podcasts: [] } })),
        axios.get(`${API}/podcasts?limit=50`).catch(() => ({ data: { podcasts: [] } }))
      ]);
      setRecommended(recRes.data.podcasts || []);
      setRecMethod(recRes.data.method || '');
      setTrending(trendRes.data.podcasts || []);
      setAllPodcasts(allRes.data.podcasts || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    try {
      const res = await axios.get(`${API}/podcasts?search=${encodeURIComponent(searchQuery)}`);
      setSearchResults(res.data.podcasts || []);
    } catch { setSearchResults([]); }
  };

  const displayName = user?.name?.split(' ')[0] || 'there';

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="user-dashboard">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        {/* Welcome */}
        <div className="mb-10">
          <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-1">
            Hey, {displayName}
          </h1>
          <p className="text-[#8A8A93]">Find your next favorite podcast</p>
        </div>

        {/* Search */}
        <div className="relative mb-10">
          <MagnifyingGlass className="absolute left-4 top-1/2 -translate-y-1/2 text-[#8A8A93] w-5 h-5" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            className="w-full bg-[#141417] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-xl text-white pl-12 pr-24 py-4 placeholder:text-[#8A8A93] transition-all outline-none"
            placeholder="Search podcasts, topics, or creators..."
            data-testid="search-input"
          />
          <button
            onClick={handleSearch}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-lg px-4 py-2 transition-colors text-sm"
            data-testid="search-btn"
          >
            Search
          </button>
        </div>

        {/* Search Results */}
        {searchResults !== null && (
          <section className="mb-12">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <MagnifyingGlass className="text-[#F5A623] w-5 h-5" />
                <h2 className="font-['Outfit'] text-xl font-semibold text-white">
                  Results for "{searchQuery}"
                </h2>
                <span className="text-sm text-[#8A8A93]">({searchResults.length})</span>
              </div>
              <button onClick={() => { setSearchResults(null); setSearchQuery(''); }}
                className="text-sm text-[#8A8A93] hover:text-white transition-colors" data-testid="clear-search-btn">
                Clear
              </button>
            </div>
            {searchResults.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                {searchResults.map(p => <PodcastCard key={p.id} podcast={p} />)}
              </div>
            ) : (
              <div className="bg-[#141417] border border-[#27272A] rounded-xl p-12 text-center">
                <p className="text-[#8A8A93]">No podcasts found matching your search.</p>
              </div>
            )}
          </section>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Recommended */}
            {recommended.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <Sparkle weight="duotone" className="text-[#F5A623] w-5 h-5" />
                  <h2 className="font-['Outfit'] text-xl font-semibold text-white">Recommended for you</h2>
                  {recMethod && (
                    <span className="bg-[#27272A] text-[10px] text-white px-3 py-1 rounded-full uppercase tracking-widest font-bold">
                      {recMethod === 'ai' ? 'AI Powered' : recMethod}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {recommended.slice(0, 8).map(p => <PodcastCard key={p.id} podcast={p} />)}
                </div>
              </section>
            )}

            {/* Trending */}
            {trending.length > 0 && (
              <section className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <Fire weight="duotone" className="text-[#F5A623] w-5 h-5" />
                  <h2 className="font-['Outfit'] text-xl font-semibold text-white">Trending Now</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {trending.slice(0, 4).map(p => <PodcastCard key={p.id} podcast={p} />)}
                </div>
              </section>
            )}

            {/* All Podcasts */}
            <section className="mb-12">
              <div className="flex items-center gap-3 mb-6">
                <Sliders weight="duotone" className="text-[#F5A623] w-5 h-5" />
                <h2 className="font-['Outfit'] text-xl font-semibold text-white">All Podcasts</h2>
              </div>
              {allPodcasts.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {allPodcasts.map(p => <PodcastCard key={p.id} podcast={p} />)}
                </div>
              ) : (
                <div className="bg-[#141417] border border-[#27272A] rounded-xl p-12 text-center">
                  <Sparkle weight="duotone" className="w-12 h-12 text-[#8A8A93] mx-auto mb-4" />
                  <h3 className="font-['Outfit'] text-lg font-medium text-white mb-2">No podcasts yet</h3>
                  <p className="text-sm text-[#8A8A93]">Podcasters haven't uploaded any content yet. Check back soon!</p>
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
