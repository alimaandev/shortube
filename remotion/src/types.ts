export interface ScriptData {
  topic: string;
  hook: string;
  points: string[];
  cta: string;
}

export interface SceneData {
  index: number;
  startTime: number;
  endTime: number;
  duration: number;
  narration: string;
  imagePath: string | null;
  mediaType?: "image" | "video";
}

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export type TransitionType = "zoomBlur" | "fade" | "slide" | "wipe";

export interface TemplateData {
  id: string;
  name: string;
  accent: string;
  accent2: string;
  background: string;
  background2: string;
  text: string;
  muted: string;
  gradient: string;
  font: string;
  transition: TransitionType;
  kenBurns: boolean;
  kenBurnsIntensity: number;
  captionStyle: {
    backgroundColor: string;
    strokeColor: string;
    highlightColor: string;
    accentColor: string;
    fontSize: number;
  };
  hook: {
    flashColor: string;
    keywordColor: string;
  };
  outro: {
    subscribeColor: string;
    tagline: string;
  };
}

export interface InputProps {
  script: ScriptData;
  scenes: SceneData[];
  voiceoverPath: string;
  musicPath: string;
  timestamps: WordTimestamp[];
  bumperDuration: number;
  transitionDuration: number;
  musicVolume: number;
  duckThreshold: number;
  captionFontSize: number;
  template: string;
  templateData: TemplateData;
  sfxEnabled: boolean;
  sfxWhooshPath: string;
  sfxPopPath: string;
  sfxRiserPath: string;
  videoWidth: number;
  videoHeight: number;
  fps: number;
}
