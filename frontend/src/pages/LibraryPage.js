import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { BookmarkSimple, Broadcast, ClockCounterClockwise, ListBullets, Play, Trash } from '@phosphor-icons/react';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import ShowCard from '../components/ShowCard';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';
import { authRequest } from '../lib/library';

function SectionHeader({ icon, title, subtitle, action }) {
  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-6">
      <div className="flex items-start gap-3">
        <div className="mt-1 text-[#F5A623]">{icon}</div>
        <div>
          <h2 className="font-['Outfit'] text-xl font-semibold text-white">{title}</h2>
          {subtitle && <p className="text-sm text-[#8A8A93] mt-1">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export default function LibraryPage() {
  const {
    currentPodcast,
    queue,
    queueIndex,
    playPodcast,
    playCollection,
    removeFromQueue,
    clearQueue,
  } = usePlayer();
  const [continueListening, setContinueListening] = useState([]);
  const [savedEpisodes, setSavedEpisodes] = useState([]);
  const [history, setHistory] = useState([]);
  const [followedShows, setFollowedShows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchLibrary() {
      setLoading(true);
      try {
        const [continueRes, savedRes, historyRes, showsRes] = await Promise.all([
          axios.get(`${API}/listening/continue?limit=12`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/podcasts/saved?limit=24`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/listening/history?limit=24`, authRequest).catch(() => ({ data: { podcasts: [] } })),
          axios.get(`${API}/shows/following?limit=12`, authRequest).catch(() => ({ data: { shows: [] } })),
        ]);

        if (!cancelled) {
          setContinueListening(continueRes.data.podcasts || []);
          setSavedEpisodes(savedRes.data.podcasts || []);
          setHistory(historyRes.data.podcasts || []);
          setFollowedShows(showsRes.data.shows || []);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchLibrary();
    return () => { cancelled = true; };
  }, []);

  const activeQueue = queue || [];
  const upcomingQueue = activeQueue.slice(Math.max(queueIndex, 0));

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="library-page">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 md:p-10 mb-10 relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,166,35,0.13),transparent_34%)]" />
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8">
            <div className="max-w-2xl">
              <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-3">Your Library</p>
              <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-3">
                Saved, queued, and unfinished episodes live here
              </h1>
              <p className="text-[#8A8A93] leading-relaxed">
                Home is for fresh recommendations. Browse is for exploration. Library is your personal listening shelf.
              </p>
            </div>
            <Link
              to="/browse"
              className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors inline-flex items-center justify-center gap-2"
            >
              <Play weight="fill" className="w-5 h-5" />
              Find more to save
            </Link>
          </div>
        </section>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            <section className="mb-12">
              <SectionHeader
                icon={<ListBullets className="w-5 h-5" />}
                title="Queue"
                subtitle="Play next, remove items, or clear the temporary listening plan."
                action={activeQueue.length > 0 && (
                  <button
                    type="button"
                    onClick={clearQueue}
                    className="text-sm text-[#8A8A93] hover:text-white transition-colors"
                  >
                    Clear queue
                  </button>
                )}
              />

              {upcomingQueue.length > 0 ? (
                <div className="space-y-3">
                  {upcomingQueue.map((episode, index) => (
                    <div key={`${episode.id}-${index}`} className="bg-[#141417] border border-[#27272A] rounded-2xl px-4 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-xs uppercase tracking-[0.18em] text-[#F5A623] mb-1">
                          {index === 0 && currentPodcast?.id === episode.id ? 'Now playing' : `Queue ${index + 1}`}
                        </p>
                        <h3 className="font-['Outfit'] text-base font-semibold text-white truncate">{episode.title}</h3>
                        <p className="text-sm text-[#8A8A93] truncate">{episode.show_title || episode.podcaster_name}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => playPodcast(episode, { queueList: activeQueue, startIndex: activeQueue.findIndex((item) => item.id === episode.id) })}
                          className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-4 py-2 transition-colors inline-flex items-center gap-2"
                        >
                          <Play weight="fill" className="w-4 h-4" />
                          Play
                        </button>
                        <button
                          type="button"
                          onClick={() => removeFromQueue(episode.id)}
                          className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-4 py-2 transition-colors inline-flex items-center gap-2"
                        >
                          <Trash className="w-4 h-4" />
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-10 text-center">
                  <p className="text-[#8A8A93] mb-4">Your queue is empty. Add episodes from any card or episode detail page.</p>
                  <Link to="/browse" className="text-[#F5A623] hover:text-[#F7B84B] transition-colors">Browse episodes</Link>
                </div>
              )}
            </section>

            {continueListening.length > 0 && (
              <section className="mb-12">
                <SectionHeader
                  icon={<ClockCounterClockwise className="w-5 h-5" />}
                  title="Continue listening"
                  subtitle="Resume unfinished episodes without hunting for them again."
                  action={(
                    <button
                      type="button"
                      onClick={() => playCollection(continueListening, 0)}
                      className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors"
                    >
                      Play first
                    </button>
                  )}
                />
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {continueListening.map((podcast) => <PodcastCard key={podcast.id} podcast={podcast} />)}
                </div>
              </section>
            )}

            {savedEpisodes.length > 0 && (
              <section className="mb-12">
                <SectionHeader
                  icon={<BookmarkSimple className="w-5 h-5" />}
                  title="Saved for later"
                  subtitle="Episodes you liked enough to keep before you had time to listen."
                />
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {savedEpisodes.map((podcast) => <PodcastCard key={podcast.id} podcast={podcast} />)}
                </div>
              </section>
            )}

            {followedShows.length > 0 && (
              <section className="mb-12">
                <SectionHeader
                  icon={<Broadcast className="w-5 h-5" />}
                  title="Followed shows"
                  subtitle="Shows you want Audioraq to keep bringing back into your home feed."
                />
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                  {followedShows.map((show) => <ShowCard key={show.id} show={show} />)}
                </div>
              </section>
            )}

            {history.length > 0 && (
              <section className="mb-12">
                <SectionHeader
                  icon={<ClockCounterClockwise className="w-5 h-5" />}
                  title="Listening history"
                  subtitle="Recently started episodes, including finished listens."
                />
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {history.map((podcast) => <PodcastCard key={podcast.id} podcast={podcast} />)}
                </div>
              </section>
            )}

            {!activeQueue.length && !continueListening.length && !savedEpisodes.length && !followedShows.length && !history.length && (
              <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-12 text-center">
                <h3 className="font-['Outfit'] text-xl font-semibold text-white mb-2">Your library is ready for its first picks</h3>
                <p className="text-[#8A8A93] mb-6">Save an episode, follow a show, or add something to queue from Browse.</p>
                <Link to="/browse" className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors inline-flex">
                  Start browsing
                </Link>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
