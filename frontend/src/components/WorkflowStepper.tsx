const STEPS = [
  "Upload Client File",
  "Review Detected Structure",
  "Discover Pull Recommendation",
  "Upload Discover Export",
  "Coverage Dashboard",
];

interface Props {
  current: number; // 0-based
  maxReached: number;
  onNavigate: (step: number) => void;
}

export default function WorkflowStepper({ current, maxReached, onNavigate }: Props) {
  return (
    <div className="stepper">
      {STEPS.map((label, i) => {
        const cls =
          i === current ? "step active" : i <= maxReached ? "step done" : "step disabled";
        return (
          <div
            key={label}
            className={cls}
            onClick={() => i <= maxReached && onNavigate(i)}
            role="button"
          >
            <span className="num">{i + 1}</span>
            {label}
          </div>
        );
      })}
    </div>
  );
}
