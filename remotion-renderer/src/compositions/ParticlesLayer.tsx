/**
 * ParticlesLayer - Floating particles overlay for Remotion.
 * Deterministic (no Math.random()) so renders are reproducible.
 * Particles float upward with gentle horizontal drift.
 */
import React, { useMemo } from 'react';
import {
	useCurrentFrame,
	useVideoConfig,
	interpolate,
	Easing,
} from 'remotion';

export interface ParticlesLayerProps {
	color: string;       // dominant color
	intensity: number;   // 0..1
	count?: number;      // base particle count
}

interface Particle {
	id: number;
	x: number;       // 0..1 horizontal position
	speed: number;    // vertical speed multiplier
	size: number;     // radius in px
	delay: number;    // frame offset before particle appears
	drift: number;    // horizontal drift factor
	opacity: number;  // max opacity
}

/**
 * Seeded pseudo-random for deterministic particles.
 * Uses a simple LCG (Linear Congruential Generator).
 */
function seededRandom(seed: number): number {
	const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
	return x - Math.floor(x);
}

export const ParticlesLayer: React.FC<ParticlesLayerProps> = ({
	color,
	intensity,
	count = 40,
}) => {
	const frame = useCurrentFrame();
	const { width, height, durationInFrames } = useVideoConfig();

	// Generate deterministic particles
	const particles = useMemo((): Particle[] => {
		const adjustedCount = Math.round(count * Math.max(intensity, 0.1));
		return Array.from({ length: adjustedCount }, (_, i) => ({
			id: i,
			x: seededRandom(i * 7 + 1),
			speed: 0.5 + seededRandom(i * 13 + 2) * 1.5,
			size: 2 + seededRandom(i * 19 + 3) * 5 * intensity,
			delay: Math.floor(seededRandom(i * 23 + 4) * 60),
			drift: (seededRandom(i * 29 + 5) - 0.5) * 0.3,
			opacity: 0.15 + seededRandom(i * 31 + 6) * 0.35,
		}));
	}, [count, intensity]);

	if (intensity <= 0) return null;

	return (
		<div
			style={{
				position: 'absolute',
				inset: 0,
				overflow: 'hidden',
				pointerEvents: 'none',
			}}
		>
			{particles.map((p) => {
				const effectiveFrame = frame - p.delay;
				if (effectiveFrame < 0) return null;

				// Vertical travel: bottom to top, looping
				const cycleDuration = height / (p.speed * 1.5);
				const progress = (effectiveFrame % cycleDuration) / cycleDuration;

				const y = height * (1 - progress);
				const x = p.x * width + Math.sin(effectiveFrame * 0.02 * p.speed) * 40 * p.drift * width;

				// Fade in at bottom, fade out at top
				const opacity = interpolate(progress, [0, 0.1, 0.85, 1], [0, p.opacity, p.opacity, 0], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				});

				// Gentle pulsing glow
				const pulse = 0.8 + 0.2 * Math.sin(effectiveFrame * 0.1 + p.id);
				const glowSize = p.size * 2 * pulse;

				return (
					<div
						key={p.id}
						style={{
							position: 'absolute',
							left: x,
							top: y,
							width: p.size,
							height: p.size,
							borderRadius: '50%',
							backgroundColor: color,
							opacity: opacity * intensity,
							boxShadow: `0 0 ${glowSize}px ${color}80`,
							transform: 'translate(-50%, -50%)',
						}}
					/>
				);
			})}
		</div>
	);
};
