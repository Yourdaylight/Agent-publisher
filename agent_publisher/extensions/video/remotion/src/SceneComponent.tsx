import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  AbsoluteFill,
  Easing,
  Audio,
  staticFile,
} from "remotion";
import { Scene, SubtitleWord } from "./types";

type SceneProps = {
  scene: Scene;
};

function getCurrentSubtitle(subtitles: SubtitleWord[], frame: number, fps: number): string {
  const currentMs = (frame / fps) * 1000;
  // Find the sentence segment that contains the current time
  for (const seg of subtitles) {
    if (currentMs >= seg.start_ms && currentMs <= seg.end_ms) {
      return seg.text;
    }
  }
  // If between segments, show the most recently ended one
  let latest: SubtitleWord | null = null;
  for (const seg of subtitles) {
    if (seg.start_ms <= currentMs) {
      latest = seg;
    }
  }
  // Only show if within 500ms after the segment ended
  if (latest && currentMs - latest.end_ms < 500) {
    return latest.text;
  }
  return "";
}

export const SceneComponent: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Entrance animations
  const headlineOpacity = interpolate(frame, [0, 0.5 * fps], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const headlineY = interpolate(frame, [0, 0.5 * fps], [30, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  const sublineOpacity = interpolate(frame, [0.3 * fps, 0.9 * fps], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  const iconScale = spring({
    frame: frame - 0.4 * fps,
    fps,
    config: { damping: 12, stiffness: 180 },
  });

  const visualOpacity = interpolate(frame, [0.5 * fps, 1.2 * fps], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  const bodyOpacity = interpolate(frame, [0.8 * fps, 1.4 * fps], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  const bodyY = interpolate(frame, [0.8 * fps, 1.4 * fps], [20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  // Subtle background scale (Ken Burns)
  const bgScale = interpolate(frame, [0, scene.duration_s * fps], [1, 1.03], {
    extrapolateRight: "clamp",
  });

  // Subtitle word highlight
  const subtitleText =
    scene.subtitles && scene.subtitles.length > 0
      ? getCurrentSubtitle(scene.subtitles, frame, fps)
      : "";

  return (
    <AbsoluteFill style={{ background: scene.bg_gradient }}>
      {/* TTS audio track — audio_url is a staticFile-relative path */}
      {scene.audio_url && (
        <Audio src={staticFile(scene.audio_url)} />
      )}

      {/* Ken Burns background scale */}
      <AbsoluteFill
        style={{
          background: scene.bg_gradient,
          transform: `scale(${bgScale})`,
        }}
      />

      {/* Content container */}
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          padding: "60px 48px 60px 48px",
          fontFamily: "'PingFang SC', 'Noto Sans SC', system-ui, sans-serif",
        }}
      >
        {/* Top zone — headline + subline (~30%) */}
        <div
          style={{
            flex: "0 0 30%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontSize: 52,
              fontWeight: 900,
              color: scene.accent_color,
              lineHeight: 1.25,
              marginBottom: 16,
              opacity: headlineOpacity,
              transform: `translateY(${headlineY}px)`,
              letterSpacing: "-0.5px",
            }}
          >
            {scene.headline}
          </div>
          <div
            style={{
              fontSize: 30,
              color: "rgba(255,255,255,0.75)",
              lineHeight: 1.5,
              opacity: sublineOpacity,
            }}
          >
            {scene.subline}
          </div>
        </div>

        {/* Visual zone — icon + description (~35%) */}
        <div
          style={{
            flex: "0 0 35%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            opacity: visualOpacity,
          }}
        >
          <div
            style={{
              width: 180,
              height: 180,
              borderRadius: "50%",
              background: `radial-gradient(circle, ${scene.accent_color}33 0%, transparent 70%)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 20,
              transform: `scale(${iconScale})`,
            }}
          >
            <span style={{ fontSize: 96 }}>{scene.icon}</span>
          </div>
          <div
            style={{
              fontSize: 28,
              color: "rgba(255,255,255,0.6)",
              textAlign: "center",
              maxWidth: 600,
            }}
          >
            {scene.visual_desc}
          </div>
        </div>

        {/* Bottom zone — body lines (~30%) */}
        <div
          style={{
            flex: "0 0 30%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
            opacity: bodyOpacity,
            transform: `translateY(${bodyY}px)`,
          }}
        >
          <div
            style={{
              width: 60,
              height: 3,
              background: scene.accent_color,
              borderRadius: 2,
              marginBottom: 20,
              opacity: 0.8,
            }}
          />
          {scene.body_lines.map((line, i) => (
            <div
              key={i}
              style={{
                fontSize: 32,
                color: "rgba(255,255,255,0.88)",
                lineHeight: 1.6,
                marginBottom: 8,
                fontWeight: i === 0 ? 500 : 400,
              }}
            >
              {line}
            </div>
          ))}
        </div>
      </AbsoluteFill>

      {/* Subtitle bar — absolutely pinned to the very bottom of the frame */}
      {subtitleText && (
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            padding: "0 40px 60px",
            display: "flex",
            justifyContent: "center",
            pointerEvents: "none",
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: "rgba(0,0,0,0.78)",
              borderRadius: 14,
              padding: "18px 32px",
              maxWidth: 920,
              textAlign: "center",
            }}
          >
            <span
              style={{
                fontSize: 38,
                color: "#ffffff",
                fontWeight: 500,
                fontFamily: "'PingFang SC', 'Noto Sans SC', system-ui, sans-serif",
                lineHeight: 1.5,
                letterSpacing: "0.5px",
              }}
            >
              {subtitleText}
            </span>
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
