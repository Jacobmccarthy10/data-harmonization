import ComparisonModeBanner from "../components/ComparisonModeBanner";
import CoverageDrilldownTable from "../components/CoverageDrilldownTable";
import CoverageKpiCards from "../components/CoverageKpiCards";
import CoverageTrendChart from "../components/CoverageTrendChart";
import ExceptionBreakdown from "../components/ExceptionBreakdown";
import ExportButtons from "../components/ExportButtons";
import MatchDiagnostics from "../components/MatchDiagnostics";
import type { CoverageResponse } from "../types";

interface Props {
  coverage: CoverageResponse;
  analysisId: string;
  onRestart: () => void;
}

export default function Step5Dashboard({ coverage, analysisId, onRestart }: Props) {
  if (coverage.blocked) {
    return (
      <>
        <div className="banner red">
          <strong>Coverage run blocked or limited — required fields missing</strong>
          <ul className="tight">
            {coverage.blocked_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
        <div className="btn-row">
          <button className="btn secondary" onClick={onRestart}>
            Start over with a different file
          </button>
        </div>
      </>
    );
  }

  const summary = coverage.coverage_summary;
  const directional = coverage.kpis.delta_label === "directional";

  return (
    <>
      <ComparisonModeBanner mode={summary.comparison_mode} />

      <div className="card" style={{ paddingBottom: 14 }}>
        <h2>Coverage summary</h2>
        <p className="sub">
          Match grain: {summary.match_grain} · Time grain: {summary.time_grain}
        </p>
        <dl className="facts">
          <dt>Customer alignment</dt>
          <dd>
            {Object.entries(summary.customer_alignment)
              .map(([c, d]) => `${c} → ${d}`)
              .join("; ") || "—"}
          </dd>
          <dt>Market alignment</dt>
          <dd>
            {summary.market_rollup_mode
              ? "All client markets rolled up to the Discover total (caveat applied)"
              : Object.entries(summary.market_alignment)
                  .map(([c, d]) => `${c} → ${d}`)
                  .join("; ") || "—"}
          </dd>
          {summary.unmapped_client_markets.length > 0 && (
            <>
              <dt>Unmapped client markets</dt>
              <dd>
                <div className="pill-list">
                  {summary.unmapped_client_markets.map((m) => (
                    <span className="pill" key={m}>
                      {m}
                    </span>
                  ))}
                </div>
                <div className="muted small" style={{ marginTop: 4 }}>
                  These client-specific regions have no NIQ market mapping yet; their
                  rows are flagged market_mismatch.
                </div>
              </dd>
            </>
          )}
        </dl>
        {summary.warnings.length > 0 && (
          <ul className="tight muted">
            {summary.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
      </div>

      <CoverageKpiCards kpis={coverage.kpis} />
      <div style={{ height: 18 }} />
      <CoverageTrendChart
        trend={coverage.trend}
        grain={summary.time_grain}
        directional={directional}
      />
      <ExceptionBreakdown exceptions={coverage.exceptions} />
      {(coverage.coverage_summary.brand_diagnostic?.length > 0 ||
        coverage.coverage_summary.period_diagnostic?.length > 0) && (
        <MatchDiagnostics
          brands={coverage.coverage_summary.brand_diagnostic ?? []}
          periods={coverage.coverage_summary.period_diagnostic ?? []}
          brandOverlap={coverage.coverage_summary.brand_overlap_diagnostic}
          brandAliases={coverage.coverage_summary.brand_alias_map ?? {}}
        />
      )}
      <CoverageDrilldownTable rows={coverage.drilldown} />
      <ExportButtons analysisId={analysisId} coverageId={coverage.coverage_id} />
      <div className="btn-row">
        <button className="btn secondary" onClick={onRestart}>
          Start a new coverage workflow
        </button>
      </div>
    </>
  );
}
