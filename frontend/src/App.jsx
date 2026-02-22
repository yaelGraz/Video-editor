/**
 * Video AI Studio - Professional SaaS Application
 * 4-Tab TOP Navigation System with Pro UI/UX
 */
import { useState, useEffect } from 'react';
import {
  VideoEditorContext,
  DEFAULT_VIDEO_SETTINGS,
  DEFAULT_PROCESSING_OPTIONS,
  EditorTab,
  YouTubeTab,
  PlannerTab,
  MarketingDashboard,
  EffectsStudioTab
} from './components';

// API Configuration — use env var if set, otherwise auto-detect from browser hostname
const _host = window.location.hostname;
const _isLocal = _host === 'localhost' || _host === '127.0.0.1';
const API_URL = import.meta.env.VITE_API_URL || (_isLocal ? 'http://localhost:8000' : `http://${_host}:8000`);
const WS_URL = import.meta.env.VITE_WS_URL || (_isLocal ? 'ws://localhost:8000' : `ws://${_host}:8000`);

// =============================================================================
// Professional SVG Icons (Monochrome, Minimal)
// =============================================================================
const Icons = {
  editor: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
    </svg>
  ),
  youtube: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.91 11.672a.375.375 0 010 .656l-5.603 3.113a.375.375 0 01-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112z" />
    </svg>
  ),
  planner: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  ),
  marketing: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
    </svg>
  ),
  effects: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
    </svg>
  )
};

// Top Navigation Tab Configuration
const TOP_TABS = [
  { id: 'editor', label: 'עריכת וידאו', icon: Icons.editor },
  { id: 'youtube', label: 'ייבוא מיוטיוב', icon: Icons.youtube },
  { id: 'planner', label: 'תכנון תסריט', icon: Icons.planner },
  { id: 'marketing', label: 'הפצה ושיווק', icon: Icons.marketing },
  { id: 'effects', label: 'אפקטים ותוספות', icon: Icons.effects }
];

// =============================================================================
// Main App Component
// =============================================================================
function App() {
  useEffect(() => {
    document.title = "Video AI Studio";
  }, []);

  return (
    <div className="h-screen bg-[#0a0c0f] text-white flex flex-col overflow-hidden">
      <VideoEditorWorkspace apiUrl={API_URL} wsUrl={WS_URL} />
    </div>
  );
}

