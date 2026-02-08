import { useState, useRef, useContext, useEffect } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function PlannerTab() {
  const ctx = useContext(VideoEditorContext);
  const apiUrl = ctx.apiUrl;

  const [extractedText, setExtractedText] = useState('');
  const [planResult, setPlanResult] = useState('');
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // טעינה מ-sessionStorage בעת פתיחת הטאב
  useEffect(() => {
    const savedPlan = sessionStorage.getItem('planner_planResult');
    const savedChat = sessionStorage.getItem('planner_chatMessages');
    if (savedPlan) setPlanResult(savedPlan);
    if (savedChat) setChatMessages(JSON.parse(savedChat));
  }, []);

  // שמירה ל-sessionStorage בכל שינוי
  useEffect(() => {
    sessionStorage.setItem('planner_planResult', planResult);
    if (chatMessages.length > 0) {
      sessionStorage.setItem('planner_chatMessages', JSON.stringify(chatMessages));
    }
  }, [planResult, chatMessages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const parseAIResponse = (responseText) => {
    if (!responseText) return { chatPart: '', scriptPart: '' };
    let chatPart = '';
    let scriptPart = '';

    if (responseText.includes('CHAT:') && responseText.includes('SCRIPT:')) {
      const parts = responseText.split('SCRIPT:');
      const chatSection = parts[0];
      const scriptSection = parts[1];

      chatPart = chatSection.replace('CHAT:', '').trim();
      const cleanedScript = scriptSection.trim();
      
      scriptPart = /^none$/i.test(cleanedScript) ? '' : cleanedScript;
    } else {
      chatPart = responseText;
      scriptPart = '';
    }
    return { chatPart, scriptPart };
  };

const handleSendMessage = async () => {
    if (!chatInput.trim() || isSending) return;
    const userMessage = chatInput.trim();
    setChatInput('');
    setIsSending(true);

    const userMsgObj = { role: 'user', content: userMessage };
    const typingMsgObj = { role: 'assistant', content: 'חושב...' };
    
    const historyToSend = [...chatMessages];
    setChatMessages(prev => [...prev, userMsgObj, typingMsgObj]);

    try {
      const response = await fetch(`${apiUrl}/video-planner/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_input: userMessage,
          history: historyToSend,
          current_script: planResult || ''
        })
      });

      const data = await response.json();
      console.log("Full Data Received:", data);

      if (data.status === 'success' || data.success) {
        // 1. טיפול בטקסט של הצ'אט
        const rawAiMessage = data.ai_message || "";
        
        // 2. טיפול בסקריפט (המערך) - כאן התיקון הקריטי!
        // אנחנו בודקים אם יש שדה script נפרד, או אם הוא חבוי בתוך ai_message
        let finalScript = "";
        
        if (data.script && data.script.toLowerCase() !== "none") {
          // אם השרת שלח שדה script ייעודי (כפי שקרה אצלך)
          finalScript = data.script;
        } else {
          // ניסיון לחלץ מתוך ה-ai_message אם אין שדה script
          const parsed = parseAIResponse(rawAiMessage);
          finalScript = parsed.scriptPart;
        }

        // עדכון התיבה השמאלית אם נמצא סקריפט
        if (finalScript) {
          setPlanResult(finalScript);
        }

        // עדכון בועית הצ'אט
        setChatMessages(prev => {
          const updated = [...prev];
          if (updated.length > 0) {
            updated[updated.length - 1] = {
              role: 'assistant',
              content: rawAiMessage.includes('SCRIPT:') ? parseAIResponse(rawAiMessage).chatPart : rawAiMessage
            };
          }
          return updated;
        });
      } else {
        throw new Error(data.error || "השרת החזיר סטטוס שגיאה");
      }
    } catch (err) {
      console.error("Chat Error:", err);
      setChatMessages(prev => {
        const updated = [...prev];
        if (updated.length > 0) {
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `❌ שגיאה: ${err.message}`
          };
        }
        return updated;
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setUploadedFileName(prev => prev ? `${prev}, ${files.map(f => f.name).join(', ')}` : files.map(f => f.name).join(', '));
    
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const response = await fetch(`${apiUrl}/video-planner/extract-file`, {
          method: 'POST',
          body: formData
        });
        const data = await response.json();
        if (data.status === 'success') {
          setExtractedText(prev => prev + "\n" + data.text);
          setChatMessages(prev => [...prev, {
            role: 'assistant',
            content: `טענתי את הקובץ "${file.name}". איך תרצה לשלב אותו במערך?`
          }]);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleClear = () => {
    if (window.confirm("לאפס את כל התכנון בטאב הזה?")) {
      setChatMessages([]);
      setPlanResult('');
      setExtractedText('');
      setUploadedFileName(null);
      sessionStorage.clear();
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0a0b0d] text-white font-sans selection:bg-[#008a8a]/30" dir="rtl">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-[#0f1115] shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#008a8a] animate-pulse"></div>
          <h2 className="text-sm font-bold tracking-wide uppercase">AI Video Planner</h2>
        </div>
        <button onClick={handleClear} className="text-[10px] text-gray-500 hover:text-red-400 transition-colors uppercase tracking-widest">אתחל מחדש</button>
      </div>

      <div className="flex-1 flex gap-6 p-6 overflow-hidden">
        {/* Right: Controls & Chat */}
        <div className="w-1/3 flex flex-col gap-4 overflow-hidden">
          <div 
            onClick={() => fileInputRef.current.click()} 
            className="border-2 border-dashed border-gray-800 rounded-2xl p-6 text-center hover:border-[#008a8a] hover:bg-[#008a8a]/5 cursor-pointer transition-all bg-[#12141a] group"
          >
            <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".txt,.docx" multiple className="hidden" />
            <p className="text-xs text-gray-400 group-hover:text-gray-200 transition-colors">
              {uploadedFileName || 'גרור קבצים לכאן או לחץ להעלאה'}
            </p>
            <p className="text-[9px] text-gray-600 mt-2 uppercase">DOCX, TXT מרובים נתמכים</p>
          </div>

          <div className="flex-1 bg-[#12141a] border border-gray-800 rounded-2xl flex flex-col overflow-hidden shadow-xl">
            <div className="p-3 border-b border-gray-800 bg-[#161920] text-[10px] font-bold text-gray-500 flex justify-between items-center">
              <span>ASSISTANT CHAT</span>
              {isSending && <span className="text-[#008a8a] animate-bounce">● ● ●</span>}
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0d0f14] scrollbar-thin scrollbar-thumb-gray-800">
              {chatMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center opacity-20 italic">
                  <p className="text-xs">העלה חומרים או כתוב הנחיה כדי להתחיל...</p>
                </div>
              ) : (
                chatMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-3 rounded-2xl text-[12px] leading-relaxed shadow-sm ${
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
                placeholder="איך תרצה לעדכן את המערך?" 
                disabled={isSending} 
                className="flex-1 bg-[#0a0b0d] border border-gray-700 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-[#008a8a] transition-all disabled:opacity-50" 
              />
              <button 
                onClick={handleSendMessage} 
                disabled={!chatInput.trim() || isSending} 
                className="bg-[#008a8a] px-5 rounded-xl text-xs font-bold hover:bg-[#00a3a3] active:scale-95 transition-all disabled:opacity-30"
              >
                {isSending ? '...' : 'שלח'}
              </button>
            </div>
          </div>
        </div>

        {/* Left: Editor */}
        <div className="w-2/3 flex flex-col gap-4 overflow-hidden">
          <div className="flex-1 bg-[#12141a] border border-gray-800 rounded-2xl flex flex-col overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-[#161920]">
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black text-gray-500 tracking-tighter uppercase">Lesson Script Editor</span>
                <span className="text-[9px] bg-gray-800 px-2 py-0.5 rounded text-gray-400">עריכה חיה</span>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => navigator.clipboard.writeText(planResult)} 
                  className="text-[10px] bg-gray-800 px-3 py-1 rounded hover:bg-gray-700 transition-colors"
                >
                  העתק
                </button>
              </div>
            </div>
            <textarea 
              className="flex-1 p-10 bg-[#0d0f14] text-gray-300 text-sm leading-8 resize-none focus:outline-none border-none outline-none font-mono scrollbar-thin scrollbar-thumb-gray-800"
              value={planResult}
              onChange={(e) => setPlanResult(e.target.value)}
              placeholder="המערך יתעדכן כאן באופן אוטומטי..."
              dir="rtl"
            />
          </div>
          <button className="w-full py-4 rounded-2xl font-black text-xs bg-gradient-to-r from-[#004d4d] to-[#006666] text-white hover:from-[#005a5a] hover:to-[#008a8a] transition-all shadow-lg border border-white/5 uppercase tracking-widest">
            Send to ElevenLabs Voiceover
          </button>
        </div>
      </div>
    </div>
  );
}

export default PlannerTab;