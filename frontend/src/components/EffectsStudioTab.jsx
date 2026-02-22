import { useState, useContext, useRef, useEffect, useCallback } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

// =============================================================================
// Constants & Presets
// =============================================================================
const SUBTITLE_STYLES = [
  { id: 'karaoke', label: 'קריוקי', desc: 'מילים קופצות עם הדגשה' },
  { id: 'bounce', label: 'קפיצה', desc: 'אנימציה שובבה וצבעונית' },
  { id: 'cinematic', label: 'קולנועי', desc: 'כניסה דרמטית מוגדלת' },
  { id: 'neon', label: 'ניאון', desc: 'זוהר ניאון עם גליץ\'' },
];

const VISUALIZER_STYLES = [
  { id: 'bars', label: 'עמודות' },
  { id: 'wave', label: 'גל' },
  { id: 'circle', label: 'מעגל' },
];

const POSITION_OPTIONS = [
  { id: 'bottom', label: 'למטה' },
  { id: 'center', label: 'מרכז' },
  { id: 'top', label: 'למעלה' },
];

// =============================================================================
// Showreel Demo Data - shown when no real video/transcription is loaded
// =============================================================================
const DEMO_ENTRIES = [
  { start: 0.0, end: 2.5, text: 'ברוכים הבאים לאולפן האפקטים' },
  { start: 2.8, end: 5.2, text: 'כאן תוכלו לראות את כל הסגנונות' },
  { start: 5.5, end: 8.0, text: 'קריוקי, קפיצה, קולנועי וניאון' },
  { start: 8.3, end: 11.0, text: 'הפעילו אפקטים כמו רעידת מצלמה' },
  { start: 11.3, end: 14.0, text: 'חלקיקים צפים וזום דינמי' },
  { start: 14.3, end: 17.0, text: 'שנו צבעים, גדלים ומיקום' },
  { start: 17.3, end: 20.0, text: 'כשתעלו סרטון, הנתונים האמיתיים יופיעו' },
];

// =============================================================================
// Audio Visualizer Component (Web Audio API + Canvas) - Client Preview
// =============================================================================
function AudioVisualizer({ audioUrl, color = '#00D1C1', style = 'bars', height = 120 }) {
  const canvasRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceRef = useRef(null);
  const animFrameRef = useRef(null);
  const audioRef = useRef(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    if (style === 'bars') {
      const barCount = 64;
      const barW = W / barCount;
      for (let i = 0; i < barCount; i++) {
        const idx = Math.floor(i * bufferLength / barCount);
        const val = dataArray[idx] / 255;
        const barH = val * H * 0.9;
        const alpha = 0.4 + val * 0.6;
        ctx.fillStyle = color + Math.round(alpha * 255).toString(16).padStart(2, '0');
        ctx.fillRect(i * barW + 1, H - barH, barW - 2, barH);
      }
    } else if (style === 'wave') {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      const sliceW = W / bufferLength;
      for (let i = 0; i < bufferLength; i++) {
        const val = dataArray[i] / 255;
        const y = H / 2 + (val - 0.5) * H * 0.8;
        if (i === 0) ctx.moveTo(0, y); else ctx.lineTo(i * sliceW, y);
      }
      ctx.stroke();
      ctx.lineTo(W, H);
      ctx.lineTo(0, H);
      ctx.closePath();
      ctx.fillStyle = color + '20';
      ctx.fill();
    } else if (style === 'circle') {
      const cx = W / 2, cy = H / 2, baseR = Math.min(W, H) * 0.25;
      const bars = 48;
      for (let i = 0; i < bars; i++) {
        const idx = Math.floor(i * bufferLength / bars);
        const val = dataArray[idx] / 255;
        const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
        const r1 = baseR;
        const r2 = baseR + val * baseR * 0.8;
        ctx.beginPath();
        ctx.strokeStyle = color + Math.round((0.4 + val * 0.6) * 255).toString(16).padStart(2, '0');
        ctx.lineWidth = 3;
        ctx.moveTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
        ctx.lineTo(cx + Math.cos(angle) * r2, cy + Math.sin(angle) * r2);
        ctx.stroke();
      }
    }

    animFrameRef.current = requestAnimationFrame(draw);
  }, [color, style]);

  useEffect(() => {
    if (!audioUrl) return;

    const audio = new Audio();
    audio.crossOrigin = 'anonymous';
    audio.src = audioUrl;
    audioRef.current = audio;

    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    audioCtxRef.current = audioCtx;

    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyserRef.current = analyser;

    const source = audioCtx.createMediaElementSource(audio);
    source.connect(analyser);
    // Do NOT connect to destination - visualize silently, don't play through speakers
    sourceRef.current = source;

    audio.play().catch(() => {});
    animFrameRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      audio.pause();
      audio.src = '';
      try { audioCtx.close(); } catch {}
    };
  }, [audioUrl, draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = height;
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [height]);

  if (!audioUrl) {
    return (
      <div className="flex items-center justify-center bg-slate-800/30 rounded-xl border border-slate-700/30" style={{ height }}>
        <span className="text-slate-600 text-sm">בחר שיר כדי לראות גלי סאונד</span>
      </div>
    );
  }

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700/40 bg-black/40">
      <canvas ref={canvasRef} style={{ width: '100%', height, display: 'block' }} />
    </div>
  );
}

