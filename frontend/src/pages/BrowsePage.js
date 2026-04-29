import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { FunnelSimple, MagnifyingGlass } from '@phosphor-icons/react';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import ShowCard from '../components/ShowCard';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';
import { authRequest } from '../lib/library';

export default function BrowsePage() {
  const { user } = useAuth();
  const { currentPodcast } = usePlayer();
  const [episodes, setEpisodes] = useState([]);
  const [shows, setShows] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [mediaType, setMediaType] = useState('');
  const [sort, setSort] = useState('recent');
  const [followingOnly, setFollowingOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchBrowse = useCallback(async (overrides = {}) => {
    const nextSearch = overrides.search ?? searchQuery;
    const nextCategory = overrides.category ?? selectedCategory;
    const nextMediaType = overrides.mediaType ?? mediaType;
    const nextSort = overrides.sort ?? sort;
    const nextFollowingOnly = overrides.followingOnly ?? followingOnly;

    setLoading(true);
    try {
      const showsUrl = `${API}/shows?limit=8${nextSearch ? `&search=${encodeURIComponent(nextSearch)}` : ''}${nextCategory ? `&category=${encodeURIComponent(nextCategory)}` : ''}${nextFollowingOnly ? '&following_only=true' : ''}`;
      const useTopicRecommendations = Boolean(user && nextCategory && nextSort !== 'recommended' && !nextSearch && !nextMediaType && !nextFollowingOnly);
      const topicSort = ['highest_rated', 'most_viewed'].includes(nextSort) ? nextSort : 'smart';
      const episodesUrl = useTopicRecommendations
        ? `${API}/recommendations?category=${encodeURIComponent(nextCategory)}&sort=${encodeURIComponent(topicSort)}`
        : `${API}/podcasts?limit=12&sort=${encodeURIComponent(nextSort)}${nextSearch ? `&search=${encodeURIComponent(nextSearch)}` : ''}${nextCategory ? `&category=${encodeURIComponent(nextCategory)}` : ''}${nextMediaType ? `&media_type=${encodeURIComponent(nextMediaType)}` : ''}${nextFollowingOnly ? '&following_only=true' : ''}`;

      const [showsRes, episodesRes] = await Promise.all([
        axios.get(showsUrl, authRequest).catch(() => ({ data: { shows: [] } })),
        axios.get(episodesUrl, authRequest).catch(() => ({ data: { podcasts: [] } })),
      ]);

      setShows(showsRes.data.shows || []);
      setEpisodes(episodesRes.data.podcasts || []);
    } finally {
      setLoading(false);
    }
  }, [followingOnly, mediaType, searchQuery, selectedCategory, sort, user]);

  useEffect(() => {
    fetchBrowse();
    axios.get(`${API}/categories`, authRequest).then((res) => setCategories(res.data.categories || [])).catch(() => {});
  }, [fetchBrowse]);

  const handleSearch = () => {
    fetchBrowse({ search: searchQuery });
  };

  const removeEpisode = (podcastId) => {
    setEpisodes((prev) => prev.filter((podcast) => podcast.id !== podcastId));
  };

  const handleShowFollowChange = (showId, nextFollowing) => {
    setShows((prev) => (
      nextFollowing || !followingOnly
        ? prev.map((show) => (show.id === showId ? { ...show, is_following: nextFollowing } : show))
        : prev.filter((show) => show.id !== showId)
    ));

    if (!nextFollowing && followingOnly) {
      setEpisodes((prev) => prev.filter((episode) => episode.show_id !== showId));
    }
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="browse-page">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        <div className="mb-10">
          <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-2">
            Browse podcasts
          </h1>
          <p className="text-[#8A8A93] max-w-3xl">
            Explore intentionally. Audioraq is built for long-form listening, so browse is tuned for shows worth keeping up with, not endless low-signal scrolling.
          </p>
        </div>

        {!user && (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-6 mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Public Browse</p>
              <p className="text-sm text-[#C7C7D1]">Search and sample shows without signing up. Save, follow, and personalized home feed tools unlock once you create an account.</p>
            </div>
            <a href="/register" className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors whitespace-nowrap text-center">
              Create account
            </a>
          </div>
        )}

        <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-5 md:p-6 mb-8">
          <div className="relative mb-4">
            <MagnifyingGlass className="absolute left-4 top-1/2 -translate-y-1/2 text-[#8A8A93] w-5 h-5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-xl text-white pl-12 pr-24 py-4 placeholder:text-[#8A8A93] transition-all outline-none"
              placeholder="Search shows, episodes, creators, or topics..."
              data-testid="browse-search-input"
            />
            <button
              onClick={handleSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-lg px-4 py-2 transition-colors text-sm"
              data-testid="browse-search-btn"
            >
              Search
            </button>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-center gap-4">
            <div className="flex items-center gap-2">
              <FunnelSimple className="text-[#8A8A93] w-4 h-4" />
              <span className="text-xs text-[#8A8A93] uppercase tracking-wider font-semibold">Filters</span>
            </div>
            <div className="flex flex-wrap gap-3">
              <select
                value={sort}
                onChange={(e) => {
                  setSort(e.target.value);
                  fetchBrowse({ sort: e.target.value });
                }}
                className="bg-[#0A0A0B] border border-[#27272A] rounded-full px-4 py-2 text-sm text-white outline-none"
              >
                <option value="recent">Newest</option>
                <option value="recommended">Recommended</option>
                <option value="trending">Trending</option>
                <option value="highest_rated">Highest rated</option>
                <option value="most_viewed">Most viewed</option>
                <option value="oldest">Oldest</option>
              </select>
              <select
                value={mediaType}
                onChange={(e) => {
                  setMediaType(e.target.value);
                  fetchBrowse({ mediaType: e.target.value });
                }}
                className="bg-[#0A0A0B] border border-[#27272A] rounded-full px-4 py-2 text-sm text-white outline-none"
              >
                <option value="">Audio &amp; video</option>
                <option value="audio">Audio only</option>
              </select>
              {user && (
                <button
                  type="button"
                  onClick={() => {
                    const nextFollowingOnly = !followingOnly;
                    setFollowingOnly(nextFollowingOnly);
                    fetchBrowse({ followingOnly: nextFollowingOnly });
                  }}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                    followingOnly
                      ? 'bg-[#F5A623] text-[#0A0A0B]'
                      : 'bg-[#0A0A0B] border border-[#27272A] text-white hover:border-[#F5A623]'
                  }`}
                  data-testid="browse-following-filter"
                >
                  From shows I follow
                </button>
              )}
            </div>
          </div>
        </div>

        {categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-8">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => {
                  const nextCategory = selectedCategory === category ? '' : category;
                  setSelectedCategory(nextCategory);
                  fetchBrowse({ category: nextCategory });
                }}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  selectedCategory === category
                    ? 'bg-[#F5A623] text-[#0A0A0B]'
                    : 'bg-[#141417] border border-[#27272A] text-[#8A8A93] hover:border-[#F5A623] hover:text-white'
                }`}
                data-testid={`category-filter-${category}`}
              >
                {category}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            <section className="mb-12">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="font-['Outfit'] text-xl font-semibold text-white">
                    {followingOnly ? 'Shows you follow' : searchQuery || selectedCategory ? 'Matching shows' : 'Featured shows'}
                  </h2>
                  <p className="text-sm text-[#8A8A93] mt-1">
                    Quality signals highlight active catalogs, branded shows, and creators who keep publishing.
                  </p>
                </div>
                <span className="text-sm text-[#8A8A93]">{shows.length} shows</span>
              </div>
              {shows.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                  {shows.map((show) => (
                    <ShowCard key={show.id} show={show} onFollowChange={handleShowFollowChange} />
                  ))}
                </div>
              ) : (
                <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-10 text-center">
                  <p className="text-[#8A8A93]">
                    {followingOnly
                      ? 'Follow a few shows first, then this filter becomes your fastest way to catch up.'
                      : 'No shows matched those filters.'}
                  </p>
                </div>
              )}
            </section>

            <section>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="font-['Outfit'] text-xl font-semibold text-white">
                    {followingOnly
                      ? 'Episodes from shows you follow'
                      : sort === 'recommended'
                        ? 'Recommended Audioraq Originals'
                      : selectedCategory
                        ? `Recommended ${selectedCategory} episodes`
                        : searchQuery || mediaType
                          ? 'Matching episodes'
                          : 'Latest episodes'}
                  </h2>
                  <p className="text-sm text-[#8A8A93] mt-1">
                    {sort === 'recommended'
                      ? 'A curated set of 10 polished proof-of-work episodes with strong Agent 2 quality, voice clarity, and listenability scores.'
                      : selectedCategory
                      ? `Topic-mapped recommendations for ${selectedCategory}, using category, keywords, titles, and show context.`
                      : 'Recommendation reasons and trust cues are built in so you can make a decision quickly.'}
                  </p>
                </div>
                <span className="text-sm text-[#8A8A93]">{episodes.length} episodes</span>
              </div>
              {episodes.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {episodes.map((podcast) => (
                    <PodcastCard key={podcast.id} podcast={podcast} onHide={removeEpisode} />
                  ))}
                </div>
              ) : (
                <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-10 text-center">
                  <p className="text-[#8A8A93]">
                    {followingOnly
                      ? 'Follow a few active shows to build a focused episode queue here.'
                      : 'No episodes matched those filters.'}
                  </p>
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
