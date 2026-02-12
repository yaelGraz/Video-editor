import { Composition } from "remotion";
import { LyricsOverlay, demoLyrics } from "./compositions/LyricsOverlay";
import type { LyricsOverlayProps } from "./compositions/LyricsOverlay";
import { EffectsComposition } from "./compositions/EffectsComposition";
import type { EffectsCompositionProps } from "./compositions/EffectsComposition";

// Extended props that include the dynamic duration
type EffectsWithDuration = EffectsCompositionProps & {
	durationInFrames?: number;
};

export const RemotionRoot: React.FC = () => {
	return (
		<>
			{/* ============================================================= */}
			{/* Main Effects Composition (all effects combined)               */}
			{/* ============================================================= */}
			<Composition<EffectsWithDuration>
				id="EffectsComposition"
				component={EffectsComposition}
				durationInFrames={300}
				fps={25}
				width={1920}
				height={1080}
				calculateMetadata={async ({ props }) => {
					return {
						// Use durationInFrames from props if provided, otherwise default 300
						durationInFrames: props.durationInFrames || 300,
					};
				}}
				defaultProps={{
					videoSrc: "",
					lyrics: demoLyrics,
					subtitleStyle: "karaoke",
					fontSize: 56,
					position: "bottom",
					primaryColor: "#FFFFFF",
					highlightColor: "#FF6B35",
					fontFamily: "system-ui, -apple-system, sans-serif",
					showGradientOverlay: true,
					useOffthreadVideo: true,
					// Camera Effects
					cameraShakeEnabled: false,
					cameraShakeIntensity: 0.5,
					// Ambience Layers
					particlesEnabled: false,
					dynamicZoomEnabled: false,
					// Sound Waves
					soundWavesEnabled: false,
					soundWavesStyle: "bars",
					// Global controls
					effectStrength: 0.7,
					dominantColor: "#00D1C1",
				}}
			/>

			{/* ============================================================= */}
			{/* Legacy: Simple lyrics-only compositions                       */}
			{/* ============================================================= */}
			<Composition<LyricsOverlayProps>
				id="LyricsOverlay"
				component={LyricsOverlay}
				durationInFrames={300}
				fps={25}
				width={1920}
				height={1080}
				defaultProps={{
					videoSrc: "",
					lyrics: demoLyrics,
					style: "karaoke",
					fontSize: 56,
					position: "bottom",
					primaryColor: "#FFFFFF",
					secondaryColor: "#E0E0E0",
					highlightColor: "#FF6B35",
					fontFamily: "system-ui, -apple-system, sans-serif",
					showGradientOverlay: true,
					useOffthreadVideo: true,
				}}
			/>

			<Composition<LyricsOverlayProps>
				id="LyricsOverlayBounce"
				component={LyricsOverlay}
				durationInFrames={300}
				fps={25}
				width={1920}
				height={1080}
				defaultProps={{
					videoSrc: "",
					lyrics: demoLyrics,
					style: "karaoke",
					fontSize: 64,
					position: "center",
					primaryColor: "#FFFFFF",
					highlightColor: "#00D1C1",
					fontFamily: "system-ui, -apple-system, sans-serif",
					showGradientOverlay: true,
					useOffthreadVideo: true,
				}}
			/>

			<Composition<LyricsOverlayProps>
				id="LyricsOverlayCinematic"
				component={LyricsOverlay}
				durationInFrames={300}
				fps={25}
				width={1920}
				height={1080}
				defaultProps={{
					videoSrc: "",
					lyrics: demoLyrics,
					style: "fade",
					fontSize: 72,
					position: "bottom",
					primaryColor: "#FFFFFF",
					highlightColor: "#FFD700",
					fontFamily: "system-ui, -apple-system, sans-serif",
					showGradientOverlay: true,
					useOffthreadVideo: true,
				}}
			/>

			<Composition<LyricsOverlayProps>
				id="LyricsOverlayNeon"
				component={LyricsOverlay}
				durationInFrames={300}
				fps={25}
				width={1920}
				height={1080}
				defaultProps={{
					videoSrc: "",
					lyrics: demoLyrics,
					style: "minimal",
					fontSize: 60,
					position: "bottom",
					primaryColor: "#E0E0FF",
					highlightColor: "#00FFFF",
					fontFamily: "system-ui, -apple-system, sans-serif",
					showGradientOverlay: true,
					useOffthreadVideo: true,
				}}
			/>
		</>
	);
};
