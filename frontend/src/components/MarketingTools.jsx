/**
 * MarketingTools - Distribution & Marketing features panel
 * Toggles for viral titles, marketing description, social tags, thumbnail generation
 * Entry point to full-screen Marketing Dashboard
 */
import { useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function MarketingTools({ onOpenDashboard }) {
  const ctx = useContext(VideoEditorContext);

  const toggleOption = (key) => {
    ctx.setProcessingOptions(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const options = ctx.processingOptions || {};

  const marketingFeatures = [
    {
      key: 'doMarketing',
      icon: '📊',
      label: 'כותרת ויראלית',
      description: 'יצירת כותרת שמושכת צפיות',
      active: options.doMarketing ?? true
    },
    {
      key: 'doThumbnail',
      icon: '🖼️',
      label: 'תמונה ממוזערת',
      description: 'יצירת Thumbnail אוטומטי',
      active: options.doThumbnail ?? true
    },
    {
      key: 'doAiThumbnail',
      icon: '🎨',
      label: 'תמונת AI',
      description: 'יצירת תמונה עם Leonardo AI',
      active: options.doAiThumbnail ?? false
    },
    {
      key: 'doShorts',
      icon: '📱',
      label: 'קליפים קצרים',
      description: 'חיתוך רגעים ויראליים',
      active: options.doShorts ?? false
    }
  ];

  return (
    <div className="h-full flex flex-col bg-[#16191e] overflow-y-auto" dir="rtl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-[#1a1d23]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-[#00C8C8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
            <h3 className="text-sm font-bold text-white">הפצה ושיווק</h3>
          </div>
          <span className="text-[9px] bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded border border-purple-500/30">
            AI מונע
          </span>
        </div>
        {/* Open Full Dashboard Button */}
        <button
          onClick={onOpenDashboard}
          className="w-full py-2 bg-gradient-to-r from-purple-600/80 to-[#00C8C8]/80 rounded-lg text-white text-xs font-medium transition-all hover:opacity-90 flex items-center justify-center gap-2"
        >
          <span>🚀</span>
          <span>פתח לוח שיווק מלא</span>
        </button>
      </div>

      {/* Options Grid */}
      <div className="p-4 grid grid-cols-2 gap-3">
        {marketingFeatures.map((feature) => (
          <button
            key={feature.key}
            onClick={() => toggleOption(feature.key)}
            className={`p-3 rounded-lg border transition-all text-right ${
              feature.active
                ? 'bg-[#00C8C8]/10 border-[#00C8C8]/30 text-white'
                : 'bg-gray-800/30 border-gray-700 text-gray-500 hover:border-gray-600'
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="text-xl">{feature.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{feature.label}</p>
                <p className="text-[10px] text-gray-500 mt-0.5 truncate">{feature.description}</p>
              </div>
              <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                feature.active
                  ? 'border-[#00C8C8] bg-[#00C8C8]'
                  : 'border-gray-600'
              }`}>
                {feature.active && (
                  <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Music Style Selector */}
      <div className="px-4 pb-4">
        <label className="text-xs text-gray-400 mb-2 block">סגנון מוזיקה</label>
        <div className="flex gap-2 flex-wrap">
          {['calm', 'dramatic', 'uplifting', 'spiritual'].map((style) => (
            <button
              key={style}
              onClick={() => ctx.setProcessingOptions(prev => ({ ...prev, musicStyle: style }))}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                (options.musicStyle || 'calm') === style
                  ? 'bg-[#00C8C8]/20 text-[#00C8C8] border border-[#00C8C8]/30'
                  : 'bg-gray-800/50 text-gray-500 border border-gray-700 hover:text-white'
              }`}
            >
              {style === 'calm' && '🌊 רגוע'}
              {style === 'dramatic' && '🎭 דרמטי'}
              {style === 'uplifting' && '✨ מרומם'}
              {style === 'spiritual' && '🙏 רוחני'}
            </button>
          ))}
        </div>
      </div>

      {/* Subtitle Options */}
      <div className="px-4 pb-4 border-t border-gray-800 pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>📝</span>
            <span className="text-xs text-gray-400">כתוביות מעוצבות</span>
          </div>
          <button
            onClick={() => toggleOption('doStyledSubtitles')}
            className={`w-10 h-5 rounded-full transition-all ${
              (options.doStyledSubtitles ?? true)
                ? 'bg-[#00C8C8]'
                : 'bg-gray-700'
            }`}
          >
            <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-0.5 ${
              (options.doStyledSubtitles ?? true) ? 'translate-x-5' : 'translate-x-0'
            }`} />
          </button>
        </div>
      </div>

      {/* Voiceover Option */}
      <div className="px-4 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>🎙️</span>
            <div>
              <span className="text-xs text-gray-400">קריינות AI</span>
              <p className="text-[10px] text-gray-600">הוספת קריינות אוטומטית</p>
            </div>
          </div>
          <button
            onClick={() => toggleOption('doVoiceover')}
            className={`w-10 h-5 rounded-full transition-all ${
              (options.doVoiceover ?? false)
                ? 'bg-[#00C8C8]'
                : 'bg-gray-700'
            }`}
          >
            <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-0.5 ${
              (options.doVoiceover ?? false) ? 'translate-x-5' : 'translate-x-0'
            }`} />
          </button>
        </div>
      </div>

      {/* Info Section */}
      <div className="p-4 border-t border-gray-800 mt-auto">
        <div className="bg-[#00C8C8]/10 border border-[#00C8C8]/30 rounded-lg p-3">
          <p className="text-[10px] text-[#00C8C8]">
            💡 הגדרות אלו יופעלו בעת עיבוד הוידאו. ניתן לשנות בכל עת.
          </p>
        </div>
      </div>
    </div>
  );
}

export default MarketingTools;
