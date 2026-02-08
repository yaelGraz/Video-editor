/**
 * VideoEditorContext - Shared state context for the Video Editor
 * All components can access video, audio, and settings state through this context
 */
import { createContext } from 'react';

// Default video settings
export const DEFAULT_VIDEO_SETTINGS = {
  font: 'Arial',
  fontColor: '#FFFFFF',
  fontSize: 24,
  musicVolume: 0.15,
  ducking: true,
  subtitles: true,
  subtitlesEnabled: true,
  subtitleText: 'טקסט לדוגמה',
};

// Default processing options
export const DEFAULT_PROCESSING_OPTIONS = {
  doSubtitles: true,
  doStyledSubtitles: true,
  doMusic: true,
  doVoiceover: false,
  doMarketing: true,
  doShorts: false,
  doThumbnail: true,
  doAiThumbnail: false,
  musicStyle: 'calm'
};

// Maximum chat history length
export const MAX_HISTORY_LENGTH = 8;

// Create the context
export const VideoEditorContext = createContext(null);

export default VideoEditorContext;
