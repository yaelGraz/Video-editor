/**
 * YouTubeImportTab - YouTube video MP4 import interface
 * Allows users to download videos from YouTube for editing
 */
import { useState, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function YouTubeImportTab() {
  const ctx = useContext(VideoEditorContext);
  const apiUrl = ctx.apiUrl;
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleImport = async () => {
    if (!url.trim()) {
      setError('אנא הזן קישור YouTube');
      return;
    }

    // Validate YouTube URL
    const youtubeRegex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)/;
    if (!youtubeRegex.test(url)) {
      setError('הקישור לא תקין. אנא הזן קישור YouTube חוקי.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const formData = new FormData();
      formData.append('url', url.trim());

      const response = await fetch(`${apiUrl}/download-youtube-video`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        // Capture detail error message from server
        throw new Error(data.detail || data.message || 'שגיאה בהורדת הוידאו');
      }

      if (data.status === 'success' && data.videoUrl) {
        // Success - update context and show success message
        ctx.setVideoUrl?.(data.videoUrl);

        // If server returns a File object URL or we need to fetch the video
        if (data.videoPath) {
          // Fetch the video as a blob and create a File object
          try {
            const videoResponse = await fetch(data.videoUrl);
            const blob = await videoResponse.blob();
            const file = new File([blob], data.filename || 'youtube_video.mp4', { type: 'video/mp4' });
            ctx.setVideoFile?.(file);
          } catch (fetchErr) {
            console.log('[YouTube Video] Using direct URL');
          }
        }

        setSuccess(`הוידאו הורד בהצלחה! 🎉`);
        setUrl('');

        // Clear success message after 5 seconds
        setTimeout(() => setSuccess(null), 5000);
      } else {
        throw new Error(data.message || 'שגיאה לא צפויה');
      }
    } catch (err) {
      console.error('[YouTube Video] Error:', err);
      setError(err.message || 'שגיאה בהורדת הוידאו מ-YouTube');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isLoading) {
      handleImport();
    }
  };

  return (
    <div className="h-full flex flex-col p-4 space-y-4 overflow-y-auto bg-[#16191e]" dir="rtl">
      {/* Header */}
      <div className="text-center mb-4">
        <div className="w-12 h-12 bg-red-500/20 rounded-xl flex items-center justify-center mx-auto mb-2">
          <svg className="w-6 h-6 text-red-400" viewBox="0 0 24 24" fill="currentColor">
            <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
          </svg>
        </div>
        <h3 className="text-sm font-bold text-white">ייבוא מ-YouTube</h3>
        <p className="text-[10px] text-gray-500 mt-1">הורד וידאו מ-YouTube לעריכה</p>
      </div>

      {/* URL Input */}
      <div className="space-y-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="הדבק קישור YouTube כאן..."
          disabled={isLoading}
          className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-[#00C8C8] transition-colors disabled:opacity-50"
          dir="ltr"
        />
      </div>

      {/* Import Button */}
      <button
        onClick={handleImport}
        disabled={isLoading || !url.trim()}
        className={`w-full py-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${
          isLoading
            ? 'bg-gray-700 text-gray-400 cursor-wait'
            : url.trim()
              ? 'bg-red-500 hover:bg-red-600 text-white cursor-pointer'
              : 'bg-gray-800 text-gray-600 cursor-not-allowed'
        }`}
      >
        {isLoading ? (
          <>
            <div className="w-4 h-4 border-2 border-gray-400/30 border-t-gray-400 rounded-full animate-spin"></div>
            <span>מוריד וידאו, אנא המתן...</span>
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>ייבא וידאו</span>
          </>
        )}
      </button>

      {/* Download to PC Button - Only visible after successful import */}
      {ctx.videoUrl && (
        <a
          href={ctx.videoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full py-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 bg-transparent border-2 border-[#00C8C8] text-[#00C8C8] hover:bg-[#00C8C8]/10"
        >
          <span>📥</span>
          <span>הורד קובץ למחשב</span>
        </a>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="bg-[#00C8C8]/10 border border-[#00C8C8]/30 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 border-2 border-[#00C8C8]/30 border-t-[#00C8C8] rounded-full animate-spin"></div>
            <span className="text-sm text-[#00C8C8]">מוריד וידאו, אנא המתן...</span>
          </div>
          <p className="text-[10px] text-gray-500 mt-2">
            ההורדה עשויה להימשך מספר דקות בהתאם לגודל הוידאו
          </p>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm text-red-400 font-medium">שגיאה</p>
              <p className="text-xs text-red-300/80 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm text-green-400">{success}</span>
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="text-[10px] text-gray-600 space-y-1">
        <p>• תמיכה בקישורים מ-youtube.com ו-youtu.be</p>
        <p>• הוידאו יישמר בפורמט MP4 באיכות הטובה ביותר</p>
        <p>• לאחר ההורדה הוידאו יופיע בתצוגה המקדימה</p>
      </div>
    </div>
  );
}

export default YouTubeImportTab;
