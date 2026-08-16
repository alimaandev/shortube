import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import type { WordTimestamp } from "./types";
import { useTemplate } from "./template";

const MAX_WORDS = 5;
const LOOKAHEAD_SECONDS = 2.2;

interface CaptionsProps {
  timestamps: WordTimestamp[];
  bumperDuration: number;
  fps: number;
  captionFontSize: number;
}

function findCurrentIndex(timestamps: WordTimestamp[], time: number): number {
  if (timestamps.length === 0) return -1;
  if (time < timestamps[0].start) return 0;
  for (let i = 0; i < timestamps.length; i++) {
    if (timestamps[i].start <= time && time < timestamps[i].end) return i;
  }
  return timestamps.length;
}

export const Captions: React.FC<CaptionsProps> = ({
  timestamps,
  bumperDuration,
  fps,
  captionFontSize,
}) => {
  const frame = useCurrentFrame();
  const template = useTemplate();
  const currentTime = frame / fps - bumperDuration;

  const { chunk, currentIndex } = useMemo(() => {
    if (!timestamps || timestamps.length === 0 || currentTime < 0) {
      return { chunk: [] as WordTimestamp[], currentIndex: -1 };
    }
    const idx = findCurrentIndex(timestamps, currentTime);
    if (idx >= timestamps.length) return { chunk: [], currentIndex: -1 };

    const lookaheadEnd = currentTime + LOOKAHEAD_SECONDS;
    const chunk: WordTimestamp[] = [];
    for (let i = idx; i < timestamps.length && chunk.length < MAX_WORDS; i++) {
      if (chunk.length > 0 && timestamps[i].start > lookaheadEnd) break;
      chunk.push(timestamps[i]);
    }
    return { chunk, currentIndex: idx };
  }, [timestamps, currentTime]);

  if (chunk.length === 0) return null;

  const totalChars = chunk.reduce(
    (sum, w) => sum + Math.max(w.word.length, 1),
    0
  );
  const fontSize =
    captionFontSize > 0 ? captionFontSize : template.captionStyle.fontSize;

  const activeWord = currentIndex >= 0 ? timestamps[currentIndex] : null;
  const wordProgress =
    activeWord && activeWord.end > activeWord.start
      ? (currentTime - activeWord.start) / (activeWord.end - activeWord.start)
      : 1;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 110,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          padding: "16px 28px",
          margin: "0 30px",
          borderRadius: 18,
          backdropFilter: "blur(14px)",
          WebkitBackdropFilter: "blur(14px)",
          backgroundColor: template.captionStyle.backgroundColor,
          border: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          maxWidth: "92%",
          width: "92%",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.35)",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            justifyContent: "center",
            alignItems: "baseline",
            width: "100%",
            flexWrap: "nowrap",
          }}
        >
          {chunk.map((w, i) => {
            const isActive = i === 0;
            const pop = isActive
              ? interpolate(
                  Math.min(Math.max(wordProgress, 0), 1),
                  [0, 0.18, 1],
                  [0.94, 1.06, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                )
              : 1;

            const widthPct = (Math.max(w.word.length, 1) / totalChars) * 100;

            return (
              <span
                key={w.start}
                style={{
                  display: "inline-block",
                  width: `${widthPct}%`,
                  textAlign: "center",
                  fontFamily: template.font,
                  fontSize,
                  fontWeight: isActive ? 800 : 600,
                  lineHeight: 1.35,
                  color: isActive
                    ? template.captionStyle.highlightColor
                    : template.muted,
                  opacity: isActive ? 1 : 0.72,
                  transform: `scale(${pop})`,
                  textShadow: `0 2px 6px ${template.captionStyle.strokeColor}`,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                }}
              >
                {w.word}
              </span>
            );
          })}
        </div>

        {activeWord && (
          <div
            style={{
              width: "100%",
              height: 3,
              borderRadius: 2,
              marginTop: 10,
              background: "rgba(255, 255, 255, 0.18)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${
                  Math.min(Math.max(wordProgress, 0), 1) * 100
                }%`,
                background: template.captionStyle.accentColor,
                borderRadius: 2,
              }}
            />
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
