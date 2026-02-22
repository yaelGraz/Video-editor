import { useState, useRef, useContext, useEffect } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

const QUICK_SUGGESTIONS = [
  'בנה דף נחיתה לקורס אונליין',
  'דף נחיתה לעסק של צילום',
  'דף נחיתה להשקת מוצר חדש',
  'דף נחיתה לאיסוף לידים',
];

function LandingPageTab() {
  const ctx = useContext(VideoEditorContext);
  const apiUrl = ctx.apiUrl;

  const [generatedHtml, setGeneratedHtml] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  const chatEndRef = useRef(null);

  // Load from sessionStorage on mount
  useEffect(() => {
    const savedHtml = sessionStorage.getItem('landing_generatedHtml');
    const savedChat = sessionStorage.getItem('landing_chatMessages');
    if (savedHtml) setGeneratedHtml(savedHtml);
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

    const userMsgObj = { role: 'user', content: userMessage };
    const typingMsgObj = { role: 'assistant', content: 'מעצב את הדף...' };

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
      sessionStorage.removeItem('landing_generatedHtml');
      sessionStorage.removeItem('landing_chatMessages');
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0a0b0d] text-white font-sans selection:bg-[#008a8a]/30" dir="rtl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-[#0f1115] shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#008a8a] animate-pulse"></div>
          <h2 className="text-sm font-bold tracking-wide uppercase">AI Landing Page Builder</h2>
        </div>
        <div className="flex items-center gap-3">
          {generatedHtml && (
            <button
              onClick={handleDownload}
              className="text-[10px] bg-[#008a8a] px-3 py-1.5 rounded hover:bg-[#00a3a3] transition-colors uppercase tracking-widest font-bold"
            >
              הורד HTML
            </button>
          )}
          <button
            onClick={handleClear}
            className="text-[10px] text-gray-500 hover:text-red-400 transition-colors uppercase tracking-widest"
          >
            אתחל מחדש
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-6 p-6 overflow-hidden">
        {/* Left: Live Preview (2/3) */}
        <div className="w-2/3 flex flex-col gap-4 overflow-hidden">
          <div className="flex-1 bg-[#12141a] border border-gray-800 rounded-2xl flex flex-col overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-[#161920]">
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black text-gray-500 tracking-tighter uppercase">Live Preview</span>
                {generatedHtml && (
                  <span className="text-[9px] bg-green-900/50 text-green-400 px-2 py-0.5 rounded">פעיל</span>
                )}
              </div>
              {generatedHtml && (
                <button
                  onClick={() => {
                    const win = window.open('', '_blank');
                    win.document.write(generatedHtml);
                    win.document.close();
                  }}
                  className="text-[10px] bg-gray-800 px-3 py-1 rounded hover:bg-gray-700 transition-colors"
                >
                  פתח בחלון חדש
                </button>
              )}
            </div>
            <div className="flex-1 bg-white rounded-b-2xl overflow-hidden">
              {generatedHtml ? (
                <iframe
                  srcDoc={generatedHtml}
                  sandbox="allow-scripts allow-same-origin"
                  className="w-full h-full border-0"
                  title="Landing Page Preview"
                />
              ) : (
                <div className="h-full flex flex-col items-center justify-center bg-[#0d0f14] text-gray-500">
                  <svg className="w-16 h-16 mb-4 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                  </svg>
                  <p className="text-xs opacity-50">תאר את דף הנחיתה שלך בצ'אט והתצוגה תופיע כאן</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Chat (1/3) */}
        <div className="w-1/3 flex flex-col gap-4 overflow-hidden">
          <div className="flex-1 bg-[#12141a] border border-gray-800 rounded-2xl flex flex-col overflow-hidden shadow-xl">
            <div className="p-3 border-b border-gray-800 bg-[#161920] text-[10px] font-bold text-gray-500 flex justify-between items-center">
              <span>LANDING PAGE CHAT</span>
              {isSending && <span className="text-[#008a8a] animate-bounce">...</span>}
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0d0f14] scrollbar-thin scrollbar-thumb-gray-800">
              {chatMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center gap-4 py-8">
                  <p className="text-xs text-gray-500 text-center">תאר את דף הנחיתה שאתה רוצה ואני אבנה אותו</p>
                  <div className="flex flex-col gap-2 w-full px-2">
                    {QUICK_SUGGESTIONS.map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => handleSendMessage(suggestion)}
                        className="text-[11px] text-right bg-[#1a1d25] border border-gray-800 rounded-xl px-4 py-3 text-gray-400 hover:border-[#008a8a] hover:text-gray-200 hover:bg-[#008a8a]/5 transition-all"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-3 rounded-2xl text-[12px] leading-relaxed shadow-sm whitespace-pre-wrap ${
                      msg.role === 'user'
                        ? 'bg-[#008a8a] text-white rounded-tr-none'
                        : 'bg-[#1f232c] text-gray-200 border border-gray-700 rounded-tl-none'
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>
            <div className="p-4 bg-[#161920] border-t border-gray-800 flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="תאר את דף הנחיתה שלך..."
                disabled={isSending}
                className="flex-1 bg-[#0a0b0d] border border-gray-700 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-[#008a8a] transition-all disabled:opacity-50"
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={!chatInput.trim() || isSending}
                className="bg-[#008a8a] px-5 rounded-xl text-xs font-bold hover:bg-[#00a3a3] active:scale-95 transition-all disabled:opacity-30"
              >
                {isSending ? '...' : 'שלח'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LandingPageTab;
