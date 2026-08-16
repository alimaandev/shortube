import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { useTemplate } from "./template";

interface ProgressBarProps {
  totalFrames: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ totalFrames }) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const template = useTemplate();

  const progress = interpolate(frame, [0, totalFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        height: 3,
        width: "100%",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress * 100}%`,
          background: `linear-gradient(90deg, ${template.accent}, ${template.accent2})`,
          borderRadius: "0 2px 2px 0",
          transition: "width 0.1s linear",
        }}
      />
    </div>
  );
};
