import { spring, type SpringConfig } from "remotion";

export const fastSpring: Partial<SpringConfig> = {
  damping: 14,
  mass: 0.4,
  stiffness: 120,
};

export const bouncySpring: Partial<SpringConfig> = {
  damping: 8,
  mass: 0.5,
  stiffness: 100,
};

export function fadeUp(frame: number, fps: number, delayFrames = 0) {
  const s = spring({
    frame: Math.max(0, frame - delayFrames),
    fps,
    config: fastSpring,
  });
  return {
    opacity: s,
    transform: `translateY(${(1 - s) * 30}px)`,
  };
}

export function scaleIn(frame: number, fps: number, delayFrames = 0) {
  const s = spring({
    frame: Math.max(0, frame - delayFrames),
    fps,
    config: bouncySpring,
  });
  return {
    opacity: s,
    transform: `scale(${s})`,
  };
}

export function typewriterChars(
  text: string,
  frame: number,
  startFrame: number,
  charDelay = 2,
) {
  const visibleCount = Math.max(
    0,
    Math.min(text.length, Math.floor((frame - startFrame) / charDelay)),
  );
  return text.slice(0, visibleCount);
}