// =============================================================================
// Popup Subtitles Preview (CSS Spring Animations)
// =============================================================================
function PopupSubtitlesPreview({
  entries = [],
  animationStyle = 'karaoke',
  primaryColor = '#FFFFFF',
  highlightColor = '#00D1C1',
  fontSize = 32,
  position = 'bottom',
  videoUrl = null,
  audioUrl = null,
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [musicMuted, setMusicMuted] = useState(false);
  const videoRef = useRef(null);
  const musicRef = useRef(null);
  const timerRef = useRef(null);

  const wordLines = (entries || []).map(entry => {
    const words = (entry.text || '').split(/\s+/).filter(Boolean);
    const duration = (entry.end || 0) - (entry.start || 0);
    const wordDur = words.length > 0 ? duration / words.length : 0;
    return {
      lineStart: entry.start || 0,
      lineEnd: entry.end || 0,
      words: words.map((w, i) => ({
        word: w,
        start: (entry.start || 0) + i * wordDur,
        end: (entry.start || 0) + (i + 1) * wordDur,
      })),
    };
  });

  const togglePlay = () => {
    if (isPlaying) {
      clearInterval(timerRef.current);
      if (videoRef.current) videoRef.current.pause();
      if (musicRef.current) musicRef.current.pause();
      setIsPlaying(false);
    } else {
      if (videoRef.current) {
        videoRef.current.currentTime = currentTime;
        videoRef.current.play().catch(() => {});
      }
      if (musicRef.current) {
        musicRef.current.currentTime = currentTime;
        musicRef.current.play().catch(() => {});
      }
      timerRef.current = setInterval(() => {
        if (videoRef.current) {
          setCurrentTime(videoRef.current.currentTime);
        } else {
          setCurrentTime(t => t + 0.04);
        }
      }, 40);
      setIsPlaying(true);
    }
  };

  const resetPlayback = () => {
    clearInterval(timerRef.current);
    setCurrentTime(0);
    setIsPlaying(false);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.pause();
    }
    if (musicRef.current) {
      musicRef.current.currentTime = 0;
      musicRef.current.pause();
    }
  };

  useEffect(() => () => {
    clearInterval(timerRef.current);
    if (musicRef.current) { musicRef.current.pause(); musicRef.current.src = ''; }
  }, []);

  const getWordStyle = (word, isActive, isPast, styleType) => {
    const base = {
      display: 'inline-block',
      marginLeft: '6px',
      marginRight: '6px',
      fontSize: `${fontSize}px`,
      fontWeight: isActive ? 700 : 500,
      textShadow: isActive
        ? `0 0 20px ${highlightColor}, 0 0 40px ${highlightColor}80, 0 4px 15px rgba(0,0,0,0.9)`
        : '0 2px 10px rgba(0,0,0,0.8)',
      transition: 'all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)',
    };

    if (!isActive && !isPast) {
      return { ...base, opacity: 0.3, color: primaryColor, transform: 'scale(0.8) translateY(10px)' };
    }

    if (styleType === 'karaoke') {
      return { ...base, color: isActive ? highlightColor : primaryColor, opacity: 1, transform: isActive ? 'scale(1.15) translateY(-2px)' : 'scale(1)' };
    }
    if (styleType === 'bounce') {
      return { ...base, color: isActive ? highlightColor : primaryColor, opacity: 1, transform: `scale(${isActive ? 1.2 : 1}) translateY(${isActive ? -8 : 0}px)`, transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)' };
    }
    if (styleType === 'cinematic') {
      return { ...base, color: isActive ? '#FFD700' : primaryColor, opacity: isActive ? 1 : 0.7, transform: isActive ? 'scale(1.4)' : 'scale(1)', letterSpacing: isActive ? '2px' : '0px', textTransform: 'uppercase', fontWeight: 900, transition: 'all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)' };
    }
    if (styleType === 'neon') {
      return { ...base, color: isActive ? '#0ff' : primaryColor, opacity: 1, transform: isActive ? 'scale(1.1)' : 'scale(1)', textShadow: isActive ? '0 0 10px #0ff, 0 0 20px #0ff, 0 0 40px #0ff, 0 0 80px #00f' : '0 0 5px rgba(0,255,255,0.3)' };
    }
    return { ...base, color: isActive ? highlightColor : primaryColor, opacity: 1, transform: 'scale(1)' };
  };

  const posStyle = position === 'top' ? { top: '10%' } : position === 'center' ? { top: '45%' } : { bottom: '10%' };

  return (
    <div className="relative rounded-xl overflow-hidden bg-black" style={{ aspectRatio: '16/9' }}>
      {videoUrl ? (
        <video ref={videoRef} src={videoUrl} className="absolute inset-0 w-full h-full object-cover" muted={isMuted} />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-b from-slate-900 to-black" />
      )}
      {/* Hidden audio element for background music playback */}
      {audioUrl && (
        <audio ref={musicRef} src={audioUrl} preload="auto" muted={musicMuted} loop />
      )}
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/80 to-transparent pointer-events-none" />
      <div className="absolute inset-x-0 px-8 text-center" style={posStyle} dir="rtl">
        {wordLines.map((line, li) => {
          if (currentTime < line.lineStart - 0.2 || currentTime > line.lineEnd + 0.5) return null;
          return (
            <div key={li} className="flex flex-wrap justify-center gap-1 mb-1">
              {line.words.map((w, wi) => {
                const isActive = currentTime >= w.start && currentTime <= w.end;
                const isPast = currentTime > w.end;
                return (
                  <span key={wi} style={getWordStyle(w, isActive, isPast, animationStyle)}>
                    {w.word}
                  </span>
                );
              })}
            </div>
          );
        })}
      </div>
      <div className="absolute bottom-3 left-3 right-3 flex items-center gap-3">
        <button onClick={togglePlay} className="w-9 h-9 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center hover:bg-white/30 transition-colors">
          {isPlaying ? (
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg>
          ) : (
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
          )}
        </button>
        <button onClick={resetPlayback} className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors">
          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h5M20 20v-5h-5M4 9a9 9 0 0115.6-6.2M20 15a9 9 0 01-15.6 6.2"/>
          </svg>
        </button>
        {/* Voice mute toggle (video audio) */}
        {videoUrl && (
          <button
            onClick={() => {
              setIsMuted(m => !m);
              if (videoRef.current) videoRef.current.muted = !videoRef.current.muted;
            }}
            className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
              isMuted ? 'bg-white/10 hover:bg-white/20' : 'bg-[#00D1C1]/30 hover:bg-[#00D1C1]/40'
            }`}
            title={isMuted ? 'הפעל קול' : 'השתק קול'}
          >
            {isMuted ? (
              <svg className="w-3.5 h-3.5 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5 text-[#00D1C1]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
              </svg>
            )}
          </button>
        )}
        {/* Music mute toggle (background music) */}
        {audioUrl && (
          <button
            onClick={() => {
              setMusicMuted(m => !m);
              if (musicRef.current) musicRef.current.muted = !musicRef.current.muted;
            }}
            className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
              musicMuted ? 'bg-white/10 hover:bg-white/20' : 'bg-purple-500/30 hover:bg-purple-500/40'
            }`}
            title={musicMuted ? 'הפעל מוזיקה' : 'השתק מוזיקה'}
          >
            {musicMuted ? (
              <svg className="w-3.5 h-3.5 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
              </svg>
            )}
          </button>
        )}
        <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-[#00D1C1] rounded-full transition-all duration-100"
            style={{ width: `${entries.length > 0 ? (currentTime / (entries[entries.length - 1]?.end || 1)) * 100 : 0}%` }}
          />
        </div>
        <span className="text-white/60 text-xs font-mono">{currentTime.toFixed(1)}s</span>
      </div>
    </div>
  );
}

