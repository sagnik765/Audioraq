import React, { useState } from 'react';
import axios from 'axios';
import { ChatCircleDots, X } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { API } from '../lib/api';

const categories = [
  { value: 'confusing', label: 'Confusing' },
  { value: 'missing_feature', label: 'Missing feature' },
  { value: 'bug', label: 'Bug' },
  { value: 'delight', label: 'Loved it' },
  { value: 'pricing', label: 'Pricing' },
  { value: 'launch', label: 'Launch feedback' },
  { value: 'other', label: 'Other' },
];

function inferPersona(user) {
  if (user?.role === 'podcaster') return 'podcaster';
  if (user?.role === 'user') return 'listener';
  return 'visitor';
}

export default function FeedbackWidget() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [category, setCategory] = useState('confusing');
  const [rating, setRating] = useState(4);
  const [message, setMessage] = useState('');
  const [desiredOutcome, setDesiredOutcome] = useState('');
  const [frictionArea, setFrictionArea] = useState('');
  const [email, setEmail] = useState('');
  const [contactOk, setContactOk] = useState(false);

  const reset = () => {
    setCategory('confusing');
    setRating(4);
    setMessage('');
    setDesiredOutcome('');
    setFrictionArea('');
    setEmail('');
    setContactOk(false);
  };

  const submitFeedback = async (event) => {
    event.preventDefault();
    if (message.trim().length < 8) {
      toast.error('Add a little more detail so we can act on it.');
      return;
    }

    setSubmitting(true);
    try {
      await axios.post(`${API}/feedback`, {
        persona: inferPersona(user),
        category,
        rating: Number(rating),
        page_url: window.location.href,
        message: message.trim(),
        desired_outcome: desiredOutcome.trim(),
        friction_area: frictionArea.trim(),
        email: email.trim(),
        contact_ok: contactOk,
      }, { withCredentials: true });
      toast.success('Feedback sent. This goes into the founder review loop.');
      reset();
      setOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not send feedback');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-24 left-5 z-50 inline-flex items-center gap-2 rounded-full border border-[#27272A] bg-[#141417]/95 px-4 py-3 text-sm font-semibold text-white shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl hover:border-[#F5A623] transition-colors"
        data-testid="feedback-open-btn"
      >
        <ChatCircleDots weight="bold" className="w-4 h-4 text-[#F5A623]" />
        Feedback
      </button>

      {open && (
        <div className="fixed inset-0 z-[70] bg-black/70 backdrop-blur-sm flex items-center justify-center px-4 py-8">
          <div className="w-full max-w-2xl bg-[#141417] border border-[#27272A] rounded-3xl shadow-[0_24px_80px_rgba(0,0,0,0.55)] overflow-hidden">
            <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-[#27272A]">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-1">Founder Feedback Loop</p>
                <h2 className="font-['Outfit'] text-2xl font-semibold text-white">Tell us what would make Audioraq harder to ignore</h2>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-[#8A8A93] hover:text-white transition-colors"
                aria-label="Close feedback"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={submitFeedback} className="px-6 py-6 space-y-5">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-[0.18em] font-semibold text-[#8A8A93] mb-2 block">Feedback type</label>
                  <select
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  >
                    {categories.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-[0.18em] font-semibold text-[#8A8A93] mb-2 block">How useful is Audioraq right now?</label>
                  <select
                    value={rating}
                    onChange={(event) => setRating(event.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  >
                    {[5, 4, 3, 2, 1].map((score) => (
                      <option key={score} value={score}>{score} / 5</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs uppercase tracking-[0.18em] font-semibold text-[#8A8A93] mb-2 block">What happened?</label>
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-xl text-white px-4 py-3 outline-none min-h-[130px] resize-none"
                  placeholder="Example: I wanted to create a podcast but did not know what to do after the AI draft."
                  data-testid="feedback-message-input"
                />
              </div>

              <div>
                <label className="text-xs uppercase tracking-[0.18em] font-semibold text-[#8A8A93] mb-2 block">What should Audioraq help you do better?</label>
                <input
                  type="text"
                  value={desiredOutcome}
                  onChange={(event) => setDesiredOutcome(event.target.value)}
                  className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                  placeholder="Example: publish a better episode faster, find the right show, trust recommendations"
                />
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-[0.18em] font-semibold text-[#8A8A93] mb-2 block">Where did it happen?</label>
                  <input
                    type="text"
                    value={frictionArea}
                    onChange={(event) => setFrictionArea(event.target.value)}
                    className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                    placeholder="Browse, Create with AI, playback, onboarding..."
                  />
                </div>
                {!user && (
                  <div>
                    <label className="text-xs uppercase tracking-[0.18em] font-semibold text-[#8A8A93] mb-2 block">Email for follow-up</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
                      placeholder="Optional"
                    />
                  </div>
                )}
              </div>

              <label className="flex items-start gap-3 text-sm text-[#C7C7D1]">
                <input
                  type="checkbox"
                  checked={contactOk}
                  onChange={(event) => setContactOk(event.target.checked)}
                  className="mt-1"
                />
                You can follow up with me about this feedback.
              </label>

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
                <p className="text-xs text-[#8A8A93]">Submissions are analyzed for product priorities and founder review.</p>
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-6 py-3 transition-colors disabled:opacity-50"
                  data-testid="feedback-submit-btn"
                >
                  {submitting ? 'Sending...' : 'Send feedback'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
