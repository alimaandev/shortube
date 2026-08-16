import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import type { TransitionType } from "./types";

interface TransitionProps {
  children: React.ReactNode;
  type: TransitionType;
  durationInFrames: number;
}

export const ZoomBlurOut: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(durationInFrames, 1);

  const scale = interpolate(progress, [0, 1], [1, 1.4]);
  const blur = interpolate(progress, [0, 0.6, 1], [0, 4, 8]);
  const opacity = interpolate(progress, [0, 0.7, 1], [1, 0.6, 0]);

  return (
    <AbsoluteFill
      style={{
        transform: `scale(${scale})`,
        filter: `blur(${blur}px)`,
        opacity,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const ZoomBlurIn: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(durationInFrames, 1);

  const scale = interpolate(progress, [0, 1], [1.4, 1]);
  const blur = interpolate(progress, [0, 0.4, 1], [8, 4, 0]);
  const opacity = interpolate(progress, [0, 0.3, 1], [0, 0.6, 1]);

  return (
    <AbsoluteFill
      style={{
        transform: `scale(${scale})`,
        filter: `blur(${blur}px)`,
        opacity,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const SlideOut: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(durationInFrames, 1);

  const translateX = interpolate(progress, [0, 1], [0, 60]);
  const opacity = interpolate(progress, [0, 0.6, 1], [1, 0.9, 0]);

  return (
    <AbsoluteFill
      style={{
        transform: `translateX(${translateX}px)`,
        opacity,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const SlideIn: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(durationInFrames, 1);

  const translateX = interpolate(progress, [0, 1], [-60, 0]);
  const opacity = interpolate(progress, [0, 0.4, 1], [0, 0.9, 1]);

  return (
    <AbsoluteFill
      style={{
        transform: `translateX(${translateX}px)`,
        opacity,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const WipeOut: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(durationInFrames, 1);

  const radius = interpolate(progress, [0, 1], [141, 0]);
  const opacity = interpolate(progress, [0, 0.85, 1], [1, 1, 0]);

  return (
    <AbsoluteFill
      style={{
        clipPath: `circle(${radius}% at 50% 50%)`,
        opacity,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const WipeIn: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const progress = frame / Math.max(durationInFrames, 1);

  const radius = interpolate(progress, [0, 1], [0, 141]);

  return (
    <AbsoluteFill
      style={{
        clipPath: `circle(${radius}% at 50% 50%)`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const TransitionOut: React.FC<TransitionProps> = ({
  children,
  type,
  durationInFrames,
}) => {
  switch (type) {
    case "slide":
      return (
        <SlideOut durationInFrames={durationInFrames}>{children}</SlideOut>
      );
    case "wipe":
      return (
        <WipeOut durationInFrames={durationInFrames}>{children}</WipeOut>
      );
    case "zoomBlur":
      return (
        <ZoomBlurOut durationInFrames={durationInFrames}>{children}</ZoomBlurOut>
      );
    case "fade":
    default:
      return <AbsoluteFill>{children}</AbsoluteFill>;
  }
};

export const TransitionIn: React.FC<TransitionProps> = ({
  children,
  type,
  durationInFrames,
}) => {
  switch (type) {
    case "slide":
      return (
        <SlideIn durationInFrames={durationInFrames}>{children}</SlideIn>
      );
    case "wipe":
      return (
        <WipeIn durationInFrames={durationInFrames}>{children}</WipeIn>
      );
    case "zoomBlur":
      return (
        <ZoomBlurIn durationInFrames={durationInFrames}>{children}</ZoomBlurIn>
      );
    case "fade":
    default:
      return <AbsoluteFill>{children}</AbsoluteFill>;
  }
};
