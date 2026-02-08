/**
 * VideoUploadBox - Compact video upload area
 * For local video file upload only (YouTube import is now a separate tab)
 */
import { useState, useRef, useContext } from 'react';
import { VideoEditorContext } from './VideoEditorContext';

function VideoUploadBox() {
  const ctx = useContext(VideoEditorContext);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    // Strictly video files only
    if (file && file.type.startsWith('video/')) {
      ctx.setVideoFile(file);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith('video/')) {
      ctx.setVideoFile(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  return (
    <div
      className={`bg-[#1a1d23] border rounded-xl p-4 transition-all ${
        isDragging
          ? 'border-[#00C8C8] bg-[#00C8C8]/5'
          : 'border-gray-800'
      }`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      dir="rtl"
    >
      {ctx.videoFile ? (
        /* Video Selected State - Compact */
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-green-500/20 rounded-lg flex items-center justify-center shrink-0">
            <span className="text-xl">✅</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white font-medium truncate">
              {ctx.videoFile.name}
            </p>
            <p className="text-[10px] text-gray-500">
              {(ctx.videoFile.size / (1024 * 1024)).toFixed(2)} MB
            </p>
          </div>
          <button
            onClick={() => ctx.setVideoFile(null)}
            className="px-3 py-1.5 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg text-[10px] hover:bg-red-500/30 transition-colors shrink-0"
          >
            הסר
          </button>
        </div>
      ) : (
        /* Empty State - Compact */
        <div className="flex items-center gap-3">
          <div
            className={`w-12 h-12 rounded-lg flex items-center justify-center shrink-0 transition-all ${
              isDragging
                ? 'bg-[#00C8C8]/20 border border-[#00C8C8] border-dashed'
                : 'bg-gray-800/50 border border-gray-700 border-dashed'
            }`}
          >
            <span className="text-2xl">{isDragging ? '📥' : '🎬'}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-400">
              {isDragging ? 'שחרר כאן' : 'גרור וידאו או'}
            </p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-xs text-[#00C8C8] hover:underline mt-0.5"
            >
              לחץ לבחירת קובץ
            </button>
          </div>
          <span className="text-[9px] text-gray-600 shrink-0">
            MP4, MOV, AVI
          </span>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
}

export default VideoUploadBox;
