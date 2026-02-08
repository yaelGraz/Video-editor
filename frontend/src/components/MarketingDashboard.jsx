import { useState, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

// =============================================================================
// Subtitle Color Options
// =============================================================================
const SUBTITLE_COLORS = [
  { name: 'לבן', value: '#FFFFFF' },
  { name: 'צהוב', value: '#FFFF00' },
  { name: 'ציאן', value: '#00FFFF' },
  { name: 'ירוק', value: '#00FF00' },
  { name: 'ורוד', value: '#FF69B4' },
  { name: 'כתום', value: '#FFA500' },
];

// =============================================================================
// Placeholder Examples
// =============================================================================
const PLACEHOLDER = {
  title: "הסודות הנסתרים של ההצלחה",
  post: "גלו איך לשדרג את התוכן שלכם!",
  tags: ["#תגיות_רלוונטיות", "#לקהל_שלכם", "#טיפים_לקידום"],
};

// =============================================================================
// Command Center Dashboard
// =============================================================================
function MarketingDashboard() {
  const ctx = useContext(VideoEditorContext);

  // Local states
  const [textError, setTextError] = useState(null);
  const [aiImageError, setAiImageError] = useState(null);
  const [shortsError, setShortsError] = useState(null);
  const [customPrompt, setCustomPrompt] = useState('');
  const [withSubtitles, setWithSubtitles] = useState(false);
  const [subtitleColor, setSubtitleColor] = useState('#FFFFFF');
  const [copiedField, setCopiedField] = useState(null);
  const [analysisStarted, setAnalysisStarted] = useState(false);

  // Copy handler
  const handleCopy = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Start Analysis - enables all modules
  const handleStartAnalysis = async () => {
    setTextError(null);
    setAnalysisStarted(true);
    const result = await ctx.generateMarketingText();
    if (!result.success) {
      setTextError(result.error);
    }
  };

  // Action Handlers
  const handleGenerateText = async () => {
    setTextError(null);
    const result = await ctx.generateMarketingText();
    if (!result.success) setTextError(result.error);
  };

  const handleGenerateAiImage = async () => {
    setAiImageError(null);
    const result = await ctx.generateMarketingAiImage(customPrompt || null);
    if (!result.success) setAiImageError(result.error);
  };

  const handleGenerateShorts = async () => {
    setShortsError(null);
    const color = withSubtitles ? subtitleColor : null;
    const result = await ctx.generateMarketingShorts(withSubtitles, color);
    if (!result.success) setShortsError(result.error);
  };

  const hasContent = !!ctx.marketingKit;
  const isEnabled = analysisStarted || hasContent;

  // =============================================================================
  // No Video State
  // =============================================================================
  if (!ctx.videoFile) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-[#0c0d15] text-white relative overflow-hidden">
        {/* Subtle Grid Background */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, #1a1b2c 1px, transparent 0)`,
            backgroundSize: '24px 24px'
          }}
        />

        <div className="text-center space-y-6 max-w-lg px-8 relative z-10">
          <h1 className="text-3xl font-bold text-white">
            תוכן להפצה ושיווק
          </h1>
          <p className="text-slate-400 text-base leading-relaxed">
            העלה סרטון וקבל כותרות, פוסטים, תמונות וסרטונים קצרים מוכנים להפצה
          </p>
          <button
            onClick={() => ctx.setActiveTab?.('editor')}
            className="px-10 py-4 bg-[#00D1C1] text-white text-base font-semibold rounded-xl hover:bg-[#00B8A9] transition-all duration-300"
          >
            העלה סרטון להתחלה
          </button>
        </div>
      </div>
    );
  }

  // =============================================================================
  // Main Command Center Layout
  // =============================================================================
  return (
    <div className="h-full flex flex-col bg-[#0c0d15] text-white overflow-hidden relative" dir="rtl">

      {/* Subtle Grid Background */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, #1a1b2c 1px, transparent 0)`,
          backgroundSize: '24px 24px'
        }}
      />

      {/* Header */}
      <header className="px-8 py-6 border-b border-slate-800/30 relative z-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">
            תוכן להפצה ושיווק
          </h1>
          <button
            onClick={() => ctx.setActiveTab?.('editor')}
            className="text-sm text-slate-500 hover:text-white transition-colors"
          >
            חזרה לעורך
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto relative z-10">
        <div className="max-w-6xl mx-auto px-8 py-8">

          {/* Step 1 Guidance - Before Analysis */}
          {!isEnabled && (
            <div className="text-center mb-12">
              <p className="text-slate-400 text-base mb-6">
                שלב 1: התחל לנתח את הסרטון שלך כדי להפעיל את כלי ההפקה.
              </p>

              {textError && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm max-w-md mx-auto">
                  {textError}
                </div>
              )}

              <button
                onClick={handleStartAnalysis}
                disabled={ctx.isGeneratingText}
                className="px-14 py-5 bg-[#00D1C1] text-white text-lg font-bold rounded-2xl hover:bg-[#00B8A9] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {ctx.isGeneratingText ? (
                  <span className="flex items-center gap-3">
                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    מנתח...
                  </span>
                ) : (
                  'התחל ניתוח'
                )}
              </button>
            </div>
          )}

          {/* Modules Grid - Command Center Style */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* =============================================================== */}
            {/* MODULE 1: Posts and Titles */}
            {/* =============================================================== */}
            <div
              className={`rounded-2xl p-6 transition-all duration-300 ${
                isEnabled
                  ? 'bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10'
                  : 'bg-slate-900/40 border border-slate-700/50'
              }`}
            >
              <h3 className="text-lg font-bold text-white mb-6">פוסטים וכותרות</h3>

              <div className="space-y-5 mb-6">
                {/* Title */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500">כותרת מושכת:</span>
                    {hasContent && (
                      <button
                        onClick={() => handleCopy(ctx.marketingKit.title, 'title')}
                        className={`text-[10px] transition-colors ${copiedField === 'title' ? 'text-[#00D1C1]' : 'text-slate-600 hover:text-white'}`}
                      >
                        {copiedField === 'title' ? 'הועתק!' : 'העתק'}
                      </button>
                    )}
                  </div>
                  <p className={`text-base leading-relaxed ${hasContent ? 'text-white' : 'text-slate-500'}`}>
                    {hasContent ? ctx.marketingKit.title : `"${PLACEHOLDER.title}"`}
                  </p>
                </div>

                {/* Post */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500">פוסט לרשתות:</span>
                    {hasContent && (
                      <button
                        onClick={() => handleCopy(ctx.marketingKit.description, 'desc')}
                        className={`text-[10px] transition-colors ${copiedField === 'desc' ? 'text-[#00D1C1]' : 'text-slate-600 hover:text-white'}`}
                      >
                        {copiedField === 'desc' ? 'הועתק!' : 'העתק'}
                      </button>
                    )}
                  </div>
                  <p className={`text-sm leading-relaxed ${hasContent ? 'text-slate-300' : 'text-slate-500'}`}>
                    {hasContent ? ctx.marketingKit.description : `"${PLACEHOLDER.post}"`}
                  </p>
                </div>

                {/* Tags */}
                <div>
                  <span className="text-xs text-slate-500 block mb-2">תגיות:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {(hasContent ? ctx.marketingKit.tags?.split(' ').slice(0, 5) : PLACEHOLDER.tags).map((tag, i) => (
                      tag && (
                        <span
                          key={i}
                          onClick={() => hasContent && handleCopy(tag, `tag-${i}`)}
                          className={`text-xs px-2.5 py-1 rounded-md ${
                            hasContent
                              ? 'bg-slate-800 text-slate-300 cursor-pointer hover:bg-slate-700'
                              : 'bg-slate-800/30 text-slate-600'
                          }`}
                        >
                          {tag}
                        </span>
                      )
                    ))}
                  </div>
                </div>
              </div>

              {/* Error */}
              {textError && isEnabled && (
                <div className="mb-4 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs">
                  {textError}
                </div>
              )}

              {/* Action Button */}
              <button
                onClick={handleGenerateText}
                disabled={!isEnabled || ctx.isGeneratingText}
                className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-300 ${
                  isEnabled
                    ? 'bg-[#00D1C1] text-white hover:bg-[#00B8A9]'
                    : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                }`}
              >
                {ctx.isGeneratingText ? 'מייצר...' : hasContent ? 'צור מחדש' : 'צור תוכן'}
              </button>
            </div>

            {/* =============================================================== */}
            {/* MODULE 2: Images (Thumbnail + AI) */}
            {/* =============================================================== */}
            <div className="space-y-6">

              {/* Thumbnail Card */}
              <div
                className={`rounded-2xl p-5 transition-all duration-300 ${
                  isEnabled
                    ? 'bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10'
                    : 'bg-slate-900/40 border border-slate-700/50'
                }`}
              >
                <h3 className="text-base font-bold text-white mb-4">תמונה ממוזערת</h3>

                {ctx.thumbnailUrl ? (
                  <div className="relative group">
                    <div className="rounded-xl overflow-hidden border border-slate-700/50">
                      <img src={ctx.thumbnailUrl} alt="Thumbnail" className="w-full aspect-video object-cover" />
                    </div>
                    <a
                      href={ctx.thumbnailUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-xl"
                    >
                      <span className="text-white text-sm">פתח בטאב חדש</span>
                    </a>
                  </div>
                ) : (
                  <div className="aspect-video bg-slate-800/30 rounded-xl flex items-center justify-center border border-slate-700/30">
                    <span className="text-slate-600 text-sm">תמונה תיווצר אוטומטית...</span>
                  </div>
                )}
              </div>

              {/* AI Image Card */}
              <div
                className={`rounded-2xl p-5 transition-all duration-300 ${
                  isEnabled
                    ? 'bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10'
                    : 'bg-slate-900/40 border border-slate-700/50'
                }`}
              >
                <h3 className="text-base font-bold text-white mb-4">תמונת AI</h3>

                {/* Image Area */}
                <div className="mb-4">
                  {ctx.isGeneratingAiImage ? (
                    <div className="aspect-video bg-slate-800/40 rounded-xl flex items-center justify-center border border-slate-700/30">
                      <span className="w-7 h-7 border-2 border-slate-600 border-t-[#00D1C1] rounded-full animate-spin" />
                    </div>
                  ) : ctx.aiThumbnailUrl ? (
                    <div className="relative group">
                      <div className="rounded-xl overflow-hidden border border-slate-700/50">
                        <img src={ctx.aiThumbnailUrl} alt="AI Image" className="w-full aspect-video object-cover" />
                      </div>
                      <a
                        href={ctx.aiThumbnailUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-xl"
                      >
                        <span className="text-white text-sm">פתח בטאב חדש</span>
                      </a>
                    </div>
                  ) : (
                    <div className="aspect-video bg-slate-800/30 rounded-xl flex items-center justify-center border border-slate-700/30">
                      {/* Dim Image Icon Placeholder */}
                      <svg
                        className="w-12 h-12 text-slate-700"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                  )}
                </div>

                {/* Custom Prompt Textarea */}
                <div className="mb-4">
                  <textarea
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    placeholder="הנחיות ליצירת תמונה (אופציונלי)..."
                    rows={2}
                    disabled={!isEnabled}
                    className="w-full bg-slate-800/40 border border-slate-700/40 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#00D1C1]/50 transition-colors resize-none disabled:opacity-40"
                  />
                </div>

                {/* Error */}
                {aiImageError && (
                  <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs">
                    {aiImageError}
                  </div>
                )}

                {/* Action Button */}
                <button
                  onClick={handleGenerateAiImage}
                  disabled={!isEnabled || ctx.isGeneratingAiImage}
                  className={`w-full py-3 rounded-xl text-sm font-bold transition-all duration-300 ${
                    isEnabled
                      ? 'bg-[#00D1C1] text-white hover:bg-[#00B8A9]'
                      : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                  }`}
                >
                  {ctx.isGeneratingAiImage ? 'יוצר תמונה...' : 'צור תמונה'}
                </button>
              </div>
            </div>

            {/* =============================================================== */}
            {/* MODULE 3: Shorts */}
            {/* =============================================================== */}
            <div
              className={`rounded-2xl p-6 transition-all duration-300 ${
                isEnabled
                  ? 'bg-slate-900/60 border border-[#00D1C1]/30 shadow-lg shadow-[#00D1C1]/10'
                  : 'bg-slate-900/40 border border-slate-700/50'
              }`}
            >
              <h3 className="text-lg font-bold text-white mb-6">סרטונים קצרים</h3>

              {/* Shorts Grid - 3 vertical rectangles */}
              <div className="grid grid-cols-3 gap-2 mb-5">
                {ctx.isGeneratingShorts ? (
                  // Loading State
                  [1, 2, 3].map(i => (
                    <div key={i} className="aspect-[9/16] bg-slate-800/40 rounded-lg flex items-center justify-center border border-slate-700/30">
                      <span className="w-5 h-5 border-2 border-slate-600 border-t-[#00D1C1] rounded-full animate-spin" />
                    </div>
                  ))
                ) : ctx.shortsUrls?.length > 0 ? (
                  // Ready Shorts
                  ctx.shortsUrls.slice(0, 3).map((url, index) => (
                    <a
                      key={index}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group relative rounded-lg overflow-hidden border border-slate-700/50 hover:border-[#00D1C1]/50 transition-all"
                    >
                      <div className="aspect-[9/16] bg-black">
                        <video src={url} className="w-full h-full object-cover" preload="metadata" />
                      </div>
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span className="text-white text-xs">פתח</span>
                      </div>
                      <span className="absolute top-1.5 right-1.5 text-white text-[9px] font-bold bg-black/60 px-1.5 py-0.5 rounded">
                        {index + 1}
                      </span>
                    </a>
                  ))
                ) : (
                  // Empty Placeholders with Play Icon
                  [1, 2, 3].map(i => (
                    <div key={i} className="aspect-[9/16] bg-slate-800/30 rounded-lg flex items-center justify-center border border-slate-700/30">
                      {/* Dim Play Icon */}
                      <svg
                        className="w-6 h-6 text-slate-700"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                  ))
                )}
              </div>

              {/* Subtitles Toggle */}
              <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-xl mb-4">
                <span className="text-sm text-slate-400">הוסף כתוביות</span>
                <button
                  onClick={() => setWithSubtitles(!withSubtitles)}
                  disabled={!isEnabled}
                  className={`relative w-11 h-6 rounded-full transition-all duration-300 disabled:opacity-40 ${
                    withSubtitles ? 'bg-[#00D1C1]' : 'bg-slate-700'
                  }`}
                >
                  <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-300 shadow ${
                    withSubtitles ? 'right-1' : 'left-1'
                  }`} />
                </button>
              </div>

              {/* Color Picker (when subtitles enabled) */}
              {withSubtitles && isEnabled && (
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xs text-slate-500">צבע:</span>
                  <div className="flex gap-1.5">
                    {SUBTITLE_COLORS.map((color) => (
                      <button
                        key={color.value}
                        onClick={() => setSubtitleColor(color.value)}
                        className={`w-6 h-6 rounded border-2 transition-all ${
                          subtitleColor === color.value
                            ? 'border-[#00D1C1] scale-110'
                            : 'border-slate-600 hover:border-slate-400'
                        }`}
                        style={{ backgroundColor: color.value }}
                        title={color.name}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Error */}
              {shortsError && (
                <div className="mb-4 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs">
                  {shortsError}
                </div>
              )}

              {/* Action Button */}
              <button
                onClick={handleGenerateShorts}
                disabled={!isEnabled || ctx.isGeneratingShorts}
                className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-300 ${
                  isEnabled
                    ? 'bg-[#00D1C1] text-white hover:bg-[#00B8A9]'
                    : 'bg-slate-800 text-slate-600 cursor-not-allowed'
                }`}
              >
                {ctx.isGeneratingShorts ? 'חותך סרטונים...' : ctx.shortsUrls?.length > 0 ? 'ייצא מחדש' : 'ייצא סרטונים'}
              </button>
            </div>

          </div>

          {/* Distribution Channels */}
          <div className="mt-10 pt-8 border-t border-slate-800/30">
            <p className="text-center text-slate-500 text-sm mb-5">ערוצי הפצה</p>
            <div className="flex justify-center gap-8" dir="rtl">
              {/* YouTube */}
              <a
                href="https://youtube.com"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex flex-col items-center gap-2"
              >
                <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center group-hover:bg-red-500/20 group-hover:border-red-500/50 group-hover:scale-105 transition-all">
                  <svg className="w-6 h-6 text-red-500 group-hover:text-red-400 transition-colors" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                  </svg>
                </div>
                <span className="text-xs text-red-400/80 group-hover:text-red-400 transition-colors">YouTube</span>
              </a>

              {/* Facebook */}
              <a
                href="https://facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex flex-col items-center gap-2"
              >
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center group-hover:bg-blue-500/20 group-hover:border-blue-500/50 group-hover:scale-105 transition-all">
                  <svg className="w-6 h-6 text-blue-500 group-hover:text-blue-400 transition-colors" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </div>
                <span className="text-xs text-blue-400/80 group-hover:text-blue-400 transition-colors">Facebook</span>
              </a>

              {/* WhatsApp */}
              <a
                href="https://whatsapp.com"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex flex-col items-center gap-2"
              >
                <div className="w-12 h-12 rounded-xl bg-green-500/10 border border-green-500/30 flex items-center justify-center group-hover:bg-green-500/20 group-hover:border-green-500/50 group-hover:scale-105 transition-all">
                  <svg className="w-6 h-6 text-green-500 group-hover:text-green-400 transition-colors" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                  </svg>
                </div>
                <span className="text-xs text-green-400/80 group-hover:text-green-400 transition-colors">WhatsApp</span>
              </a>
            </div>
          </div>

          {/* Status Bar - After Analysis */}
          {isEnabled && (
            <div className="mt-6 text-center">
              <p className="text-slate-600 text-sm">
                כל המודולים זמינים • בחר פעולה להפקת תוכן
              </p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

export default MarketingDashboard;
