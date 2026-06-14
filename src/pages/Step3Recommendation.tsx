import ComparisonModeBanner from "../components/ComparisonModeBanner";
import DiscoverRecommendationCard from "../components/DiscoverRecommendationCard";
import type { AnalysisResponse } from "../types";

interface Props {
  analysis: AnalysisResponse;
  onContinue: () => void;
}

export default function Step3Recommendation({ analysis, onContinue }: Props) {
  return (
    <>
      <ComparisonModeBanner
        mode={analysis.comparison_mode.mode}
        reasons={analysis.comparison_mode.reasons}
      />
      <DiscoverRecommendationCard rec={analysis.discover_recommendation} />
      <div className="btn-row">
        <button className="btn" onClick={onContinue}>
          I have the Discover export — continue to upload →
        </button>
      </div>
    </>
  );
}
