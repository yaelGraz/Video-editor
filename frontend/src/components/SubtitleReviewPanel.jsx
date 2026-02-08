/**
 * SubtitleReviewPanel - Subtitle Review & Edit Before Processing
 *
 * Collapsed = inline notification bar in the editor flow.
 * Expanded  = FIXED full-screen overlay (z-[9999]) so no parent can clip it.
 */
import { useState, useContext, useEffect, useRef } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function formatTime(seconds) {
  if (typeof seconds !== 'number' || isNaN(seconds)) return '00:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function SubtitleReviewPanel() {
  const ctx = useContext(VideoEditorContext);
  const subtitleReview = ctx?.subtitleReview || { isActive: false, entries: [], pendingFileId: null };
  const setSubtitleReview = ctx?.setSubtitleReview;
  const apiUrl = ctx?.apiUrl;

  const [isExpanded, setIsExpanded] = useState(false);
  const [localEntries, setLocalEntries] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const prevIsActive = useRef(false);

  // === MOUNT / ACTIVATION LOG ===
  useEffect(() => {
    console.log('[SubtitleReviewPanel] MOUNTED');
    return () => console.log('[SubtitleReviewPanel] UNMOUNTED');
  }, []);

  useEffect(() => {
    console.log('[SubtitleReviewPanel] isActive:', subtitleReview.isActive,
      '| entries:', subtitleReview.entries?.length,
      '| isExpanded:', isExpanded);
  }, [subtitleReview.isActive, subtitleReview.entries, isExpanded]);

  // Sync entries when a new review session starts
  useEffect(() => {
    const justActivated = subtitleReview.isActive && !prevIsActive.current;
    prevIsActive.current = subtitleReview.isActive;

    if (justActivated && subtitleReview.entries?.length > 0) {
      console.log('[SubtitleReviewPanel] NEW session -', subtitleReview.entries.length, 'entries');
      setLocalEntries([...subtitleReview.entries]);
      setHasChanges(false);
      setIsExpanded(false);
    }
    if (!subtitleReview.isActive) {
      setIsExpanded(false);
      setLocalEntries([]);
      setHasChanges(false);
    }
  }, [subtitleReview.isActive, subtitleReview.entries]);

  if (!subtitleReview.isActive) return null;

  const entries = localEntries.length > 0 ? localEntries : (subtitleReview.entries || []);
  const entryCount = entries.length;

  const toggleExpanded = () => {
    console.log('[SubtitleReviewPanel] toggleExpanded →', !isExpanded);
    setIsExpanded(prev => !prev);
  };

  const updateEntry = (index, newText) => {
    const source = localEntries.length > 0 ? localEntries : (subtitleReview.entries || []);
    const updated = [...source];
    updated[index] = { ...updated[index], text: newText };
    setLocalEntries(updated);
    setHasChanges(true);
  };

  const resetAndResume = () => {
    if (typeof setSubtitleReview === 'function') {
      setSubtitleReview({ isActive: false, entries: [], pendingFileId: null });
    }
    setIsExpanded(false);
    setLocalEntries([]);
    setHasChanges(false);
    ctx.setIsProcessing(true);
    ctx.setProgress(22);
    ctx.setProgressMessage('ממשיך בעיבוד...');
  };

  const handleSkip = async () => {
    const fileId = subtitleReview.pendingFileId;
    if (!fileId) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${apiUrl}/continue-processing/${fileId}`, { method: 'POST' });
      if (res.ok) resetAndResume();
      else alert('שגיאה: ' + await res.text());
    } catch (e) { alert('שגיאת רשת: ' + e.message); }
    finally { setIsSubmitting(false); }
  };

  const handleConfirm = async () => {
    const fileId = subtitleReview.pendingFileId;
    if (!fileId) return;
    setIsSubmitting(true);
    try {
      if (hasChanges && localEntries.length > 0) {
        const saveRes = await fetch(`${apiUrl}/update-subtitles/${fileId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subtitles: localEntries }),
        });
        if (!saveRes.ok) throw new Error('Save failed: ' + await saveRes.text());
      }
      const res = await fetch(`${apiUrl}/continue-processing/${fileId}`, { method: 'POST' });
      if (res.ok) resetAndResume();
      else throw new Error('Continue failed: ' + await res.text());
    } catch (e) { alert('שגיאה: ' + e.message); }
    finally { setIsSubmitting(false); }
  };

  // ================================================================
  // COLLAPSED - inline notification bar (stays in normal flow)
  // ================================================================
  if (!isExpanded) {
    return (
      <div
        className="bg-[#1e2028] border border-amber-500/40 rounded-xl p-4 shadow-lg"
        style={{ fontFamily: 'Heebo, sans-serif' }}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="flex flex-col" dir="rtl">
            <span className="text-base font-medium text-white">כתוביות מוכנות לעריכה</span>
            <span className="text-sm text-amber-400/80 mt-0.5">
              {entryCount} שורות זוהו - ניתן לערוך לפני המשך העיבוד
            </span>
          </div>
          <div className="flex gap-3 flex-shrink-0">
            <button
              onClick={toggleExpanded}
              disabled={isSubmitting}
              className="px-5 py-2.5 bg-[#00C8C8] text-black font-semibold rounded-lg text-sm
                         hover:bg-[#00B0B0] active:bg-[#009999] transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              הצג כתוביות
            </button>
            <button
              onClick={handleSkip}
              disabled={isSubmitting}
              className="px-5 py-2.5 bg-[#2a2d38] text-gray-200 rounded-lg text-sm
                         hover:bg-[#3a3d48] active:bg-[#4a4d58] transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'ממתין...' : 'דלג והמשך'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ================================================================
  // EXPANDED - FIXED OVERLAY with z-[9999] — nothing can clip this
  // ================================================================
  console.log('[SubtitleReviewPanel] RENDERING EXPANDED OVERLAY with', entryCount, 'entries');

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm"
         style={{ fontFamily: 'Heebo, sans-serif' }}>
      <div className="bg-[#1e2028] border border-gray-600/50 rounded-2xl overflow-hidden shadow-2xl
                      w-[90vw] max-w-[800px] max-h-[85vh] flex flex-col">

        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-700/50 bg-[#252830] shrink-0">
          <div className="flex flex-col" dir="rtl">
            <h3 className="text-lg font-semibold text-white">עריכת כתוביות</h3>
            <span className="text-sm text-gray-400">{entryCount} שורות</span>
          </div>
          <button
            onClick={toggleExpanded}
            className="text-sm text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/10"
          >
            סגור ✕
          </button>
        </div>

        {/* Subtitle entries - scrollable */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-[#1a1c24]">
          {entries.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p className="text-lg">אין כתוביות להצגה</p>
            </div>
          ) : (
            entries.map((entry, i) => (
              <div
                key={i}
                className="flex gap-3 items-center p-3 bg-[#252830] rounded-lg
                           border border-gray-700/30 hover:border-gray-600/50 transition-colors"
              >
                <span className="flex-shrink-0 w-8 text-center text-xs text-gray-500 font-mono">
                  {i + 1}
                </span>
                <span className="flex-shrink-0 w-14 text-xs text-[#00C8C8] font-mono">
                  {formatTime(entry.start)}
                </span>
                <input
                  type="text"
                  value={entry.text || ''}
                  onChange={(e) => updateEntry(i, e.target.value)}
                  dir="rtl"
                  className="flex-1 bg-[#1a1c24] border border-gray-600/50 px-3 py-2
                             text-base text-white rounded-lg
                             focus:border-[#00C8C8] focus:ring-1 focus:ring-[#00C8C8]/30
                             focus:outline-none transition-all placeholder-gray-600"
                  style={{ fontFamily: 'Heebo, sans-serif' }}
                  placeholder="טקסט כתובית..."
                />
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center px-6 py-4 border-t border-gray-700/50 bg-[#252830] shrink-0">
          <span className="text-sm text-gray-400" dir="rtl">
            {hasChanges
              ? <span className="text-amber-400">יש שינויים שלא נשמרו</span>
              : 'לחץ על שורה כדי לערוך'}
          </span>
          <div className="flex gap-3">
            <button
              onClick={handleSkip}
              disabled={isSubmitting}
              className="px-5 py-2.5 bg-[#2a2d38] text-gray-200 rounded-lg text-sm font-medium
                         hover:bg-[#3a3d48] active:bg-[#4a4d58] transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              דלג והמשך
            </button>
            <button
              onClick={handleConfirm}
              disabled={isSubmitting}
              className="px-6 py-2.5 bg-[#00C8C8] text-black font-semibold rounded-lg text-sm
                         hover:bg-[#00B0B0] active:bg-[#009999] transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'שומר ומעבד...' : 'אישור והמשך עיבוד'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SubtitleReviewPanel;
