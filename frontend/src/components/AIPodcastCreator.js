import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { PencilSimple, Play, Plus } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { API } from '../lib/api';
import { displayAIText } from '../lib/displayText';

function uniqueSuggestions(values) {
  return [...new Set((values || []).filter(Boolean).map((value) => String(value).trim()).filter(Boolean))];
}

function buildInitialBrief(activeShow) {
  const categoryHint = activeShow?.category && activeShow.category !== 'general' ? activeShow.category : '';
  const showTitle = activeShow?.title || '';

  return {
    identity: {
      podcastName: showTitle,
      niche: categoryHint,
      targetAudience: '',
    },
    episodeIntent: {
      episodeGoal: 'educate',
      desiredOutcome: '',
    },
    contentInput: {
      topic: '',
      keyPoints: [],
      references: [],
    },
    toneStyle: {
      tone: categoryHint === 'comedy' ? 'energetic' : 'professional',
      format: 'solo',
      lengthPreference: 'medium',
    },
    growthOptimization: {
      optimizeFor: 'clarity',
      includeHook: true,
      knownIssues: '',
    },
    voiceCasting: {
      selectedVoiceIds: ['aman-warm-analyst', 'samantha-warm-cohost', 'daniel-calm-british'],
    },
  };
}

function getValueAtPath(source, path) {
  return path.reduce((value, key) => value?.[key], source);
}

