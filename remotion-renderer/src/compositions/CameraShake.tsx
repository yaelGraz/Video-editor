/**
 * CameraShake - Spring-based camera shake effect for Remotion.
 * Uses Remotion's spring() for smooth, natural vibrations.
 * Intensity is modulated by a simulated audio energy curve
 * that peaks during lyric lines and calms during gaps.
 */
import React from 'react';
import {
	useCurrentFrame,
	useVideoConfig,
	spring,
	interpolate,
} from 'remotion';
import type { LyricsData } from './LyricsOverlay';

export interface CameraShakeProps {
	children: React.ReactNode;
	lyrics?: LyricsData;
	intensity: number; // 0..1, multiplied by effectStrength
}

/**
 * Compute a pseudo-audio energy value based on whether the current
 * frame falls inside a lyric line (high energy) or a gap (low energy).
 */
function getAudioEnergy(frame: number, fps: number, lyrics?: LyricsData): number {
	if (!lyrics || lyrics.lines.length === 0) {
		// No lyrics data → use a gentle pulsing sine wave
		return 0.3 + 0.2 * Math.sin(frame * 0.08);
	}

	const currentTime = frame / fps;

	for (const line of lyrics.lines) {
		// Inside a spoken line → high energy
		if (currentTime >= line.lineStart && currentTime <= line.lineEnd) {
			// Ramp up energy toward the middle of the line
			const lineMid = (line.lineStart + line.lineEnd) / 2;
			const halfDur = (line.lineEnd - line.lineStart) / 2;
			const dist = Math.abs(currentTime - lineMid) / Math.max(halfDur, 0.01);
			return 0.6 + 0.4 * (1 - dist); // 0.6 → 1.0 → 0.6
		}
	}

	// In a gap → low ambient energy
	return 0.1 + 0.1 * Math.sin(frame * 0.05);
}

export const CameraShake: React.FC<CameraShakeProps> = ({
	children,
	lyrics,
	intensity,
}) => {
	const frame = useCurrentFrame();
	const { fps } = useVideoConfig();

	if (intensity <= 0) {
		return <>{children}</>;
	}

	const energy = getAudioEnergy(frame, fps, lyrics);
	const maxShift = intensity * 12; // max pixel shift at full intensity

	// Create smooth oscillations using multiple spring cycles.
	// We use different frequencies for X and Y to avoid a boring circular path.
	const cycleX = Math.floor(frame / 8); // new shake impulse every ~8 frames
	const cycleY = Math.floor((frame + 3) / 10);

	const springX = spring({
		frame: frame - cycleX * 8,
		fps,
		config: { damping: 6, stiffness: 180, mass: 0.25 },
	});

	const springY = spring({
		frame: frame - cycleY * 10,
		fps,
		config: { damping: 7, stiffness: 150, mass: 0.3 },
	});

	// Directional oscillation using sin/cos seeded by the cycle index
	const dirX = Math.sin(cycleX * 2.71828) > 0 ? 1 : -1;
	const dirY = Math.cos(cycleY * 3.14159) > 0 ? 1 : -1;

	const shakeX = dirX * (1 - springX) * maxShift * energy;
	const shakeY = dirY * (1 - springY) * maxShift * energy;

	// Subtle rotation using spring
	const rotCycle = Math.floor(frame / 12);
	const springRot = spring({
		frame: frame - rotCycle * 12,
		fps,
		config: { damping: 8, stiffness: 120, mass: 0.35 },
	});
	const rotDir = Math.sin(rotCycle * 1.618) > 0 ? 1 : -1;
	const rotation = rotDir * (1 - springRot) * intensity * 0.8 * energy;

	return (
		<div
			style={{
				width: '100%',
				height: '100%',
				transform: `translate(${shakeX}px, ${shakeY}px) rotate(${rotation}deg)`,
			}}
		>
			{children}
		</div>
	);
};