// =============================================================================
// Video Editor Workspace - Context Provider & Professional Layout
// =============================================================================
function VideoEditorWorkspace({ apiUrl, wsUrl }) {
  // Active tab state
  const [activeTab, setActiveTab] = useState('editor');

  // Video state (PERSISTS across all tabs)
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);

  // Audio state (PERSISTS)
  const [audioUrl, setAudioUrl] = useState(null);
  const [audioError, setAudioError] = useState(null);
  const [isDownloadingAudio, setIsDownloadingAudio] = useState(false);
  const [lastDownloadedUrl, setLastDownloadedUrl] = useState(null);

  // Video settings (PERSISTS)
  const [videoSettings, setVideoSettings] = useState(DEFAULT_VIDEO_SETTINGS);

  // Processing options (PERSISTS)
  const [processingOptions, setProcessingOptions] = useState(DEFAULT_PROCESSING_OPTIONS);

  // Processing state (PERSISTS)
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [resultUrl, setResultUrl] = useState(null);

  // Marketing generation states (SEPARATE for each endpoint)
  const [isGeneratingText, setIsGeneratingText] = useState(false);
  const [isGeneratingAiImage, setIsGeneratingAiImage] = useState(false);
  const [isGeneratingShorts, setIsGeneratingShorts] = useState(false);

  // Results (PERSISTS across tabs)
  const [marketingKit, setMarketingKit] = useState(null);
  const [thumbnailUrl, setThumbnailUrl] = useState(null);
  const [aiThumbnailUrl, setAiThumbnailUrl] = useState(null);
  const [shortsUrls, setShortsUrls] = useState([]);

  // Track uploaded video_id on server
  const [uploadedVideoId, setUploadedVideoId] = useState(null);

  // Chat history (PERSISTS)
  const [chatHistory, setChatHistory] = useState([]);

  // Planner state (PERSISTS)
  const [extractedText, setExtractedText] = useState('');
  const [planResult, setPlanResult] = useState(null);
  const [plannerChatHistory, setPlannerChatHistory] = useState([]);

  // =============================================================================
  // SUBTITLE REVIEW STATE (Dedicated, isolated state for stability)
  // =============================================================================
  // Subtitle review data only - isExpanded is managed locally in SubtitleReviewPanel
  const [subtitleReview, setSubtitleReview] = useState({
    isActive: false,
    entries: [],
    pendingFileId: null,
  });

  // Update video URL when file changes
  useEffect(() => {
    if (videoFile) {
      const url = URL.createObjectURL(videoFile);
      setVideoUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setVideoUrl(null);
    }
  }, [videoFile]);

  // =============================================================================
  // Marketing Functions (Separate endpoints for better UX)
  // =============================================================================

  // Reset uploadedVideoId when video file changes
  useEffect(() => {
    setUploadedVideoId(null);
    // Also reset marketing results for new video
    setMarketingKit(null);
    setThumbnailUrl(null);
    setAiThumbnailUrl(null);
    setShortsUrls([]);
  }, [videoFile]);

  // Helper: Ensure video is uploaded to server
  const ensureVideoUploaded = async () => {
    if (uploadedVideoId) return uploadedVideoId;
    if (!videoFile) throw new Error('אין סרטון להעלאה');

    console.log('[Upload] Uploading video to server...');
    const formData = new FormData();
    formData.append('video', videoFile);

    const response = await fetch(`${apiUrl}/upload-video`, {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();
    if (data.status !== 'success') {
      throw new Error(data.error || 'שגיאה בהעלאת הסרטון');
    }

    setUploadedVideoId(data.video_id);
    console.log('[Upload] Success:', data.video_id);
    return data.video_id;
  };

  // 1. Generate Marketing Text (titles, description, tags)
  const generateMarketingText = async () => {
    if (isGeneratingText) return { success: false, error: 'כבר מייצר...' };
    setIsGeneratingText(true);

    try {
      const videoId = await ensureVideoUploaded();

      const formData = new FormData();
      formData.append('video_id', videoId);

      const response = await fetch(`${apiUrl}/generate-marketing-text`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.status === 'success') {
        setMarketingKit(data.marketing_kit);
        if (data.thumbnail_url) setThumbnailUrl(data.thumbnail_url);
        console.log('[MarketingText] Success:', data.marketing_kit?.title);
        return { success: true, data };
      } else {
        throw new Error(data.error || 'שגיאה ביצירת תוכן שיווקי');
      }
    } catch (error) {
      console.error('[MarketingText] Error:', error);
      return { success: false, error: error.message };
    } finally {
      setIsGeneratingText(false);
    }
  };

  // 2. Generate AI Image (Leonardo or Nano Banana) with optional custom prompt
  const generateMarketingAiImage = async (customPrompt = null, provider = 'leonardo', netfreeMode = false) => {
    if (isGeneratingAiImage) return { success: false, error: 'כבר מייצר...' };
    setIsGeneratingAiImage(true);

    try {
      const videoId = await ensureVideoUploaded();

      const formData = new FormData();
      formData.append('video_id', videoId);
      formData.append('provider', provider);
      formData.append('netfree_mode', netfreeMode ? 'true' : 'false');
      if (customPrompt && customPrompt.trim()) {
        formData.append('custom_prompt', customPrompt.trim());
      }

      const response = await fetch(`${apiUrl}/generate-marketing-ai-image`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.status === 'success') {
        setAiThumbnailUrl(data.ai_thumbnail_url);
        console.log(`[AiImage] Success (${provider}):`, data.ai_thumbnail_url?.substring(0, 60));
        return { success: true, data };
      } else if (data.status === 'netfree_preview') {
        // NetFree mode: return preview URL for approval flow
        console.log(`[AiImage] NetFree preview:`, data.preview_url);
        return { success: true, data };
      } else {
        throw new Error(data.error || 'שגיאה ביצירת תמונת AI');
      }
    } catch (error) {
      console.error(`[AiImage] Error (${provider}):`, error);
      return { success: false, error: error.message };
    } finally {
      setIsGeneratingAiImage(false);
    }
  };

  // 3. Generate Shorts with optional subtitles and color
  const generateMarketingShorts = async (withSubtitles = false, subtitleColor = null) => {
    if (isGeneratingShorts) return { success: false, error: 'כבר מייצר...' };
    setIsGeneratingShorts(true);

    try {
      const videoId = await ensureVideoUploaded();

      const formData = new FormData();
      formData.append('video_id', videoId);
      formData.append('with_subtitles', withSubtitles);
      if (subtitleColor) {
        formData.append('subtitle_color', subtitleColor);
      }

      const response = await fetch(`${apiUrl}/generate-marketing-shorts`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.status === 'success') {
        setShortsUrls(data.shorts_urls);
        console.log('[Shorts] Success:', data.shorts_urls?.length, 'shorts');
        return { success: true, data };
      } else {
        throw new Error(data.error || 'שגיאה ביצירת Shorts');
      }
    } catch (error) {
      console.error('[Shorts] Error:', error);
      return { success: false, error: error.message };
    } finally {
      setIsGeneratingShorts(false);
    }
  };
  // Context value - SHARED and PERSISTED across ALL tabs
  const contextValue = {
    videoSettings, setVideoSettings,
    previewConfig: videoSettings,
    setPreviewConfig: setVideoSettings,
    processingOptions, setProcessingOptions,
    videoFile, setVideoFile,
    videoUrl, setVideoUrl,
    audioUrl, setAudioUrl,
    audioError, setAudioError,
    isDownloadingAudio, setIsDownloadingAudio,
    lastDownloadedUrl, setLastDownloadedUrl,
    isProcessing, setIsProcessing,
    progress, setProgress,
    progressMessage, setProgressMessage,
    resultUrl, setResultUrl,
    // Marketing states (separate for each)
    marketingKit, setMarketingKit,
    thumbnailUrl, setThumbnailUrl,
    aiThumbnailUrl, setAiThumbnailUrl,
    shortsUrls, setShortsUrls,
    uploadedVideoId, setUploadedVideoId,
    isGeneratingText, isGeneratingAiImage, isGeneratingShorts,
    // Marketing functions (separate endpoints)
    generateMarketingText,
    generateMarketingAiImage,
    generateMarketingShorts,
    // Other
    chatHistory, setChatHistory,
    extractedText, setExtractedText,
    planResult, setPlanResult,
    plannerChatHistory, setPlannerChatHistory,
    apiUrl, wsUrl,
    activeTab, setActiveTab,
    // Subtitle Review (dedicated state)
    subtitleReview, setSubtitleReview,
  };

  // Render active tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'editor':
        return <EditorTab />;
      case 'youtube':
        return <YouTubeTab />;
      case 'planner':
        return <PlannerTab />;
      case 'marketing':
        return <MarketingDashboard isFullPage={true} />;
      case 'effects':
        return <EffectsStudioTab />;
      default:
        return <EditorTab />;
    }
  };

  return (
    <VideoEditorContext.Provider value={contextValue}>
      <FontStyles />

      {/* Professional Sticky Header */}
      <header className="sticky top-0 z-50 bg-[#0f1115]/95 backdrop-blur-sm border-b border-gray-800/50">
        <div className="flex items-center justify-between h-14 px-6">
          {/* Left - Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-[#00C8C8] to-[#0891b2] rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
              </svg>
            </div>
            <span className="text-base font-semibold text-white tracking-tight">Video AI Studio</span>
          </div>

          {/* Center - Navigation Tabs */}
          <nav className="flex items-center gap-1" dir="rtl">
            {TOP_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-4 py-2 text-sm font-medium transition-all duration-200 flex items-center gap-2 rounded-md ${
                  activeTab === tab.id
                    ? 'text-white'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                }`}
              >
                <span className={activeTab === tab.id ? 'text-[#00C8C8]' : ''}>{tab.icon}</span>
                <span>{tab.label}</span>
                {/* Active indicator - subtle underline */}
                {activeTab === tab.id && (
                  <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-[#00C8C8] rounded-full" />
                )}
              </button>
            ))}
          </nav>

          {/* Right - Minimal info */}
          <div className="flex items-center gap-4">
            <span className="text-[11px] text-gray-500 font-medium tracking-wide">PRO</span>
          </div>
        </div>
      </header>

      {/* Main Content - Full height minus header */}
      <main className="flex-1 overflow-hidden">
        {renderTabContent()}
      </main>
    </VideoEditorContext.Provider>
  );
}

// =============================================================================
// Font Styles Component
// =============================================================================
const FontStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: #374151;
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #4b5563;
    }
  `}</style>
);

export default App;
