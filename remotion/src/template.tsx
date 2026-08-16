import React, { createContext, useContext } from "react";
import type { TemplateData } from "./types";

export const DEFAULT_TEMPLATE: TemplateData = {
  id: "premium",
  name: "Premium Bold",
  accent: "#4caf50",
  accent2: "#81c784",
  background: "#0a0a0a",
  background2: "#141414",
  text: "#ffffff",
  muted: "#aaaaaa",
  gradient: "135deg, #0a0a0a 0%, #1a1a1a 50%, #0d2b0d 100%",
  font: "'Segoe UI', -apple-system, Roboto, Helvetica, Arial, sans-serif",
  transition: "zoomBlur",
  kenBurns: true,
  kenBurnsIntensity: 1.1,
  captionStyle: {
    backgroundColor: "rgba(0, 0, 0, 0.55)",
    strokeColor: "rgba(0, 0, 0, 0.85)",
    highlightColor: "#ffffff",
    accentColor: "#4caf50",
    fontSize: 34,
  },
  hook: {
    flashColor: "rgba(255, 255, 255, 0.5)",
    keywordColor: "#ffd54f",
  },
  outro: {
    subscribeColor: "#4caf50",
    tagline: "Follow for more",
  },
};

const TemplateContext = createContext<TemplateData>(DEFAULT_TEMPLATE);

function mergeTemplate(data?: TemplateData): TemplateData {
  if (!data || typeof data !== "object") return DEFAULT_TEMPLATE;
  return {
    ...DEFAULT_TEMPLATE,
    ...data,
    captionStyle: { ...DEFAULT_TEMPLATE.captionStyle, ...data.captionStyle },
    hook: { ...DEFAULT_TEMPLATE.hook, ...data.hook },
    outro: { ...DEFAULT_TEMPLATE.outro, ...data.outro },
  };
}

export const TemplateProvider: React.FC<{
  data?: TemplateData;
  children: React.ReactNode;
}> = ({ data, children }) => {
  const template = React.useMemo(() => mergeTemplate(data), [data]);
  return (
    <TemplateContext.Provider value={template}>
      {children}
    </TemplateContext.Provider>
  );
};

export const useTemplate = (): TemplateData => useContext(TemplateContext);
