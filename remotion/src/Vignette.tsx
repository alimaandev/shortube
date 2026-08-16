import React from "react";
import { AbsoluteFill } from "remotion";

export const Vignette: React.FC = () => {
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `
            radial-gradient(
              ellipse 70% 60% at 50% 50%,
              transparent 40%,
              rgba(0, 0, 0, 0.4) 100%
            )
          `,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};

export const ColorGrade: React.FC = () => {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background:
          "linear-gradient(180deg, rgba(0,0,0,0.02) 0%, rgba(0,0,0,0.06) 100%)",
        mixBlendMode: "multiply",
        pointerEvents: "none",
      }}
    />
  );
};
