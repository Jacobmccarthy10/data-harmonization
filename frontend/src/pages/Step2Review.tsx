import ClientProfileSummary from "../components/ClientProfileSummary";
import ComparisonModeBanner from "../components/ComparisonModeBanner";
import MappingConfidenceTable from "../components/MappingConfidenceTable";
import NormalizedPreviewTable from "../components/NormalizedPreviewTable";
import type { AnalysisResponse } from "../types";

interface Props {
  analysis: AnalysisResponse;
  onContinue: () => void;
  onRestart: () => void;
}

export default function Step2Review({ analysis, onContinue, onRestart }: Props) {
  const mode = analysis.comparison_mode;
  return (
    <>
      <ComparisonModeBanner mode={mode.mode} reasons={mode.reasons} />
      <ClientProfileSummary analysis={analysis} />
      <MappingConfidenceTable mappings={analysis.column_mapping_summary} />
      <NormalizedPreviewTable rows={analysis.normalized_preview} />
      <div className="btn-row">
        <button className="btn" onClick={onContinue}>
          Continue to Discover recommendation →
        </button>
        <button className="btn secondary" onClick={onRestart}>
          Start over with a different file
        </button>
      </div>
    </>
  );
}
