/**
 * VideoPlanner - AI-powered video script planner
 * Upload .docx/.txt files and get AI assistance for video planning
 * Design: Professional high-tech look with #00C8C8 accents
 */
import { useState, useRef, useContext, useEffect } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function VideoPlanner() {
  const ctx = useContext(VideoEditorContext);
  const apiUrl = ctx.apiUrl;

  // Core state
  const [extractedText, setExtractedText] = useState(''); // Hidden from UI, used in logic
  const [isExtracting, setIsExtracting] = useState(false);
  const [isPlanning, setIsPlanning] = useState(false);
  const [planResult, setPlanResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [userPrompt, setUserPrompt] = useState('');
  const [chatHistory, setChatHistory] = useState([]);

  // Library slots (synced with ManualEditor defaults)
  const [librarySlots, setLibrarySlots] = useState([
    { id: 0, filename: 'emotional_piano_slow_trimmed.mp3', displayName: 'פסנתר רגשי', url: null },
    { id: 1, filename: 'inspiring_epic_drive_high_trimmed.mp3', displayName: 'אפי מרומם', url: null },
    { id: 2, filename: 'peaceful_nature_trimmed.mp3', displayName: 'טבע שליו', url: null }
  ]);
  const [activeSlot, setActiveSlot] = useState(null);
  const [uploadingSlot, setUploadingSlot] = useState(null);
  const libraryFileRefs = [useRef(null), useRef(null), useRef(null)];

  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // Scroll chat to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  // Fetch user library on mount
  useEffect(() => {
    fetchUserLibrary();
  }, []);

  const fetchUserLibrary = async () => {
    try {
      const response = await fetch(`${apiUrl}/user-library`);
      const data = await response.json();
      if (data.status === 'success' && data.library?.slots) {
        setLibrarySlots(data.library.slots);
      }
    } catch (error) {
      console.log('[Library] Fetch error:', error.message);
    }
  };

  // Handle file upload and text extraction
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const validTypes = ['.txt', '.docx'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!validTypes.includes(fileExt)) {
      setError('אנא העלה קובץ טקסט (.txt) או Word (.docx)');
      return;
    }

    setIsExtracting(true);
    setError(null);
    setUploadedFileName(file.name);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${apiUrl}/video-planner/extract-file`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'שגיאה בחילוץ הטקסט');
      }

      if (data.status === 'success' && data.text) {
        setExtractedText(data.text);
        setChatHistory(prev => [...prev, {
          role: 'system',
          content: `📄 קובץ "${file.name}" נטען בהצלחה (${data.char_count} תווים)`
        }]);
      } else {
        throw new Error('לא נמצא טקסט בקובץ');
      }
    } catch (err) {
      setError(err.message);
      setExtractedText('');
    } finally {
      setIsExtracting(false);
    }
  };

  // Smart planning - uses extractedText if available, otherwise userPrompt
  const handlePlanVideo = async () => {
    const hasFile = extractedText.trim().length > 0;
    const hasPrompt = userPrompt.trim().length > 0;

    if (!hasFile && !hasPrompt) {
      setError('אנא העלה קובץ או הזן תיאור לסרטון');
      return;
    }

    setIsPlanning(true);
    setError(null);

    // Smart logic: If file uploaded, use it as primary source
    const promptToSend = hasFile
      ? (hasPrompt ? userPrompt : 'צור לי תסריט מפורט לסרטון בהתבסס על הטקסט')
      : userPrompt;

    const scriptSource = hasFile ? extractedText : '';

    try {
      const response = await fetch(`${apiUrl}/video-planner/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_input: promptToSend,
          history: chatHistory,
          current_script: scriptSource
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'שגיאה בתכנון הוידאו');
      }

      if (data.status === 'success') {
        setPlanResult(data.script || data.ai_message);
        setChatHistory(prev => [
          ...prev,
          { role: 'user', content: promptToSend },
          { role: 'assistant', content: data.ai_message }
        ]);
        setUserPrompt('');
      } else {
        throw new Error(data.error || 'שגיאה לא צפויה');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsPlanning(false);
    }
  };

  const handleClearAll = () => {
    setExtractedText('');
    setPlanResult(null);
    setChatHistory([]);
    setUploadedFileName(null);
    setUserPrompt('');
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Library handlers
  const selectLibrarySlot = (slot) => {
    if (!slot.filename) return;
    setActiveSlot(slot.id);
    const audioUrl = slot.url || `${apiUrl}/assets/music/${slot.filename}`;
    ctx.setAudioUrl?.(audioUrl);
  };

  const handleLibraryUpload = async (slotId, file) => {
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
      }
    } catch (error) {
      console.error('[Library] Upload error:', error);
    } finally {
      setUploadingSlot(null);
      if (libraryFileRefs[slotId]?.current) {
        libraryFileRefs[slotId].current.value = '';
      }
    }
  };

  return (
    <div className="h-full flex bg-[#0a0b0d]" dir="rtl">
      {/* ========== MAIN CONTENT ========== */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-[#00C8C8]/20 bg-[#0f1115]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00C8C8]/20 to-purple-500/20 flex items-center justify-center border border-[#00C8C8]/30">
                <span className="text-lg">📋</span>
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">מתכנן תסריט AI</h2>
                <p className="text-[10px] text-gray-500">העלה קובץ או תאר את הסרטון וקבל תסריט מפורט</p>
              </div>
            </div>
            {(extractedText || planResult || chatHistory.length > 0) && (
              <button
                onClick={handleClearAll}
                className="px-3 py-1.5 text-xs text-red-400 hover:text-red-300 border border-red-400/30 rounded-lg hover:bg-red-400/10 transition-all"
              >
                נקה הכל
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 flex gap-4 p-4 overflow-hidden">
          {/* ===== LEFT PANEL - Input ===== */}
          <div className="w-1/2 flex flex-col gap-4">
            {/* File Upload Box */}
            <div className="bg-[#12141a] border-2 border-[#00C8C8]/30 rounded-xl p-4">
              <label className="text-xs text-[#00C8C8] mb-3 block font-medium">העלאת קובץ מקור</label>

              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
                  isExtracting
                    ? 'border-[#00C8C8] bg-[#00C8C8]/5'
                    : uploadedFileName
                      ? 'border-green-500/50 bg-green-500/5'
                      : 'border-gray-700 hover:border-[#00C8C8]/50 hover:bg-[#00C8C8]/5'
                }`}
                onClick={() => !isExtracting && fileInputRef.current?.click()}
              >
                {isExtracting ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-10 h-10 border-3 border-[#00C8C8]/30 border-t-[#00C8C8] rounded-full animate-spin"></div>
                    <span className="text-sm text-[#00C8C8] font-medium">מחלץ טקסט...</span>
                  </div>
                ) : uploadedFileName ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                      <span className="text-2xl">✅</span>
                    </div>
                    <span className="text-sm text-green-400 font-medium">{uploadedFileName}</span>
                    <span className="text-[10px] text-gray-500">לחץ להחלפת קובץ</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-14 h-14 rounded-full bg-[#00C8C8]/10 flex items-center justify-center border border-[#00C8C8]/30">
                      <span className="text-2xl">📄</span>
                    </div>
                    <span className="text-sm text-gray-300 font-medium">גרור קובץ או לחץ לבחירה</span>
                    <span className="text-[10px] text-gray-600">.txt או .docx</span>
                  </div>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.docx"
                onChange={handleFileUpload}
                className="hidden"
              />

              {/* File loaded indicator (no textarea) */}
              {extractedText && (
                <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-[#00C8C8]/10 border border-[#00C8C8]/30 rounded-lg">
                  <span className="text-[#00C8C8]">✓</span>
                  <span className="text-xs text-[#00C8C8]">הטקסט נטען ומוכן לעיבוד ({extractedText.length} תווים)</span>
                </div>
              )}
            </div>

            {/* User Prompt Box */}
            <div className="flex-1 bg-[#12141a] border-2 border-[#00C8C8]/30 rounded-xl p-4 flex flex-col">
              <label className="text-xs text-[#00C8C8] mb-3 block font-medium">
                {extractedText ? 'הנחיות נוספות (אופציונלי)' : 'תאר את הסרטון שלך'}
              </label>
              <textarea
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                className="flex-1 bg-[#0a0b0d] border border-[#00C8C8]/20 rounded-lg p-4 text-sm text-white resize-none focus:outline-none focus:border-[#00C8C8] transition-colors"
                placeholder={extractedText
                  ? 'למשל: צור תסריט לסרטון של 2 דקות בסגנון מרגש...'
                  : 'תאר את הסרטון שברצונך ליצור, כולל נושא, סגנון, אורך וקהל יעד...'
                }
              />
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-red-500/10 border-2 border-red-500/40 rounded-xl p-4">
                <div className="flex items-center gap-2">
                  <span className="text-red-400 text-lg">⚠️</span>
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              </div>
            )}

            {/* Plan Button */}
            <button
              onClick={handlePlanVideo}
              disabled={isPlanning || (!extractedText.trim() && !userPrompt.trim())}
              className={`w-full py-4 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-3 border-2 ${
                isPlanning
                  ? 'bg-[#00C8C8]/10 border-[#00C8C8]/30 text-[#00C8C8] cursor-wait'
                  : (extractedText.trim() || userPrompt.trim())
                    ? 'bg-gradient-to-r from-[#00C8C8] to-[#0891b2] border-[#00C8C8] text-white hover:shadow-lg hover:shadow-[#00C8C8]/25'
                    : 'bg-gray-800/50 border-gray-700 text-gray-600 cursor-not-allowed'
              }`}
            >
              {isPlanning ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>מייצר תסריט...</span>
                </>
              ) : (
                <>
                  <span className="text-lg">🎬</span>
                  <span>תכנן וידאו עם AI</span>
                </>
              )}
            </button>
          </div>

          {/* ===== RIGHT PANEL - Results & Chat ===== */}
          <div className="w-1/2 flex flex-col gap-4">
            {/* Script Result Box */}
            <div className="flex-1 bg-[#12141a] border-2 border-[#00C8C8]/30 rounded-xl p-4 flex flex-col min-h-0">
              <div className="flex items-center justify-between mb-3">
                <label className="text-xs text-[#00C8C8] font-medium">תסריט מוצע</label>
                {planResult && (
                  <button
                    onClick={() => navigator.clipboard.writeText(planResult)}
                    className="text-xs text-gray-400 hover:text-[#00C8C8] transition-colors px-2 py-1 rounded border border-transparent hover:border-[#00C8C8]/30"
                  >
                    [ העתק ]
                  </button>
                )}
              </div>

              {planResult ? (
                <div className="flex-1 bg-[#0a0b0d] border border-[#00C8C8]/20 rounded-lg p-4 overflow-y-auto">
                  <pre className="text-sm text-white whitespace-pre-wrap font-sans leading-relaxed">{planResult}</pre>
                </div>
              ) : (
                <div className="flex-1 bg-[#0a0b0d] border border-gray-800 rounded-lg flex flex-col items-center justify-center text-gray-600">
                  <div className="w-16 h-16 rounded-full bg-[#00C8C8]/5 flex items-center justify-center border border-[#00C8C8]/20 mb-4">
                    <span className="text-3xl">🎯</span>
                  </div>
                  <p className="text-sm text-gray-500">התסריט יופיע כאן</p>
                  <p className="text-[10px] text-gray-700 mt-1">העלה קובץ או תאר את הסרטון</p>
                </div>
              )}
            </div>

            {/* Chat History Box */}
            <div className="bg-[#12141a] border-2 border-[#00C8C8]/30 rounded-xl p-4 max-h-64 flex flex-col">
              <label className="text-xs text-[#00C8C8] font-medium mb-3">שיחה עם AI</label>

              <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {chatHistory.length === 0 ? (
                  <div className="flex items-center justify-center h-20 text-gray-600">
                    <p className="text-xs">השיחה תופיע כאן...</p>
                  </div>
                ) : (
                  chatHistory.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-2.5 rounded-2xl ${
                          msg.role === 'user'
                            ? 'bg-[#00C8C8]/15 text-[#00C8C8] rounded-tr-sm border border-[#00C8C8]/30'
                            : msg.role === 'system'
                              ? 'bg-gray-800/80 text-gray-400 rounded-tl-sm border border-gray-700'
                              : 'bg-purple-500/15 text-purple-300 rounded-tl-sm border border-purple-500/30'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-medium opacity-70">
                            {msg.role === 'user' ? '👤 אתה' : msg.role === 'system' ? '⚙️ מערכת' : '🤖 AI'}
                          </span>
                        </div>
                        <p className="text-xs leading-relaxed">
                          {msg.content.length > 300 ? msg.content.substring(0, 300) + '...' : msg.content}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={chatEndRef} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ========== SIDEBAR - Library ========== */}
      <div className="w-64 bg-[#0f1115] border-r border-[#00C8C8]/20 flex flex-col">
        <div className="p-4 border-b border-[#00C8C8]/20">
          <h3 className="text-sm font-bold text-white">הספרייה שלי</h3>
          <p className="text-[10px] text-gray-500 mt-1">שמירת עד 3 קבצים לגישה מהירה</p>
        </div>

        <div className="flex-1 p-4 space-y-3 overflow-y-auto">
          {librarySlots.map((slot, index) => (
            <div
              key={slot.id}
              className={`p-3 rounded-xl transition-all ${
                activeSlot === slot.id
                  ? 'bg-[#00C8C8]/10 border-2 border-[#00C8C8]'
                  : 'bg-[#1a1d23] border border-gray-800 hover:border-gray-700'
              }`}
            >
              <input
                type="file"
                ref={libraryFileRefs[index]}
                accept="audio/*,.mp3,.wav,.ogg,.m4a"
                onChange={(e) => handleLibraryUpload(slot.id, e.target.files?.[0])}
                className="hidden"
              />

              <div className="flex flex-col gap-2">
                {/* Slot info */}
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

                {/* Action buttons */}
                <div className="flex items-center gap-3">
                  {slot.filename ? (
                    <>
                      <button
                        onClick={() => selectLibrarySlot(slot)}
                        className="text-xs text-gray-400 hover:text-[#00C8C8] transition-colors"
                      >
                        [ בחר ]
                      </button>
                      <button
                        onClick={() => libraryFileRefs[index].current?.click()}
                        className="text-xs text-gray-400 hover:text-[#00C8C8] transition-colors"
                      >
                        [ החלף ]
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => libraryFileRefs[index].current?.click()}
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

        {/* Settings hint */}
        <div className="p-4 border-t border-gray-800">
          <p className="text-[10px] text-gray-600 text-center">
            הספרייה משותפת עם העורך
          </p>
        </div>
      </div>
    </div>
  );
}

export default VideoPlanner;
