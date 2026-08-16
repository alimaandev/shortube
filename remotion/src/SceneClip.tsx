import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { OffthreadVideo } from "remotion";
import { fadeUp, fastSpring } from "./textAnimations";
import { Vignette, ColorGrade } from "./Vignette";
import { useTemplate } from "./template";

interface SceneClipProps {
  imagePath: string | null;
  duration: number;
  fps: number;
  index: number;
  narration: string;
  mediaType?: "image" | "video";
}

function kenBurnsTransform(
  index: number,
  frame: number,
  totalFrames: number,
  intensity: number
) {
  const directions = [
    { x: 0, y: 0, z: 1 },
    { x: 2, y: 1, z: 1.08 },
    { x: -2, y: -1, z: 1.06 },
    { x: 1, y: -2, z: 1.07 },
    { x: -1, y: 2, z: 1.05 },
  ];
  const dir = directions[index % directions.length];
  const progress = frame / Math.max(totalFrames, 1);
  return {
    scale: interpolate(progress, [0, 1], [1, dir.z * intensity]),
    translateX: interpolate(progress, [0, 1], [0, dir.x]),
    translateY: interpolate(progress, [0, 1], [0, dir.y]),
  };
}

export const SceneClip: React.FC<SceneClipProps> = ({
  imagePath,
  duration,
  fps,
  index,
  narration,
  mediaType = "image",
}) => {
  const frame = useCurrentFrame();
  const { fps: contextFps } = useVideoConfig();
  const template = useTemplate();
  const totalFrames = Math.floor(duration * fps);

  const kb = kenBurnsTransform(
    index,
    frame,
    totalFrames,
    template.kenBurns ? template.kenBurnsIntensity : 1.0
  );

  const imageLoaded = spring({
    frame: Math.max(0, frame - 1),
    fps: contextFps,
    config: { damping: 20, mass: 0.5, stiffness: 100 },
  });

  const badgeStyle = spring({
    frame: Math.max(0, frame - 3),
    fps: contextFps,
    config: fastSpring,
  });

  const textStyle = fadeUp(frame, contextFps, 10);

  const isHook = index === 0;
  const hookFlash =
    isHook && frame < contextFps * 0.7
      ? interpolate(frame / Math.max(contextFps * 0.7, 1), [0, 0.5, 1], [0, 0.8, 0])
      : 0;

  const num = String(index + 1).padStart(2, "0");

  return (
    <AbsoluteFill style={{ backgroundColor: template.background2 }}>
      <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
        <div
          style={{
            width: "100%",
            height: "100%",
            opacity: imageLoaded,
            transform: `scale(${kb.scale}) translate(${kb.translateX}px, ${kb.translateY}px)`,
          }}
        >
          {imagePath && mediaType === "video" ? (
            <OffthreadVideo
              src={staticFile(imagePath)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          ) : imagePath ? (
            <Img
              src={staticFile(imagePath)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          ) : (
            <AbsoluteFill
              style={{
                background: `linear-gradient(135deg, ${template.background}, ${template.background2})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "0 40px",
              }}
            >
              <span
                style={{
                  color: template.text,
                  fontSize: 36,
                  fontWeight: 700,
                  fontFamily: template.font,
                  textAlign: "center",
                  lineHeight: 1.4,
                  textShadow: "0 2px 8px rgba(0,0,0,0.6)",
                }}
              >
                {narration}
              </span>
            </AbsoluteFill>
          )}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "55%",
          background:
            "linear-gradient(transparent 20%, rgba(0,0,0,0.5) 60%, rgba(0,0,0,0.85) 100%)",
        }}
      />

      <Vignette />
      <ColorGrade />

      <div
        style={{
          position: "absolute",
          top: 50,
          right: 30,
          opacity: badgeStyle,
          transform: `scale(${badgeStyle})`,
        }}
      >
        <div
          style={{
            background: template.accent,
            color: "#fff",
            fontSize: 18,
            fontWeight: 700,
            fontFamily: template.font,
            padding: "6px 12px",
            borderRadius: 8,
            letterSpacing: 1,
            backdropFilter: "blur(4px)",
            WebkitBackdropFilter: "blur(4px)",
          }}
        >
          {num}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: isHook ? 170 : 110,
          left: 24,
          right: 24,
          opacity: textStyle.opacity,
          transform: textStyle.transform,
        }}
      >
        {isHook ? (
          <>
            {narration.split(/\s+/).map((word, i) => {
              const isKeyword = /\d/.test(word);
              return (
                <span
                  key={i}
                  style={{
                    color: isKeyword ? template.hook.keywordColor : template.text,
                    fontSize: isHook ? 44 : 30,
                    fontWeight: 800,
                    fontFamily: template.font,
                    lineHeight: 1.3,
                    textShadow: "0 2px 12px rgba(0,0,0,0.6)",
                  }}
                >
                  {word}
                  {i < narration.split(/\s+/).length - 1 ? " " : ""}
                </span>
              );
            })}
          </>
        ) : (
          <span
            style={{
              color: template.text,
              fontSize: 30,
              fontWeight: 600,
              fontFamily: template.font,
              lineHeight: 1.35,
              textShadow: "0 2px 12px rgba(0,0,0,0.5)",
            }}
          >
            {narration}
          </span>
        )}
      </div>

      {isHook && hookFlash > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(circle at 50% 45%, ${template.hook.flashColor}, transparent 60%)`,
            opacity: hookFlash,
            pointerEvents: "none",
          }}
        />
      )}
    </AbsoluteFill>
  );
};
