/**
 * AudioVisualizerRemotion - Frequency-bar visualizer for Remotion SSR.
 * Since Web Audio API is unavailable during server-side render,
 * this uses deterministic sine-wave-based simulation to create
 * convincing audio-reactive bar animations.
 * Energy peaks are synced to lyric lines for realism.
 */
import React from 'react';
import {
	useCurrentFrame,
	useVideoConfig,
	interpolate,
	spring,
	Easing,
} from 'remotion';
import type { LyricsData } from './LyricsOverlay';

export interface AudioVisualizerRemotionProps {
	color: string;
	intensity: number;     // 0..1
	style?: 'bars' | 'wave' | 'circle';
	lyrics?: LyricsData;
	barCount?: number;
}

/**
 * Compute speech energy at the given time using lyrics timing.
 */
function getSpeechEnergy(time: number, lyrics?: LyricsData): number {
	if (!lyrics || lyrics.lines.length === 0) return 0.3;

	for (const line of lyrics.lines) {
		if (time >= line.lineStart && time <= line.lineEnd) {
			// Check for active word for extra energy
			for (const word of line.words) {
				if (time >= word.start && time <= word.end) {
					return word.emphasis === 'hero' ? 1.0 : word.emphasis === 'strong' ? 0.85 : 0.7;
				}
			}
			return 0.5; // In line but between words
		}
	}
	return 0.15; // Gap between lines
}

/**
 * Generate a deterministic frequency value for bar i at the given frame.
 */
function getBarValue(i: number, frame: number, energy: number, barCount: number): number {
	// Mix of sine waves at different frequencies for organic look
	const freq1 = Math.sin(frame * 0.15 + i * 0.9) * 0.3;
	const freq2 = Math.sin(frame * 0.08 + i * 1.7) * 0.25;
	const freq3 = Math.sin(frame * 0.22 + i * 0.4) * 0.15;
	const bassBoost = i < barCount * 0.3 ? 0.15 : 0; // Bass frequencies are stronger

	const raw = 0.1 + Math.abs(freq1 + freq2 + freq3) + bassBoost;
	return Math.min(1, raw * energy * 2);
}

export const AudioVisualizerRemotion: React.FC<AudioVisualizerRemotionProps> = ({
	color,
	intensity,
	style = 'bars',
	lyrics,
	barCount = 48,
}) => {
	const frame = useCurrentFrame();
	const { fps, width, height } = useVideoConfig();

	if (intensity <= 0) return null;

	const currentTime = frame / fps;
	const energy = getSpeechEnergy(currentTime, lyrics);
	const vizHeight = height * 0.12; // 12% of video height
	const barWidth = width / barCount;

	if (style === 'bars') {
		return (
			<div
				style={{
					position: 'absolute',
					bottom: 0,
					left: 0,
					right: 0,
					height: vizHeight,
					display: 'flex',
					alignItems: 'flex-end',
					justifyContent: 'center',
					gap: 1,
					opacity: intensity * 0.8,
					pointerEvents: 'none',
				}}
			>
				{Array.from({ length: barCount }, (_, i) => {
					const value = getBarValue(i, frame, energy, barCount);
					const barH = value * vizHeight * 0.9;
					const alpha = 0.4 + value * 0.6;

					return (
						<div
							key={i}
							style={{
								width: barWidth - 2,
								height: barH,
								backgroundColor: color,
								opacity: alpha,
								borderRadius: '2px 2px 0 0',
							}}
						/>
					);
				})}
			</div>
		);
	}

	if (style === 'wave') {
		// SVG wave path
		const points: string[] = [];
		for (let i = 0; i <= barCount; i++) {
			const value = getBarValue(i, frame, energy, barCount);
			const x = (i / barCount) * width;
			const y = vizHeight / 2 + (value - 0.3) * vizHeight * 0.8;
			points.push(`${x},${y}`);
		}
		// Close the path for fill
		const pathD = `M0,${vizHeight} L${points.join(' L')} L${width},${vizHeight} Z`;

		return (
			<svg
				style={{
					position: 'absolute',
					bottom: 0,
					left: 0,
					width,
					height: vizHeight,
					opacity: intensity * 0.7,
					pointerEvents: 'none',
				}}
			>
				<defs>
					<linearGradient id="waveGrad" x1="0" y1="0" x2="0" y2="1">
						<stop offset="0%" stopColor={color} stopOpacity="0.6" />
						<stop offset="100%" stopColor={color} stopOpacity="0.05" />
					</linearGradient>
				</defs>
				<path d={pathD} fill="url(#waveGrad)" />
				<polyline
					points={points.join(' ')}
					fill="none"
					stroke={color}
					strokeWidth="2"
					opacity="0.8"
				/>
			</svg>
		);
	}

	// Circle style
	const cx = width / 2;
	const cy = height / 2;
	const baseRadius = Math.min(width, height) * 0.15;
	const circleBarCount = 36;

	return (
		<div
			style={{
				position: 'absolute',
				inset: 0,
				opacity: intensity * 0.6,
				pointerEvents: 'none',
			}}
		>
			<svg width={width} height={height}>
				{Array.from({ length: circleBarCount }, (_, i) => {
					const value = getBarValue(i, frame, energy, circleBarCount);
					const angle = (i / circleBarCount) * Math.PI * 2 - Math.PI / 2;
					const r1 = baseRadius;
					const r2 = baseRadius + value * baseRadius * 0.8;
					const x1 = cx + Math.cos(angle) * r1;
					const y1 = cy + Math.sin(angle) * r1;
					const x2 = cx + Math.cos(angle) * r2;
					const y2 = cy + Math.sin(angle) * r2;
					const alpha = 0.4 + value * 0.6;

					return (
						<line
							key={i}
							x1={x1}
							y1={y1}
							x2={x2}
							y2={y2}
							stroke={color}
							strokeWidth="3"
							opacity={alpha}
							strokeLinecap="round"
						/>
					);
				})}
			</svg>
		</div>
	);
};