function setValueAtPath(source, path, nextValue) {
  const clone = JSON.parse(JSON.stringify(source));
  let cursor = clone;
  for (let index = 0; index < path.length - 1; index += 1) {
    cursor = cursor[path[index]];
  }
  cursor[path[path.length - 1]] = nextValue;
  return clone;
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function normalizeListInput(value) {
  return value
    .split('\n')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function qualityTone(status) {
  if (status === 'blocked') return 'text-[#FF6B6B] border-[#FF6B6B]/40 bg-[#FF6B6B]/10';
  if (status === 'revise') return 'text-[#F5A623] border-[#F5A623]/40 bg-[#F5A623]/10';
  return 'text-[#2EC4B6] border-[#2EC4B6]/40 bg-[#2EC4B6]/10';
}

const studioStages = [
  { id: 'brief', label: 'Brief' },
  { id: 'research', label: 'Research' },
  { id: 'outline', label: 'Outline' },
  { id: 'script', label: 'Script' },
  { id: 'cast', label: 'Cast' },
  { id: 'table_read', label: 'Table Read' },
  { id: 'final_render', label: 'Render' },
  { id: 'quality_review', label: 'AI Agents' },
  { id: 'publish', label: 'Publish' },
];

function studioStatusTone(status) {
  if (['blocked', 'needs_revision'].includes(status)) return 'border-[#FF6B6B]/40 bg-[#FF6B6B]/10 text-[#FFB3B3]';
  if (['needs_review', 'queued', 'ready', 'in_progress'].includes(status)) return 'border-[#F5A623]/40 bg-[#F5A623]/10 text-[#FFD58A]';
  if (['complete', 'published'].includes(status)) return 'border-[#2EC4B6]/40 bg-[#2EC4B6]/10 text-[#9CF3EA]';
  return 'border-[#27272A] bg-[#141417] text-[#8A8A93]';
}

function formatStatus(status) {
  return String(status || 'pending').replace(/_/g, ' ');
}

const preferredScorecardOrder = [
  'hook_strength',
  'dialogue_realism',
  'voice_clarity',
  'voice_resonance',
  'voice_articulation',
  'podcast_voice_listenability',
  'specificity',
  'structure',
  'factual_safety',
  'audio_readiness',
  'publish_readiness',
];

const fallbackVoiceLibrary = [
  { id: 'aman-warm-analyst', name: 'Aman', gender: 'male', style: 'warm analyst', accent: 'Indian English', description: 'Warm, steady, and trustworthy for education or finance.' },
  { id: 'rishi-clear-guide', name: 'Rishi', gender: 'male', style: 'clear guide', accent: 'Indian English', description: 'Crisp and composed for explainers and founder conversations.' },
  { id: 'daniel-calm-british', name: 'Daniel', gender: 'male', style: 'calm British host', accent: 'British English', description: 'Polished and calm for law, current affairs, and long-form analysis.' },
  { id: 'reed-bright-teacher', name: 'Reed', gender: 'male', style: 'clear teacher', accent: 'Warm Indian English', description: 'Friendly and articulate for practical tutorials.' },
  { id: 'eddy-casual-host', name: 'Eddy', gender: 'male', style: 'casual host', accent: 'Warm Indian English', description: 'Conversational and approachable for creator-led shows.' },
  { id: 'rocko-energetic-host', name: 'Rocko', gender: 'male', style: 'energetic host', accent: 'American English', description: 'More energetic without rushing; useful for technology and startup topics.' },
  { id: 'grandpa-wise-narrator', name: 'Grandpa', gender: 'male', style: 'wise narrator', accent: 'American English', description: 'Grounded and patient for reflective storytelling.' },
  { id: 'oliver-uk-commentator', name: 'Oliver', gender: 'male', style: 'UK commentator', accent: 'British English', description: 'Composed and conversational for business and current-affairs contrast.' },
  { id: 'rowan-uk-analyst', name: 'Rowan', gender: 'male', style: 'UK analyst', accent: 'British English', description: 'Crisp, slightly brighter analyst voice for explainers.' },
  { id: 'roman-uk-host', name: 'Roman', gender: 'male', style: 'energetic host', accent: 'American English', description: 'Energetic but controlled for technology and startup discussions.' },
  { id: 'samantha-warm-cohost', name: 'Samantha', gender: 'female', style: 'warm co-host', accent: 'American English', description: 'Warm, clear, and easy to stay with for long listening.' },
  { id: 'tara-bright-indian', name: 'Tara', gender: 'female', style: 'bright Indian host', accent: 'Indian English', description: 'Bright and precise for education, health, and creator shows.' },
  { id: 'flo-friendly-guide', name: 'Flo', gender: 'female', style: 'friendly guide', accent: 'American English', description: 'Friendly and modern for onboarding-style episodes.' },
  { id: 'sandy-calm-educator', name: 'Sandy', gender: 'female', style: 'calm educator', accent: 'American English', description: 'Clear, relaxed, and teacherly for explainers.' },
  { id: 'shelley-story-host', name: 'Shelley', gender: 'female', style: 'story host', accent: 'American English', description: 'Expressive but controlled for narrative shows.' },
  { id: 'grandma-reflective-narrator', name: 'Grandma', gender: 'female', style: 'reflective narrator', accent: 'American English', description: 'Patient and intimate for reflective narration.' },
  { id: 'karen-australian-guide', name: 'Karen', gender: 'female', style: 'Australian guide', accent: 'Australian English', description: 'Clean and composed for global business and environment shows.' },
  { id: 'moira-irish-storyteller', name: 'Moira', gender: 'female', style: 'reflective storyteller', accent: 'Warm neutral English', description: 'Textured and warm for story-led episodes.' },
  { id: 'tessa-global-host', name: 'Tessa', gender: 'female', style: 'global host', accent: 'South African English', description: 'Distinctive and articulate for international topics.' },
  { id: 'fiona-british-guide', name: 'Fiona', gender: 'female', style: 'British guide', accent: 'British English', description: 'Friendly and precise for educational recaps and guided explainers.' },
];

function firstScorecardEntries(scorecard) {
  const available = scorecard || {};
  const prioritized = preferredScorecardOrder
    .filter((key) => available[key])
    .map((key) => [key, available[key]]);
  const leftovers = Object.entries(available).filter(([key]) => !preferredScorecardOrder.includes(key));
  return [...prioritized, ...leftovers].slice(0, 8);
}

function isStepComplete(step, value) {
  if (step.optional) return true;
  if (step.type === 'list') return Array.isArray(value) && value.length > 0;
  if (step.type === 'voice-multi') return Array.isArray(value) && value.length > 0;
  if (step.type === 'boolean') return typeof value === 'boolean';
  return String(value || '').trim().length > 0;
}

export default function AIPodcastCreator({
  shows,
  selectedShowId,
  onSelectShow,
  activeShow,
  onApplyDraft,
  seedBrief,
}) {
  const [brief, setBrief] = useState(() => buildInitialBrief(activeShow));
  const [stepIndex, setStepIndex] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [renderJobLoading, setRenderJobLoading] = useState(false);
  const [generatedDraft, setGeneratedDraft] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [voiceLibrary, setVoiceLibrary] = useState(fallbackVoiceLibrary);

  useEffect(() => {
    setBrief((current) => ({
      ...current,
      identity: {
        ...current.identity,
        podcastName: current.identity.podcastName || activeShow?.title || '',
        niche: current.identity.niche || ((activeShow?.category && activeShow.category !== 'general') ? activeShow.category : ''),
      },
    }));
  }, [activeShow?.category, activeShow?.title]);

  useEffect(() => {
    if (!seedBrief || typeof seedBrief !== 'object') return;
    setBrief(seedBrief);
    setGeneratedDraft(null);
    setActiveProject(null);
    setStepIndex(0);
    toast.success('Loaded an AI Strategist idea into the brief.');
  }, [seedBrief]);

  useEffect(() => {
    let isMounted = true;
    axios.get(`${API}/ai-voice-library`)
      .then(({ data }) => {
        if (isMounted && Array.isArray(data.voices) && data.voices.length >= 20) {
          setVoiceLibrary(data.voices);
          setBrief((current) => ({
            ...current,
            voiceCasting: {
              ...current.voiceCasting,
              selectedVoiceIds: current.voiceCasting?.selectedVoiceIds?.length
                ? current.voiceCasting.selectedVoiceIds
                : (data.defaults || fallbackVoiceLibrary.slice(0, 3).map((voice) => voice.id)),
            },
          }));
        }
      })
      .catch(() => setVoiceLibrary(fallbackVoiceLibrary));
    return () => {
      isMounted = false;
    };
  }, []);

  const steps = useMemo(() => {
    const nicheSuggestions = uniqueSuggestions([
      activeShow?.category && activeShow.category !== 'general' ? activeShow.category : '',
      'technology',
      'business',
      'education',
      'health',
    ]);

    return [
      {
        id: 'podcastName',
        category: 'Podcast Identity',
        label: 'Podcast name',
        prompt: 'What should this episode feel connected to?',
        help: 'This can match your show title or the umbrella name you want the episode to live under.',
        type: 'text',
        path: ['identity', 'podcastName'],
        placeholder: activeShow?.title || 'Signal Over Noise',
        suggestions: uniqueSuggestions([activeShow?.title, `${activeShow?.title || 'Signal Over Noise'} Deep Dive`]),
      },
      {
        id: 'niche',
        category: 'Podcast Identity',
        label: 'Niche',
        prompt: 'Which niche or domain should the AI stay anchored in?',
        help: 'Keeping this specific helps the outline sound like a real show, not generic content.',
        type: 'text',
        path: ['identity', 'niche'],
        placeholder: 'technology, founder stories, policy, health, sports...',
        suggestions: nicheSuggestions,
      },
      {
        id: 'targetAudience',
        category: 'Podcast Identity',
        label: 'Target audience',
        prompt: 'Who exactly are we making this episode for?',
        help: 'Be concrete about who should feel this was made for them.',
        type: 'text',
        path: ['identity', 'targetAudience'],
        placeholder: 'busy founders who want practical operating insight',
        suggestions: [
          'busy professionals who want clear signal fast',
          'curious listeners who want a smarter breakdown',
          'operators looking for practical next steps',
        ],
      },
      {
        id: 'episodeGoal',
        category: 'Episode Intent',
        label: 'Episode goal',
        prompt: 'What is the main job of this episode?',
        help: 'Choose the primary intent so the structure does not drift.',
        type: 'option',
        path: ['episodeIntent', 'episodeGoal'],
        options: [
          { value: 'educate', label: 'Educate', description: 'Teach something clearly and usefully.' },
          { value: 'entertain', label: 'Entertain', description: 'Keep it lively and memorable.' },
          { value: 'storytelling', label: 'Storytelling', description: 'Lead with narrative and tension.' },
          { value: 'interview', label: 'Interview', description: 'Design around strong questions and answers.' },
        ],
      },
      {
        id: 'desiredOutcome',
        category: 'Episode Intent',
        label: 'Desired outcome',
        prompt: 'What should listeners know, feel, or do by the end?',
        help: 'This is the finish line the AI will optimize around.',
        type: 'text',
        path: ['episodeIntent', 'desiredOutcome'],
        placeholder: 'walk away with a practical framework they can apply this week',
        suggestions: [
          'leave with a framework they can apply immediately',
          'feel more confident about the topic',
          'see the tradeoffs more clearly',
        ],
      },
      {
        id: 'topic',
        category: 'Content Input',
        label: 'Topic',
        prompt: 'What is the central topic for this episode?',
        help: 'Phrase it the way you would pitch it to a listener.',
        type: 'text',
        path: ['contentInput', 'topic'],
        placeholder: 'How founders can make better hiring decisions early',
      },
      {
        id: 'keyPoints',
        category: 'Content Input',
        label: 'Key points',
        prompt: 'What are the must-hit points or beats?',
        help: 'Use one point per line. The AI will turn these into the episode spine.',
        type: 'list',
        path: ['contentInput', 'keyPoints'],
        placeholder: 'The mistake most people make\nA useful framework\nA real example or story\nThe action step',
      },
      {
        id: 'references',
        category: 'Content Input',
        label: 'References',
        prompt: 'Any sources, links, books, or examples the AI should respect?',
        help: 'Optional. One reference per line.',
        type: 'list',
        path: ['contentInput', 'references'],
        optional: true,
        placeholder: 'https://example.com/article\nA book title\nA report or case study',
      },
      {
        id: 'tone',
        category: 'Tone & Style',
        label: 'Tone',
        prompt: 'What tone should the episode use?',
        help: 'This affects the hook, pacing, and how the script opens.',
        type: 'option',
        path: ['toneStyle', 'tone'],
        options: [
          { value: 'casual', label: 'Casual', description: 'Relaxed and easy to follow.' },
          { value: 'professional', label: 'Professional', description: 'Clear, credible, and polished.' },
          { value: 'energetic', label: 'Energetic', description: 'High momentum without feeling noisy.' },
          { value: 'storytelling', label: 'Storytelling', description: 'Narrative-led and scene-driven.' },
        ],
      },
      {
        id: 'format',
        category: 'Tone & Style',
        label: 'Format',
        prompt: 'Which format should the AI structure for?',
        help: 'The outline and talking points will adapt to this.',
        type: 'option',
        path: ['toneStyle', 'format'],
        options: [
          { value: 'solo', label: 'Solo', description: 'One voice, focused and direct.' },
          { value: 'interview', label: 'Interview', description: 'Lead with guest questions and responses.' },
          { value: 'narrative', label: 'Narrative', description: 'Build with scenes and progression.' },
        ],
      },
      {
        id: 'selectedVoiceIds',
        category: 'Voice Casting',
        label: 'Voices',
        prompt: 'Which voices should Audioraq cast for this episode?',
        help: 'Choose up to 4 voices. Different speakers will rotate through your choices, and final audio uses one-second sentence gaps so the episode does not feel rushed.',
        type: 'voice-multi',
        path: ['voiceCasting', 'selectedVoiceIds'],
        options: voiceLibrary,
      },
      {
        id: 'lengthPreference',
        category: 'Tone & Style',
        label: 'Length',
        prompt: 'How long should this episode feel?',
        help: 'This influences the scope of the outline, not an exact minute count.',
        type: 'option',
        path: ['toneStyle', 'lengthPreference'],
        options: [
          { value: 'short', label: 'Short', description: 'Tight, focused, and quick to finish.' },
          { value: 'medium', label: 'Medium', description: 'Balanced depth and pace.' },
          { value: 'long', label: 'Long', description: 'Go deeper with more examples and layers.' },
        ],
      },
      {
        id: 'optimizeFor',
        category: 'Growth Optimization',
        label: 'Optimize for',
        prompt: 'What should the AI prioritize most?',
        help: 'This is the main growth lens for the hook and structure.',
        type: 'option',
        path: ['growthOptimization', 'optimizeFor'],
        options: [
          { value: 'retention', label: 'Retention', description: 'Keep listeners staying through the full episode.' },
          { value: 'virality', label: 'Virality', description: 'Make the angle especially shareable.' },
          { value: 'clarity', label: 'Clarity', description: 'Make the message easy to follow and remember.' },
        ],
      },
      {
        id: 'includeHook',
        category: 'Growth Optimization',
        label: 'Include hook',
        prompt: 'Do you want the AI to open with a sharper hook?',
        help: 'Recommended for most discovery-oriented episodes.',
        type: 'boolean',
        path: ['growthOptimization', 'includeHook'],
        options: [
          { value: true, label: 'Yes', description: 'Lead with a stronger cold open.' },
          { value: false, label: 'No', description: 'Open more directly and calmly.' },
        ],
      },
      {
        id: 'knownIssues',
        category: 'Growth Optimization',
        label: 'Known issues',
        prompt: 'Any pitfalls the AI should avoid or solve around?',
        help: 'Optional. Mention concerns like sounding too generic, too technical, or too long.',
        type: 'textarea',
        path: ['growthOptimization', 'knownIssues'],
        optional: true,
        placeholder: 'Avoid jargon. Keep the intro tight. Do not sound salesy.',
      },
    ];
  }, [activeShow?.category, activeShow?.title, voiceLibrary]);

  const currentStep = steps[stepIndex];
  const currentValue = getValueAtPath(brief, currentStep.path);
  const canProceed = isStepComplete(currentStep, currentValue);

  const fetchDrafts = useCallback(async () => {
    if (!selectedShowId) {
      setDrafts([]);
      return;
    }

    setDraftsLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/ai-podcast-drafts/my?show_id=${encodeURIComponent(selectedShowId)}`,
        { withCredentials: true },
      );
      setDrafts(data.drafts || []);
    } catch {
      setDrafts([]);
    } finally {
      setDraftsLoading(false);
    }
  }, [selectedShowId]);

  const fetchProjects = useCallback(async () => {
    if (!selectedShowId) {
      setProjects([]);
      setActiveProject(null);
      return;
    }

    setProjectsLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/ai-studio/projects/my?show_id=${encodeURIComponent(selectedShowId)}`,
        { withCredentials: true },
      );
      const nextProjects = data.projects || [];
      setProjects(nextProjects);
      setActiveProject((current) => {
        if (current?.id && nextProjects.some((project) => project.id === current.id)) {
          return nextProjects.find((project) => project.id === current.id);
        }
        return nextProjects[0] || null;
      });
    } catch {
      setProjects([]);
    } finally {
      setProjectsLoading(false);
    }
  }, [selectedShowId]);

  useEffect(() => {
    fetchDrafts();
  }, [fetchDrafts]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const updateBriefValue = (nextValue) => {
    setBrief((current) => setValueAtPath(current, currentStep.path, nextValue));
  };

  const handleSuggestion = (suggestion) => {
    if (currentStep.type === 'list') {
      const existing = Array.isArray(currentValue) ? currentValue : [];
      updateBriefValue([...new Set([...existing, suggestion])]);
      return;
    }
    updateBriefValue(suggestion);
  };

  const toggleVoiceSelection = (voiceId) => {
    const existing = Array.isArray(currentValue) ? currentValue : [];
    if (existing.includes(voiceId)) {
      updateBriefValue(existing.filter((id) => id !== voiceId));
      return;
    }
    if (existing.length >= 4) {
      toast.error('Choose up to 4 voices for one episode.');
      return;
    }
    updateBriefValue([...existing, voiceId]);
  };

  const handleGenerate = async () => {
    if (!selectedShowId) {
      toast.error('Create a show first so the AI draft has a real home in your catalog.');
      return;
    }

    setIsGenerating(true);
    try {
      const { data } = await axios.post(
        `${API}/ai-podcast-drafts/generate`,
        { show_id: selectedShowId, intake: brief },
        { withCredentials: true },
      );
      setGeneratedDraft(data);
      setDrafts((current) => [data, ...current.filter((draft) => draft.id !== data.id)].slice(0, 8));
      if (data.ai_studio_project) {
        setActiveProject(data.ai_studio_project);
        setProjects((current) => [data.ai_studio_project, ...current.filter((project) => project.id !== data.ai_studio_project.id)].slice(0, 12));
      } else {
        fetchProjects();
      }
      toast.success('AI Studio project is ready');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not generate the AI podcast draft');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleNext = () => {
    if (stepIndex === steps.length - 1) {
      handleGenerate();
      return;
    }
    setStepIndex((current) => Math.min(current + 1, steps.length - 1));
  };

  const handleStartFresh = () => {
    setBrief(buildInitialBrief(activeShow));
    setGeneratedDraft(null);
    setActiveProject(null);
    setStepIndex(0);
  };

  const handleReuseDraft = (draft) => {
    setBrief(draft.intake || buildInitialBrief(activeShow));
    setGeneratedDraft(draft);
    setActiveProject(draft.ai_studio_project || projects.find((project) => project.id === draft.ai_studio_project_id) || null);
    setStepIndex(0);
    toast.success('Loaded that AI brief back into the flow');
  };

  const handleQueueRender = async () => {
    const project = activeProject || generatedDraft?.ai_studio_project;
    if (!project?.id) {
      toast.error('Generate or select an AI Studio project first.');
      return;
    }
    setRenderJobLoading(true);
    try {
      await axios.post(
        `${API}/ai-studio/render-jobs`,
        {
          project_id: project.id,
          draft_id: generatedDraft?.id || project.source_draft_id || '',
          render_type: 'preview',
        },
        { withCredentials: true },
      );
      toast.success('Preview render queued for the AI Studio pipeline');
      fetchProjects();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not queue the render job');
    } finally {
      setRenderJobLoading(false);
    }
  };

  const renderInput = () => {
    if (currentStep.type === 'voice-multi') {
      const selectedVoices = Array.isArray(currentValue) ? currentValue : [];
      return (
        <div>
          <div className="flex items-center justify-between gap-4 mb-4">
            <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93]">
              {selectedVoices.length}/4 selected
            </p>
            <button
              type="button"
              onClick={() => updateBriefValue(['aman-warm-analyst', 'samantha-warm-cohost', 'daniel-calm-british'])}
              className="text-xs text-[#F5A623] hover:text-[#F7B84B]"
            >
              Reset to recommended cast
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[430px] overflow-auto pr-1">
            {currentStep.options.map((voice) => {
              const isSelected = selectedVoices.includes(voice.id);
              return (
                <button
                  type="button"
                  key={voice.id}
                  onClick={() => toggleVoiceSelection(voice.id)}
                  className={`text-left rounded-2xl border p-4 transition-all ${
                    isSelected
                      ? 'border-[#F5A623] bg-[#F5A623]/10'
                      : 'border-[#27272A] bg-[#141417] hover:border-[#F5A623]/60'
                  }`}
                  data-testid={`ai-voice-option-${voice.id}`}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <p className="text-white font-semibold">{voice.name}</p>
                      <p className="text-xs text-[#F5A623] capitalize">{voice.gender} · {voice.style}</p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.14em] ${
                      isSelected ? 'bg-[#F5A623] text-[#0A0A0B]' : 'bg-[#0A0A0B] text-[#8A8A93]'
                    }`}>
                      {isSelected ? 'Selected' : 'Choose'}
                    </span>
                  </div>
                  <p className="text-xs text-[#8A8A93] mb-2">{voice.accent}</p>
                  <p className="text-sm text-[#C7C7D1] leading-relaxed">{voice.description}</p>
                </button>
              );
            })}
          </div>
        </div>
      );
    }

    if (currentStep.type === 'option' || currentStep.type === 'boolean') {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {currentStep.options.map((option) => {
            const isSelected = currentValue === option.value;
            return (
              <button
                key={String(option.value)}
                type="button"
                onClick={() => updateBriefValue(option.value)}
                className={`text-left rounded-2xl border p-4 transition-all ${
                  isSelected
                    ? 'border-[#F5A623] bg-[#F5A623]/10'
                    : 'border-[#27272A] bg-[#0A0A0B] hover:border-[#8A8A93]'
                }`}
                data-testid={`ai-step-option-${currentStep.id}-${String(option.value)}`}
              >
                <p className="text-sm font-semibold text-white mb-1">{option.label}</p>
                <p className="text-xs text-[#8A8A93] leading-relaxed">{option.description}</p>
              </button>
            );
          })}
        </div>
      );
    }

    if (currentStep.type === 'list') {
      return (
        <textarea
          value={Array.isArray(currentValue) ? currentValue.join('\n') : ''}
          onChange={(event) => updateBriefValue(normalizeListInput(event.target.value))}
          placeholder={currentStep.placeholder}
          className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-2xl text-white px-4 py-4 min-h-[180px] outline-none resize-none"
          data-testid={`ai-step-input-${currentStep.id}`}
        />
      );
    }

    if (currentStep.type === 'textarea') {
      return (
        <textarea
          value={currentValue || ''}
          onChange={(event) => updateBriefValue(event.target.value)}
          placeholder={currentStep.placeholder}
          className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-2xl text-white px-4 py-4 min-h-[160px] outline-none resize-none"
          data-testid={`ai-step-input-${currentStep.id}`}
        />
      );
    }

    return (
      <input
        type="text"
        value={currentValue || ''}
        onChange={(event) => updateBriefValue(event.target.value)}
        placeholder={currentStep.placeholder}
        className="w-full bg-[#0A0A0B] border border-[#27272A] focus:border-[#F5A623] rounded-2xl text-white px-4 py-4 outline-none"
        data-testid={`ai-step-input-${currentStep.id}`}
      />
    );
  };

  const displayedProject = activeProject || generatedDraft?.ai_studio_project || null;
  const projectArtifacts = displayedProject?.artifacts || {};
  const stageState = displayedProject?.stage_state || {};
  const claimCards = projectArtifacts.research?.claim_cards || [];
  const cast = projectArtifacts.cast || [];
  const scriptTurns = projectArtifacts.script?.audio_script_turns || [];
  const scorecardEntries = firstScorecardEntries(
    displayedProject?.quality_review?.scorecard || generatedDraft?.quality_review?.scorecard,
  );

  return (
    <section className="bg-[#141417] border border-[#27272A] rounded-3xl p-8 mb-10" data-testid="ai-podcast-creator">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5 mb-8">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] font-semibold text-[#F5A623] mb-2">Create Podcast with AI</p>
          <h2 className="font-['Outfit'] text-2xl font-semibold text-white mb-2">Build an episode brief one answer at a time</h2>
          <p className="text-sm text-[#8A8A93] max-w-3xl">
            Audioraq keeps this conversational on purpose. You answer one focused question, we store the brief as structured JSON, and AI Agents turn it into an audio-only podcast package with quality scoring, safety retrieval, and self-feedback before it reaches publishing.
          </p>
        </div>

        <div className="min-w-[240px]">
          <label className="text-xs uppercase tracking-[0.2em] font-semibold text-[#8A8A93] mb-2 block">Working show</label>
          <select
            value={selectedShowId}
            onChange={(event) => onSelectShow(event.target.value)}
            className="w-full bg-[#0A0A0B] border border-[#27272A] rounded-xl text-white px-4 py-3 outline-none"
            data-testid="ai-show-select"
          >
            <option value="">Select a show</option>
            {shows.map((show) => <option key={show.id} value={show.id}>{show.title}</option>)}
          </select>
        </div>
      </div>

      {shows.length > 0 && (
        <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-6 mb-8" data-testid="ai-studio-production-room">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-6">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-[#F5A623] mb-2">AI Creator Studio</p>
              <h3 className="font-['Outfit'] text-xl font-semibold text-white mb-2">Production-room workflow</h3>
              <p className="text-sm text-[#8A8A93] max-w-3xl">
                This keeps Audioraq&apos;s USP focused: creators get guided podcast strategy, dialogue structure, source review, voice casting, AI Agents QA, and audio-only AI publishing in one simple pipeline.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              {projectsLoading && <span className="text-sm text-[#8A8A93] px-3 py-2">Loading Studio projects...</span>}
              <button
                type="button"
                onClick={handleQueueRender}
                disabled={!displayedProject?.id || renderJobLoading}
                className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-4 py-2 transition-colors disabled:opacity-40"
              >
                {renderJobLoading ? 'Queueing...' : 'Queue Preview Render'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-9 gap-3 mb-6">
            {studioStages.map((stage) => {
              const state = stageState[stage.id] || {};
              return (
                <div key={stage.id} className={`rounded-2xl border p-3 min-h-[92px] ${studioStatusTone(state.status)}`}>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] mb-2">{stage.label}</p>
                  <p className="text-[11px] uppercase tracking-[0.12em]">{formatStatus(state.status)}</p>
                  {state.notes && <p className="text-[11px] text-[#C7C7D1] mt-2 line-clamp-2">{state.notes}</p>}
                </div>
              );
            })}
          </div>

          {displayedProject ? (
            <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
              <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Show Bible</p>
                <h4 className="text-white font-semibold mb-2">{displayedProject.show_bible?.show_title || displayedProject.show_title}</h4>
                <p className="text-sm text-[#C7C7D1] leading-relaxed mb-3">
                  {displayedProject.show_bible?.positioning || 'Generate a brief to create the show bible.'}
                </p>
                <p className="text-xs text-[#F5A623] leading-relaxed">
                  {displayedProject.show_bible?.tone_contract || 'Tone contract appears after generation.'}
                </p>
              </div>

              <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Research Cards</p>
                {claimCards.length > 0 ? (
                  <div className="space-y-3 max-h-[260px] overflow-auto pr-1">
                    {claimCards.slice(0, 5).map((card) => (
                      <div key={card.id} className="border border-[#27272A] rounded-xl p-3">
                        <p className="text-sm text-white line-clamp-3">{card.claim}</p>
                        <p className="text-[11px] text-[#8A8A93] mt-2">
                          {card.source ? `Source: ${card.source}` : 'Needs creator review before factual recording'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[#8A8A93]">Claim cards appear after the AI builds an episode package.</p>
                )}
              </div>

              <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Cast & Table Read</p>
                <div className="space-y-3 mb-4">
                  {(cast.length ? cast : [{ speaker: 'Host', voice_role: 'host', delivery: 'Generate a script to assign voice roles.' }]).slice(0, 4).map((member) => (
                    <div key={`${member.speaker}-${member.voice_role}`} className="border border-[#27272A] rounded-xl p-3">
                      <p className="text-sm font-semibold text-white">{member.speaker} <span className="text-[#8A8A93] font-normal">/{member.voice_role}</span></p>
                      {member.voice_name && (
                        <p className="text-[11px] uppercase tracking-[0.14em] text-[#F5A623] mt-1">
                          {member.voice_name} · {member.voice_gender} · {member.voice_style}
                        </p>
                      )}
                      <p className="text-xs text-[#C7C7D1] mt-1">{member.delivery}</p>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-[#8A8A93]">
                  {scriptTurns.length ? `${scriptTurns.length} voice-ready turns prepared for audio rendering.` : 'No voice-ready turns yet.'}
                </p>
              </div>

              <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">AI Agents Scorecard</p>
                {scorecardEntries.length > 0 ? (
                  <div className="space-y-2">
                    {scorecardEntries.map(([key, item]) => (
                      <div key={key} className="flex items-center justify-between gap-3 border-b border-[#27272A] pb-2 last:border-b-0">
                        <span className="text-xs text-[#C7C7D1] capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="text-sm font-semibold text-white">{Math.round(item.score || 0)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[#8A8A93]">AI Agents scores appear after generation and review.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-5">
              <p className="text-sm text-[#8A8A93]">
                Answer the brief questions and generate an episode to create the first persistent AI Studio project.
              </p>
            </div>
          )}
        </div>
      )}

      {!shows.length ? (
        <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-8 text-center">
          <p className="text-sm text-[#8A8A93] mb-4">
            Create a show first so AI-generated episodes stay anchored to a real catalog and preserve Audioraq&apos;s show-first workflow.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-[0.9fr_1.1fr] gap-6 mb-8">
            <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-6">
              <div className="flex items-center justify-between gap-4 mb-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">{currentStep.category}</p>
                  <h3 className="font-['Outfit'] text-xl font-semibold text-white">
                    Step {stepIndex + 1} of {steps.length}: {currentStep.label}
                  </h3>
                </div>
                <span className="text-xs text-[#F5A623] uppercase tracking-[0.18em] font-semibold">
                  {Math.round(((stepIndex + 1) / steps.length) * 100)}% brief
                </span>
              </div>

              <div className="h-2 bg-[#141417] rounded-full overflow-hidden mb-6">
                <div className="h-full bg-[#F5A623]" style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }} />
              </div>

              <p className="text-white text-base mb-2">{currentStep.prompt}</p>
              <p className="text-sm text-[#8A8A93] mb-5">{currentStep.help}</p>

              {renderInput()}

              {currentStep.suggestions?.length > 0 && (
                <div className="mt-5">
                  <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">Suggested starting points</p>
                  <div className="flex flex-wrap gap-2">
                    {currentStep.suggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => handleSuggestion(suggestion)}
                        className="px-3 py-1.5 rounded-full bg-[#141417] border border-[#27272A] text-xs text-white hover:border-[#F5A623] transition-colors"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3 mt-8">
                <button
                  type="button"
                  onClick={() => setStepIndex((current) => Math.max(current - 1, 0))}
                  disabled={stepIndex === 0}
                  className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors disabled:opacity-40"
                >
                  Back
                </button>
                {currentStep.optional && (
                  <button
                    type="button"
                    onClick={handleNext}
                    className="bg-[#141417] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-5 py-3 transition-colors"
                  >
                    Skip for now
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleNext}
                  disabled={!canProceed || isGenerating}
                  className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors disabled:opacity-50"
                  data-testid="ai-step-next-btn"
                >
                  {stepIndex === steps.length - 1 ? (isGenerating ? 'Generating...' : 'Generate AI Episode') : 'Continue'}
                </button>
                <button
                  type="button"
                  onClick={handleStartFresh}
                  className="text-sm text-[#8A8A93] hover:text-white transition-colors"
                >
                  Start fresh
                </button>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-6">
                <div className="flex items-center justify-between gap-4 mb-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Structured JSON</p>
                    <h3 className="font-['Outfit'] text-lg font-semibold text-white">Live creator brief</h3>
                  </div>
                  <span className="text-xs text-[#F5A623] uppercase tracking-[0.18em] font-semibold">
                    stored as JSON
                  </span>
                </div>
                <pre className="bg-[#141417] border border-[#27272A] rounded-2xl p-4 text-xs text-[#C7C7D1] overflow-auto max-h-[340px] whitespace-pre-wrap break-words">
                  {JSON.stringify(brief, null, 2)}
                </pre>
              </div>

              <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-6">
                {generatedDraft ? (
                  <>
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-5">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">AI Episode Package</p>
                        <h3 className="font-['Outfit'] text-2xl font-semibold text-white">{generatedDraft.generation?.episode_title}</h3>
                        <p className="text-sm text-[#8A8A93] mt-2">{generatedDraft.generation?.one_line_promise}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => onApplyDraft(generatedDraft)}
                        className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-5 py-3 transition-colors whitespace-nowrap"
                        data-testid="ai-apply-draft-btn"
                      >
                        Use Audio Draft
                      </button>
                    </div>

                    {generatedDraft.quality_review && (
                      <div className={`border rounded-2xl p-4 mb-4 ${qualityTone(generatedDraft.quality_review.status)}`}>
                        <p className="text-xs uppercase tracking-[0.18em] mb-2">AI Agents Quality Gate</p>
                        <p className="text-sm font-semibold text-white mb-1">
                          Score {generatedDraft.quality_review.quality_score}/100 · {generatedDraft.quality_review.status}
                        </p>
                        <p className="text-xs text-[#C7C7D1] leading-relaxed">
                          {displayAIText(generatedDraft.quality_review.summary)}
                        </p>
                        {generatedDraft.quality_review.rlaif?.improvement_actions?.length > 0 && (
                          <p className="text-xs text-[#8A8A93] mt-2">
                            Next improvement: {displayAIText(generatedDraft.quality_review.rlaif.improvement_actions[0])}
                          </p>
                        )}
                        {generatedDraft.quality_review.scorecard && (
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-4">
                            {firstScorecardEntries(generatedDraft.quality_review.scorecard).map(([key, item]) => (
                              <div key={key} className="bg-[#0A0A0B]/70 border border-[#27272A] rounded-xl p-3">
                                <p className="text-[10px] uppercase tracking-[0.14em] text-[#8A8A93] mb-1">{key.replace(/_/g, ' ')}</p>
                                <p className="text-sm font-semibold text-white">{Math.round(item.score || 0)}/100</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4 mb-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Hook</p>
                      <p className="text-sm text-white leading-relaxed">{generatedDraft.generation?.hook}</p>
                    </div>

                    <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4 mb-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Intro</p>
                      <p className="text-sm text-[#C7C7D1] leading-relaxed">{generatedDraft.generation?.intro_script}</p>
                    </div>

                    <div className="mb-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-3">Outline</p>
                      <div className="space-y-3">
                        {(generatedDraft.generation?.outline || []).map((section) => (
                          <div key={section.section_title} className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                            <p className="text-sm font-semibold text-white mb-1">{section.section_title}</p>
                            {section.purpose && <p className="text-xs text-[#F5A623] mb-2">{section.purpose}</p>}
                            <div className="space-y-1">
                              {(section.beats || []).map((beat) => (
                                <p key={beat} className="text-sm text-[#C7C7D1]">- {beat}</p>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                      <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Talking points</p>
                        <div className="space-y-1">
                          {(generatedDraft.generation?.talking_points || []).map((point) => (
                            <p key={point} className="text-sm text-[#C7C7D1]">- {point}</p>
                          ))}
                        </div>
                      </div>
                      <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Production notes</p>
                        <div className="space-y-1">
                          {(generatedDraft.generation?.production_notes || []).map((note) => (
                            <p key={note} className="text-sm text-[#C7C7D1]">- {note}</p>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">Publish-ready description</p>
                      <p className="text-sm text-[#C7C7D1] whitespace-pre-wrap leading-relaxed">
                        {generatedDraft.publish_prefill?.description || generatedDraft.generation?.suggested_description}
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-2">What the AI will create</p>
                    <h3 className="font-['Outfit'] text-xl font-semibold text-white mb-3">A draft built for real long-form podcasting</h3>
                    <div className="space-y-3">
                      {[
                        'A structured episode outline that matches the show, audience, and goal.',
                        'A sharper intro hook without turning the episode into generic clickbait.',
                        'Talking points, production notes, and publish-ready copy for an audio-only AI episode.',
                        'An AI Agents quality report with GAN-inspired scoring, RAG safety retrieval, and RLAIF-style feedback.',
                      ].map((line) => (
                        <div key={line} className="bg-[#141417] border border-[#27272A] rounded-2xl p-4">
                          <p className="text-sm text-[#C7C7D1]">{line}</p>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-6 mb-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-5">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Recent Studio Projects</p>
                <h3 className="font-['Outfit'] text-xl font-semibold text-white">Production work in progress</h3>
              </div>
              {projectsLoading && <span className="text-sm text-[#8A8A93]">Refreshing projects...</span>}
            </div>

            {projects.length > 0 ? (
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                {projects.slice(0, 6).map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => {
                      setActiveProject(project);
                      const linkedDraft = drafts.find((draft) => draft.id === project.source_draft_id);
                      if (linkedDraft) setGeneratedDraft(linkedDraft);
                    }}
                    className={`text-left bg-[#141417] border rounded-2xl p-5 transition-colors ${
                      activeProject?.id === project.id ? 'border-[#F5A623]' : 'border-[#27272A] hover:border-[#8A8A93]'
                    }`}
                  >
                    <p className="text-sm font-semibold text-white mb-1 line-clamp-2">{project.title}</p>
                    <p className="text-xs text-[#8A8A93] mb-3">{project.show_title} · {formatDate(project.updated_at || project.created_at)}</p>
                    <div className="flex flex-wrap gap-2">
                      {studioStages.slice(0, 4).map((stage) => (
                        <span key={stage.id} className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.12em] ${studioStatusTone(project.stage_state?.[stage.id]?.status)}`}>
                          {stage.label}: {formatStatus(project.stage_state?.[stage.id]?.status)}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-6 text-center">
                <p className="text-sm text-[#8A8A93]">Studio projects will appear here once a creator generates or saves an AI episode package.</p>
              </div>
            )}
          </div>

          <div className="bg-[#0A0A0B] border border-[#27272A] rounded-3xl p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-5">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-[#8A8A93] mb-1">Recent AI drafts</p>
                <h3 className="font-['Outfit'] text-xl font-semibold text-white">Reusable episode packages</h3>
              </div>
              {draftsLoading && <span className="text-sm text-[#8A8A93]">Loading drafts...</span>}
            </div>

            {drafts.length > 0 ? (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {drafts.map((draft) => (
                  <div key={draft.id} className="bg-[#141417] border border-[#27272A] rounded-2xl p-5">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{draft.generation?.episode_title || draft.publish_prefill?.title}</p>
                        <p className="text-xs text-[#8A8A93] truncate">{draft.show_title} · {formatDate(draft.created_at)}</p>
                      </div>
                      <span className="text-[10px] uppercase tracking-[0.18em] text-[#F5A623]">
                        {draft.publish_prefill?.category || draft.recommended_category}
                      </span>
                    </div>
                    {draft.quality_review && (
                      <div className={`inline-flex rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.16em] mb-3 ${qualityTone(draft.quality_review.status)}`}>
                        AI Agents {draft.quality_review.quality_score}/100 · {draft.quality_review.status}
                      </div>
                    )}
                    <p className="text-sm text-[#C7C7D1] line-clamp-3 mb-4">
                      {draft.generation?.hook || draft.generation?.one_line_promise}
                    </p>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => onApplyDraft(draft)}
                        className="bg-[#F5A623] hover:bg-[#F7B84B] text-[#0A0A0B] font-bold rounded-full px-4 py-2 transition-colors inline-flex items-center gap-2"
                      >
                        <Play className="w-4 h-4" />
                        Use draft
                      </button>
                      <button
                        type="button"
                        onClick={() => handleReuseDraft(draft)}
                        className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-4 py-2 transition-colors inline-flex items-center gap-2"
                      >
                        <PencilSimple className="w-4 h-4" />
                        Edit brief
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setGeneratedDraft(draft);
                          setActiveProject(draft.ai_studio_project || projects.find((project) => project.id === draft.ai_studio_project_id) || null);
                        }}
                        className="bg-[#0A0A0B] hover:bg-[#27272A] border border-[#27272A] text-white rounded-full px-4 py-2 transition-colors inline-flex items-center gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        Preview
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-[#141417] border border-[#27272A] rounded-2xl p-6 text-center">
                <p className="text-sm text-[#8A8A93]">Your AI-created episode packages will show up here once you generate the first one.</p>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
