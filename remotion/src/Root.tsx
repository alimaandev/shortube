import React from "react";
import { Composition } from "remotion";
import { ShortubeVideo } from "./ShortubeVideo";
import type { InputProps } from "./types";
import { DEFAULT_TEMPLATE } from "./template";

const defaultProps: InputProps = {
  script: {
    topic: "Amazing Facts About the Universe",
    hook: "Did you know the universe is expanding faster than we thought?",
    points: [
      "The speed of light is 299,792 kilometers per second.",
      "There are more stars than grains of sand on Earth.",
    ],
    cta: "Like and subscribe for more!",
  },
  scenes: [
    {
      index: 0,
      startTime: 0,
      endTime: 4,
      duration: 4,
      narration: "Did you know the universe is expanding faster than we thought?",
      imagePath: null,
    },
    {
      index: 1,
      startTime: 4,
      endTime: 8,
      duration: 4,
      narration: "Light travels at 299,792 kilometers per second.",
      imagePath: null,
    },
  ],
  voiceoverPath: "",
  musicPath: "",
  timestamps: [],
  bumperDuration: 1.5,
  transitionDuration: 0.3,
  musicVolume: 0.5,
  duckThreshold: 6,
  captionFontSize: 48,
  template: "",
  templateData: DEFAULT_TEMPLATE,
  sfxEnabled: true,
  sfxWhooshPath: "",
  sfxPopPath: "",
  sfxRiserPath: "",
  videoWidth: 1080,
  videoHeight: 1920,
  fps: 30,
};

export const Root: React.FC = () => {
  return (
    <Composition
      id="ShortubeVideo"
      component={ShortubeVideo as never}
      durationInFrames={99999}
      fps={30}
      width={1080}
      height={1920}
      calculateMetadata={({ props }) => {
        const p = props as Partial<InputProps>;
        return {
          fps: p.fps ?? 30,
          width: p.videoWidth ?? 1080,
          height: p.videoHeight ?? 1920,
        };
      }}
      defaultProps={defaultProps}
    />
  );
};
