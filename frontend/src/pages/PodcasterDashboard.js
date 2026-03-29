import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { usePlayer } from '../contexts/PlayerContext';
import Navbar from '../components/Navbar';
import PodcastCard from '../components/PodcastCard';
import { Upload, Microphone, Play, Trash, CloudArrowUp } from '@phosphor-icons/react';
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PodcasterDashboard() {
  const { user } = useAuth();
  const { currentPodcast } = usePlayer();
  const [myPodcasts, setMyPodcasts] = useState([]);
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);

  // Upload form
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('general');
  const [file, setFile] = useState(null);
  const [thumbnail, setThumbnail] = useState(null);
  const [uploading, setUploading] = useState(false);

  const fetchPodcasts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/podcasts/my`, { withCredentials: true });
      setMyPodcasts(res.data.podcasts || []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchPodcasts(); }, [fetchPodcasts]);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) { toast.error('Please select an audio or video file'); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', title);
      formData.append('description', description);
      formData.append('category', category);
      if (thumbnail) formData.append('thumbnail', thumbnail);

      await axios.post(`${API}/podcasts/upload`, formData, {
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Podcast uploaded successfully!');
      setShowUpload(false);
      setTitle(''); setDescription(''); setCategory('general'); setFile(null); setThumbnail(null);
      fetchPodcasts();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (podcastId) => {
    if (!window.confirm('Delete this podcast?')) return;
    try {
      await axios.delete(`${API}/podcasts/${podcastId}`, { withCredentials: true });
      toast.success('Podcast deleted');
      fetchPodcasts();
    } catch {
      toast.error('Failed to delete');
    }
  };

  const totalPlays = myPodcasts.reduce((sum, p) => sum + (p.play_count || 0), 0);

  const categories = [
    'general', 'technology', 'science', 'business', 'health', 'education',
    'entertainment', 'sports', 'politics', 'music', 'comedy', 'true crime',
    'history', 'philosophy', 'art', 'gaming', 'finance', 'travel', 'food'
  ];

  return (
    <div className={`min-h-screen bg-[#0A0A0B] ${currentPodcast ? 'has-player' : ''}`} data-testid="podcaster-dashboard">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-10 gap-4">
          <div>
            <h1 className="font-['Outfit'] text-3xl sm:text-4xl tracking-tight font-bold text-white mb-1">
              Creator Studio
            </h1>
            <p className="text-[#8A8A93]">Manage and upload your podcasts</p>
          </div>
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors inline-flex items-center gap-2"
            data-testid="upload-toggle-btn"
          >
            <Upload weight="bold" className="w-5 h-5" />
            Upload Podcast
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          {[
            { label: 'Total Podcasts', value: myPodcasts.length, icon: <Microphone weight="duotone" className="w-6 h-6 text-[#F5A623]" /> },
            { label: 'Total Plays', value: totalPlays, icon: <Play weight="duotone" className="w-6 h-6 text-[#F5A623]" /> },
            { label: 'Keywords', value: user?.podcast_keywords?.length || 0, icon: <Microphone weight="duotone" className="w-6 h-6 text-[#F5A623]" /> }
          ].map((stat, i) => (
            <div key={i} className="bg-[#141417] border border-[#27272A] rounded-xl p-6 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#F5A623]/10 flex items-center justify-center">{stat.icon}</div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93]">{stat.label}</p>
                <p className="font-['Outfit'] text-2xl font-bold text-white">{stat.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Upload Form */}
        {showUpload && (
          <div className="bg-[#141417] border border-[#27272A] rounded-xl p-8 mb-10 opacity-0 animate-fade-in-up" data-testid="upload-podcast-form">
            <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-6 flex items-center gap-2">
              <CloudArrowUp weight="duotone" className="w-6 h-6 text-[#F5A623]" />
              Upload New Podcast
            </h2>
            <form onSubmit={handleUpload} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Title</label>
                  <input
                    type="text" value={title} onChange={e => setTitle(e.target.value)} required
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none"
                    placeholder="Podcast title" data-testid="upload-title-input"
                  />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Category</label>
                  <select
                    value={category} onChange={e => setCategory(e.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-lg text-white px-4 py-3 transition-all outline-none"
                    data-testid="upload-category-select"
                  >
                    {categories.map(c => (
                      <option key={c} value={c} className="bg-[#141417]">{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Description</label>
                <textarea
                  value={description} onChange={e => setDescription(e.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] focus:ring-1 focus:ring-[#F5A623] rounded-lg text-white px-4 py-3 placeholder:text-[#8A8A93] transition-all outline-none min-h-[100px] resize-none"
                  placeholder="Describe your podcast episode..." data-testid="upload-description-textarea"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">
                    Audio/Video File *
                  </label>
                  <div className="relative">
                    <input
                      type="file"
                      accept="audio/*,video/*"
                      onChange={e => setFile(e.target.files[0])}
                      className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-lg text-white px-4 py-3 file:mr-4 file:rounded-full file:border-0 file:bg-[#F5A623] file:text-[#0A0A0B] file:font-bold file:px-4 file:py-1 file:text-sm file:cursor-pointer"
                      data-testid="upload-file-input"
                    />
                  </div>
                  {file && <p className="text-xs text-[#8A8A93] mt-1">{file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)</p>}
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">
                    Thumbnail (Optional)
                  </label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={e => setThumbnail(e.target.files[0])}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-lg text-white px-4 py-3 file:mr-4 file:rounded-full file:border-0 file:bg-[#27272A] file:text-white file:font-medium file:px-4 file:py-1 file:text-sm file:cursor-pointer"
                    data-testid="upload-thumbnail-input"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowUpload(false)}
                  className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-6 py-3 transition-colors"
                  data-testid="upload-cancel-btn">
                  Cancel
                </button>
                <button type="submit" disabled={uploading}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3 transition-colors disabled:opacity-50 inline-flex items-center gap-2"
                  data-testid="upload-submit-btn">
                  <CloudArrowUp weight="bold" className="w-5 h-5" />
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* My Podcasts */}
        <section>
          <h2 className="font-['Outfit'] text-xl font-semibold text-white mb-6">Your Podcasts</h2>
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : myPodcasts.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {myPodcasts.map(p => (
                <div key={p.id} className="relative group">
                  <PodcastCard podcast={p} />
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="absolute top-3 right-3 bg-[#EF4444]/80 hover:bg-[#EF4444] text-white rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                    data-testid={`delete-podcast-${p.id}`}
                  >
                    <Trash weight="bold" className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-[#141417] border border-[#27272A] rounded-xl p-12 text-center">
              <Microphone weight="duotone" className="w-12 h-12 text-[#8A8A93] mx-auto mb-4" />
              <h3 className="font-['Outfit'] text-lg font-medium text-white mb-2">No podcasts yet</h3>
              <p className="text-sm text-[#8A8A93] mb-6">Start by uploading your first podcast episode</p>
              <button
                onClick={() => setShowUpload(true)}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors inline-flex items-center gap-2"
                data-testid="empty-upload-btn"
              >
                <Upload weight="bold" className="w-5 h-5" />
                Upload Your First Podcast
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
