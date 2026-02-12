/**
 * ChatSection - AI Chat interface for video editing commands
 * Handles natural language commands, YouTube audio downloads, and settings updates
 */
import { useState, useRef, useEffect, useContext } from 'react';
import { VideoEditorContext, MAX_HISTORY_LENGTH } from './VideoEditorContext';

function ChatSection({ isInTab = false }) {
  const ctx = useContext(VideoEditorContext);
  const apiUrl = ctx.apiUrl;

  // Chat state
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'שלום! אני העוזר האישי שלך לעריכת וידאו. 🎬\n\nאני יכול לעזור לך עם:\n• שינוי צבע ופונט של כתוביות\n• בחירת מוזיקת רקע (גם מ-YouTube!)\n• התאמת עוצמה ודאקינג\n• עיבוד וייצוא הוידאו\n\nפשוט ספר לי מה תרצה!'
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const chatEndRef = useRef(null);

  // Access settings
  const settings = ctx.videoSettings || ctx.previewConfig || {};
  const setSettings = ctx.setVideoSettings || ctx.setPreviewConfig;

  // =============================================================================
  // FONT INJECTION SYSTEM (for external Google Fonts)
  // =============================================================================

  // Build Google Fonts CSS URL from font name
  const buildFontUrl = (fontName, weight = 400) => {
    const encodedFont = encodeURIComponent(fontName).replace(/%20/g, '+');
    const weights = weight === 400 ? '400' : `400;${weight}`;
    return `https://fonts.googleapis.com/css2?family=${encodedFont}:wght@${weights}&display=swap`;
  };

  // Extract font name from Google Fonts URL
  const extractFontNameFromUrl = (url) => {
    // Handle URLs like: https://fonts.google.com/specimen/Rubik+Scribble
    const specimenMatch = url.match(/specimen\/([^?&]+)/);
    if (specimenMatch) {
      return decodeURIComponent(specimenMatch[1].replace(/\+/g, ' '));
    }
    // Handle CSS URLs like: https://fonts.googleapis.com/css2?family=Rubik+Scribble
    const familyMatch = url.match(/family=([^:&]+)/);
    if (familyMatch) {
      return decodeURIComponent(familyMatch[1].replace(/\+/g, ' '));
    }
    return null;
  };

  // Inject font stylesheet into document head
  const injectFontStylesheet = (url) => {
    const existingLink = document.querySelector(`link[href="${url}"]`);
    if (!existingLink) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = url;
      document.head.appendChild(link);
      console.log('[Chat] Injected font:', url);
      return true;
    }
    return false;
  };

  // Load a font by name or URL
  const loadFont = (fontNameOrUrl) => {
    let fontName = fontNameOrUrl;
    let fontUrl = null;

    // Check if it's a Google Fonts URL
    if (fontNameOrUrl.includes('fonts.google.com') || fontNameOrUrl.includes('fonts.googleapis.com')) {
      fontName = extractFontNameFromUrl(fontNameOrUrl);
      if (!fontName) {
        console.warn('[Chat] Could not extract font name from URL:', fontNameOrUrl);
        return null;
      }
    }

    // Build CSS URL for the font
    fontUrl = buildFontUrl(fontName);
    injectFontStylesheet(fontUrl);

    console.log('[Chat] Loaded font:', fontName, fontUrl);
    return { fontName, fontUrl };
  };

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMessage = (role, content) => {
    setMessages(prev => [...prev, { role, content }]);
  };

  // Check if the message is ONLY a YouTube URL (no other text)
  // If the user added extra words/commands alongside the link → send to /chat instead
  const isOnlyYouTubeUrl = (text) => {
    const trimmed = text.trim();
    return /^https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)[\w-]+(?:[?&]\S*)?$/.test(trimmed);
  };

  // Check if text contains a YouTube URL anywhere (for logging)
  const containsYouTubeUrl = (text) => {
    return /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)/.test(text);
  };

  // Send message to backend (with retry on transient connection errors)
  const sendMessageToBackend = async (message, history) => {
    const contextMessages = history.slice(-MAX_HISTORY_LENGTH);

    const currentContext = {
      font: settings.font || 'Assistant',
      fontColor: settings.fontColor || '#FFFFFF',
      fontSize: settings.fontSize || 24,
      musicVolume: settings.musicVolume || 0.15,
      ducking: settings.ducking ?? true,
      subtitlesEnabled: settings.subtitlesEnabled ?? settings.subtitles ?? true,
      subtitleText: settings.subtitleText || '',
      musicFile: settings.musicFile || null,
      hasAudio: !!ctx.audioUrl
    };

    const formData = new FormData();
    formData.append('message', message);
    formData.append('history', JSON.stringify(contextMessages.map(m => ({
      role: m.role,
      content: m.content
    }))));
    formData.append('currentContext', JSON.stringify(currentContext));
    formData.append('has_video', ctx.videoFile ? 'true' : 'false');

    const sendTime = new Date().toLocaleTimeString('he-IL');
    console.log(`[Chat] >>> [${sendTime}] Sending to /chat:`, {
      message,
      hasYouTubeUrl: /youtube\.com|youtu\.be/.test(message),
      contextKeys: Object.keys(currentContext),
    });

    // Retry once on transient network failures (connection reset, etc.)
    let lastError = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const t0 = performance.now();
        const response = await fetch(`${apiUrl}/chat`, {
          method: 'POST',
          body: formData
        });
        const elapsed = Math.round(performance.now() - t0);

        if (!response.ok) {
          console.error(`[Chat] !!! Server returned HTTP ${response.status} after ${elapsed}ms`);
          throw new Error(`שגיאת שרת: ${response.status}`);
        }

        const data = await response.json();
        console.log(`[Chat] <<< [${elapsed}ms] Server response:`, {
          answer: data.answer?.slice(0, 80),
          commandCount: data.commands?.length ?? (data.command ? 1 : 0),
          commands: data.commands || (data.command ? [data.command] : [])
        });
        return data;
      } catch (err) {
        lastError = err;
        const isTransient = err.message.includes('Failed to fetch') ||
                            err.message.includes('NetworkError') ||
                            err.message.includes('ERR_CONNECTION');
        if (isTransient && attempt === 0) {
          console.warn(`[Chat] !!! Request FAILED before reaching server (attempt ${attempt + 1}/2): ${err.message}`);
          console.warn('[Chat] Retrying in 1s...');
          await new Promise(r => setTimeout(r, 1000));
          continue;
        }
        console.error(`[Chat] !!! Request FAILED (attempt ${attempt + 1}/2, giving up): ${err.message}`);
        throw err;
      }
    }
    throw lastError;
  };

  // Download YouTube audio
  const downloadYouTubeAudio = async (url, forceDownload = false) => {
    if (!forceDownload && ctx.lastDownloadedUrl && ctx.lastDownloadedUrl === url) {
      console.log('[YouTube] Skipping duplicate download:', url);
      return { success: true, message: '🎵 המוזיקה כבר טעונה! לחץ Play כדי לשמוע.', skipped: true };
    }

    ctx.setIsDownloadingAudio(true);
    ctx.setAudioError(null);

    try {
      const formData = new FormData();
      formData.append('url', url);

      const response = await fetch(`${apiUrl}/download-youtube-audio`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'שגיאת שרת');
      }

      const data = await response.json();

      if (data.status === 'success') {
        const finalAudioUrl = data.audioUrl ||
          (data.file_path ? `${apiUrl}/assets/music/temp/${data.file_path}` : null) ||
          (data.filename ? `${apiUrl}/assets/music/${data.filename}` : null);

        if (!finalAudioUrl) {
          throw new Error('השרת לא החזיר כתובת אודיו תקינה');
        }

        console.log('[YouTube] 📥 Setting audioUrl:', finalAudioUrl);
        ctx.setAudioUrl(finalAudioUrl);
        ctx.setAudioError(null);
        ctx.setLastDownloadedUrl(url);

        return { success: true, message: `הורדתי את המוזיקה בהצלחה! 🎵\nלחץ Play כדי לשמוע.`, audioUrl: finalAudioUrl };
      } else {
        throw new Error(data.detail || data.error || 'שגיאה בהורדה');
      }
    } catch (error) {
      const errorMsg = error.message || 'שגיאה בהורדה מ-YouTube';
      ctx.setAudioError(errorMsg);
      console.error('[YouTube] Error:', errorMsg);
      return { success: false, message: `❌ ${errorMsg}` };
    } finally {
      ctx.setIsDownloadingAudio(false);
    }
  };

  // Apply command from AI response
  const applyCommand = async (command) => {
    if (!command || Object.keys(command).length === 0) return;

    // Safety: only process_video triggers actual processing
    if (command.action === 'process_video') {
      handleAction({ type: 'process_video', ...command });
      return;
    }

    if (command.action === 'play' || command.action === 'play_preview') {
      addMessage('assistant', '▶️ מפעיל את התצוגה המקדימה...');
      return;
    }

    // YouTube URL handling
    if (command.youtubeUrl) {
      const result = await downloadYouTubeAudio(command.youtubeUrl);
      if (!result.skipped) {
        addMessage('assistant', result.message);
      }
    }

    // Music file from library
    if (command.musicFile) {
      const musicUrl = `${apiUrl}/assets/music/${command.musicFile}`;
      ctx.setAudioUrl(musicUrl);
      ctx.setAudioError(null);
      console.log('[Music Library] Loading:', musicUrl);
      addMessage('assistant', `🎵 מוזיקה נטענה: ${command.musicFile}\nלחץ Play כדי לשמוע!`);
    }

    // Handle font loading (from name or URL)
    let loadedFont = null;
    if (command.fontUrl) {
      // Font URL provided (e.g., Google Fonts link)
      loadedFont = loadFont(command.fontUrl);
    } else if (command.font) {
      // Font name provided - load it
      loadedFont = loadFont(command.font);
    }

    // Update settings
    setSettings(prev => {
      const updates = {};

      // Apply loaded font
      if (loadedFont) {
        updates.font = loadedFont.fontName;
        updates.fontUrl = loadedFont.fontUrl;
      } else if (command.font) {
        updates.font = command.font;
      }
      if (command.fontColor) updates.fontColor = command.fontColor;
      if (command.fontSize) updates.fontSize = command.fontSize;

      if (command.musicVolume !== undefined) {
        const vol = command.musicVolume > 1 ? command.musicVolume / 100 : command.musicVolume;
        updates.musicVolume = vol;
      }
      if (command.ducking !== undefined) {
        updates.ducking = command.ducking;
      }

      if (command.subtitlesEnabled !== undefined) {
        updates.subtitles = command.subtitlesEnabled;
      }
      if (command.subtitles !== undefined) {
        updates.subtitles = command.subtitles;
      }
      if (command.subtitleText) {
        updates.subtitleText = command.subtitleText;
      }

      if (Object.keys(updates).length > 0) {
        console.log('[Chat] Applying style updates:', updates);
        return { ...prev, ...updates };
      }
      return prev;
    });
  };

  // Handle video processing action
  const handleAction = async (action) => {
    if (!action) return;

    if (action.type === 'process_video' || action.action === 'process_video') {
      if (!ctx.videoFile) {
        addMessage('assistant', '⚠️ אנא העלה וידאו לפני העיבוד.');
        return;
      }

      addMessage('assistant', '🚀 מתחיל בעיבוד הוידאו...');
      ctx.setIsProcessing(true);
      ctx.setProgress(0);

      // Get processing options from context (MarketingTools toggles)
      const opts = ctx.processingOptions || {};

      try {
        const formData = new FormData();
        formData.append('video', ctx.videoFile);

        // Subtitles options - CRITICAL: Always enable by default
        const doSubtitles = opts.doSubtitles ?? action.subtitles ?? true;
        const doStyledSubtitles = opts.doStyledSubtitles ?? true;
        formData.append('do_subtitles', doSubtitles);
        formData.append('do_styled_subtitles', doStyledSubtitles);
        console.log('[Chat] Subtitles enabled:', doSubtitles, 'Styled:', doStyledSubtitles);

        // Music options
        formData.append('do_music', opts.doMusic ?? action.music ?? true);
        formData.append('music_style', opts.musicStyle || action.musicStyle || 'calm');

        // Marketing options (from MarketingTools)
        formData.append('do_marketing', opts.doMarketing ?? true);
        formData.append('do_thumbnail', opts.doThumbnail ?? true);
        formData.append('do_ai_thumbnail', opts.doAiThumbnail ?? false);
        formData.append('do_shorts', opts.doShorts ?? false);
        formData.append('do_voiceover', opts.doVoiceover ?? false);

        // Style settings - Font (default to Arial size 24 for readability)
        const fontName = action.font || settings.font || 'Arial';
        const fontColor = action.fontColor || settings.fontColor || '#FFFFFF';
        const fontSize = action.fontSize || settings.fontSize || 24;

        formData.append('font_name', fontName);
        formData.append('font_color', fontColor);
        formData.append('font_size', fontSize);

        // Music settings
        formData.append('music_volume', action.musicVolume ?? settings.musicVolume ?? 0.15);
        formData.append('ducking', action.ducking ?? settings.ducking ?? true);

        // CRITICAL: Send the music source correctly
        // music_library_file = filename from library
        // music_url = URL for downloaded audio
        if (settings.musicFile) {
          formData.append('music_source', 'library');
          formData.append('music_library_file', settings.musicFile);
          console.log('[Chat] Sending music library file:', settings.musicFile);
        } else if (ctx.audioUrl) {
          // If it's a localhost URL, extract just the filename
          if (ctx.audioUrl.includes('/assets/music/')) {
            const filename = ctx.audioUrl.split('/assets/music/').pop();
            formData.append('music_source', 'library');
            formData.append('music_library_file', filename);
            console.log('[Chat] Sending music from URL as library:', filename);
          } else {
            formData.append('music_source', 'link');
            formData.append('music_url', ctx.audioUrl);
            console.log('[Chat] Sending music URL:', ctx.audioUrl);
          }
        }

        console.log('[Chat] ========== PROCESSING SETTINGS ==========');
        console.log('[Chat] FONT NAME:', fontName);
        console.log('[Chat] FONT COLOR:', fontColor);
        console.log('[Chat] FONT SIZE:', fontSize);
        console.log('[Chat] settings.font:', settings.font);
        console.log('[Chat] action.font:', action?.font);
        console.log('[Chat] Music file:', settings.musicFile);
        console.log('[Chat] Audio URL:', ctx.audioUrl);
        console.log('[Chat] ==========================================');

        const response = await fetch(`${apiUrl}/process`, {
          method: 'POST',
          body: formData
        });

        const data = await response.json();

        if (data.file_id) {
          // Store file_id immediately so Effects tab can find the video on server
          if (typeof ctx.setUploadedVideoId === 'function') {
            ctx.setUploadedVideoId(data.file_id);
            console.log('[ChatSection] Stored file_id as uploadedVideoId:', data.file_id);
          }
          const ws = new WebSocket(`${ctx.wsUrl}/ws/progress/${data.file_id}`);

          ws.onmessage = (event) => {
            const msgData = JSON.parse(event.data);
            ctx.setProgress(msgData.progress || 0);
            ctx.setProgressMessage(msgData.message || '');

            if (msgData.status === 'completed') {
              ctx.setIsProcessing(false);
              ctx.setResultUrl(msgData.download_url);

              // Store marketing results if available
              if (msgData.marketing_kit) {
                ctx.setMarketingKit(msgData.marketing_kit);
              }
              if (msgData.thumbnail_url) {
                ctx.setThumbnailUrl(msgData.thumbnail_url);
              }
              if (msgData.ai_thumbnail_url) {
                ctx.setAiThumbnailUrl(msgData.ai_thumbnail_url);
              }
              if (msgData.shorts_urls && msgData.shorts_urls.length > 0) {
                ctx.setShortsUrls(msgData.shorts_urls);
              }

              // Capture music URL from backend (auto-selected music)
              if (msgData.music_url && !ctx.audioUrl) {
                console.log('[ChatSection] Setting audioUrl from backend:', msgData.music_url);
                ctx.setAudioUrl(msgData.music_url);
              }

              // Build completion message with results summary
              let completionMsg = '✅ העיבוד הושלם בהצלחה!\n\nהוידאו מוכן להורדה.';
              if (msgData.marketing_kit) {
                completionMsg += '\n\n📊 חומרי שיווק נוצרו!';
              }
              if (msgData.thumbnail_url) {
                completionMsg += '\n🖼️ תמונה ממוזערת מוכנה';
              }
              if (msgData.shorts_urls && msgData.shorts_urls.length > 0) {
                completionMsg += `\n📱 ${msgData.shorts_urls.length} קליפים קצרים נוצרו`;
              }

              addMessage('assistant', completionMsg);
              ws.close();
            }

            // Handle subtitle review pause
            if (msgData.status === 'subtitle_review') {
              // Detailed logging for debugging
              console.log('[ChatSection] ========== SUBTITLE REVIEW ==========');
              console.log('[ChatSection] Raw msgData:', JSON.stringify(msgData).slice(0, 500));
              console.log('[ChatSection] total_entries:', msgData.total_entries);
              console.log('[ChatSection] subtitles array length:', msgData.subtitles?.length);
              console.log('[ChatSection] First subtitle:', msgData.subtitles?.[0]);
              console.log('[ChatSection] file_id:', data.file_id);
              console.log('[ChatSection] =====================================');

              // Extract subtitles safely
              const subtitles = Array.isArray(msgData.subtitles) ? msgData.subtitles : [];
              const fileId = data.file_id;

              if (subtitles.length === 0) {
                console.warn('[ChatSection] No subtitles received!');
              }

              // Set subtitle review data in context (isExpanded is managed locally in SubtitleReviewPanel)
              const reviewState = {
                isActive: true,
                entries: subtitles,
                pendingFileId: fileId,
              };
              console.log('[ChatSection] Setting subtitleReview:', subtitles.length, 'entries for', fileId);

              if (typeof ctx.setSubtitleReview === 'function') {
                ctx.setSubtitleReview(reviewState);
              } else {
                console.error('[ChatSection] ctx.setSubtitleReview is not a function!');
              }

              // Now update processing state
              ctx.setIsProcessing(false);
              ctx.setProgress(20);
              ctx.setProgressMessage('כתוביות מוכנות לעריכה');

              addMessage('assistant',
                `📝 הכתוביות מוכנות!\n\n` +
                `זיהיתי ${subtitles.length} שורות כתוביות.\n` +
                `לחץ על "הצג כתוביות" למעלה כדי לערוך, או "דלג והמשך" להמשיך בלי עריכה.`
              );
              // Keep WebSocket open for continuation
            }

            if (msgData.status === 'error') {
              ctx.setIsProcessing(false);
              addMessage('assistant', `❌ שגיאה: ${msgData.message}`);
              ws.close();
            }
          };

          ws.onerror = () => {
            ctx.setIsProcessing(false);
            addMessage('assistant', '❌ שגיאת חיבור. נסה שוב.');
          };
        }
      } catch (err) {
        ctx.setIsProcessing(false);
        addMessage('assistant', `❌ שגיאת שרת: ${err.message}`);
      }
    }
  };

  // Handle send
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    addMessage('user', userMessage);

    // Direct YouTube URL handling — ONLY if the message is purely a URL
    // If there's any extra text (commands, instructions), route to /chat so the AI
    // can parse all intents (e.g. "download from YT + change font to red")
    if (isOnlyYouTubeUrl(userMessage)) {
      console.log('[Chat] Bare YouTube URL detected → direct download');
      setIsLoading(true);
      const result = await downloadYouTubeAudio(userMessage);
      if (result.skipped) {
        addMessage('assistant', '🎵 המוזיקה הזו כבר טעונה! לחץ Play בנגן כדי לשמוע.');
      } else {
        addMessage('assistant', result.message);
      }
      setIsLoading(false);
      return;
    }

    // Log if message contains a YT URL mixed with other text — this goes to /chat
    if (containsYouTubeUrl(userMessage)) {
      console.log('[Chat] YouTube URL + text detected → routing to /chat for multi-intent parsing');
    }

    setIsLoading(true);

    try {
      const response = await sendMessageToBackend(userMessage, [...messages, { role: 'user', content: userMessage }]);

      if (response.error) {
        let errorMsg = response.error;
        if (errorMsg.includes('download') || errorMsg.includes('הורדה')) {
          errorMsg = '❌ שגיאה בהורדה - לא ניתן להוריד את הקובץ';
        } else if (errorMsg.includes('invalid') || errorMsg.includes('url') || errorMsg.includes('URL')) {
          errorMsg = '❌ הקישור לא תקין - אנא בדוק את הכתובת';
        }
        addMessage('assistant', errorMsg);
        return;
      }

      const answerText = response.answer || response.message || 'קיבלתי את הבקשה';
      addMessage('assistant', answerText);

      // Log server-side debug info if present
      if (response.debug) {
        console.log('[Chat] === SERVER DEBUG ===');
        console.log('[Chat] Detected intents:', response.debug.detected_intents);
        console.log('[Chat] Command count:', response.debug.command_count);
        console.log('[Chat] Regex extracted:', response.debug.regex_extracted);
        if (response.debug.parse_error) {
          console.warn('[Chat] LLM parse error:', response.debug.parse_error);
        }
        console.log('[Chat] ====================');
      }

      // Multi-intent: support both "commands" (array) and legacy "command" (single)
      let commands = response.commands || [];
      if (commands.length === 0 && response.command && Object.keys(response.command).length > 0) {
        commands = [response.command];
      }

      console.log(`[Chat] Multi-intent: ${commands.length} command(s) to execute:`, JSON.stringify(commands));

      if (commands.length > 0) {
        // Sort: style commands first, action commands (process_video) last
        const styleCommands = commands.filter(c => c.action !== 'process_video');
        const actionCommands = commands.filter(c => c.action === 'process_video');

        console.log(`[Chat] Pipeline: ${styleCommands.length} style → ${actionCommands.length} action`);

        // Apply style commands first so settings are in place before processing
        for (let i = 0; i < styleCommands.length; i++) {
          const cmd = styleCommands[i];
          if (Object.keys(cmd).length > 0) {
            console.log(`[Chat] ▶ Style [${i + 1}/${styleCommands.length}]:`, cmd);
            await applyCommand(cmd);
            console.log(`[Chat] ✓ Style [${i + 1}/${styleCommands.length}] applied`);
          }
        }
        // Then trigger action commands
        for (let i = 0; i < actionCommands.length; i++) {
          console.log(`[Chat] ▶ Action [${i + 1}/${actionCommands.length}]:`, actionCommands[i]);
          await applyCommand(actionCommands[i]);
          console.log(`[Chat] ✓ Action [${i + 1}/${actionCommands.length}] triggered`);
        }
        console.log(`[Chat] All ${commands.length} command(s) applied successfully`);
      } else {
        console.log('[Chat] No commands to apply (text-only response)');
      }

    } catch (error) {
      let errorMessage = '❌ מצטער, נתקלתי בשגיאה';

      if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        errorMessage = '❌ שגיאת חיבור - לא ניתן להתחבר לשרת.\nבדוק שהשרת פועל ונסה שוב.';
      } else if (error.message.includes('500')) {
        errorMessage = '❌ שגיאת שרת פנימית';
      } else {
        errorMessage = `❌ שגיאה: ${error.message}`;
      }

      addMessage('assistant', errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Wrapper component - changes based on isInTab prop
  const Wrapper = isInTab ? 'div' : 'aside';
  const wrapperClass = isInTab
    ? 'h-full bg-[#16191e] flex flex-col'
    : 'w-[400px] bg-[#16191e] border-r border-gray-800 flex flex-col shadow-2xl shrink-0';

  return (
    <Wrapper className={wrapperClass} dir="rtl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-purple-500 rounded-full animate-pulse"></span>
            <h2 className="text-sm font-bold text-white">צ'אט AI לעריכה</h2>
          </div>
          <span className="text-[9px] bg-gray-800 text-gray-500 px-2 py-0.5 rounded" dir="ltr">
            {Math.min(messages.length, MAX_HISTORY_LENGTH)}/{MAX_HISTORY_LENGTH}
          </span>
        </div>
        <p className="text-[10px] text-gray-600 mt-1">
          פקודות בשפה טבעית • מוזיקה • כתוביות • עיבוד
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`max-w-[85%] px-3 py-2 rounded-xl text-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-[#00C8C8]/20 text-[#00C8C8] border border-[#00C8C8]/30'
                  : 'bg-gray-800/80 text-gray-200 border border-gray-700'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-end">
            <div className="bg-gray-800/80 text-gray-400 px-3 py-2 rounded-xl text-sm border border-gray-700">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-gray-600/30 border-t-gray-400 rounded-full animate-spin"></div>
                <span>חושב...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="הקלד פקודה או קישור YouTube..."
            disabled={isLoading}
            className="flex-1 px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-[#00C8C8] transition-colors disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim()}
            className={`px-4 py-3 rounded-xl transition-all ${
              isLoading || !inputValue.trim()
                ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                : 'bg-[#00C8C8] text-white hover:bg-[#00B0B0] cursor-pointer'
            }`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>

        {/* Quick actions */}
        <div className="flex flex-wrap gap-2 mt-3">
          {[
            { label: '🎵 מוזיקה', action: 'שים מוזיקת רקע' },
            { label: '🎨 צבע', action: 'שנה את צבע הכתוביות ללבן' },
            { label: '📝 כתוביות', action: 'הפעל כתוביות' },
            { label: '🚀 עבד', action: 'תערוך לי את הסרטון' }
          ].map((item, i) => (
            <button
              key={i}
              onClick={() => {
                setInputValue(item.action);
                setTimeout(() => handleSend(), 100);
              }}
              disabled={isLoading}
              className="px-2 py-1 bg-gray-800/50 text-gray-400 text-[10px] rounded hover:bg-gray-800 hover:text-white transition-colors disabled:opacity-50"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </Wrapper>
  );
}

export default ChatSection;
