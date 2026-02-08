/**
 * YouTubeTab - Professional YouTube Import workspace
 * Clean, minimal design matching SaaS aesthetic
 */
import { useState, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function YouTubeTab() {
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
        throw new Error(data.detail || data.message || 'שגיאה בהורדת הוידאו');
      }

      if (data.status === 'success' && data.videoUrl) {
        ctx.setVideoUrl?.(data.videoUrl);

        if (data.videoPath) {
          try {
            const videoResponse = await fetch(data.videoUrl);
            const blob = await videoResponse.blob();
            const file = new File([blob], data.filename || 'youtube_video.mp4', { type: 'video/mp4' });
            ctx.setVideoFile?.(file);
          } catch (fetchErr) {
            console.log('[YouTube Video] Using direct URL');
          }
        }

        setSuccess('הוידאו הורד בהצלחה');
        setUrl('');
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

  return (
    <div className="h-full bg-[#0a0c0f] overflow-y-auto" dir="rtl">
      <div className="max-w-2xl mx-auto p-8">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="w-14 h-14 bg-[#FF0000]/10 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-[#FF0000]/20">
            <svg className="w-7 h-7 text-[#FF0000]" viewBox="0 0 24 24" fill="currentColor">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-white mb-2">ייבוא מ-YouTube</h1>
          <p className="text-sm text-gray-500">הורד וידאו מ-YouTube לעריכה בסטודיו</p>
        </div>

        {/* Import Card */}
        <div className="bg-[#111318] border border-gray-800/50 rounded-xl p-6 mb-5">
          <label className="text-sm font-medium text-gray-300 mb-3 block">קישור YouTube</label>
          <div className="flex gap-3">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !isLoading && handleImport()}
              placeholder="https://youtube.com/watch?v=..."
              disabled={isLoading}
              className="flex-1 px-4 py-3.5 bg-[#0a0c0f] border border-gray-800/50 rounded-lg text-white text-sm placeholder-gray-600 focus:outline-none focus:border-[#FF0000]/50 transition-colors disabled:opacity-50"
              dir="ltr"
            />
            <button
              onClick={handleImport}
              disabled={isLoading || !url.trim()}
              className={`px-6 py-3.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                isLoading
                  ? 'bg-gray-800 text-gray-500 cursor-wait'
                  : url.trim()
                    ? 'bg-[#FF0000] hover:bg-[#cc0000] text-white'
                    : 'bg-gray-800 text-gray-600 cursor-not-allowed'
              }`}
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>מוריד...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  <span>ייבא</span>
                </>
              )}
            </button>
          </div>

          {/* Loading Progress */}
          {isLoading && (
            <div className="mt-4 bg-[#FF0000]/5 border border-[#FF0000]/20 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-[#FF0000]/30 border-t-[#FF0000] rounded-full animate-spin"></div>
                <div>
                  <p className="text-sm text-[#FF0000] font-medium">מוריד וידאו...</p>
                  <p className="text-[11px] text-gray-500">ההורדה עשויה להימשך מספר דקות</p>
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 bg-red-500/5 border border-red-500/20 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <div>
                  <p className="text-sm text-red-400 font-medium">שגיאה</p>
                  <p className="text-xs text-red-300/70 mt-0.5">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Success */}
          {success && (
            <div className="mt-4 bg-[#00C8C8]/5 border border-[#00C8C8]/20 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <svg className="w-5 h-5 text-[#00C8C8]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <span className="text-sm text-[#00C8C8] font-medium">{success}</span>
              </div>
            </div>
          )}
        </div>

        {/* Video Preview Card */}
        {ctx.videoUrl && (
          <div className="bg-[#111318] border border-gray-800/50 rounded-xl p-6 mb-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-[#00C8C8] rounded-full"></span>
                <span className="text-sm font-medium text-gray-300">וידאו מוכן לעריכה</span>
              </div>
              <a
                href={ctx.videoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-[#00C8C8]/10 text-[#00C8C8] border border-[#00C8C8]/20 rounded-lg text-xs font-medium hover:bg-[#00C8C8]/20 transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                <span>הורד למחשב</span>
              </a>
            </div>
            <video
              src={ctx.videoUrl}
              controls
              className="w-full rounded-lg border border-gray-800/50"
              style={{ maxHeight: '360px' }}
            />
          </div>
        )}

        {/* Help Section */}
        <div className="bg-[#111318] border border-gray-800/50 rounded-xl p-5">
          <h3 className="text-sm font-medium text-gray-300 mb-4">פורמטים נתמכים</h3>
          <div className="grid grid-cols-2 gap-3 text-[12px] text-gray-500">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#00C8C8]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              <span>youtube.com/watch?v=</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#00C8C8]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              <span>youtu.be/</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#00C8C8]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              <span>YouTube Shorts</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#00C8C8]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              <span>MP4 באיכות גבוהה</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default YouTubeTab;
