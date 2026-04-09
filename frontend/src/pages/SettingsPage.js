import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import { API } from '../lib/api';

const starterInterests = ['technology', 'business', 'self improvement'];

export default function SettingsPage() {
  const { user, checkAuth, updateInterests } = useAuth();
  const { currentPodcast } = usePlayer();
  const [interestOptions, setInterestOptions] = useState([]);
  const [selectedInterests, setSelectedInterests] = useState([]);
  const [shows, setShows] = useState([]);
  const [activeShowId, setActiveShowId] = useState('');
  const [showTitle, setShowTitle] = useState('');
  const [showDescription, setShowDescription] = useState('');
  const [showCategory, setShowCategory] = useState('general');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSelectedInterests(user?.interests || []);
  }, [user]);

  useEffect(() => {
    axios.get(`${API}/interests/options`).then((res) => {
      setInterestOptions(res.data.interests || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (user?.role !== 'podcaster') return;
    axios.get(`${API}/shows/my`, { withCredentials: true }).then((res) => {
      const nextShows = res.data.shows || [];
      setShows(nextShows);
      if (nextShows[0]) {
        setActiveShowId(nextShows[0].id);
        setShowTitle(nextShows[0].title || '');
        setShowDescription(nextShows[0].description || '');
        setShowCategory(nextShows[0].category || 'general');
      }
    }).catch(() => {});
  }, [user]);

  useEffect(() => {
    const activeShow = shows.find((show) => show.id === activeShowId);
    if (!activeShow) return;
    setShowTitle(activeShow.title || '');
    setShowDescription(activeShow.description || '');
    setShowCategory(activeShow.category || 'general');
  }, [activeShowId, shows]);

  const toggleInterest = (interest) => {
    setSelectedInterests((prev) => (
      prev.includes(interest) ? prev.filter((item) => item !== interest) : [...prev, interest]
    ));
  };

  const handleSaveInterests = async () => {
    setSaving(true);
    const result = await updateInterests(selectedInterests);
    setSaving(false);
    if (result.success) {
      toast.success('Interests updated');
      checkAuth();
    } else {
      toast.error(result.error || 'Failed to update interests');
    }
  };

  const handleSaveShow = async (e) => {
    e.preventDefault();
    if (!activeShowId) {
      toast.error('Create a show first from Creator Studio');
      return;
    }
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('title', showTitle);
      formData.append('description', showDescription);
      formData.append('category', showCategory);
      await axios.put(`${API}/shows/${activeShowId}`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Show settings updated');
      checkAuth();
      const refreshed = await axios.get(`${API}/shows/my`, { withCredentials: true });
      setShows(refreshed.data.shows || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update show');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="settings-page">
      <Navbar />
      <main className="max-w-5xl mx-auto px-6 md:px-8 lg:px-12 py-10">
        <div className="mb-10">
          <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-1">Settings</h1>
          <p className="text-[#8A8A93]">
            {user?.role === 'podcaster' ? 'Manage your show identity and publishing defaults.' : 'Refine your interests to improve the home feed.'}
          </p>
        </div>

        {user?.role === 'podcaster' ? (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="flex flex-wrap gap-3 mb-8">
              {shows.map((show) => (
                <button
                  key={show.id}
                  type="button"
                  onClick={() => setActiveShowId(show.id)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    activeShowId === show.id
                      ? 'bg-[#F5A623] text-[#0A0A0B]'
                      : 'bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93] hover:text-white hover:border-[#F5A623]'
                  }`}
                >
                  {show.title}
                </button>
              ))}
            </div>

            <form onSubmit={handleSaveShow} className="space-y-5">
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Title</label>
                <input
                  type="text"
                  value={showTitle}
                  onChange={(e) => setShowTitle(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none"
                  required
                />
              </div>
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Category</label>
                <input
                  type="text"
                  value={showCategory}
                  onChange={(e) => setShowCategory(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none"
                />
              </div>
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Show Description</label>
                <textarea
                  value={showDescription}
                  onChange={(e) => setShowDescription(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none min-h-[160px] resize-none"
                />
              </div>
              <button
                type="submit"
                disabled={saving}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Show Settings'}
              </button>
            </form>
          </div>
        ) : (
          <div className="bg-[#141417] border border-[#27272A] rounded-3xl p-8">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-1">Your interests</h2>
                <p className="text-sm text-[#8A8A93]">These shape the recommendations on your home feed.</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedInterests(starterInterests)}
                className="text-sm text-[#F5A623] hover:text-[#F7B84B] transition-colors"
              >
                Use starter picks
              </button>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              {interestOptions.map((interest) => (
                <button
                  key={interest}
                  type="button"
                  onClick={() => toggleInterest(interest)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    selectedInterests.includes(interest)
                      ? 'bg-[#F5A623] text-[#0A0A0B]'
                      : 'bg-[#0A0A0B] border border-[#27272A] text-[#8A8A93] hover:text-white hover:border-[#F5A623]'
                  }`}
                >
                  {interest}
                </button>
              ))}
            </div>
            <p className="text-sm text-[#8A8A93] mb-6">{selectedInterests.length} selected</p>
            <button
              type="button"
              onClick={handleSaveInterests}
              disabled={saving}
              className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Interests'}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
