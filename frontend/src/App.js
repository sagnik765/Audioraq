import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { PlayerProvider } from "./contexts/PlayerContext";
import { Toaster } from "./components/ui/sonner";
import PlayerBar from "./components/PlayerBar";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import UserDashboard from "./pages/UserDashboard";
import PodcasterDashboard from "./pages/PodcasterDashboard";
import BrowsePage from "./pages/BrowsePage";
import EpisodeDetailPage from "./pages/EpisodeDetailPage";
import LibraryPage from "./pages/LibraryPage";
import ShowPage from "./pages/ShowPage";
import SettingsPage from "./pages/SettingsPage";

function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard'} replace />;
  }

  return children;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#F5A623] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (user && user.role) {
    return <Navigate to={user.role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard'} replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute allowedRoles={['user', 'admin']}><UserDashboard /></ProtectedRoute>} />
        <Route path="/dashboard/podcaster" element={<ProtectedRoute allowedRoles={['podcaster']}><PodcasterDashboard /></ProtectedRoute>} />
        <Route path="/library" element={<ProtectedRoute allowedRoles={['user', 'admin']}><LibraryPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/browse" element={<BrowsePage />} />
        <Route path="/shows/:showId" element={<ShowPage />} />
        <Route path="/episodes/:podcastId" element={<EpisodeDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <PlayerBar />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <PlayerProvider>
          <AppRoutes />
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: '#141417',
                border: '1px solid #27272A',
                color: '#F8F8F8',
              },
            }}
          />
        </PlayerProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
