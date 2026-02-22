import { useState, useRef, useContext, useEffect } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

const TEMPLATE_CATEGORIES = [
  {
    id: 'course',
    icon: '🎓',
    label: 'קורס אונליין',
    desc: 'מכירת קורסים דיגיטליים',
    prompt: 'בנה דף נחיתה מקצועי למכירת קורס אונליין. הקורס מלמד מיומנות חדשה ויש לו 3 חבילות מחיר. כולל המלצות תלמידים, תוכן הקורס, ו-FAQ.'
  },
  {
    id: 'saas',
    icon: '🚀',
    label: 'SaaS / מוצר טכנולוגי',
    desc: 'השקת מוצר דיגיטלי',
    prompt: 'בנה דף נחיתה מרשים למוצר SaaS טכנולוגי. עיצוב מודרני עם גרדיאנטים כהים, אנימציות, פיצ\'רים עם אייקונים, חבילות מחיר, והמלצות לקוחות.'
  },
  {
    id: 'leads',
    icon: '📋',
    label: 'איסוף לידים',
    desc: 'טפסי הרשמה וליד מגנט',
    prompt: 'בנה דף נחיתה לאיסוף לידים עם טופס הרשמה בולט. כולל הצעת ערך חזקה, יתרונות, הוכחה חברתית, ו-CTA שמניע לפעולה מיידית.'
  },
  {
    id: 'business',
    icon: '💼',
    label: 'עסק / שירות',
    desc: 'עסקים ונותני שירות',
    prompt: 'בנה דף נחיתה מקצועי לעסק שנותן שירותים. כולל הצגת השירותים, תהליך עבודה, המלצות לקוחות, תמחור, ויצירת קשר.'
  },
  {
    id: 'event',
    icon: '🎤',
    label: 'אירוע / וובינר',
    desc: 'כנסים, הרצאות, וובינרים',
    prompt: 'בנה דף נחיתה לאירוע או וובינר. כולל ספירה לאחור, פרטי האירוע, המרצים, מה תלמדו, וכפתור הרשמה בולט.'
  },
  {
    id: 'portfolio',
    icon: '🎨',
    label: 'תיק עבודות',
    desc: 'פרילנסרים ויוצרים',
    prompt: 'בנה דף נחיתה - תיק עבודות מרשים לפרילנסר. עיצוב נקי ומודרני עם גלריית עבודות, "על עצמי", המלצות, ויצירת קשר.'
  },
];

