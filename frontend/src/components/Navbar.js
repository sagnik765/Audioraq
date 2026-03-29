import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Microphone, SignOut, User, MagnifyingGlass, House } from '@phosphor-icons/react';
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
      <div className="max-w-7xl mx-auto px-6 md:px-8 lg:px-12 flex items-center justify-between h-16">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#F5A623] flex items-center justify-center">
            <Microphone weight="bold" className="text-[#0A0A0B] w-4 h-4" />
          </div>
          <span className="font-['Outfit'] text-lg font-bold text-white tracking-tight">Podlyzer</span>
        </Link>

        {/* Nav Links */}
        <div className="flex items-center gap-6">
          <Link to={user?.role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard'}
            className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
            data-testid="nav-dashboard-link">
            <House weight="bold" className="w-4 h-4" />
            Dashboard
          </Link>
          <Link to="/browse"
            className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium flex items-center gap-1.5"
            data-testid="nav-browse-link">
            <MagnifyingGlass weight="bold" className="w-4 h-4" />
            Browse
          </Link>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 bg-[#141417] border border-[#27272A] rounded-full px-3 py-1.5 hover:border-[#F5A623]/50 transition-colors" data-testid="user-menu-trigger">
                <div className="w-6 h-6 rounded-full bg-[#F5A623]/20 flex items-center justify-center">
                  <User weight="bold" className="w-3.5 h-3.5 text-[#F5A623]" />
                </div>
                <span className="text-sm text-white font-medium max-w-[100px] truncate">{user?.name || 'User'}</span>
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
        </div>
      </div>
    </nav>
  );
}
