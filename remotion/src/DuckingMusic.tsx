import React from "react";
import { Audio, staticFile, useCurrentFrame } from "remotion";
import type { WordTimestamp } from "./types";

const RAMP_SECONDS = 0.15;

interface DuckingMusicProps {
  musicPath: string;
  timestamps: WordTimestamp[];
  bumperDuration: number;
  fps: number;
  baseVolume: number;
  duckDb: number;
}

/**
 * Background music with speech ducking driven by word timestamps.
 * Ducks `duckDb` dB while words are spoken, with 150ms smooth ramps
 * so the volume swells naturally between words and into the outro.
 */
export const DuckingMusic: React.FC<DuckingMusicProps> = ({
  musicPath,
  timestamps,
  bumperDuration,
  fps,
  baseVolume,
  duckDb,
}) => {
  const frame = useCurrentFrame();
  const currentTime = frame / fps - bumperDuration;

  const duckFactor = Math.pow(10, -duckDb / 20);
  let volume = baseVolume;

  for (const ts of timestamps) {
    const center = (ts.start + ts.end) / 2;
    const half = (ts.end - ts.start) / 2;
    const dist = Math.abs(currentTime - center);
    let wordVolume = baseVolume;
    if (dist <= half) {
      wordVolume = baseVolume * duckFactor;
    } else if (dist < half + RAMP_SECONDS) {
      const t = (dist - half) / RAMP_SECONDS;
      wordVolume = baseVolume * (1 - t + t * duckFactor);
    }
    if (wordVolume < volume) {
      volume = wordVolume;
    }
  }

  return <Audio src={staticFile(musicPath)} volume={volume} />;
};
