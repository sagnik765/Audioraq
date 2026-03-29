import React, { useState, useEffect } from 'react';
import { usePlayer } from '../contexts/PlayerContext';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import { MagnifyingGlass, FunnelSimple } from '@phosphor-icons/react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BrowsePage() {
  const { currentPodcast } = usePlayer();
  const [podcasts, setPodcasts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchPodcasts = async (search = '', cat = '', pg = 1) => {
    setLoading(true);
    try {
      let url = `${API}/podcasts?page=${pg}&limit=20`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (cat) url += `&category=${encodeURIComponent(cat)}`;
      const res = await axios.get(url);
      setPodcasts(res.data.podcasts || []);
      setTotalPages(res.data.pages || 1);
    } catch { setPodcasts([]); } finally { setLoading(false); }
  };

  useEffect(() => {
    fetchPodcasts();
    axios.get(`${API}/categories`).then(res => setCategories(res.data.categories || [])).catch(() => {});
  }, []);

  const handleSearch = () => {
    setPage(1);
    fetchPodcasts(searchQuery, selectedCategory, 1);
  };

  const handleCategoryFilter = (cat) => {
    const newCat = cat === selectedCategory ? '' : cat;
    setSelectedCategory(newCat);
    setPage(1);
    fetchPodcasts(searchQuery, newCat, 1);
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="browse-page">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        <div className="mb-10">
          <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-1">
            Browse Podcasts
          </h1>
          <p className="text-[#8A8A93]">Explore content from creators worldwide</p>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <MagnifyingGlass className="absolute left-4 top-1/2 -translate-y-1/2 text-[#8A8A93] w-5 h-5" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            className="w-full bg-[#141417] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-xl text-white pl-12 pr-24 py-4 placeholder:text-[#8A8A93] transition-all outline-none"
            placeholder="Search podcasts..."
            data-testid="browse-search-input"
          />
          <button onClick={handleSearch}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-lg px-4 py-2 transition-colors text-sm"
            data-testid="browse-search-btn">
            Search
          </button>
        </div>

        {/* Categories */}
        {categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-8">
            <div className="flex items-center gap-2 mr-2">
              <FunnelSimple className="text-[#8A8A93] w-4 h-4" />
              <span className="text-xs text-[#8A8A93] uppercase tracking-wider font-semibold">Filter:</span>
            </div>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => handleCategoryFilter(cat)}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                  selectedCategory === cat
                    ? 'bg-[#F5A623] text-[#0A0A0B]'
                    : 'bg-[#141417] border border-[#27272A] text-[#8A8A93] hover:border-[#F5A623] hover:text-white'
                }`}
                data-testid={`category-filter-${cat}`}
              >
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </button>
            ))}
          </div>
        )}

        {/* Results */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : podcasts.length > 0 ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {podcasts.map(p => <PodcastCard key={p.id} podcast={p} />)}
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-10">
                <button
                  onClick={() => { const np = page - 1; setPage(np); fetchPodcasts(searchQuery, selectedCategory, np); }}
                  disabled={page <= 1}
                  className="bg-[#141417] border border-[#27272A] text-white rounded-full px-6 py-2 disabled:opacity-30 transition-colors hover:bg-[#27272A]"
                  data-testid="prev-page-btn"
                >
                  Previous
                </button>
                <span className="text-sm text-[#8A8A93]">Page {page} of {totalPages}</span>
                <button
                  onClick={() => { const np = page + 1; setPage(np); fetchPodcasts(searchQuery, selectedCategory, np); }}
                  disabled={page >= totalPages}
                  className="bg-[#141417] border border-[#27272A] text-white rounded-full px-6 py-2 disabled:opacity-30 transition-colors hover:bg-[#27272A]"
                  data-testid="next-page-btn"
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="bg-[#141417] border border-[#27272A] rounded-xl p-12 text-center">
            <p className="text-[#8A8A93]">No podcasts found. Try a different search or category.</p>
          </div>
        )}
      </main>
    </div>
  );
}
