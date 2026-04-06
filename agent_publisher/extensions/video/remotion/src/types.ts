export type ScenePurpose = "hook" | "context" | "core" | "highlight" | "cta";

export type SubtitleWord = {
  text: string;
  start_ms: number;
  end_ms: number;
};

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
  // TTS fields (added by pipeline)
  audio_url?: string;           // absolute URL served by FastAPI, e.g. /api/extensions/video/audio/{task_id}/{scene_id}
  subtitles?: SubtitleWord[];   // word-level timestamps from edge-tts
};

export type VideoScript = {
  title: string;
  total_duration_s: number;
  scenes: Scene[];
};

export type VideoCompositionProps = VideoScript;
