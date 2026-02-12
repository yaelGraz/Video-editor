/**
 * EffectsComposition - Master composition that layers all effects.
 * Combines: Video + CameraShake + DynamicZoom + Particles + Lyrics + AudioVisualizer
 */
import React from 'react';
import {
	AbsoluteFill,
	Video,
	OffthreadVideo,
	useCurrentFrame,
	useVideoConfig,
} from 'remotion';
import type { LyricsData, LyricsStyle, LyricsPosition } from './LyricsOverlay';
import { LyricsOverlay } from './LyricsOverlay';
import { CameraShake } from './CameraShake';
import { DynamicZoom } from './DynamicZoom';
import { ParticlesLayer } from './ParticlesLayer';
import { AudioVisualizerRemotion } from './AudioVisualizerRemotion';

export interface EffectsCompositionProps {
	// Video
	videoSrc: string;
	useOffthreadVideo?: boolean;

	// Lyrics / Subtitles
	lyrics: LyricsData;
	subtitleStyle?: LyricsStyle;
	fontSize?: number;
	position?: LyricsPosition;
	primaryColor?: string;
	highlightColor?: string;
	fontFamily?: string;
	isRTL?: boolean;
	showGradientOverlay?: boolean;

	// Camera Effects
	cameraShakeEnabled?: boolean;
	cameraShakeIntensity?: number;  // 0..1

	// Ambience Layers
	particlesEnabled?: boolean;
	dynamicZoomEnabled?: boolean;

	// Sound Waves
	soundWavesEnabled?: boolean;
	soundWavesStyle?: 'bars' | 'wave' | 'circle';

	// Global controls
	effectStrength?: number;  // 0..1 master multiplier
	dominantColor?: string;   // hex color used by particles, waves, etc.
}

export const EffectsComposition: React.FC<EffectsCompositionProps> = ({
	videoSrc,
	useOffthreadVideo = true,
	lyrics,
	subtitleStyle = 'karaoke',
	fontSize = 56,
	position = 'bottom',
	primaryColor = '#FFFFFF',
	highlightColor = '#FF6B35',
	fontFamily = 'system-ui, -apple-system, sans-serif',
	isRTL,
	showGradientOverlay = true,
	cameraShakeEnabled = false,
	cameraShakeIntensity = 0.5,
	particlesEnabled = false,
	dynamicZoomEnabled = false,
	soundWavesEnabled = false,
	soundWavesStyle = 'bars',
	effectStrength = 0.7,
	dominantColor = '#00D1C1',
}) => {
	const VideoComponent = useOffthreadVideo ? OffthreadVideo : Video;

	// Compute actual intensities (individual × global effectStrength)
	const shakeIntensity = cameraShakeEnabled ? cameraShakeIntensity * effectStrength : 0;
	const zoomIntensity = dynamicZoomEnabled ? effectStrength : 0;
	const particleIntensity = particlesEnabled ? effectStrength : 0;
	const wavesIntensity = soundWavesEnabled ? effectStrength : 0;

	// Determine the effective dominant color to use for effects
	const effectColor = dominantColor || '#00D1C1';

	return (
		<AbsoluteFill style={{ backgroundColor: '#000', fontFamily, overflow: 'hidden' }}>
			{/* Layer 1: Video with CameraShake + DynamicZoom wrappers */}
			<DynamicZoom intensity={zoomIntensity}>
				<CameraShake
					lyrics={lyrics}
					intensity={shakeIntensity}
				>
					<AbsoluteFill>
						{videoSrc && (
							<VideoComponent
								src={videoSrc}
								style={{ width: '100%', height: '100%', objectFit: 'cover' }}
							/>
						)}
					</AbsoluteFill>
				</CameraShake>
			</DynamicZoom>

			{/* Layer 2: Particles floating in background */}
			<ParticlesLayer
				color={effectColor}
				intensity={particleIntensity}
				count={50}
			/>

			{/* Layer 3: Gradient overlay for text readability */}
			{showGradientOverlay && (
				<GradientOverlay position={position} />
			)}

			{/* Layer 4: Lyrics overlay (subtitles) */}
			<LyricsContainer
				lyrics={lyrics}
				style={subtitleStyle}
				fontSize={fontSize}
				position={position}
				primaryColor={primaryColor}
				highlightColor={highlightColor}
				isRTL={isRTL}
			/>

			{/* Layer 5: Audio Visualizer */}
			<AudioVisualizerRemotion
				color={effectColor}
				intensity={wavesIntensity}
				style={soundWavesStyle}
				lyrics={lyrics}
			/>
		</AbsoluteFill>
	);
};

