export type ScenePurpose = "hook" | "context" | "core" | "highlight" | "cta";

export type Scene = {
  scene_id: string;
  duration_s: number;
  purpose: ScenePurpose;
  headline: string;
  subline: string;
  icon: string;
  visual_desc: string;
  bg_gradient: string;
  accent_color: string;
  body_lines: string[];
  narration: string;
};

export type VideoScript = {
  title: string;
  total_duration_s: number;
  scenes: Scene[];
};

export type VideoCompositionProps = VideoScript;
