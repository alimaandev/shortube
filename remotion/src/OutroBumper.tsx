import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { bouncySpring, fastSpring } from "./textAnimations";
import { useTemplate } from "./template";

interface OutroBumperProps {
  text: string;
}

const RING_SIZE = 180;
const RING_RADIUS = 76;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export const OutroBumper: React.FC<OutroBumperProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const template = useTemplate();

  const ctaSpring = spring({
    frame: Math.max(0, frame - 2),
    fps,
    config: bouncySpring,
  });

  const ringProgress = interpolate(frame, [fps * 0.4, durationInFrames - fps * 0.1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const subSpring = spring({
    frame: Math.max(0, frame - fps * 0.5),
    fps,
    config: fastSpring,
  });

  const bellSpring = spring({
    frame: Math.max(0, frame - fps * 0.7),
    fps,
    config: { damping: 6, mass: 0.3, stiffness: 150 },
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${template.gradient})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          opacity: ctaSpring,
          transform: `scale(${ctaSpring})`,
          textAlign: "center",
          marginBottom: 56,
        }}
      >
        <span
          style={{
            color: template.text,
            fontSize: 38,
            fontWeight: 700,
            fontFamily: template.font,
            lineHeight: 1.3,
            textShadow: "0 2px 10px rgba(0,0,0,0.4)",
          }}
        >
          {text}
        </span>
      </div>

      <div
        style={{
          position: "relative",
          width: RING_SIZE,
          height: RING_SIZE,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 28,
        }}
      >
        <svg
          width={RING_SIZE}
          height={RING_SIZE}
          style={{ position: "absolute", transform: "rotate(-90deg)" }}
        >
          <circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={RING_RADIUS}
            fill="none"
            stroke="rgba(255, 255, 255, 0.15)"
            strokeWidth={8}
          />
          <circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={RING_RADIUS}
            fill="none"
            stroke={template.outro.subscribeColor}
            strokeWidth={8}
            strokeLinecap="round"
            strokeDasharray={RING_CIRCUMFERENCE}
            strokeDashoffset={RING_CIRCUMFERENCE * (1 - ringProgress)}
          />
        </svg>

        <div
          style={{
            opacity: subSpring,
            transform: `translateY(${(1 - subSpring) * 20}px) scale(${subSpring})`,
            background: template.outro.subscribeColor,
            color: "#fff",
            fontSize: 22,
            fontWeight: 700,
            fontFamily: template.font,
            padding: "12px 34px",
            borderRadius: 30,
            display: "flex",
            alignItems: "center",
            gap: 10,
            boxShadow: `0 4px 24px ${template.outro.subscribeColor}66`,
          }}
        >
          <span>Subscribe</span>
        </div>
      </div>

      <div
        style={{
          opacity: subSpring,
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 24,
        }}
      >
        <div
          style={{
            opacity: bellSpring,
            transform: `rotate(${(1 - bellSpring) * 30}deg) scale(${bellSpring})`,
            fontSize: 24,
          }}
        >
          🔔
        </div>
        <span
          style={{
            color: template.muted,
            fontSize: 16,
            fontFamily: template.font,
          }}
        >
          {template.outro.tagline}
        </span>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 36,
          textAlign: "center",
        }}
      >
        <span
          style={{
            color: template.muted,
            fontSize: 14,
            fontFamily: template.font,
            letterSpacing: 2,
            textTransform: "uppercase",
            opacity: 0.7,
          }}
        >
          Made with Shortube
        </span>
      </div>
    </AbsoluteFill>
  );
};
