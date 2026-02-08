/**
 * EditorTab - Professional Video Editor Workspace
 * Layout: Video Preview (LEFT/CENTER) | Editing Sidebar (RIGHT - pinned)
 * Sidebar has 2 sub-tabs: Manual Editor / AI Chat
 */
import { useState, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';
import ChatSection from './ChatSection';
import VideoPreviewer from './VideoPreviewer';
import AudioPreviewCard from './AudioPreviewCard';
import VideoUploadBox from './VideoUploadBox';
import ManualEditor from './ManualEditor';
import SubtitleReviewPanel from './SubtitleReviewPanel';

// Professional SVG Icons for sidebar tabs
const SidebarIcons = {
  manual: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
    </svg>
  ),
  chat: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
    </svg>
  )
};

// Sub-tab configuration for right sidebar
const SIDEBAR_TABS = [
  { id: 'manual', label: 'עורך ידני', icon: SidebarIcons.manual },
  { id: 'chat', label: 'צ\'אט AI', icon: SidebarIcons.chat }
];

function EditorTab() {
  const ctx = useContext(VideoEditorContext);

  // Sub-tab state for right sidebar
  const [activeSidebarTab, setActiveSidebarTab] = useState('manual');

  // Render sidebar content based on active sub-tab
  const renderSidebarContent = () => {
    switch (activeSidebarTab) {
      case 'manual':
        return <ManualEditor />;
      case 'chat':
        return <ChatSection isInTab={true} />;
      default:
        return <ManualEditor />;
    }
  };

  return (
    <div className="flex flex-row-reverse h-full bg-[#0a0c0f]">
      {/* LEFT/CENTER - Main Workspace (Video Preview) */}
      <main className="flex-1 flex flex-col p-5 gap-4 overflow-y-auto min-w-0 bg-[#0a0c0f]" dir="rtl">
        {/* Status Bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-[#00C8C8] rounded-full"></span>
              <span className="text-xs font-medium text-gray-400">תצוגה מקדימה</span>
            </div>
          </div>

          {/* Processing indicator */}
          {ctx.isProcessing && (
            <div className="flex items-center gap-3 bg-[#111318] px-4 py-2 rounded-lg border border-gray-800/50">
              <div className="w-3 h-3 border-2 border-[#00C8C8]/30 border-t-[#00C8C8] rounded-full animate-spin"></div>
              <span className="text-xs text-gray-400">{ctx.progressMessage}</span>
              <div className="w-24 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#00C8C8] transition-all duration-500"
                  style={{ width: `${ctx.progress}%` }}
                />
              </div>
              <span className="text-xs text-[#00C8C8] font-medium">{ctx.progress}%</span>
            </div>
          )}
        </div>

        {/* Video Upload */}
        <VideoUploadBox />

        {/* Audio Preview Card */}
        <AudioPreviewCard />

        {/* Subtitle Review Panel - Shows when subtitles are ready for review */}
        <SubtitleReviewPanel />

        {/* Video Preview - Takes remaining space */}
        <div className="flex-1 min-h-[400px]">
          <VideoPreviewer showSubtitles={true} />
        </div>
      </main>

      {/* RIGHT - Editing Sidebar (Pinned, 380px) */}
      <aside className="w-[380px] bg-[#111318] border-l border-gray-800/50 flex flex-col shrink-0">
        {/* Sidebar Sub-Tab Navigation */}
        <div className="border-b border-gray-800/50" dir="rtl">
          <div className="flex">
            {SIDEBAR_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveSidebarTab(tab.id)}
                className={`flex-1 px-4 py-3.5 text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2 relative ${
                  activeSidebarTab === tab.id
                    ? 'text-white bg-[#0a0c0f]'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.02]'
                }`}
              >
                <span className={activeSidebarTab === tab.id ? 'text-[#00C8C8]' : ''}>{tab.icon}</span>
                <span>{tab.label}</span>
                {/* Active indicator */}
                {activeSidebarTab === tab.id && (
                  <span className="absolute bottom-0 left-4 right-4 h-0.5 bg-[#00C8C8] rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Sidebar Content */}
        <div className="flex-1 overflow-hidden">
          {renderSidebarContent()}
        </div>
      </aside>
    </div>
  );
}

export default EditorTab;