// =============================================================================
// Toggle Switch Component
// =============================================================================
function ToggleSwitch({ enabled, onChange, label, desc }) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      className={`w-full text-right p-3 rounded-xl transition-all flex items-center justify-between gap-3 ${
        enabled
          ? 'bg-[#00D1C1]/15 border border-[#00D1C1]/50'
          : 'bg-slate-800/40 border border-slate-700/30 hover:border-slate-600'
      }`}
    >
      <div className="flex-1 min-w-0">
        <span className={`text-sm font-bold block ${enabled ? 'text-[#00D1C1]' : 'text-white'}`}>{label}</span>
        {desc && <p className="text-xs text-slate-500 mt-0.5">{desc}</p>}
      </div>
      <div className={`w-10 h-5 rounded-full transition-all flex-shrink-0 relative ${enabled ? 'bg-[#00D1C1]' : 'bg-slate-700'}`}>
        <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all ${enabled ? 'right-0.5' : 'left-0.5'}`} />
      </div>
    </button>
  );
}

// =============================================================================
// Section Header Component
// =============================================================================
function SectionHeader({ icon, title }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div className="w-7 h-7 rounded-lg bg-[#00D1C1]/15 border border-[#00D1C1]/30 flex items-center justify-center flex-shrink-0">
        {icon}
      </div>
      <h3 className="text-base font-bold text-white">{title}</h3>
    </div>
  );
}

// =============================================================================
// Main Effects Studio Tab Component
// =============================================================================
export default function EffectsStudioTab() {
  const ctx = useContext(VideoEditorContext);

  // --- Subtitle Style ---
  const [animStyle, setAnimStyle] = useState('karaoke');
  const [highlightColor, setHighlightColor] = useState('#FF6B35');
  const [subtitlePosition, setSubtitlePosition] = useState('bottom');
  const [subtitleSize, setSubtitleSize] = useState(28);

  // --- Camera Effects ---
  const [cameraShakeEnabled, setCameraShakeEnabled] = useState(false);
  const [cameraShakeIntensity, setCameraShakeIntensity] = useState(50);

  // --- Ambience Layers ---
  const [particlesEnabled, setParticlesEnabled] = useState(false);
  const [dynamicZoomEnabled, setDynamicZoomEnabled] = useState(false);

  // --- Sound Waves ---
  const [soundWavesEnabled, setSoundWavesEnabled] = useState(false);
  const [vizStyle, setVizStyle] = useState('bars');

  // --- Global Controls ---
  const [effectStrength, setEffectStrength] = useState(70);
  const [dominantColor, setDominantColor] = useState('#00D1C1');

  // --- Render ---
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderMessage, setRenderMessage] = useState('');
  const [renderResult, setRenderResult] = useState(null);
  const [renderError, setRenderError] = useState(null);
  const pollRef = useRef(null);

  const srtEntries = ctx.subtitleReview?.entries || [];

  // --- Showreel Mode: use demo data when no real data is loaded ---
  const isShowreel = srtEntries.length === 0;
  const effectiveEntries = isShowreel ? DEMO_ENTRIES : srtEntries;
  // Use the FINAL processed video (has subtitles + music baked in) if available,
  // fall back to the raw upload blob URL
  const effectiveVideoUrl = ctx.resultUrl || ctx.videoUrl || null;

  // Debug: log data availability when tab renders
  useEffect(() => {
    console.log('[EffectsStudio] Tab data:', {
      srtEntries: srtEntries.length,
      isShowreel,
      resultUrl: ctx.resultUrl || 'null',
      videoUrl: ctx.videoUrl ? 'blob' : 'null',
      effectiveVideoUrl: effectiveVideoUrl ? (effectiveVideoUrl.startsWith('blob:') ? 'blob' : effectiveVideoUrl) : 'null',
      audioUrl: ctx.audioUrl || 'null',
      pendingFileId: ctx.subtitleReview?.pendingFileId || 'null',
      uploadedVideoId: ctx.uploadedVideoId || 'null',
    });
  }, [srtEntries.length, ctx.audioUrl, ctx.uploadedVideoId, ctx.resultUrl]);

  // --- Trim ---
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);

  // --- Timing Corrections ---
  const [correctedEntries, setCorrectedEntries] = useState([]);

  // Sync corrected entries when real SRT changes (or load demo on mount)
  const srtKey = effectiveEntries.map(e => `${e.start}-${e.end}`).join(',');
  useEffect(() => {
    if (effectiveEntries.length > 0) {
      setCorrectedEntries(effectiveEntries.map(e => ({ ...e })));
    }
  }, [srtKey]);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Get video duration
  useEffect(() => {
    if (ctx.videoUrl) {
      const vid = document.createElement('video');
      vid.preload = 'metadata';
      vid.onloadedmetadata = () => {
        const dur = vid.duration || 0;
        if (dur > 0) {
          setVideoDuration(dur);
          setTrimEnd(prev => prev === 0 ? dur : prev);
        }
      };
      vid.src = ctx.videoUrl;
      return () => { vid.src = ''; };
    } else {
      // Use the last entry end time as duration (for showreel or srt-only mode)
      const lastEnd = effectiveEntries.length > 0
        ? effectiveEntries[effectiveEntries.length - 1]?.end || 0
        : 0;
      if (lastEnd > 0 && videoDuration === 0) {
        setVideoDuration(lastEnd);
        setTrimEnd(prev => prev === 0 ? lastEnd : prev);
      }
    }
  }, [ctx.videoUrl, effectiveEntries.length]);

  // Helpers
  const formatTime = (seconds) => {
    if (!seconds || seconds < 0) seconds = 0;
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}:${secs.padStart(4, '0')}`;
  };

  const shiftEntryTiming = (index, delta) => {
    setCorrectedEntries(prev => prev.map((entry, i) => {
      if (i !== index) return entry;
      return {
        ...entry,
        start: Math.max(0, +(entry.start + delta).toFixed(3)),
        end: Math.max(0.1, +(entry.end + delta).toFixed(3)),
      };
    }));
  };

  const resetTimingCorrections = () => {
    setCorrectedEntries(effectiveEntries.map(e => ({ ...e })));
  };

  // Handle export/render
  const handleExport = async () => {
    setIsRendering(true);
    setRenderError(null);
    setRenderResult(null);

    try {
      // Resolve the server-side video ID through multiple fallbacks
      let videoId = ctx.subtitleReview?.pendingFileId || ctx.uploadedVideoId || '';

      // Fallback: extract file_id from resultUrl (e.g. "${ctx.apiUrl}/outputs/a1b2c3d4_final.mp4")
      if (!videoId && ctx.resultUrl) {
        const match = ctx.resultUrl.match(/\/([a-f0-9]{8})(?:_final)?\.mp4/i);
        if (match) videoId = match[1];
      }

      // Last resort: use original filename
      if (!videoId) videoId = ctx.videoFile?.name || '';

      console.log('[EffectsStudio] Export video_id resolution:', {
        pendingFileId: ctx.subtitleReview?.pendingFileId,
        uploadedVideoId: ctx.uploadedVideoId,
        resultUrl: ctx.resultUrl,
        videoFileName: ctx.videoFile?.name,
        resolved: videoId,
      });

      if (!videoId) {
        setIsRendering(false);
        setRenderError('לא נמצא מזהה וידאו. יש לעבד סרטון בלשונית העריכה קודם.');
        return;
      }

      const payload = {
        video_id: videoId,
        animation_style: animStyle,
        highlight_color: highlightColor,
        subtitle_position: subtitlePosition,
        subtitle_size: subtitleSize,
        // Camera Effects
        camera_shake_enabled: cameraShakeEnabled,
        camera_shake_intensity: cameraShakeIntensity / 100,
        // Ambience Layers
        particles_enabled: particlesEnabled,
        dynamic_zoom_enabled: dynamicZoomEnabled,
        // Sound Waves
        sound_waves_enabled: soundWavesEnabled,
        visualizer_style: vizStyle,
        // Global
        effect_strength: effectStrength / 100,
        dominant_color: dominantColor,
        audio_url: ctx.audioUrl || '',
        // Trim
        trim_start: trimStart,
        trim_end: trimEnd,
        // Corrected subtitles
        corrected_entries: correctedEntries.map(e => ({
          text: e.text,
          start: e.start,
          end: e.end,
        })),
      };

      console.log('[EffectsStudio] Render request:', payload);

      const response = await fetch(`${ctx.apiUrl}/api/render/effects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (data.status === 'success') {
        const taskId = data.task_id;
        setRenderProgress(0);
        setRenderMessage('מתחיל רינדור...');

        // Clear any previous poll
        if (pollRef.current) clearInterval(pollRef.current);

        let networkErrors = 0;
        pollRef.current = setInterval(async () => {
          try {
            const res = await fetch(`${ctx.apiUrl}/api/render/effects/status/${taskId}`);
            const st = await res.json();
            networkErrors = 0; // Reset on success

            if (st.status === 'completed') {
              clearInterval(pollRef.current);
              pollRef.current = null;
              setIsRendering(false);
              setRenderProgress(100);
              setRenderMessage('');
              setRenderResult({ url: st.url, message: st.message });
            } else if (st.status === 'error') {
              clearInterval(pollRef.current);
              pollRef.current = null;
              setIsRendering(false);
              setRenderProgress(0);
              setRenderMessage('');
              setRenderError(st.message);
            } else if (st.status === 'processing') {
              setRenderProgress(st.progress || 0);
              setRenderMessage(st.message || 'מעבד...');
            }
          } catch {
            networkErrors++;
            // Only abort after 5 consecutive network errors
            if (networkErrors >= 5) {
              clearInterval(pollRef.current);
              pollRef.current = null;
              setIsRendering(false);
              setRenderProgress(0);
              setRenderMessage('');
              setRenderError('שגיאה בבדיקת סטטוס - בדוק שהשרת פעיל');
            }
          }
        }, 3000);
        // No timeout - poll indefinitely until completed/error
      } else {
        setIsRendering(false);
        setRenderError(data.message);
      }
    } catch (err) {
      setIsRendering(false);
      setRenderError(err.message);
    }
  };

  // =============================================================================
  // Main Layout (always rendered - showreel mode fills in demo data)
  // =============================================================================
  return (
    <div className="h-full flex flex-col bg-[#0c0d15] text-white overflow-hidden relative" dir="rtl">
      {/* Grid background */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, #1a1b2c 1px, transparent 0)', backgroundSize: '24px 24px' }} />

      {/* Header */}
      <header className="px-8 py-5 border-b border-slate-800/30 relative z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">אפקטים ותוספות</h1>
            <span className="text-xs text-slate-500 bg-slate-800/50 px-2 py-0.5 rounded-md">Remotion</span>
            {isShowreel && (
              <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded-md animate-pulse">
                מצב דוגמה
              </span>
            )}
          </div>
          <button onClick={() => ctx.setActiveTab?.('editor')} className="text-sm text-slate-500 hover:text-white transition-colors">
            חזרה לעורך
          </button>
        </div>
      </header>

      {/* Showreel banner */}
      {isShowreel && (
        <div className="px-8 py-2 bg-amber-500/10 border-b border-amber-500/20 relative z-10">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <p className="text-xs text-amber-400">
              מצב דוגמה - העלה סרטון ועבד כתוביות כדי לעבוד עם הנתונים האמיתיים שלך
            </p>
            <button
              onClick={() => ctx.setActiveTab?.('editor')}
              className="text-xs px-3 py-1 rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30 transition-colors"
            >
              העלה סרטון
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto relative z-10">
        <div className="max-w-7xl mx-auto px-8 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

            {/* ============================================================= */}
            {/* LEFT: Preview Area (8 cols) */}
            {/* ============================================================= */}
            <div className="lg:col-span-8 space-y-5">

              {/* ---- Video Trimmer ---- */}
              {videoDuration > 0 && (
                <div className="rounded-2xl bg-slate-900/60 border border-emerald-500/30 shadow-lg shadow-emerald-500/10 p-5">
                  <SectionHeader
                    title="חיתוך וידאו"
                    icon={<svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25v13.5m-7.5-13.5v13.5M4.5 19.5h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15A2.25 2.25 0 002.25 6.75v10.5A2.25 2.25 0 004.5 19.5z" /></svg>}
                  />
                  {/* Visual range bar */}
                  <div className="relative h-10 bg-slate-800 rounded-lg overflow-hidden mb-3 cursor-pointer">
                    {/* Full track */}
                    <div className="absolute inset-0 bg-slate-800" />
                    {/* Selected range */}
                    <div
                      className="absolute h-full bg-emerald-500/20 border-x-2 border-emerald-400"
                      style={{
                        left: `${(trimStart / Math.max(videoDuration, 0.1)) * 100}%`,
                        width: `${((trimEnd - trimStart) / Math.max(videoDuration, 0.1)) * 100}%`,
                      }}
                    />
                    {/* Time markers */}
                    <div className="absolute inset-0 flex items-center justify-between px-3">
                      <span className="text-[10px] text-emerald-300 font-mono bg-slate-900/80 px-1 rounded">{formatTime(trimStart)}</span>
                      <span className="text-[10px] text-slate-400 font-mono bg-slate-900/80 px-1 rounded">{formatTime(trimEnd - trimStart)}</span>
                      <span className="text-[10px] text-emerald-300 font-mono bg-slate-900/80 px-1 rounded">{formatTime(trimEnd)}</span>
                    </div>
                  </div>
                  {/* Dual sliders */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">התחלה:</label>
                      <input
                        type="range"
                        min={0}
                        max={videoDuration}
                        step={0.1}
                        value={trimStart}
                        onChange={e => setTrimStart(Math.min(Number(e.target.value), trimEnd - 0.5))}
                        className="w-full accent-emerald-400"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">סיום:</label>
                      <input
                        type="range"
                        min={0}
                        max={videoDuration}
                        step={0.1}
                        value={trimEnd}
                        onChange={e => setTrimEnd(Math.max(Number(e.target.value), trimStart + 0.5))}
                        className="w-full accent-emerald-400"
                      />
                    </div>
                  </div>
                  <p className="text-center text-[10px] text-slate-600 mt-2">
                    טווח: {formatTime(trimStart)} – {formatTime(trimEnd)} ({formatTime(trimEnd - trimStart)} מתוך {formatTime(videoDuration)})
                  </p>
                </div>
              )}

              {/* Subtitle Preview - always shows (demo or real data) */}
              <div className="rounded-2xl bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-base font-bold text-white">תצוגה מקדימה</h3>
                  {isShowreel && (
                    <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">דוגמה</span>
                  )}
                </div>
                <PopupSubtitlesPreview
                  key={isShowreel ? 'demo' : 'real'}
                  entries={correctedEntries.length > 0 ? correctedEntries : effectiveEntries}
                  animationStyle={animStyle}
                  highlightColor={highlightColor}
                  fontSize={subtitleSize}
                  position={subtitlePosition}
                  videoUrl={effectiveVideoUrl}
                  audioUrl={ctx.audioUrl}
                />
              </div>

              {/* ---- Manual Timing Correction ---- */}
              {correctedEntries.length > 0 && (
                <div className="rounded-2xl bg-slate-900/60 border border-cyan-500/20 shadow-lg shadow-cyan-500/5 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <SectionHeader
                      title="תיקון תזמון ידני"
                      icon={<svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
                    />
                    <button
                      onClick={resetTimingCorrections}
                      className="text-[10px] text-slate-500 hover:text-cyan-400 transition-colors px-2 py-1 rounded-lg bg-slate-800/40 hover:bg-slate-800/60 border border-slate-700/30"
                    >
                      איפוס
                    </button>
                  </div>
                  <div className="max-h-64 overflow-y-auto space-y-1 pr-1" style={{ scrollbarWidth: 'thin', scrollbarColor: '#334155 transparent' }}>
                    {correctedEntries.map((entry, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/40 hover:bg-slate-800/60 transition-colors group"
                      >
                        <span className="text-[10px] text-slate-600 font-mono w-5 flex-shrink-0 text-center">{idx + 1}</span>
                        <span className="text-xs text-white flex-1 truncate" dir="rtl" title={entry.text}>{entry.text}</span>
                        <span className="text-[10px] text-slate-500 font-mono flex-shrink-0 hidden group-hover:inline">
                          {formatTime(entry.start)}→{formatTime(entry.end)}
                        </span>
                        <button
                          onClick={() => shiftEntryTiming(idx, -0.1)}
                          className="px-1.5 py-0.5 text-[10px] rounded bg-red-500/10 text-red-400 hover:bg-red-500/25 border border-red-500/20 font-mono flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
                          title="הקדם 0.1 שניות"
                        >
                          -0.1s
                        </button>
                        <button
                          onClick={() => shiftEntryTiming(idx, 0.1)}
                          className="px-1.5 py-0.5 text-[10px] rounded bg-green-500/10 text-green-400 hover:bg-green-500/25 border border-green-500/20 font-mono flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
                          title="אחר 0.1 שניות"
                        >
                          +0.1s
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-600 text-center mt-2">{correctedEntries.length} שורות כתוביות</p>
                </div>
              )}

              {/* Sound Waves Preview */}
              {soundWavesEnabled && (
                <div className="rounded-2xl bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-base font-bold text-white">גלי סאונד - תצוגה חיה</h3>
                    <div className="flex gap-2">
                      {VISUALIZER_STYLES.map(vs => (
                        <button
                          key={vs.id}
                          onClick={() => setVizStyle(vs.id)}
                          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                            vizStyle === vs.id
                              ? 'bg-[#00D1C1]/20 text-[#00D1C1] border border-[#00D1C1]/50'
                              : 'bg-slate-800/60 text-slate-400 border border-slate-700/50 hover:border-slate-500'
                          }`}
                        >
                          {vs.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <AudioVisualizer
                    audioUrl={ctx.audioUrl}
                    color={dominantColor}
                    style={vizStyle}
                    height={100}
                  />
                </div>
              )}

              {/* Active Effects Summary */}
              <div className="rounded-2xl bg-slate-900/40 border border-slate-700/30 p-4">
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs text-slate-500">אפקטים פעילים:</span>
                  <EffectBadge label="כתוביות" active />
                  {cameraShakeEnabled && <EffectBadge label="רעידת מצלמה" active />}
                  {particlesEnabled && <EffectBadge label="חלקיקים" active />}
                  {dynamicZoomEnabled && <EffectBadge label="זום דינמי" active />}
                  {soundWavesEnabled && <EffectBadge label="גלי סאונד" active />}
                  {!cameraShakeEnabled && !particlesEnabled && !dynamicZoomEnabled && !soundWavesEnabled && (
                    <span className="text-xs text-slate-600">כתוביות בלבד</span>
                  )}
                </div>
              </div>
            </div>

            {/* ============================================================= */}
            {/* RIGHT: Controls Panel (4 cols) */}
            {/* ============================================================= */}
            <div className="lg:col-span-4 space-y-4">

              {/* ---- Section 1: סגנון כתוביות (Subtitle Style) ---- */}
              <div className="rounded-2xl bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10 p-5">
                <SectionHeader
                  title="סגנון כתוביות"
                  icon={<svg className="w-3.5 h-3.5 text-[#00D1C1]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.068.157 2.148.279 3.238.364.466.037.893.281 1.153.671L12 21l2.652-3.978c.26-.39.687-.634 1.153-.671 1.09-.086 2.17-.207 3.238-.364 1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>}
                />
                <div className="space-y-2 mb-4">
                  {SUBTITLE_STYLES.map(s => (
                    <button
                      key={s.id}
                      onClick={() => setAnimStyle(s.id)}
                      className={`w-full text-right p-3 rounded-xl transition-all ${
                        animStyle === s.id
                          ? 'bg-[#00D1C1]/15 border border-[#00D1C1]/50'
                          : 'bg-slate-800/40 border border-slate-700/30 hover:border-slate-600'
                      }`}
                    >
                      <span className={`text-sm font-bold ${animStyle === s.id ? 'text-[#00D1C1]' : 'text-white'}`}>
                        {s.label}
                      </span>
                      <p className="text-xs text-slate-500 mt-0.5">{s.desc}</p>
                    </button>
                  ))}
                </div>

                {/* Position & Size */}
                <div className="space-y-3 pt-3 border-t border-slate-700/30">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">מיקום כתוביות:</label>
                    <div className="flex gap-2">
                      {POSITION_OPTIONS.map(p => (
                        <button
                          key={p.id}
                          onClick={() => setSubtitlePosition(p.id)}
                          className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                            subtitlePosition === p.id
                              ? 'bg-[#00D1C1]/20 text-[#00D1C1] border border-[#00D1C1]/50'
                              : 'bg-slate-800/60 text-slate-400 border border-slate-700/50'
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">גודל כתוביות: {subtitleSize}px</label>
                    <input type="range" min={16} max={72} value={subtitleSize} onChange={e => setSubtitleSize(Number(e.target.value))} className="w-full accent-[#00D1C1]" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">צבע הדגשת מילים:</label>
                    <div className="flex items-center gap-2">
                      <input type="color" value={highlightColor} onChange={e => setHighlightColor(e.target.value)} className="w-8 h-8 rounded border-0 cursor-pointer bg-transparent" />
                      <span className="text-xs text-slate-500 font-mono">{highlightColor}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* ---- Section 2: אפקטי מצלמה (Camera Effects) ---- */}
              <div className="rounded-2xl bg-slate-900/60 border border-purple-500/20 shadow-lg shadow-purple-500/5 p-5">
                <SectionHeader
                  title="אפקטי מצלמה"
                  icon={<svg className="w-3.5 h-3.5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" /><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" /></svg>}
                />
                <div className="space-y-2">
                  <ToggleSwitch
                    enabled={cameraShakeEnabled}
                    onChange={setCameraShakeEnabled}
                    label="רעידת מצלמה"
                    desc="רעידה קצבית מבוססת Spring"
                  />
                  {cameraShakeEnabled && (
                    <div className="pr-3 pt-2">
                      <label className="text-xs text-slate-400 block mb-1.5">עוצמת רעידה: {cameraShakeIntensity}%</label>
                      <input type="range" min={10} max={100} value={cameraShakeIntensity} onChange={e => setCameraShakeIntensity(Number(e.target.value))} className="w-full accent-purple-400" />
                    </div>
                  )}
                </div>
              </div>

              {/* ---- Section 3: שכבות אווירה (Ambience Layers) ---- */}
              <div className="rounded-2xl bg-slate-900/60 border border-amber-500/20 shadow-lg shadow-amber-500/5 p-5">
                <SectionHeader
                  title="שכבות אווירה"
                  icon={<svg className="w-3.5 h-3.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" /></svg>}
                />
                <div className="space-y-2">
                  <ToggleSwitch
                    enabled={particlesEnabled}
                    onChange={setParticlesEnabled}
                    label="חלקיקים צפים"
                    desc="חלקיקים זוהרים ברקע"
                  />
                  <ToggleSwitch
                    enabled={dynamicZoomEnabled}
                    onChange={setDynamicZoomEnabled}
                    label="זום דינמי"
                    desc="אפקט Ken Burns - התקרבות איטית"
                  />
                </div>
              </div>

              {/* ---- Section 4: גלי סאונד (Sound Waves) ---- */}
              <div className="rounded-2xl bg-slate-900/60 border border-blue-500/20 shadow-lg shadow-blue-500/5 p-5">
                <SectionHeader
                  title="גלי סאונד"
                  icon={<svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" /></svg>}
                />
                <div className="space-y-2">
                  <ToggleSwitch
                    enabled={soundWavesEnabled}
                    onChange={setSoundWavesEnabled}
                    label="ויזואלייזר"
                    desc="גלי תדר מונפשים בתחתית הסרטון"
                  />
                  {soundWavesEnabled && (
                    <div className="flex gap-2 pr-3 pt-2">
                      {VISUALIZER_STYLES.map(vs => (
                        <button
                          key={vs.id}
                          onClick={() => setVizStyle(vs.id)}
                          className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                            vizStyle === vs.id
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                              : 'bg-slate-800/60 text-slate-400 border border-slate-700/50'
                          }`}
                        >
                          {vs.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* ---- Global Controls ---- */}
              <div className="rounded-2xl bg-slate-900/60 border border-slate-600/30 p-5 space-y-4">
                <SectionHeader
                  title="בקרה כללית"
                  icon={<svg className="w-3.5 h-3.5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" /></svg>}
                />

                {/* Effect Strength */}
                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">עוצמת אפקטים: {effectStrength}%</label>
                  <input type="range" min={10} max={100} value={effectStrength} onChange={e => setEffectStrength(Number(e.target.value))} className="w-full accent-[#00D1C1]" />
                  <div className="flex justify-between text-[10px] text-slate-600 mt-1">
                    <span>עדין</span>
                    <span>חזק</span>
                  </div>
                </div>

                {/* Dominant Color */}
                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">צבע דומיננטי:</label>
                  <div className="flex items-center gap-3">
                    <input type="color" value={dominantColor} onChange={e => setDominantColor(e.target.value)} className="w-8 h-8 rounded border-0 cursor-pointer bg-transparent" />
                    <span className="text-xs text-slate-500 font-mono">{dominantColor}</span>
                    <div className="flex gap-1.5 mr-auto">
                      {['#00D1C1', '#FF6B35', '#8B5CF6', '#3B82F6', '#EF4444', '#FFD700'].map(c => (
                        <button
                          key={c}
                          onClick={() => setDominantColor(c)}
                          className={`w-5 h-5 rounded-full border-2 transition-all ${dominantColor === c ? 'border-white scale-110' : 'border-slate-700 hover:border-slate-500'}`}
                          style={{ backgroundColor: c }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* ---- Export ---- */}
              <div className="rounded-2xl bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10 p-5">
                <h3 className="text-base font-bold text-white mb-3">ייצוא</h3>

                {renderResult ? (
                  <div className="text-center py-3">
                    <div className="w-12 h-12 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center mx-auto mb-3">
                      <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-green-400 font-bold text-sm mb-2">הסרטון מוכן!</p>
                    <button
                      onClick={() => {
                        const a = document.createElement('a');
                        a.href = `${ctx.apiUrl}${renderResult.url}`;
                        a.target = '_blank';
                        a.rel = 'noopener noreferrer';
                        a.click();
                      }}
                      className="inline-block px-4 py-2 bg-[#00D1C1] text-black font-bold rounded-lg hover:opacity-90 transition-all text-sm cursor-pointer"
                    >
                      הורד סרטון
                    </button>
                    <button onClick={() => setRenderResult(null)} className="block mx-auto mt-2 text-xs text-slate-500 hover:text-white">
                      ייצא שוב
                    </button>
                  </div>
                ) : (
                  <>
                    {renderError && (
                      <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs">
                        {renderError}
                      </div>
                    )}
                    <button
                      onClick={handleExport}
                      disabled={isRendering || isShowreel}
                      className="w-full py-3.5 bg-gradient-to-l from-[#00D1C1] to-[#0891b2] text-white font-bold rounded-xl hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                    >
                      {isRendering ? (
                        <span className="flex items-center justify-center gap-2">
                          <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          מרנדר... {renderProgress > 0 ? `${renderProgress}%` : ''}
                        </span>
                      ) : (
                        'ייצא סרטון עם אפקטים'
                      )}
                    </button>
                    {isRendering && (
                      <div className="mt-3">
                        <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-l from-[#00D1C1] to-[#0891b2] rounded-full transition-all duration-500"
                            style={{ width: `${renderProgress}%` }}
                          />
                        </div>
                        {renderMessage && (
                          <p className="text-slate-400 text-xs text-center mt-1.5">{renderMessage}</p>
                        )}
                      </div>
                    )}
                    {isShowreel && (
                      <p className="text-amber-500 text-xs text-center mt-2">העלה סרטון ועבד כתוביות כדי לייצא</p>
                    )}
                  </>
                )}
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Effect Badge (Active effects summary)
// =============================================================================
function EffectBadge({ label, active }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-md ${active ? 'bg-[#00D1C1]/15 text-[#00D1C1] border border-[#00D1C1]/30' : 'bg-slate-800 text-slate-500'}`}>
      {label}
    </span>
  );
}
