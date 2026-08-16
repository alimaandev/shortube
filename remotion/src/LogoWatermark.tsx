import React from "react";
import { AbsoluteFill } from "remotion";

export const LogoWatermark: React.FC = () => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          bottom: 20,
          right: 20,
          display: "flex",
          alignItems: "center",
          gap: 6,
          opacity: 0.35,
        }}
      >
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: 4,
            background: "#4caf50",
          }}
        />
        <span
          style={{
            color: "#fff",
            fontSize: 12,
            fontWeight: 600,
            fontFamily: "Arial, sans-serif",
            letterSpacing: 1,
          }}
        >
          Shortube
        </span>
      </div>
    </AbsoluteFill>
  );
};
