import type { LyricsData, LyricLine, LyricWord } from '../compositions/LyricsOverlay';

// SRT parsing types
interface SRTEntry {
	index: number;
	startTime: number;
	endTime: number;
	text: string;
}

/**
 * Parse SRT timestamp to seconds
 * Format: HH:MM:SS,mmm or HH:MM:SS.mmm
 */
function parseSRTTime(timeStr: string): number {
	const parts = timeStr.replace(',', '.').split(':');
	const hours = parseInt(parts[0], 10);
	const minutes = parseInt(parts[1], 10);
	const seconds = parseFloat(parts[2]);
	return hours * 3600 + minutes * 60 + seconds;
}

/**
 * Parse SRT file content into LyricsData
 * Creates approximate word timings by distributing time evenly
 */
export function parseSRT(srtContent: string): LyricsData {
	const lines: LyricLine[] = [];

	// Normalize line endings and split by double newline
	const entries = srtContent.replace(/\r\n/g, '\n').trim().split(/\n\n+/);

	for (const entry of entries) {
		const entryLines = entry.trim().split('\n');
		if (entryLines.length < 3) continue;

		const timeLine = entryLines[1];
		const textLines = entryLines.slice(2).join(' ');

		const timeMatch = timeLine.match(/(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})/);
		if (!timeMatch) continue;

		const startTime = parseSRTTime(timeMatch[1]);
		const endTime = parseSRTTime(timeMatch[2]);

		const wordTexts = textLines.split(/\s+/).filter(w => w.length > 0);
		if (wordTexts.length === 0) continue;

		const totalDuration = endTime - startTime;
		const wordDuration = totalDuration / wordTexts.length;

		const words: LyricWord[] = wordTexts.map((word, idx) => ({
			word,
			start: startTime + idx * wordDuration,
			end: startTime + (idx + 1) * wordDuration,
			emphasis: detectEmphasis(word),
		}));

		lines.push({
			lineStart: startTime,
			lineEnd: endTime,
			words,
		});
	}

	const duration = lines.length > 0 ? lines[lines.length - 1].lineEnd : 0;
	return { lines, duration };
}

/**
 * Detect word emphasis based on punctuation and common patterns
 */
function detectEmphasis(word: string): 'hero' | 'strong' | 'normal' {
	const trimmed = word.trim();
	if (/!$/.test(trimmed) || (trimmed.length > 2 && trimmed === trimmed.toUpperCase())) {
		return 'hero';
	}
	if (/[?"]/.test(trimmed)) {
		return 'strong';
	}
	return 'normal';
}

/**
 * Convert LyricsData to SRT format string
 */
export function lyricsToSRT(lyrics: LyricsData): string {
	const outputLines: string[] = [];

	lyrics.lines.forEach((line, index) => {
		const startTime = formatSRTTime(line.lineStart);
		const endTime = formatSRTTime(line.lineEnd);
		const text = line.words.map(w => w.word).join(' ');

		outputLines.push(`${index + 1}`);
		outputLines.push(`${startTime} --> ${endTime}`);
		outputLines.push(text);
		outputLines.push('');
	});

	return outputLines.join('\n');
}

function formatSRTTime(seconds: number): string {
	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = Math.floor(seconds % 60);
	const ms = Math.round((seconds % 1) * 1000);

	return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}

export { parseSRT as parseElevenLabsTranscript };
