import React from "react";
import {
  TransitionSeries,
  linearTiming,
  springTiming,
} from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { useVideoConfig } from "remotion";
import { VideoCompositionProps } from "./types";
import { SceneComponent } from "./SceneComponent";

const TRANSITION_DURATION_FRAMES = 15;

export const VideoComposition: React.FC<VideoCompositionProps> = (props) => {
  const { fps } = useVideoConfig();
  const { scenes } = props;

  return (
    <TransitionSeries>
      {scenes.map((scene, i) => {
        const durationInFrames = Math.round(scene.duration_s * fps);
        // Alternate between fade and slide transitions for variety
        const isEven = i % 2 === 0;

        return (
          <React.Fragment key={scene.scene_id}>
            <TransitionSeries.Sequence
              durationInFrames={durationInFrames}
              premountFor={TRANSITION_DURATION_FRAMES}
            >
              <SceneComponent scene={scene} />
            </TransitionSeries.Sequence>

            {/* Add transition between scenes (not after last scene) */}
            {i < scenes.length - 1 && (
              <TransitionSeries.Transition
                presentation={
                  isEven
                    ? fade()
                    : slide({ direction: "from-right" })
                }
                timing={linearTiming({ durationInFrames: TRANSITION_DURATION_FRAMES })}
              />
            )}
          </React.Fragment>
        );
      })}
    </TransitionSeries>
  );
};
