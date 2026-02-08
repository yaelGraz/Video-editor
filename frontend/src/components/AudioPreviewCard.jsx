/**
 * AudioPreviewCard - Slim horizontal card for background music preview
 * Independent from video playback - user can audition music separately
 */
import { useState, useRef, useEffect, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function AudioPreviewCard() {
  const ctx = useContext(VideoEditorContext);
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioLoaded, setAudioLoaded] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Access volume settings
  const settings = ctx.videoSettings || ctx.previewConfig || {};

  // Update volume when settings change
  useEffect(() => {
    if (audioRef.current) {
      const vol = settings.musicVolume ?? 0.15;
      audioRef.current.volume = Math.max(0, Math.min(1, vol));
    }
  }, [settings.musicVolume]);

  // Track URL with timestamp to prevent stale cache issues
  const [audioSrcWithTimestamp, setAudioSrcWithTimestamp] = useState('');

  // Reset when URL changes
  useEffect(() => {
    console.log('[AudioCard] 🔄 audioUrl changed:', ctx.audioUrl);
    setAudioLoaded(false);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);

    // Add timestamp only for localhost URLs to bust cache on URL change
    if (ctx.audioUrl) {
      if (ctx.audioUrl.includes('localhost')) {
        const separator = ctx.audioUrl.includes('?') ? '&' : '?';
        setAudioSrcWithTimestamp(`${ctx.audioUrl}${separator}_t=${Date.now()}`);
      } else {
        setAudioSrcWithTimestamp(ctx.audioUrl);
      }
    } else {
      setAudioSrcWithTimestamp('');
    }
  }, [ctx.audioUrl]);

  const handleAudioLoaded = () => {
    setAudioLoaded(true);
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
      const vol = settings.musicVolume ?? 0.15;
      audioRef.current.volume = Math.max(0, Math.min(1, vol));
    }
    console.log('[AudioCard] ✅ Audio loaded successfully');
  };

  const handleAudioError = (e) => {
    const audio = audioRef.current;
    let errorMessage = 'לא ניתן לטעון את קובץ האודיו';

    if (audio?.error) {
      const code = audio.error.code;
      console.error('[AudioCard] ❌ Error code:', code, audio.error.message);

      switch (code) {
        case MediaError.MEDIA_ERR_ABORTED:
          errorMessage = 'הטעינה בוטלה';
          break;
        case MediaError.MEDIA_ERR_NETWORK:
          errorMessage = 'שגיאת רשת - בדוק את החיבור';
          break;
        case MediaError.MEDIA_ERR_DECODE:
          errorMessage = 'פורמט הקובץ אינו נתמך';
          break;
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          errorMessage = 'הקובץ אינו זמין או הנתיב שגוי';
          break;
      }
    }

    // Check for 416 Range Not Satisfiable (common when file doesn't exist)
    console.error('[AudioCard] ❌ Load error:', errorMessage, 'URL:', ctx.audioUrl);
    setAudioLoaded(false);
    ctx.setAudioError?.(errorMessage);
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const togglePlayPause = () => {
    if (!audioRef.current || !audioLoaded) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => {
        setIsPlaying(true);
      }).catch(err => {
        console.log('[AudioCard] Cannot play:', err.message);
      });
    }
  };

  const formatTime = (time) => {
    if (!time || isNaN(time)) return '0:00';
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Downloading state
  if (ctx.isDownloadingAudio) {
    return (
      <div className="bg-gray-800/40 border border-[#00C8C8]/30 rounded-xl p-3 mb-4" dir="rtl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#00C8C8]/20 rounded-lg flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-[#00C8C8]/30 border-t-[#00C8C8] rounded-full animate-spin"></div>
          </div>
          <div className="flex-1">
            <p className="text-sm text-[#00C8C8]">מוריד מוזיקה מ-YouTube...</p>
            <p className="text-xs text-gray-500">אנא המתן</p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (ctx.audioError && !ctx.audioUrl) {
    return (
      <div className="bg-gray-800/40 border border-red-500/30 rounded-xl p-3 mb-4" dir="rtl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-red-500/20 rounded-lg flex items-center justify-center">
            <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-sm text-red-400">שגיאה בטעינת מוזיקה</p>
            <p className="text-xs text-gray-500">{ctx.audioError}</p>
          </div>
        </div>
      </div>
    );
  }

  // Empty state - no audio selected
  if (!ctx.audioUrl) {
    return (
      <div className="bg-gray-800/40 border border-gray-700 rounded-xl p-3 mb-4" dir="rtl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gray-700/50 rounded-lg flex items-center justify-center">
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-sm text-gray-400">טרם נבחרה מוזיקה</p>
            <p className="text-xs text-gray-600">שלח קישור YouTube או בחר מהספרייה בצ'אט</p>
          </div>
        </div>
      </div>
    );
  }

  // Ready state - audio loaded
  return (
    <div className="bg-gray-800/40 border border-gray-700 rounded-xl p-3 mb-4" dir="rtl">
      {/* Hidden audio element - uses timestamped URL to avoid 416 cache errors */}
      <audio
        ref={audioRef}
        src={audioSrcWithTimestamp}
        preload="metadata"
        loop
        crossOrigin="anonymous"
        onCanPlayThrough={handleAudioLoaded}
        onLoadedMetadata={() => {
          if (audioRef.current) {
            setDuration(audioRef.current.duration);
          }
        }}
        onError={handleAudioError}
        onTimeUpdate={handleTimeUpdate}
        onEnded={() => setIsPlaying(false)}
      />

      <div className="flex items-center gap-3">
        {/* Play/Pause button */}
        <button
          onClick={togglePlayPause}
          disabled={!audioLoaded}
          className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all ${
            audioLoaded
              ? 'bg-[#00C8C8] hover:bg-[#00B0B0] text-white cursor-pointer'
              : 'bg-gray-700/50 text-gray-500 cursor-wait'
          }`}
        >
          {!audioLoaded ? (
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : isPlaying ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>

        {/* Info and progress */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <p className="text-sm text-white truncate">
              {audioLoaded ? '🎵 מוזיקת רקע מוכנה' : '⏳ טוען...'}
            </p>
            <span className="text-xs text-gray-400 mr-2" dir="ltr">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#00C8C8] transition-all duration-200"
              style={{ width: duration ? `${(currentTime / duration) * 100}%` : '0%' }}
            />
          </div>
        </div>

        {/* Volume indicator */}
        <div className="flex items-center gap-1 text-xs text-gray-400" dir="ltr">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
          </svg>
          <span>{Math.round((settings.musicVolume ?? 0.15) * 100)}%</span>
        </div>
      </div>
    </div>
  );
}

export default AudioPreviewCard;