// =============================================================================
// Sub-components used by EffectsComposition (self-contained)
// =============================================================================

/**
 * Gradient overlay for text readability, positioned based on subtitle location.
 */
const GradientOverlay: React.FC<{ position: LyricsPosition }> = ({ position }) => {
	const getStyle = (): React.CSSProperties => {
		switch (position) {
			case 'top':
				return {
					top: 0, left: 0, right: 0, height: '35%',
					background: 'linear-gradient(to bottom, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.4) 60%, transparent 100%)',
				};
			case 'center':
				return {
					top: '30%', left: 0, right: 0, height: '40%',
					background: 'linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.5) 30%, rgba(0,0,0,0.5) 70%, transparent 100%)',
				};
			case 'bottom':
			default:
				return {
					bottom: 0, left: 0, right: 0, height: '35%',
					background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.4) 60%, transparent 100%)',
				};
		}
	};

	return <div style={{ position: 'absolute', ...getStyle(), pointerEvents: 'none' }} />;
};

/**
 * Lyrics container that renders word-level animated subtitles.
 * This is a simplified inline version that reuses the LyricLineComponent
 * logic from LyricsOverlay but rendered directly here.
 */
import {
	interpolate,
	spring,
	Easing,
} from 'remotion';
import type { LyricWord, LyricLine } from './LyricsOverlay';

const isRTLText = (text: string): boolean => {
	const rtlRegex = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F]/;
	return rtlRegex.test(text);
};

interface LyricsContainerProps {
	lyrics: LyricsData;
	style: LyricsStyle;
	fontSize: number;
	position: LyricsPosition;
	primaryColor: string;
	highlightColor: string;
	isRTL?: boolean;
}

const LyricsContainer: React.FC<LyricsContainerProps> = ({
	lyrics,
	style,
	fontSize,
	position,
	primaryColor,
	highlightColor,
	isRTL,
}) => {
	const frame = useCurrentFrame();
	const { fps } = useVideoConfig();

	const effectiveRTL = isRTL ?? (
		lyrics.lines.length > 0 && lyrics.lines[0].words.length > 0
			? isRTLText(lyrics.lines[0].words[0].word)
			: false
	);

	const getPositionStyle = (): React.CSSProperties => {
		switch (position) {
			case 'top':
				return { top: 80, left: 60, right: 60 };
			case 'center':
				return { top: '50%', left: 60, right: 60, transform: 'translateY(-50%)' };
			case 'bottom':
			default:
				return { bottom: 100, left: 60, right: 60 };
		}
	};

	return (
		<div style={{ position: 'absolute', ...getPositionStyle() }}>
			{lyrics.lines.map((line, index) => {
				const lineStartFrame = line.lineStart * fps;
				const lineEndFrame = line.lineEnd * fps;
				if (frame < lineStartFrame - 5 || frame > lineEndFrame + 40) return null;

				return (
					<div
						key={index}
						style={{
							display: 'flex',
							justifyContent: 'center',
							alignItems: 'baseline',
							flexWrap: 'wrap',
							gap: '4px 0',
							direction: effectiveRTL ? 'rtl' : 'ltr',
						}}
					>
						{line.words.map((word, wi) => (
							<AnimatedWord
								key={`${word.word}-${wi}`}
								word={word}
								lineEnd={line.lineEnd}
								frame={frame}
								fps={fps}
								style={style}
								primaryColor={primaryColor}
								highlightColor={highlightColor}
								fontSize={fontSize}
								isRTL={effectiveRTL}
							/>
						))}
					</div>
				);
			})}
		</div>
	);
};

/**
 * Animated word with karaoke/fade/minimal style support.
 */
interface AnimatedWordProps {
	word: LyricWord;
	lineEnd: number;
	frame: number;
	fps: number;
	style: LyricsStyle;
	primaryColor: string;
	highlightColor: string;
	fontSize: number;
	isRTL: boolean;
}

