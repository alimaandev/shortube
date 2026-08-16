import React, { useMemo } from "react";
import { Audio, Sequence, staticFile } from "remotion";
import type { SceneData, WordTimestamp } from "./types";

const MAX_POPS = 12;
const RISER_LEAD_SECONDS = 1.2;

interface SoundEffectsProps {
  enabled: boolean;
  whooshPath: string;
  popPath: string;
  riserPath: string;
  scenes: SceneData[];
  timestamps: WordTimestamp[];
  bumperDuration: number;
  transitionDuration: number;
  fps: number;
  totalFrames: number;
}

interface SoundEvent {
  frame: number;
  path: string;
  volume: number;
}

/**
 * Premium sound design: whoosh on scene transitions, pop on statistical
 * words (numbers), riser into the outro. All events are silence-guarded
 * (missing assets simply produce no sound).
 */
export const SoundEffects: React.FC<SoundEffectsProps> = ({
  enabled,
  whooshPath,
  popPath,
  riserPath,
  scenes,
  timestamps,
  bumperDuration,
  transitionDuration,
  fps,
  totalFrames,
}) => {
  const events = useMemo(() => {
    if (!enabled) return [];
    const out: SoundEvent[] = [];
    const bumperFrames = Math.floor(bumperDuration * fps);
    const transitionFrames = Math.floor(transitionDuration * fps);

    // Whooshes at each transition-out (interior scenes only)
    if (whooshPath) {
      let current = bumperFrames;
      for (let i = 0; i < scenes.length - 1; i++) {
        const sceneFrames = Math.floor(scenes[i].duration * fps);
        const clipFrames = sceneFrames - transitionFrames;
        current += clipFrames;
        out.push({ frame: current, path: whooshPath, volume: 0.45 });
        current += transitionFrames * 2;
      }
    }

    // Pops on statistical words (contain digits)
    if (popPath) {
      let pops = 0;
      for (const ts of timestamps) {
        if (pops >= MAX_POPS) break;
        if (!/\d/.test(ts.word)) continue;
        const frame = Math.floor((bumperDuration + ts.start) * fps);
        out.push({ frame, path: popPath, volume: 0.55 });
        pops++;
      }
    }

    // Riser into the outro
    if (riserPath) {
      const outroStart = totalFrames - bumperFrames;
      const frame = Math.max(
        0,
        outroStart - Math.floor(RISER_LEAD_SECONDS * fps)
      );
      out.push({ frame, path: riserPath, volume: 0.4 });
    }

    return out.sort((a, b) => a.frame - b.frame);
  }, [
    enabled,
    whooshPath,
    popPath,
    riserPath,
    scenes,
    timestamps,
    bumperDuration,
    transitionDuration,
    fps,
    totalFrames,
  ]);

  if (events.length === 0) return null;

  return (
    <>
      {events.map((e, i) => (
        <Sequence key={i} from={e.frame}>
          <Audio src={staticFile(e.path)} volume={e.volume} />
        </Sequence>
      ))}
    </>
  );
};
