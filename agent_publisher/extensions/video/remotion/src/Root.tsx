import React from "react";
import { Composition, CalculateMetadataFunction } from "remotion";
import { VideoComposition } from "./VideoComposition";
import { VideoCompositionProps } from "./types";

const FPS = 30;
const TRANSITION_FRAMES = 15;

const calculateMetadata: CalculateMetadataFunction<VideoCompositionProps> = ({
  props,
}) => {
  const scenes = props.scenes || [];
  const totalFrames = scenes.reduce((sum, scene) => {
    return sum + Math.round(scene.duration_s * FPS);
  }, 0);
  // Subtract transition frames (one transition per scene boundary)
  const transitionFrames = Math.max(0, scenes.length - 1) * TRANSITION_FRAMES;
  const durationInFrames = Math.max(totalFrames - transitionFrames, FPS * 5);

  return {
    durationInFrames,
    fps: FPS,
    width: 1080,
    height: 1920,
  };
};

const defaultProps: VideoCompositionProps = {
  title: "Sample Video",
  total_duration_s: 60,
  scenes: [
    {
      scene_id: "scene_01",
      duration_s: 6,
      purpose: "hook",
      headline: "AI 正在改变世界",
      subline: "每天有 100 万人使用 AI 工具",
      icon: "🚀",
      visual_desc: "技术浪潮席卷全球",
      bg_gradient: "linear-gradient(160deg, #0f0c29, #302b63, #24243e)",
      accent_color: "#818cf8",
      body_lines: ["2024年，AI 用户突破 10 亿", "增速超过历史上任何技术"],
      narration: "你知道吗？AI 正在以前所未有的速度改变我们的生活方式。",
    },
    {
      scene_id: "scene_02",
      duration_s: 7,
      purpose: "core",
      headline: "三大关键突破",
      subline: "让 AI 从实验室走向大众",
      icon: "⚡",
      visual_desc: "算力、数据、算法三驾马车",
      bg_gradient: "linear-gradient(160deg, #0d1117, #1a1a2e, #16213e)",
      accent_color: "#34d399",
      body_lines: ["算力成本下降 99%", "大模型能力指数级提升", "开源生态爆炸式增长"],
      narration: "这背后有三个关键突破：算力的普及、数据的积累和算法的革命性进步。",
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="VideoComposition"
      component={VideoComposition}
      durationInFrames={180}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
