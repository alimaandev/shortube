import React from "react";
import {
  AbsoluteFill,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { typewriterChars, fastSpring } from "./textAnimations";
import { useTemplate } from "./template";

interface IntroBumperProps {
  text: string;
}

export const IntroBumper: React.FC<IntroBumperProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const template = useTemplate();

  const bgSpring = spring({
    frame,
    fps,
    config: { damping: 20, mass: 0.8, stiffness: 80 },
  });

  const startFrame = 3;
  const endBuffer = 6;
  const availableFrames = Math.max(durationInFrames - startFrame - endBuffer, 1);
  // Auto-fit: slow the typewriter down/up so the full text fits the bumper.
  const charDelay = Math.max(
    1,
    Math.min(5, Math.floor(availableFrames / Math.max(text.length, 1)))
  );

  const shown = typewriterChars(text, frame, startFrame, charDelay);

  const subtitleOpacity = spring({
    frame: Math.max(0, frame - fps * 0.8),
    fps,
    config: fastSpring,
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${template.gradient})`,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: "30%",
          left: "50%",
          width: 400,
          height: 400,
          transform: `translate(-50%, -50%) scale(${bgSpring})`,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${template.accent}26 0%, transparent 70%)`,
        }}
      />

      <div
        style={{
          position: "absolute",
          top: "42%",
          left: "10%",
          right: "10%",
          textAlign: "center",
        }}
      >
        <span
          style={{
            color: template.text,
            fontSize: 40,
            fontWeight: 700,
            fontFamily: template.font,
            lineHeight: 1.3,
            textShadow: "0 2px 12px rgba(0,0,0,0.5)",
          }}
        >
          {shown}
          {frame > startFrame && shown.length < text.length ? (
            <span
              style={{
                display: "inline-block",
                width: 3,
                height: 40,
                backgroundColor: template.accent,
                marginLeft: 2,
                verticalAlign: "text-bottom",
                opacity: Math.floor(frame / 4) % 2 ? 1 : 0,
              }}
            />
          ) : null}
        </span>
      </div>

      <div
        style={{
          position: "absolute",
          top: "58%",
          left: 0,
          right: 0,
          textAlign: "center",
          opacity: subtitleOpacity,
        }}
      >
        <span
          style={{
            color: template.muted,
            fontSize: 18,
            fontFamily: template.font,
            letterSpacing: 3,
            textTransform: "uppercase",
          }}
        >
          Shortube
        </span>
      </div>
    </AbsoluteFill>
  );
};
