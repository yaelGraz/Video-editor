/**
 * VideoPreviewer - Video preview component (video only, no audio)
 * Audio is handled separately by AudioPreviewCard
 */
import { useState, useRef, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function VideoPreviewer() {
  const ctx = useContext(VideoEditorContext);
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Access settings
  const settings = ctx.videoSettings || ctx.previewConfig || {};

  const handleVideoPlay = () => setIsPlaying(true);
  const handleVideoPause = () => setIsPlaying(false);

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
  };

  // Dynamic subtitle style - fully synced with ManualEditor Style Engine
  const subtitleStyle = {
    fontFamily: `'${settings.font || 'Assistant'}', sans-serif`,
    fontWeight: settings.fontWeight || 400,
    fontStyle: settings.fontStyle || 'normal',
    color: settings.fontColor || '#FFFFFF',
    fontSize: `${settings.fontSize || 24}px`,
    textShadow: settings.textShadow || '2px 2px 4px rgba(0,0,0,0.9)'
  };

  // Subtitle position (bottom or center)
  const subtitlePosition = settings.subtitlePosition || 'bottom';
  const positionClass = subtitlePosition === 'center'
    ? 'absolute inset-0 flex items-center justify-center pointer-events-none z-50'
    : 'absolute bottom-8 left-4 right-4 pointer-events-none z-50';

  const showSubtitles = (settings.subtitlesEnabled ?? settings.subtitles ?? true) && settings.subtitleText;

  return (
    <section className="flex-1 bg-[#1a1d23] border border-gray-800 rounded-xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <h3 className="text-xs font-bold text-gray-400 flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full"></span>
          תצוגה מקדימה
        </h3>

        {/* Indicators */}
        <div className="flex items-center gap-1.5" dir="ltr">
          {settings.activeStyleId && (
            <span className="text-[9px] bg-[#00C8C8]/15 text-[#00C8C8] px-2 py-0.5 rounded border border-[#00C8C8]/30">
              {settings.activeStyleId}
            </span>
          )}
          <span className="text-[9px] bg-white/5 text-gray-400 px-2 py-0.5 rounded border border-white/10">
            {settings.font || 'Assistant'}
          </span>
          <span
            className="text-[9px] w-5 h-5 rounded border"
            style={{
              backgroundColor: settings.fontColor || '#FFFFFF',
              borderColor: 'rgba(255,255,255,0.2)'
            }}
          />
        </div>
      </div>

      {/* Preview area */}
      <div className="flex-1 p-4">
        <div className="h-full bg-black rounded-xl overflow-hidden border border-gray-700 relative">
          {ctx.videoUrl ? (
            <>
              <video
                ref={videoRef}
                src={ctx.videoUrl}
                className="w-full h-full object-contain"
                onClick={togglePlayPause}
                onPlay={handleVideoPlay}
                onPause={handleVideoPause}
                playsInline
              />

              {/* Play/Pause overlay */}
              {!isPlaying && (
                <div
                  className="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer"
                  onClick={togglePlayPause}
                >
                  <div className="w-16 h-16 bg-white/20 backdrop-blur rounded-full flex items-center justify-center hover:bg-white/30 transition-colors">
                    <span className="text-white text-2xl ml-1">▶</span>
                  </div>
                </div>
              )}

              {/* Subtitles overlay - dynamic position based on style */}
              {showSubtitles && (
                <div className={positionClass}>
                  <div className="text-center">
                    <span className="inline-block px-4 py-2 rounded-lg bg-black/60" style={subtitleStyle}>
                      {settings.subtitleText}
                    </span>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-gray-600 relative">
              <span className="text-6xl mb-4">🎥</span>
              <p className="text-sm">העלה וידאו לתצוגה מקדימה</p>
              <p className="text-[10px] text-gray-700 mt-2">הכתוביות יופיעו כאן בזמן אמת</p>

              {showSubtitles && (
                <div className={positionClass}>
                  <div className="text-center">
                    <span className="inline-block px-4 py-2 rounded-lg bg-black/60" style={subtitleStyle}>
                      {settings.subtitleText}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="p-4 border-t border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            <button
              onClick={togglePlayPause}
              disabled={!ctx.videoUrl}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                ctx.videoUrl
                  ? 'bg-[#00C8C8]/20 text-[#00C8C8] border border-[#00C8C8]/30 hover:bg-[#00C8C8]/30'
                  : 'bg-gray-800 text-gray-600 cursor-not-allowed'
              }`}
            >
              {isPlaying ? '⏸️ עצור' : '▶️ הפעל'}
            </button>

            {/* Download to PC button - for source video */}
            {ctx.videoUrl && !ctx.resultUrl && (
              <a
                href={ctx.videoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg text-xs font-bold hover:bg-purple-500/30 transition-colors"
              >
                💾 פתח בטאב חדש
              </a>
            )}
          </div>

          {/* Download result button */}
          {ctx.resultUrl && (
            <a
              href={ctx.resultUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg text-xs font-bold hover:bg-green-500/30 transition-colors"
            >
              ⬇️ פתח תוצאה בטאב חדש
            </a>
          )}
        </div>

      </div>
    </section>
  );
}

export default VideoPreviewer;