const AnimatedWord: React.FC<AnimatedWordProps> = ({
	word,
	lineEnd,
	frame,
	fps,
	style: animStyle,
	primaryColor,
	highlightColor,
	fontSize,
	isRTL,
}) => {
	const wordStartFrame = word.start * fps;
	const wordEndFrame = word.end * fps;
	const lineEndFrame = lineEnd * fps;
	const localFrame = frame - wordStartFrame;

	// Not yet visible
	if (frame < wordStartFrame) {
		if (animStyle === 'fade' || animStyle === 'minimal') {
			return <span style={{ opacity: 0 }}>{word.word}{!isRTL && '\u00A0'}</span>;
		}
		return (
			<span style={{ opacity: 0.4, display: 'inline-block', color: primaryColor, fontSize }}>
				{word.word}{!isRTL && '\u00A0'}
			</span>
		);
	}

	const isActive = frame >= wordStartFrame && frame <= wordEndFrame;

	// Exit animation
	const exitDuration = 35;
	const exitStart = lineEndFrame;
	const exitProgress = frame > exitStart
		? interpolate(frame, [exitStart, exitStart + exitDuration], [0, 1], {
			extrapolateLeft: 'clamp',
			extrapolateRight: 'clamp',
			easing: Easing.out(Easing.cubic),
		})
		: 0;
	const exitOpacity = 1 - exitProgress;

	// Minimal style
	if (animStyle === 'minimal') {
		const lineStartFrame = (lineEnd - (lineEnd - word.start)) * fps; // approx
		const entranceProgress = interpolate(frame, [wordStartFrame - 5, wordStartFrame + 5], [0, 1], {
			extrapolateLeft: 'clamp',
			extrapolateRight: 'clamp',
		});
		return (
			<span
				style={{
					display: 'inline-block',
					fontSize,
					fontWeight: isActive ? 700 : 500,
					color: isActive ? highlightColor : primaryColor,
					textShadow: isActive
						? `0 0 20px ${highlightColor}, 0 2px 10px rgba(0,0,0,0.9)`
						: '0 2px 10px rgba(0,0,0,0.8)',
					marginLeft: isRTL ? 8 : 0,
					marginRight: isRTL ? 0 : 8,
					opacity: Math.min(entranceProgress, exitOpacity),
					transform: isActive ? 'scale(1.05)' : 'scale(1)',
				}}
			>
				{word.word}
			</span>
		);
	}

	// Fade style
	if (animStyle === 'fade') {
		const fadeIn = interpolate(localFrame, [0, 8], [0, 1], { extrapolateRight: 'clamp' });
		return (
			<span
				style={{
					display: 'inline-block',
					opacity: fadeIn * exitOpacity,
					fontSize,
					fontWeight: 600,
					color: primaryColor,
					textShadow: '0 2px 15px rgba(0,0,0,0.9), 0 0 30px rgba(0,0,0,0.5)',
					marginLeft: isRTL ? 8 : 0,
					marginRight: isRTL ? 0 : 8,
				}}
			>
				{word.word}
			</span>
		);
	}

	// Karaoke style (default) - spring animations
	const springConfig = word.emphasis === 'hero'
		? { damping: 8, stiffness: 200, mass: 0.3 }
		: word.emphasis === 'strong'
			? { damping: 10, stiffness: 160, mass: 0.4 }
			: { damping: 12, stiffness: 140, mass: 0.5 };

	const scale = spring({ frame: localFrame, fps, config: springConfig });
	const translateY = interpolate(localFrame, [0, 5], [15, 0], {
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	const fadeIn = interpolate(localFrame, [0, 3], [0.4, 1], { extrapolateRight: 'clamp' });

	const emFontSize = word.emphasis === 'hero' ? fontSize * 1.3
		: word.emphasis === 'strong' ? fontSize * 1.1
			: fontSize;

	const fontWeight = word.emphasis === 'hero' ? 900
		: word.emphasis === 'strong' ? 700
			: 600;

	const color = isActive ? highlightColor : primaryColor;
	const textShadow = isActive
		? `0 0 30px ${highlightColor}, 0 0 60px ${highlightColor}80, 0 4px 15px rgba(0,0,0,0.9)`
		: '0 2px 15px rgba(0,0,0,0.9), 0 0 30px rgba(0,0,0,0.5)';

	return (
		<span
			style={{
				display: 'inline-block',
				opacity: fadeIn * exitOpacity,
				transform: `translateY(${translateY + exitProgress * 15}px) scale(${scale})`,
				fontSize: emFontSize,
				fontWeight,
				color,
				textShadow,
				marginLeft: isRTL ? 12 : 0,
				marginRight: isRTL ? 0 : 12,
			}}
		>
			{word.word}
		</span>
	);
};
