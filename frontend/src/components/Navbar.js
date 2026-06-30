import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BookmarkSimple, Broadcast, Code, Gear, House, MagnifyingGlass, Microphone, SignOut, User } from '@phosphor-icons/react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <nav className="backdrop-blur-xl bg-[#0A0A0B]/70 border-b border-[#27272A]/50 sticky top-0 z-50" data-testid="navbar">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 lg:px-12 flex items-center justify-between h-16 gap-3">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#F5A623] flex items-center justify-center">
            <Microphone weight="bold" className="text-[#0A0A0B] w-4 h-4" />
          </div>
          <span className="font-['Outfit'] text-lg font-bold text-white tracking-tight">Audioraq</span>
        </Link>

        <div className="flex items-center gap-3 md:gap-5 lg:gap-6">
          <Link
            to="/browse"
            className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
            data-testid="nav-browse-link"
            aria-label="Browse"
          >
            <MagnifyingGlass weight="bold" className="w-4 h-4" />
            <span className="hidden lg:inline">Browse</span>
          </Link>

          <Link
            to="/developers"
            className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
            data-testid="nav-developers-link"
            aria-label="Audioraq API"
          >
            <Code weight="bold" className="w-4 h-4" />
            <span className="hidden lg:inline">API</span>
          </Link>

          {user?.role ? (
            <>
              <Link
                to={user.role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard'}
                className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
                data-testid="nav-dashboard-link"
                aria-label={user.role === 'podcaster' ? 'Creator Studio' : 'Home'}
              >
                {user.role === 'podcaster' ? <Broadcast weight="bold" className="w-4 h-4" /> : <House weight="bold" className="w-4 h-4" />}
                <span className="hidden xl:inline">{user.role === 'podcaster' ? 'Studio' : 'Home'}</span>
              </Link>

              {user.role !== 'podcaster' && (
                <Link
                  to="/library"
                  className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
                  data-testid="nav-library-link"
                  aria-label="Library"
                >
                  <BookmarkSimple weight="bold" className="w-4 h-4" />
                  <span className="hidden xl:inline">Library</span>
                </Link>
              )}

              <Link
                to="/settings"
                className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
                data-testid="nav-settings-link"
                aria-label="Settings"
              >
                <Gear weight="bold" className="w-4 h-4" />
                <span className="hidden xl:inline">Settings</span>
              </Link>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-2 bg-[#141417] border border-[#27272A] rounded-full px-3 py-1.5 hover:border-[#F5A623]/50 transition-colors" data-testid="user-menu-trigger">
                    <div className="w-6 h-6 rounded-full bg-[#F5A623]/20 flex items-center justify-center">
                      <User weight="bold" className="w-3.5 h-3.5 text-[#F5A623]" />
                    </div>
                    <span className="hidden xl:inline text-sm text-white font-medium max-w-[100px] truncate">{user?.name || 'User'}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="bg-[#141417] border-[#27272A] min-w-[180px]">
                  <div className="px-3 py-2">
                    <p className="text-sm font-medium text-white">{user?.name}</p>
                    <p className="text-xs text-[#8A8A93]">{user?.email}</p>
                    <span className="inline-block mt-1 bg-[#27272A] text-[10px] text-[#F5A623] px-2 py-0.5 rounded-full uppercase tracking-widest font-bold">
                      {user?.role}
                    </span>
                  </div>
                  <DropdownMenuSeparator className="bg-[#27272A]" />
                  <DropdownMenuItem
                    onClick={handleLogout}
                    className="text-[#EF4444] focus:text-[#EF4444] focus:bg-[#EF4444]/10 cursor-pointer"
                    data-testid="logout-btn"
                  >
                    <SignOut weight="bold" className="w-4 h-4 mr-2" />
                    Sign Out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : (
            <div className="flex items-center gap-2 sm:gap-4">
              <Link
                to="/login"
                className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium"
                data-testid="nav-login-link"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-4 sm:px-5 py-2.5 transition-colors text-sm"
                data-testid="nav-register-link"
              >
                <span className="sm:hidden">Join</span>
                <span className="hidden sm:inline">Get Started</span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
