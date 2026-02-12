/**
 * ManualEditor - Professional Video Editor Controls
 * Features: AI Style Engine, Smart Font Matching, Music Controls
 * Design: Minimalist, Dark, Professional (SaaS-style)
 */
import { useState, useContext, useEffect, useRef } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

// =============================================================================
// THE ULTIMATE FONT-STYLE & COLOR MAP
// =============================================================================
const STYLE_MAP = {
  horror: {
    id: 'horror',
    label: 'אימה',
    labelEn: 'Horror',
    font: 'Heebo',
    fontWeight: 400,
    color: '#FF0000',
    shadow: '3px 3px 6px #000000, -1px -1px 3px #000000',
    position: 'bottom',
    keywords: ['אימה', 'horror', 'מפחיד', 'scary', 'dark', 'חושך', 'סרט אימה', 'מותחן', 'thriller']
  },
  emotional: {
    id: 'emotional',
    label: 'מרגש',
    labelEn: 'Emotional',
    font: 'Bellefair',
    fontWeight: 400,
    color: '#F8F8F8',
    fontStyle: 'italic',
    shadow: '2px 2px 4px rgba(0,0,0,0.8)',
    position: 'bottom',
    keywords: ['מרגש', 'emotional', 'רגשי', 'עצוב', 'sad', 'מצמרר', 'touching', 'סנטימנטלי']
  },
  elegant: {
    id: 'elegant',
    label: 'אלגנטי',
    labelEn: 'Elegant',
    font: 'Cinzel',
    fontWeight: 400,
    color: '#D4AF37',
    shadow: '2px 2px 4px rgba(0,0,0,0.7)',
    position: 'bottom',
    keywords: ['אלגנטי', 'elegant', 'יוקרתי', 'luxury', 'מלכותי', 'royal', 'פרימיום', 'premium', 'זהב', 'gold']
  },
  happy: {
    id: 'happy',
    label: 'שמח',
    labelEn: 'Happy',
    font: 'Varela Round',
    fontWeight: 400,
    color: '#00BFFF',
    shadow: '2px 2px 4px rgba(0,0,0,0.6)',
    position: 'bottom',
    keywords: ['שמח', 'happy', 'עליז', 'cheerful', 'מצחיק', 'funny', 'קומדי', 'comedy', 'שמחה', 'joy']
  },
  tiktok: {
    id: 'tiktok',
    label: 'טיקטוק',
    labelEn: 'TikTok',
    font: 'Heebo',
    fontWeight: 900,
    color: '#FFFF00',
    shadow: '3px 3px 0px #000000, -1px -1px 0px #000000',
    position: 'center',
    keywords: ['טיקטוק', 'tiktok', 'reels', 'רילס', 'shorts', 'שורטס', 'viral', 'ויראלי', 'טרנד', 'trend']
  },
  youtube: {
    id: 'youtube',
    label: 'יוטיוב',
    labelEn: 'YouTube',
    font: 'Assistant',
    fontWeight: 600,
    color: '#FFFFFF',
    shadow: '2px 2px 0px #000000, -2px -2px 0px #000000, 2px -2px 0px #000000, -2px 2px 0px #000000',
    position: 'bottom',
    keywords: ['יוטיוב', 'youtube', 'yt', 'סרטון', 'video', 'ערוץ', 'channel']
  },
  vlog: {
    id: 'vlog',
    label: 'וולוג',
    labelEn: 'Vlog',
    font: 'Heebo',
    fontWeight: 800,
    color: '#FFFFFF',
    shadow: '2px 2px 4px rgba(0,0,0,0.8)',
    position: 'bottom',
    keywords: ['וולוג', 'vlog', 'יומן', 'diary', 'אישי', 'personal', 'lifestyle', 'לייפסטייל']
  },
  neutral: {
    id: 'neutral',
    label: 'ניטרלי',
    labelEn: 'Neutral',
    font: 'Assistant',
    fontWeight: 400,
    color: '#FFFFFF',
    shadow: '2px 2px 4px rgba(0,0,0,0.9)',
    position: 'bottom',
    keywords: ['ניטרלי', 'neutral', 'רגיל', 'normal', 'פשוט', 'simple', 'בסיסי', 'basic']
  }
};

// Ordered list for chip display
const STYLE_CHIPS = ['tiktok', 'horror', 'elegant', 'emotional', 'vlog', 'happy', 'youtube', 'neutral'];

