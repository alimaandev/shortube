import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useVideoConfig,
} from "remotion";
import type { InputProps } from "./types";
import { IntroBumper } from "./IntroBumper";
import { SceneClip } from "./SceneClip";
import { OutroBumper } from "./OutroBumper";
import { Captions } from "./Captions";
import { ProgressBar } from "./ProgressBar";
import { LogoWatermark } from "./LogoWatermark";
import { TransitionOut, TransitionIn } from "./Transitions";
import { DuckingMusic } from "./DuckingMusic";
import { SoundEffects } from "./SoundEffects";
import { TemplateProvider, useTemplate } from "./template";

export const ShortubeVideo: React.FC<InputProps> = ({
  script,
  scenes,
  voiceoverPath,
  musicPath,
  timestamps,
  bumperDuration,
  transitionDuration,
  musicVolume,
  duckThreshold,
  captionFontSize,
  sfxEnabled,
  sfxWhooshPath,
  sfxPopPath,
  sfxRiserPath,
  templateData,
}) => {
  return (
    <TemplateProvider data={templateData}>
      <ShortubeVideoInner
        script={script}
        scenes={scenes}
        voiceoverPath={voiceoverPath}
        musicPath={musicPath}
        timestamps={timestamps}
        bumperDuration={bumperDuration}
        transitionDuration={transitionDuration}
        musicVolume={musicVolume}
        duckThreshold={duckThreshold}
        captionFontSize={captionFontSize}
        sfxEnabled={sfxEnabled}
        sfxWhooshPath={sfxWhooshPath}
        sfxPopPath={sfxPopPath}
        sfxRiserPath={sfxRiserPath}
      />
    </TemplateProvider>
  );
};

const ShortubeVideoInner: React.FC<{
  script: InputProps["script"];
  scenes: InputProps["scenes"];
  voiceoverPath: string;
  musicPath: string;
  timestamps: InputProps["timestamps"];
  bumperDuration: number;
  transitionDuration: number;
  musicVolume: number;
  duckThreshold: number;
  captionFontSize: number;
  sfxEnabled: boolean;
  sfxWhooshPath: string;
  sfxPopPath: string;
  sfxRiserPath: string;
}> = ({
  script,
  scenes,
  voiceoverPath,
  musicPath,
  timestamps,
  bumperDuration,
  transitionDuration,
  musicVolume,
  duckThreshold,
  captionFontSize,
  sfxEnabled,
  sfxWhooshPath,
  sfxPopPath,
  sfxRiserPath,
}) => {
  const { fps } = useVideoConfig();
  const template = useTemplate();
  const transitionType = template.transition;
  const bumperFrames = Math.floor(bumperDuration * fps);
  const transitionFrames = Math.floor(transitionDuration * fps);

  let currentFrame = 0;
  const totalContentFrames =
    bumperFrames +
    scenes.reduce((sum, s) => sum + Math.floor(s.duration * fps), 0) +
    Math.max(0, scenes.length - 2) * transitionFrames +
    bumperFrames;

  const sections: {
    from: number;
    durationInFrames: number;
    component: React.ReactNode;
  }[] = [];

  // ── INTRO BUMPER ──
  sections.push({
    from: 0,
    durationInFrames: bumperFrames,
    component: <IntroBumper text={script.topic} />,
  });
  currentFrame = bumperFrames;

  // ── SCENE CLIPS with transitions ──
  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    const sceneFrames = Math.floor(scene.duration * fps);
    const clipFrames = sceneFrames - transitionFrames;

    // Scene content
    sections.push({
      from: currentFrame,
      durationInFrames: clipFrames,
      component: (
        <SceneClip
          imagePath={scene.imagePath}
          duration={clipFrames / fps}
          fps={fps}
          index={scene.index}
          narration={scene.narration}
          mediaType={scene.mediaType}
        />
      ),
    });
    currentFrame += clipFrames;

    // Transition out (except after last scene)
    if (i < scenes.length - 1) {
      sections.push({
        from: currentFrame,
        durationInFrames: transitionFrames,
        component: (
          <TransitionOut type={transitionType} durationInFrames={transitionFrames}>
            <SceneClip
              imagePath={scene.imagePath}
              duration={transitionFrames / fps}
              fps={fps}
              index={scene.index}
              narration=""
              mediaType={scene.mediaType}
            />
          </TransitionOut>
        ),
      });
      currentFrame += transitionFrames;

      const nextScene = scenes[i + 1];
      sections.push({
        from: currentFrame,
        durationInFrames: transitionFrames,
        component: (
          <TransitionIn type={transitionType} durationInFrames={transitionFrames}>
            <SceneClip
              imagePath={nextScene.imagePath}
              duration={transitionFrames / fps}
              fps={fps}
              index={nextScene.index}
              narration=""
              mediaType={nextScene.mediaType}
            />
          </TransitionIn>
        ),
      });
      currentFrame += transitionFrames;
    }
  }

  // ── OUTRO BUMPER ──
  sections.push({
    from: currentFrame,
    durationInFrames: bumperFrames,
    component: <OutroBumper text={script.cta} />,
  });
  currentFrame += bumperFrames;

  return (
    <AbsoluteFill>
      {sections.map((section, i) => (
        <Sequence
          key={i}
          from={section.from}
          durationInFrames={section.durationInFrames}
        >
          {section.component}
        </Sequence>
      ))}

      {/* Captions overlay — only during scene section */}
      <Sequence from={bumperFrames} durationInFrames={currentFrame - bumperFrames}>
        <Captions
          timestamps={timestamps}
          bumperDuration={bumperDuration}
          fps={fps}
          captionFontSize={captionFontSize}
        />
      </Sequence>

      {/* Progress bar */}
      <Sequence from={0} durationInFrames={currentFrame}>
        <ProgressBar totalFrames={currentFrame} />
      </Sequence>

      {/* Watermark */}
      <LogoWatermark />

      {/* Voiceover audio */}
      {voiceoverPath ? <Audio src={staticFile(voiceoverPath)} /> : null}

      {/* Background music with word-synced ducking */}
      {musicPath ? (
        <DuckingMusic
          musicPath={musicPath}
          timestamps={timestamps}
          bumperDuration={bumperDuration}
          fps={fps}
          baseVolume={musicVolume}
          duckDb={duckThreshold}
        />
      ) : null}

      {/* Sound design: whoosh / pop / riser */}
      <SoundEffects
        enabled={sfxEnabled}
        whooshPath={sfxWhooshPath}
        popPath={sfxPopPath}
        riserPath={sfxRiserPath}
        scenes={scenes}
        timestamps={timestamps}
        bumperDuration={bumperDuration}
        transitionDuration={transitionDuration}
        fps={fps}
        totalFrames={totalContentFrames}
      />
    </AbsoluteFill>
  );
};
