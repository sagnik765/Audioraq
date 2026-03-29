import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Microphone, MagnifyingGlass, Headphones, WaveformSlash } from '@phosphor-icons/react';

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[#0A0A0B]" data-testid="landing-page">
      {/* Hero Section */}
      <div className="relative min-h-screen flex items-center overflow-hidden">
        {/* Background Image */}
        <div className="absolute inset-0">
          <img
            src="https://images.unsplash.com/photo-1709846486154-f9172678be6f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA4Mzl8MHwxfHNlYXJjaHwzfHxwb2RjYXN0JTIwbWljcm9waG9uZSUyMHN0dWRpbyUyMGRhcmt8ZW58MHx8fHwxNzc0NzgxMzcyfDA&ixlib=rb-4.1.0&q=85"
            alt="Studio microphone"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0B] via-[#0A0A0B]/85 to-[#0A0A0B]/40" />
        </div>

        {/* Nav */}
        <nav className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between p-6 md:p-8 lg:px-12">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#F5A623] flex items-center justify-center">
              <Microphone weight="bold" className="text-[#0A0A0B] w-5 h-5" />
            </div>
            <span className="font-['Outfit'] text-xl font-bold text-white tracking-tight">Podlyzer</span>
          </Link>
          <div className="flex items-center gap-4">
            {user && user.role ? (
              <Link
                to={user.role === 'podcaster' ? '/dashboard/podcaster' : '/dashboard'}
                className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-2.5 transition-colors text-sm"
                data-testid="go-to-dashboard-btn"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-[#8A8A93] hover:text-white transition-colors text-sm font-medium"
                  data-testid="login-nav-btn"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-2.5 transition-colors text-sm"
                  data-testid="register-nav-btn"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </nav>

        {/* Hero Content */}
        <div className="relative z-10 max-w-3xl px-6 md:px-8 lg:px-12 opacity-0 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 bg-[#141417]/80 border border-[#27272A] rounded-full px-4 py-2 mb-8">
            <span className="w-2 h-2 rounded-full bg-[#F5A623] animate-pulse" />
            <span className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93]">A platform built for podcasters</span>
          </div>
          <h1 className="font-['Outfit'] text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-bold text-white leading-[1.1] mb-6">
            Your podcast deserves<br />
            <span className="text-[#F5A623]">its own stage.</span>
          </h1>
          <p className="text-base text-[#8A8A93] leading-relaxed max-w-xl mb-10">
            Stop competing with short-form content. Podlyzer is a dedicated platform where podcasters connect directly with listeners who are searching for exactly what you create.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link
              to="/register"
              className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3.5 transition-colors inline-flex items-center gap-2"
              data-testid="hero-get-started-btn"
            >
              <Microphone weight="bold" className="w-5 h-5" />
              Start Podcasting
            </Link>
            <Link
              to="/browse"
              className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-8 py-3.5 transition-colors inline-flex items-center gap-2"
              data-testid="hero-browse-btn"
            >
              <Headphones weight="bold" className="w-5 h-5" />
              Browse Podcasts
            </Link>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <section className="py-24 px-6 md:px-8 lg:px-12">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16 opacity-0 animate-fade-in-up stagger-1">
            <span className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-4 block">Why Podlyzer</span>
            <h2 className="font-['Outfit'] text-2xl sm:text-3xl lg:text-4xl tracking-tight font-semibold text-white">
              Built exclusively for podcasts
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: <Microphone weight="duotone" className="w-8 h-8 text-[#F5A623]" />,
                title: "For Podcasters",
                desc: "Upload your audio and video content. Your show gets discovered by listeners actively searching for your niche."
              },
              {
                icon: <MagnifyingGlass weight="duotone" className="w-8 h-8 text-[#F5A623]" />,
                title: "Smart Discovery",
                desc: "AI-powered recommendations match listeners with podcasts based on their interests and viewing history."
              },
              {
                icon: <WaveformSlash weight="duotone" className="w-8 h-8 text-[#F5A623]" />,
                title: "No Noise",
                desc: "No short videos, no memes. Just podcasts. Your content isn't buried under unrelated media."
              }
            ].map((feature, i) => (
              <div
                key={i}
                className="bg-[#141417] border border-[#27272A] rounded-xl p-8 transition-transform duration-300 hover:-translate-y-1 opacity-0 animate-fade-in-up"
                style={{ animationDelay: `${0.2 + i * 0.1}s` }}
              >
                <div className="w-14 h-14 rounded-xl bg-[#F5A623]/10 flex items-center justify-center mb-6">
                  {feature.icon}
                </div>
                <h3 className="font-['Outfit'] text-xl font-medium text-white mb-3">{feature.title}</h3>
                <p className="text-sm text-[#8A8A93] leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 md:px-8 lg:px-12">
        <div className="max-w-4xl mx-auto text-center bg-[#141417] border border-[#27272A] rounded-2xl p-12 md:p-16 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-[#F5A623]/5 to-transparent" />
          <div className="relative z-10">
            <h2 className="font-['Outfit'] text-2xl sm:text-3xl lg:text-4xl tracking-tight font-semibold text-white mb-4">
              Ready to be heard?
            </h2>
            <p className="text-[#8A8A93] mb-8 max-w-md mx-auto">
              Join the community of podcasters and listeners who value quality content.
            </p>
            <Link
              to="/register"
              className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-8 py-3.5 transition-colors inline-block"
              data-testid="cta-get-started-btn"
            >
              Create Your Account
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#27272A] py-8 px-6 md:px-8 lg:px-12">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Microphone weight="bold" className="text-[#F5A623] w-4 h-4" />
            <span className="text-sm text-[#8A8A93]">Podlyzer</span>
          </div>
          <span className="text-xs text-[#8A8A93]">&copy; 2026 Podlyzer</span>
        </div>
      </footer>
    </div>
  );
}