const DEVICE_MODES = [
  { id: 'desktop', icon: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z', width: '100%' },
  { id: 'tablet', icon: 'M12 18h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z', width: '768px' },
  { id: 'mobile', icon: 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z', width: '375px' },
];

function LandingPageTab() {
  const ctx = useContext(VideoEditorContext);
  const apiUrl = ctx.apiUrl;

  const [generatedHtml, setGeneratedHtml] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [deviceMode, setDeviceMode] = useState('desktop');
  const [showTemplates, setShowTemplates] = useState(true);

  const chatEndRef = useRef(null);

  // Load from sessionStorage on mount
  useEffect(() => {
    const savedHtml = sessionStorage.getItem('landing_generatedHtml');
    const savedChat = sessionStorage.getItem('landing_chatMessages');
    if (savedHtml) {
      setGeneratedHtml(savedHtml);
      setShowTemplates(false);
    }
    if (savedChat) setChatMessages(JSON.parse(savedChat));
  }, []);

  // Save to sessionStorage on change
  useEffect(() => {
    if (generatedHtml) sessionStorage.setItem('landing_generatedHtml', generatedHtml);
    if (chatMessages.length > 0) {
      sessionStorage.setItem('landing_chatMessages', JSON.stringify(chatMessages));
    }
  }, [generatedHtml, chatMessages]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSendMessage = async (messageOverride) => {
    const userMessage = (messageOverride || chatInput).trim();
    if (!userMessage || isSending) return;
    setChatInput('');
    setIsSending(true);
    setShowTemplates(false);

    const userMsgObj = { role: 'user', content: userMessage };
    const typingMsgObj = { role: 'assistant', content: '🎨 מעצב את הדף שלך... זה יכול לקחת כמה שניות' };

    const historyToSend = [...chatMessages];
    setChatMessages(prev => [...prev, userMsgObj, typingMsgObj]);

    try {
      const response = await fetch(`${apiUrl}/landing-page/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_input: userMessage,
          history: historyToSend,
          current_html: generatedHtml || ''
        })
      });

      const data = await response.json();

      if (data.status === 'success') {
        if (data.html) {
          setGeneratedHtml(data.html);
        }

        setChatMessages(prev => {
          const updated = [...prev];
          if (updated.length > 0) {
            updated[updated.length - 1] = {
              role: 'assistant',
              content: data.ai_message || 'הדף מוכן!'
            };
          }
          return updated;
        });
      } else {
        throw new Error(data.detail || 'שגיאה מהשרת');
      }
    } catch (err) {
      console.error('[Landing] Chat Error:', err);
      setChatMessages(prev => {
        const updated = [...prev];
        if (updated.length > 0) {
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `שגיאה: ${err.message}`
          };
        }
        return updated;
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleDownload = () => {
    if (!generatedHtml) return;
    const blob = new Blob([generatedHtml], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'landing-page.html';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClear = () => {
    if (window.confirm('לאפס את כל הצ\'אט והדף?')) {
      setChatMessages([]);
      setGeneratedHtml('');
      setChatInput('');
      setShowTemplates(true);
      sessionStorage.removeItem('landing_generatedHtml');
      sessionStorage.removeItem('landing_chatMessages');
    }
  };

  const currentDeviceWidth = DEVICE_MODES.find(d => d.id === deviceMode)?.width || '100%';

  return (
    <div className="h-full flex flex-col bg-[#0a0b0d] text-white font-sans selection:bg-[#6C63FF]/30" dir="rtl">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-800/60 flex justify-between items-center bg-gradient-to-l from-[#0f1115] to-[#12141a]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6C63FF] to-[#00D2FF] flex items-center justify-center text-sm">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-wide">AI Landing Page Builder</h2>
            <p className="text-[10px] text-gray-500">דפי נחיתה מקצועיים בלחיצה</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {generatedHtml && (
            <>
              {/* Device preview toggle */}
              <div className="flex items-center bg-[#1a1d25] rounded-lg border border-gray-800 p-0.5">
                {DEVICE_MODES.map(device => (
                  <button
                    key={device.id}
                    onClick={() => setDeviceMode(device.id)}
                    className={`p-1.5 rounded-md transition-all ${
                      deviceMode === device.id
                        ? 'bg-[#6C63FF] text-white shadow-lg shadow-[#6C63FF]/20'
                        : 'text-gray-500 hover:text-gray-300'
                    }`}
                    title={device.id}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={device.icon} />
                    </svg>
                  </button>
                ))}
              </div>

              <button
                onClick={() => {
                  const win = window.open('', '_blank');
                  win.document.write(generatedHtml);
                  win.document.close();
                }}
                className="text-[10px] bg-[#1a1d25] border border-gray-800 px-3 py-1.5 rounded-lg hover:border-gray-600 transition-colors flex items-center gap-1.5"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                תצוגה מלאה
              </button>

              <button
                onClick={handleDownload}
                className="text-[10px] bg-gradient-to-l from-[#6C63FF] to-[#8B83FF] px-4 py-1.5 rounded-lg hover:opacity-90 transition-opacity font-bold flex items-center gap-1.5 shadow-lg shadow-[#6C63FF]/20"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                הורד HTML
              </button>
            </>
          )}
          <button
            onClick={handleClear}
            className="text-[10px] text-gray-600 hover:text-red-400 transition-colors px-2 py-1.5"
            title="אתחל מחדש"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Live Preview (2/3) */}
        <div className="w-2/3 flex flex-col overflow-hidden border-l border-gray-800/40">
          {generatedHtml ? (
            <div className="flex-1 bg-[#1a1d25] flex items-start justify-center overflow-auto p-4">
              <div
                className="bg-white rounded-xl overflow-hidden shadow-2xl transition-all duration-500 h-full"
                style={{ width: currentDeviceWidth, maxWidth: '100%' }}
              >
                <iframe
                  srcDoc={generatedHtml}
                  sandbox="allow-scripts allow-same-origin"
                  className="w-full h-full border-0"
                  title="Landing Page Preview"
                />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center bg-[#0d0f14] px-8">
              {showTemplates ? (
                <div className="w-full max-w-2xl">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#6C63FF]/20 to-[#00D2FF]/20 flex items-center justify-center border border-[#6C63FF]/20">
                      <svg className="w-8 h-8 text-[#6C63FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                      </svg>
                    </div>
                    <h3 className="text-xl font-bold mb-2 bg-gradient-to-l from-[#6C63FF] to-[#00D2FF] bg-clip-text text-transparent">
                      בחר סוג דף נחיתה
                    </h3>
                    <p className="text-sm text-gray-500">בחר תבנית או תאר בצ'אט בדיוק מה שאתה רוצה</p>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {TEMPLATE_CATEGORIES.map(cat => (
                      <button
                        key={cat.id}
                        onClick={() => handleSendMessage(cat.prompt)}
                        disabled={isSending}
                        className="group text-right bg-[#12141a] border border-gray-800/60 rounded-xl p-4 hover:border-[#6C63FF]/50 hover:bg-[#6C63FF]/5 transition-all duration-300 disabled:opacity-50"
                      >
                        <span className="text-2xl block mb-2">{cat.icon}</span>
                        <span className="text-xs font-bold text-gray-200 block mb-1 group-hover:text-white transition-colors">{cat.label}</span>
                        <span className="text-[10px] text-gray-600 block group-hover:text-gray-400 transition-colors">{cat.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-[#6C63FF]/30 border-t-[#6C63FF] animate-spin" />
                  <p className="text-sm text-gray-500">מייצר את דף הנחיתה שלך...</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Chat (1/3) */}
        <div className="w-1/3 flex flex-col overflow-hidden bg-[#0f1115]">
          <div className="px-4 py-3 border-b border-gray-800/60 bg-[#12141a] flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isSending ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
              <span className="text-[11px] font-bold text-gray-400">AI Designer</span>
            </div>
            {chatMessages.length > 0 && (
              <span className="text-[9px] text-gray-600">{chatMessages.filter(m => m.role === 'user').length} הודעות</span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-thumb-gray-800">
            {chatMessages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center gap-3 py-8">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#6C63FF]/20 to-[#00D2FF]/20 flex items-center justify-center">
                  <svg className="w-5 h-5 text-[#6C63FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                  </svg>
                </div>
                <p className="text-xs text-gray-500 text-center leading-relaxed">
                  בחר תבנית בצד שמאל<br/>או תאר כאן מה שאתה רוצה
                </p>
                <div className="w-full space-y-1.5 mt-2">
                  <p className="text-[10px] text-gray-600 text-center mb-2">דוגמאות לבקשות:</p>
                  {[
                    'שנה את הצבע הראשי לכחול',
                    'הוסף סקשן של המלצות',
                    'שנה את הכותרת ל...',
                    'עדכן את המחירים'
                  ].map((hint, i) => (
                    <div key={i} className="text-[10px] text-gray-700 text-center py-1">
                      "{hint}"
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[88%] p-3 rounded-2xl text-[12px] leading-relaxed whitespace-pre-wrap ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-l from-[#6C63FF] to-[#8B83FF] text-white rounded-tr-sm shadow-lg shadow-[#6C63FF]/10'
                      : 'bg-[#1a1d25] text-gray-200 border border-gray-800/60 rounded-tl-sm'
                  }`}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="p-3 bg-[#12141a] border-t border-gray-800/60">
            <div className="flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder={generatedHtml ? 'בקש שינוי בדף...' : 'תאר את דף הנחיתה שלך...'}
                disabled={isSending}
                className="flex-1 bg-[#0a0b0d] border border-gray-700/50 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-[#6C63FF]/50 focus:ring-1 focus:ring-[#6C63FF]/20 transition-all disabled:opacity-50 placeholder:text-gray-600"
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={!chatInput.trim() || isSending}
                className="bg-gradient-to-l from-[#6C63FF] to-[#8B83FF] w-10 h-10 rounded-xl flex items-center justify-center hover:opacity-90 active:scale-95 transition-all disabled:opacity-30 shadow-lg shadow-[#6C63FF]/20"
              >
                {isSending ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <svg className="w-4 h-4 rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LandingPageTab;