function ManualEditor() {
  const ctx = useContext(VideoEditorContext);
  const settings = ctx.videoSettings || {};
  const setSettings = ctx.setVideoSettings;
  const apiUrl = ctx.apiUrl;
  const chipsContainerRef = useRef(null);

  // Local state
  const [styleQuery, setStyleQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchMessage, setSearchMessage] = useState(null);
  const [customFontUrl, setCustomFontUrl] = useState('');
  const [isLoadingFont, setIsLoadingFont] = useState(false);
  const [fontLoadError, setFontLoadError] = useState(null);

  // Processing state
  const [processError, setProcessError] = useState(null);

  // Music state
  const [musicLinkUrl, setMusicLinkUrl] = useState('');
  const [isDownloadingMusic, setIsDownloadingMusic] = useState(false);
  const [musicDownloadError, setMusicDownloadError] = useState(null);
  const [musicUploadFile, setMusicUploadFile] = useState(null);

  // User Library state (3 persistent slots) - Pre-populated with defaults
  const [librarySlots, setLibrarySlots] = useState([
    { id: 0, filename: 'emotional_piano_slow_trimmed.mp3', displayName: 'פסנתר רגשי', url: null },
    { id: 1, filename: 'inspiring_epic_drive_high_trimmed.mp3', displayName: 'אפי מרומם', url: null },
    { id: 2, filename: 'peaceful_nature_trimmed.mp3', displayName: 'טבע שליו', url: null }
  ]);
  const [uploadingSlot, setUploadingSlot] = useState(null);
  const fileInputRefs = [useRef(null), useRef(null), useRef(null)];

  // =============================================================================
  // USER LIBRARY - PERSISTENT 3-SLOT STORAGE
  // =============================================================================

  // Fetch library on mount
  useEffect(() => {
    fetchUserLibrary();
  }, []);

  const fetchUserLibrary = async () => {
    try {
      const response = await fetch(`${apiUrl}/user-library`);
      const data = await response.json();
      if (data.status === 'success' && data.library?.slots) {
        setLibrarySlots(data.library.slots);
        console.log('[Library] Loaded:', data.library.slots);
      }
    } catch (error) {
      console.log('[Library] Fetch error:', error.message);
    }
  };

  const handleLibrarySlotUpload = async (slotId, file) => {
    if (!file) return;

    setUploadingSlot(slotId);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${apiUrl}/user-library/upload/${slotId}`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (data.status === 'success' && data.slot) {
        // Update local state immediately (visual update)
        setLibrarySlots(prev => {
          const updated = [...prev];
          updated[slotId] = {
            id: slotId,
            filename: data.slot.filename,
            displayName: data.slot.displayName,
            url: data.slot.url
          };
          return updated;
        });
        console.log('[Library] Slot updated:', slotId, data.slot.displayName);
      }
    } catch (error) {
      console.error('[Library] Upload error:', error);
    } finally {
      setUploadingSlot(null);
      // Reset file input
      if (fileInputRefs[slotId]?.current) {
        fileInputRefs[slotId].current.value = '';
      }
    }
  };

  const selectLibrarySlot = (slot) => {
    if (!slot.filename) return;

    // Use custom URL if available, otherwise use default assets path
    const audioUrl = slot.url || `${apiUrl}/assets/music/${slot.filename}`;
    ctx.setAudioUrl(audioUrl);
    ctx.setAudioError(null);
    updateSetting('musicFile', slot.filename);
    updateSetting('musicSource', 'library');
    updateSetting('activeLibrarySlot', slot.id);
    console.log('[Library] Selected slot:', slot.id, slot.displayName);
  };

  // =============================================================================
  // FONT INJECTION SYSTEM
  // =============================================================================

  // Build Google Fonts CSS URL with proper weights
  const buildFontUrl = (fontName, weight = 400) => {
    const encodedFont = encodeURIComponent(fontName).replace(/%20/g, '+');
    const weights = weight === 400 ? '400' : `400;${weight}`;
    return `https://fonts.googleapis.com/css2?family=${encodedFont}:wght@${weights}&display=swap`;
  };

  // Inject font stylesheet into document head
  const injectFontStylesheet = (url) => {
    const existingLink = document.querySelector(`link[href="${url}"]`);
    if (!existingLink) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = url;
      document.head.appendChild(link);
      console.log('[Style Engine] Injected font:', url);
    }
  };

  // Pre-load all style fonts on mount
  useEffect(() => {
    Object.values(STYLE_MAP).forEach(style => {
      const url = buildFontUrl(style.font, style.fontWeight);
      injectFontStylesheet(url);
    });
  }, []);

  // Re-inject custom font on mount if one was previously loaded
  useEffect(() => {
    if (settings.fontUrl && settings.fontUrl.includes('fonts.googleapis.com')) {
      injectFontStylesheet(settings.fontUrl);
    }
  }, []);

  // =============================================================================
  // SMART STYLE MATCHING ENGINE
  // =============================================================================

  // Semantic matching - find closest style by keywords
  const findStyleByKeywords = (query) => {
    const queryLower = query.toLowerCase().trim();
    let bestMatch = null;
    let bestScore = 0;

    for (const [styleId, style] of Object.entries(STYLE_MAP)) {
      for (const keyword of style.keywords) {
        if (queryLower.includes(keyword.toLowerCase())) {
          // Exact match gets highest score
          const score = keyword.length;
          if (score > bestScore) {
            bestScore = score;
            bestMatch = style;
          }
        }
      }
    }

    return bestMatch;
  };

  // Apply a style from the STYLE_MAP
  const applyStyle = async (style) => {
    // Build and inject font URL
    const fontUrl = buildFontUrl(style.font, style.fontWeight);
    injectFontStylesheet(fontUrl);

    // Update settings with all style properties
    setSettings(prev => ({
      ...prev,
      font: style.font,
      fontWeight: style.fontWeight,
      fontColor: style.color,
      fontStyle: style.fontStyle || 'normal',
      textShadow: style.shadow,
      subtitlePosition: style.position,
      fontUrl: fontUrl,
      activeStyleId: style.id,
      subtitleText: prev.subtitleText || 'טקסט לדוגמה'
    }));

    // Notify backend
    await notifyBackendStyleChange(style, fontUrl);

    console.log('[Style Engine] Applied style:', style.label);
  };

  // Smart search handler
  const handleStyleSearch = async () => {
    if (!styleQuery.trim()) return;

    setIsSearching(true);
    setSearchMessage(null);

    try {
      const matchedStyle = findStyleByKeywords(styleQuery);

      if (matchedStyle) {
        await applyStyle(matchedStyle);
        setStyleQuery('');
        setSearchMessage({ type: 'success', text: `נבחר סגנון: ${matchedStyle.label}` });
      } else {
        // Fallback message for unknown input
        setSearchMessage({
          type: 'warning',
          text: 'לא הצלחתי למצוא פונט שמתאים לסגנון שביקשת. ניתן להדביק קישור ידני או לנסות סגנון כמו: טיקטוק, אימה או אלגנטי.'
        });
      }
    } finally {
      setIsSearching(false);
      // Clear message after 5 seconds
      setTimeout(() => setSearchMessage(null), 5000);
    }
  };

  // =============================================================================
  // BACKEND NOTIFICATION
  // =============================================================================

  const notifyBackendStyleChange = async (style, fontUrl) => {
    try {
      const response = await fetch(`${apiUrl}/update-settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          font: style.font,
          fontWeight: style.fontWeight,
          fontColor: style.color,
          fontUrl: fontUrl,
          styleId: style.id,
          timestamp: Date.now()
        })
      });
      console.log('[Style Engine] Backend notified:', response.status);
    } catch (error) {
      console.log('[Style Engine] Backend notification failed (non-critical):', error.message);
    }
  };

  // =============================================================================
  // CUSTOM FONT LOADER (Manual URL)
  // =============================================================================

  const parseGoogleFontUrl = (inputUrl) => {
    let url = inputUrl.trim();

    if (url.includes('fonts.googleapis.com/css')) {
      return url;
    }

    // specimen URL
    const specimenMatch = url.match(/fonts\.google\.com\/specimen\/([^?&#/]+)/i) ||
                          url.match(/\/specimen\/([^?&#/]+)/i);
    if (specimenMatch) {
      const fontName = specimenMatch[1].replace(/\+/g, ' ');
      return buildFontUrl(fontName, 400);
    }

    // Just font name
    if (!url.includes('http') && !url.includes('/')) {
      return buildFontUrl(url, 400);
    }

    return url;
  };

  const extractFontNameFromUrl = (url) => {
    const cssMatch = url.match(/family=([^:&]+)/);
    if (cssMatch) {
      return decodeURIComponent(cssMatch[1].replace(/\+/g, ' '));
    }
    const specimenMatch = url.match(/\/specimen\/([^?&#/]+)/i);
    if (specimenMatch) {
      return decodeURIComponent(specimenMatch[1].replace(/\+/g, ' '));
    }
    return null;
  };

  const loadCustomFont = async () => {
    if (!customFontUrl.trim()) return;

    setIsLoadingFont(true);
    setFontLoadError(null);

    try {
      const parsedUrl = parseGoogleFontUrl(customFontUrl);
      let fontName = extractFontNameFromUrl(customFontUrl) || extractFontNameFromUrl(parsedUrl);

      if (!fontName && !parsedUrl.includes('fonts.googleapis.com')) {
        fontName = customFontUrl.trim();
      }

      if (parsedUrl.includes('fonts.googleapis.com')) {
        injectFontStylesheet(parsedUrl);

        setSettings(prev => ({
          ...prev,
          font: fontName || 'CustomFont',
          fontUrl: parsedUrl,
          customFontName: fontName,
          activeStyleId: null
        }));

        await notifyBackendStyleChange({ font: fontName, id: 'custom' }, parsedUrl);
        setCustomFontUrl('');
      } else {
        throw new Error('Invalid font URL');
      }
    } catch (error) {
      setFontLoadError('שגיאה בטעינת הפונט - בדוק את הקישור');
      console.error('[Font] Load error:', error);
    } finally {
      setIsLoadingFont(false);
    }
  };

  // =============================================================================
  // MUSIC HANDLERS
  // =============================================================================

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const downloadMusicFromLink = async () => {
    if (!musicLinkUrl.trim()) return;

    setIsDownloadingMusic(true);
    setMusicDownloadError(null);

    try {
      const isYouTube = musicLinkUrl.includes('youtube.com') || musicLinkUrl.includes('youtu.be');

      if (isYouTube) {
        const formData = new FormData();
        formData.append('url', musicLinkUrl);

        const response = await fetch(`${apiUrl}/download-youtube-audio`, {
          method: 'POST',
          body: formData
        });

        const data = await response.json();

        if (data.status === 'success' && data.audioUrl) {
          ctx.setAudioUrl(data.audioUrl);
          ctx.setAudioError(null);
          updateSetting('musicFile', data.filename || 'youtube_audio.mp3');
          updateSetting('musicSource', 'youtube');
          setMusicLinkUrl('');
        } else {
          throw new Error(data.message || 'שגיאה בהורדה מיוטיוב');
        }
      } else {
        ctx.setAudioUrl(musicLinkUrl);
        ctx.setAudioError(null);
        updateSetting('musicFile', 'external_audio');
        updateSetting('musicSource', 'link');
        setMusicLinkUrl('');
      }
    } catch (error) {
      setMusicDownloadError(error.message || 'שגיאה בהורדת המוזיקה');
    } finally {
      setIsDownloadingMusic(false);
    }
  };

  const handleMusicFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setMusicUploadFile(file);
    const localUrl = URL.createObjectURL(file);
    ctx.setAudioUrl(localUrl);
    ctx.setAudioError(null);
    updateSetting('musicFile', file.name);
    updateSetting('musicSource', 'upload');
  };

  // =============================================================================
  // PROCESS VIDEO - Send to /process with all manual settings
  // =============================================================================

  const handleProcessVideo = async () => {
    if (!ctx.videoFile || ctx.isProcessing) return;

    setProcessError(null);
    ctx.setIsProcessing(true);
    ctx.setProgress(0);
    ctx.setProgressMessage('מתחיל עיבוד...');
    ctx.setResultUrl(null);

    const opts = ctx.processingOptions || {};

    try {
      const formData = new FormData();
      formData.append('video', ctx.videoFile);

      // Subtitles
      const doSubtitles = opts.doSubtitles ?? true;
      const doStyledSubtitles = opts.doStyledSubtitles ?? true;
      formData.append('do_subtitles', doSubtitles);
      formData.append('do_styled_subtitles', doStyledSubtitles);

      // Music
      formData.append('do_music', opts.doMusic ?? true);
      formData.append('music_style', opts.musicStyle || 'calm');

      // Marketing options
      formData.append('do_marketing', opts.doMarketing ?? true);
      formData.append('do_thumbnail', opts.doThumbnail ?? true);
      formData.append('do_ai_thumbnail', opts.doAiThumbnail ?? false);
      formData.append('do_shorts', opts.doShorts ?? false);
      formData.append('do_voiceover', opts.doVoiceover ?? false);

      // Font settings from manual editor
      formData.append('font_name', settings.font || 'Arial');
      formData.append('font_color', settings.fontColor || '#FFFFFF');
      formData.append('font_size', settings.fontSize || 24);

      // Music settings
      formData.append('music_volume', settings.musicVolume ?? 0.15);
      formData.append('ducking', settings.ducking ?? true);

      // Music source
      if (settings.musicFile) {
        formData.append('music_source', 'library');
        formData.append('music_library_file', settings.musicFile);
      } else if (ctx.audioUrl) {
        if (ctx.audioUrl.includes('/assets/music/')) {
          const filename = ctx.audioUrl.split('/assets/music/').pop();
          formData.append('music_source', 'library');
          formData.append('music_library_file', filename);
        } else {
          formData.append('music_source', 'link');
          formData.append('music_url', ctx.audioUrl);
        }
      }

      console.log('[ManualEditor] ========== PROCESSING ==========');
      console.log('[ManualEditor] Font:', settings.font, 'Color:', settings.fontColor, 'Size:', settings.fontSize);
      console.log('[ManualEditor] Music:', settings.musicFile || ctx.audioUrl || 'auto');
      console.log('[ManualEditor] ================================');

      const response = await fetch(`${apiUrl}/process`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.file_id) {
        // Store file_id immediately so Effects tab can find the video on server
        if (typeof ctx.setUploadedVideoId === 'function') {
          ctx.setUploadedVideoId(data.file_id);
          console.log('[ManualEditor] Stored file_id as uploadedVideoId:', data.file_id);
        }
        const ws = new WebSocket(`${ctx.wsUrl}/ws/progress/${data.file_id}`);

        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          ctx.setProgress(msg.progress || 0);
          ctx.setProgressMessage(msg.message || '');

          if (msg.status === 'completed') {
            ctx.setIsProcessing(false);
            ctx.setResultUrl(msg.download_url);
            if (msg.marketing_kit) ctx.setMarketingKit(msg.marketing_kit);
            if (msg.thumbnail_url) ctx.setThumbnailUrl(msg.thumbnail_url);
            if (msg.ai_thumbnail_url) ctx.setAiThumbnailUrl(msg.ai_thumbnail_url);
            if (msg.shorts_urls?.length > 0) ctx.setShortsUrls(msg.shorts_urls);
            // Capture music URL from backend (auto-selected music)
            if (msg.music_url && !ctx.audioUrl) {
              console.log('[ManualEditor] Setting audioUrl from backend:', msg.music_url);
              ctx.setAudioUrl(msg.music_url);
            }
            ws.close();
          }

          if (msg.status === 'subtitle_review') {
            const subtitles = Array.isArray(msg.subtitles) ? msg.subtitles : [];
            if (typeof ctx.setSubtitleReview === 'function') {
              ctx.setSubtitleReview({
                isActive: true,
                entries: subtitles,
                pendingFileId: data.file_id,
              });
            }
            ctx.setIsProcessing(false);
            ctx.setProgress(20);
            ctx.setProgressMessage('כתוביות מוכנות לעריכה');
          }

          if (msg.status === 'error') {
            ctx.setIsProcessing(false);
            setProcessError(msg.message || 'שגיאה בעיבוד');
            ws.close();
          }
        };

        ws.onerror = () => {
          ctx.setIsProcessing(false);
          setProcessError('שגיאת חיבור לשרת');
        };
      } else {
        throw new Error(data.error || 'שגיאה בשליחה לשרת');
      }
    } catch (err) {
      ctx.setIsProcessing(false);
      setProcessError(err.message);
      console.error('[ManualEditor] Process error:', err);
    }
  };

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className="h-full flex flex-col overflow-y-auto" dir="rtl">
      {/* ========== STYLE ENGINE SECTION ========== */}
      <div className="p-4 border-b border-white/5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white">סגנון כתוביות</h3>
          <button
            onClick={() => updateSetting('subtitlesEnabled', !(settings.subtitlesEnabled ?? true))}
            className={`w-11 h-6 rounded-full transition-all duration-200 ${
              (settings.subtitlesEnabled ?? true) ? 'bg-[#00C8C8]' : 'bg-white/10'
            }`}
          >
            <div className={`w-5 h-5 bg-white rounded-full transition-transform duration-200 mx-0.5 ${
              (settings.subtitlesEnabled ?? true) ? 'translate-x-5' : 'translate-x-0'
            }`} />
          </button>
        </div>

        {(settings.subtitlesEnabled ?? true) && (
          <div className="space-y-4">
            {/* Style Chips - Horizontal Scroll */}
            <div className="relative">
              <div
                ref={chipsContainerRef}
                className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide"
                style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
              >
                {STYLE_CHIPS.map((styleId) => {
                  const style = STYLE_MAP[styleId];
                  const isActive = settings.activeStyleId === styleId;
                  return (
                    <button
                      key={styleId}
                      onClick={() => applyStyle(style)}
                      className={`px-4 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-200 ${
                        isActive
                          ? 'bg-[#00C8C8]/15 text-[#00C8C8] border border-[#00C8C8]/40 shadow-[0_0_12px_rgba(0,200,200,0.15)]'
                          : 'bg-white/5 text-gray-400 border border-white/10 hover:text-white hover:border-white/20 hover:bg-white/8'
                      }`}
                    >
                      {style.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Smart Search Input */}
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={styleQuery}
                  onChange={(e) => setStyleQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleStyleSearch()}
                  placeholder="תאר את הסגנון שלך (למשל: סרטון טיקטוק מצחיק)..."
                  className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#00C8C8]/50 focus:bg-white/8 transition-all"
                />
                <button
                  onClick={handleStyleSearch}
                  disabled={isSearching || !styleQuery.trim()}
                  className={`px-4 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isSearching
                      ? 'bg-white/5 text-gray-500'
                      : 'bg-[#00C8C8]/15 text-[#00C8C8] border border-[#00C8C8]/30 hover:bg-[#00C8C8]/25'
                  }`}
                >
                  {isSearching ? (
                    <span className="w-4 h-4 border-2 border-[#00C8C8]/30 border-t-[#00C8C8] rounded-full animate-spin inline-block" />
                  ) : 'חפש'}
                </button>
              </div>

              {/* Search Message */}
              {searchMessage && (
                <div className={`text-xs px-3 py-2 rounded-lg ${
                  searchMessage.type === 'success'
                    ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }`}>
                  {searchMessage.text}
                </div>
              )}
            </div>

            {/* Manual Font URL */}
            <div className="bg-white/3 border border-white/8 rounded-lg p-3 space-y-2">
              <label className="text-xs text-gray-400 block">קישור ידני לפונט</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={customFontUrl}
                  onChange={(e) => setCustomFontUrl(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && loadCustomFont()}
                  placeholder="fonts.google.com/specimen/FontName"
                  className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#00C8C8]/50 transition-all"
                  dir="ltr"
                />
                <button
                  onClick={loadCustomFont}
                  disabled={isLoadingFont || !customFontUrl.trim()}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isLoadingFont
                      ? 'bg-white/5 text-gray-500'
                      : 'bg-white/10 text-gray-300 border border-white/10 hover:bg-white/15 hover:text-white'
                  }`}
                >
                  {isLoadingFont ? '...' : 'טען'}
                </button>
              </div>
              {fontLoadError && (
                <p className="text-xs text-red-400">{fontLoadError}</p>
              )}
            </div>

            {/* Color Picker */}
            <div className="space-y-2">
              <label className="text-xs text-gray-400 block">צבע</label>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <input
                    type="color"
                    value={settings.fontColor || '#FFFFFF'}
                    onChange={(e) => updateSetting('fontColor', e.target.value)}
                    className="w-10 h-10 rounded-lg border border-white/10 cursor-pointer bg-transparent"
                  />
                </div>
                <div className="flex gap-1.5">
                  {['#FFFFFF', '#FFFF00', '#00BFFF', '#FF0000', '#D4AF37', '#F8F8F8'].map((color) => (
                    <button
                      key={color}
                      onClick={() => updateSetting('fontColor', color)}
                      className={`w-7 h-7 rounded-md border transition-all ${
                        settings.fontColor === color
                          ? 'border-[#00C8C8] scale-110'
                          : 'border-white/20 hover:border-white/40'
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Font Size */}
            <div className="space-y-2">
              <div className="flex justify-between">
                <label className="text-xs text-gray-400">גודל</label>
                <span className="text-xs text-gray-500">{settings.fontSize || 48}px</span>
              </div>
              <input
                type="range"
                min="24"
                max="72"
                value={settings.fontSize || 48}
                onChange={(e) => updateSetting('fontSize', parseInt(e.target.value))}
                className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[#00C8C8]"
              />
            </div>

            {/* Preview Text Input */}
            <div className="space-y-2">
              <label className="text-xs text-gray-400 block">טקסט לתצוגה</label>
              <input
                type="text"
                value={settings.subtitleText || ''}
                onChange={(e) => updateSetting('subtitleText', e.target.value)}
                placeholder="טקסט לדוגמה"
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-[#00C8C8]/50 transition-all"
              />
            </div>

            {/* Live Preview */}
            <div className="bg-black rounded-xl p-6 text-center min-h-[80px] flex items-center justify-center">
              <span
                style={{
                  fontFamily: `'${settings.font || 'Assistant'}', sans-serif`,
                  fontWeight: settings.fontWeight || 400,
                  fontStyle: settings.fontStyle || 'normal',
                  color: settings.fontColor || '#FFFFFF',
                  fontSize: `${Math.min(settings.fontSize || 48, 28)}px`,
                  textShadow: settings.textShadow || '2px 2px 4px rgba(0,0,0,0.9)'
                }}
              >
                {settings.subtitleText || 'טקסט לדוגמה'}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ========== MUSIC SECTION ========== */}
      <div className="p-4 border-b border-white/5">
        <h3 className="text-sm font-semibold text-white mb-4">מוזיקת רקע</h3>

        <div className="space-y-3">
          {/* YouTube/URL Link */}
          <div className="bg-white/3 border border-white/8 rounded-lg p-3 space-y-2">
            <label className="text-xs text-gray-400 block">קישור YouTube / URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={musicLinkUrl}
                onChange={(e) => setMusicLinkUrl(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && downloadMusicFromLink()}
                placeholder="https://youtube.com/watch?v=..."
                className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#00C8C8]/50 transition-all"
                dir="ltr"
              />
              <button
                onClick={downloadMusicFromLink}
                disabled={isDownloadingMusic || !musicLinkUrl.trim()}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isDownloadingMusic
                    ? 'bg-white/5 text-gray-500'
                    : 'bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25'
                }`}
              >
                {isDownloadingMusic ? (
                  <span className="w-4 h-4 border-2 border-red-400/30 border-t-red-400 rounded-full animate-spin inline-block" />
                ) : 'הורד'}
              </button>
            </div>
            {musicDownloadError && (
              <p className="text-xs text-red-400">{musicDownloadError}</p>
            )}
          </div>

          {/* File Upload */}
          <div className="bg-white/3 border border-white/8 rounded-lg p-3 space-y-2">
            <label className="text-xs text-gray-400 block">העלאת קובץ</label>
            <input
              type="file"
              accept="audio/*,.mp3,.wav,.ogg,.m4a"
              onChange={handleMusicFileUpload}
              className="hidden"
              id="music-upload"
            />
            <label
              htmlFor="music-upload"
              className="flex items-center justify-center gap-2 px-4 py-2 bg-white/5 text-gray-400 border border-white/10 rounded-lg text-xs font-medium cursor-pointer hover:bg-white/10 hover:text-white transition-all"
            >
              {musicUploadFile ? musicUploadFile.name : 'בחר קובץ אודיו...'}
            </label>
          </div>

          {/* ===== MY LIBRARY: 3 Persistent Slots ===== */}
          <div className="space-y-3">
            <div>
              <h4 className="text-sm font-bold text-white">הספרייה שלי</h4>
              <p className="text-xs text-gray-500 mt-0.5">שמירת עד 3 קבצים לגישה מהירה</p>
            </div>

            <div className="space-y-2">
              {librarySlots.map((slot, index) => (
                <div
                  key={slot.id}
                  className={`p-3 rounded-lg transition-all ${
                    settings.musicFile === slot.filename
                      ? 'bg-white/5 border-2 border-[#00C8C8]'
                      : 'bg-white/3 border border-white/10'
                  }`}
                >
                  <input
                    type="file"
                    ref={fileInputRefs[index]}
                    accept="audio/*,.mp3,.wav,.ogg,.m4a"
                    onChange={(e) => handleLibrarySlotUpload(slot.id, e.target.files?.[0])}
                    className="hidden"
                  />

                  <div className="flex items-center justify-between">
                    {/* Slot info */}
                    <div className="flex-1 min-w-0">
                      {uploadingSlot === slot.id ? (
                        <div className="flex items-center gap-2">
                          <span className="w-4 h-4 border-2 border-[#00C8C8]/30 border-t-[#00C8C8] rounded-full animate-spin inline-block" />
                          <span className="text-xs text-gray-400">מעלה...</span>
                        </div>
                      ) : slot.filename ? (
                        <div>
                          <p className="text-sm text-white truncate" title={slot.filename}>
                            {slot.displayName || `קובץ ${slot.id + 1}`}
                          </p>
                          <p className="text-[10px] text-gray-500 truncate">{slot.filename}</p>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500">משבצת ריקה</p>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 mr-2">
                      {slot.filename ? (
                        <>
                          <button
                            onClick={() => selectLibrarySlot(slot)}
                            className="text-xs text-gray-400 hover:text-[#00C8C8] transition-colors"
                          >
                            [ בחר ]
                          </button>
                          <button
                            onClick={() => fileInputRefs[index].current?.click()}
                            className="text-xs text-gray-400 hover:text-[#00C8C8] transition-colors"
                          >
                            [ החלף ]
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => fileInputRefs[index].current?.click()}
                          className="text-xs text-gray-400 hover:text-[#00C8C8] transition-colors"
                        >
                          [ בחר ]
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Audio Status */}
          {ctx.audioUrl && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2">
              <p className="text-xs text-green-400">מוזיקה נטענה</p>
            </div>
          )}

          {/* Volume */}
          <div className="space-y-2">
            <div className="flex justify-between">
              <label className="text-xs text-gray-400">עוצמה</label>
              <span className="text-xs text-gray-500">{Math.round((settings.musicVolume || 0.15) * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={Math.round((settings.musicVolume || 0.15) * 100)}
              onChange={(e) => updateSetting('musicVolume', parseInt(e.target.value) / 100)}
              className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[#00C8C8]"
            />
          </div>
        </div>
      </div>

      {/* ========== DUCKING SECTION ========== */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">דאקינג</h3>
            <p className="text-[10px] text-gray-500">הנמכת מוזיקה בזמן דיבור</p>
          </div>
          <button
            onClick={() => updateSetting('ducking', !(settings.ducking ?? true))}
            className={`w-11 h-6 rounded-full transition-all duration-200 ${
              (settings.ducking ?? true) ? 'bg-[#00C8C8]' : 'bg-white/10'
            }`}
          >
            <div className={`w-5 h-5 bg-white rounded-full transition-transform duration-200 mx-0.5 ${
              (settings.ducking ?? true) ? 'translate-x-5' : 'translate-x-0'
            }`} />
          </button>
        </div>

        {(settings.ducking ?? true) && (
          <div className="mt-4 space-y-2">
            <div className="flex justify-between">
              <label className="text-xs text-gray-400">רמת הנמכה</label>
              <span className="text-xs text-gray-500">{Math.round((settings.duckingLevel || 0.3) * 100)}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="50"
              value={Math.round((settings.duckingLevel || 0.3) * 100)}
              onChange={(e) => updateSetting('duckingLevel', parseInt(e.target.value) / 100)}
              className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-[#00C8C8]"
            />
          </div>
        )}
      </div>

      {/* ========== PROCESS BUTTON ========== */}
      <div className="p-4 border-t border-white/5 mt-auto">
        <button
          onClick={handleProcessVideo}
          disabled={!ctx.videoFile || ctx.isProcessing}
          className={`w-full py-3 rounded-xl text-sm font-semibold transition-all ${
            ctx.videoFile && !ctx.isProcessing
              ? 'bg-gradient-to-r from-[#00C8C8] to-[#0891b2] text-white hover:opacity-90'
              : 'bg-white/5 text-gray-600 cursor-not-allowed'
          }`}
        >
          {ctx.isProcessing ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>מעבד...</span>
            </span>
          ) : (
            <span>עבד וידאו</span>
          )}
        </button>
        {!ctx.videoFile && (
          <p className="text-[10px] text-gray-500 text-center mt-2">יש להעלות וידאו קודם</p>
        )}
        {processError && (
          <p className="text-xs text-red-400 text-center mt-2">{processError}</p>
        )}
      </div>
    </div>
  );
}

export default ManualEditor;
