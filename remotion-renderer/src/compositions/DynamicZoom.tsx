/**
 * DynamicZoom - Slow Ken Burns-style scale effect for Remotion.
 * Smoothly zooms in over the duration of the video using spring easing.
 */
import React from 'react';
import {
	useCurrentFrame,
	useVideoConfig,
	interpolate,
	spring,
	Easing,
} from 'remotion';

export interface DynamicZoomProps {
	children: React.ReactNode;
	intensity: number; // 0..1
}

export const DynamicZoom: React.FC<DynamicZoomProps> = ({
	children,
	intensity,
}) => {
	const frame = useCurrentFrame();
	const { durationInFrames, fps } = useVideoConfig();

	if (intensity <= 0) {
		return <>{children}</>;
	}

	// Maximum zoom at full intensity: 1.0 → 1.15
	const maxZoom = intensity * 0.15;

	// Smooth zoom progression over the full video duration
	// Use a cubic easing so it starts slow, accelerates, then eases out
	const progress = interpolate(
		frame,
		[0, durationInFrames],
		[0, 1],
		{ extrapolateRight: 'clamp' }
	);

	// Apply an ease-in-out curve for natural feel
	const easedProgress = Easing.inOut(Easing.cubic)(progress);
	const scale = 1 + maxZoom * easedProgress;

	// Subtle focal point drift using spring for organic movement
	// Drift from center toward slight offset
	const driftX = interpolate(
		frame,
		[0, durationInFrames * 0.5, durationInFrames],
		[0, intensity * 2, -intensity * 1.5],
		{ extrapolateRight: 'clamp' }
	);
	const driftY = interpolate(
		frame,
		[0, durationInFrames * 0.3, durationInFrames * 0.7, durationInFrames],
		[0, -intensity * 1.5, intensity * 1, 0],
		{ extrapolateRight: 'clamp' }
	);

	return (
		<div
			style={{
				width: '100%',
				height: '100%',
				transform: `scale(${scale}) translate(${driftX}%, ${driftY}%)`,
				transformOrigin: 'center center',
			}}
		>
			{children}
		</div>
	);
};
