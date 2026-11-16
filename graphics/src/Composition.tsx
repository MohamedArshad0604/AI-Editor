import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Composition,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type Props = {
  text: string;
  color: string;
};

const calculateMetadata: CalculateMetadataFunction<Props> = () => {
  return {};
};

export const MyComposition = () => {
  return (
    <Composition
      id="KeywordPop"
      component={KeywordPop}
      durationInFrames={45}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ text: "No hours", color: "#FFFFFF" }}
      calculateMetadata={calculateMetadata}
    />
  );
};

// A keyword that swipes in on a highlight bar, pops slightly, then fades out.
// Sits in the upper third so it does not collide with the centered captions.
export const KeywordPop: React.FC<Props> = ({ text, color }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const pop = spring({ frame, fps, config: { damping: 12, stiffness: 160 } });
  const scale = interpolate(pop, [0, 1], [0.85, 1]);

  // Bar wipes in from the left over the first 8 frames
  const reveal = interpolate(frame, [0, 8], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Fade out over the last 8 frames
  const opacity = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: "center",
        paddingTop: 520,
        opacity,
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          clipPath: `inset(0 ${reveal}% 0 0)`,
          backgroundColor: color,
          color: "#111111",
          fontFamily: "Arial, Helvetica, sans-serif",
          fontWeight: 900,
          fontSize: 120,
          textTransform: "uppercase",
          padding: "14px 48px",
          borderRadius: 12,
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
