import { useState } from "react";
import type { BrandDiagRow, BrandOverlapDiag, PeriodDiagRow } from "../types";

function money(v: number | null): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}
function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}
function badgeForRate(rate: number): string {
  if (rate >= 0.95) return "green";
  if (rate >= 0.5) return "amber";
  if (rate > 0) return "amber";
  return "red";
}

interface Props {
  brands: BrandDiagRow[];
  periods: PeriodDiagRow[];
  brandOverlap: BrandOverlapDiag;
  brandAliases: Record<string, string>;
}

export default function MatchDiagnostics({ brands, periods, brandOverlap, brandAliases }: Props) {
  const [showAllBrands, setShowAllBrands] = useState(false);
  const aliasEntries = Object.entries(brandAliases || {});
  const unmatchedBrands = brands.filter((b) => b.match_rate === 0);
  const matchedBrands = brands.filter((b) => b.match_rate > 0);
  const visibleBrands = showAllBrands
    ? brands
    : [...matchedBrands.slice(0, 10), ...unmatchedBrands.slice(0, 10)];

  return (
    <div className="card">
      <h2>What matched and what didn’t</h2>
      <p className="sub">
        Per-brand and per-period diagnostics so you can see exactly where coverage is
        coming from and what to investigate. Brand fuzzy aliases (e.g. client
        “smartwater” → Discover “glaceau smart water”) are listed below.
      </p>

      <div className="grid-2">
        <div>
          <h3>By brand (KPI scope)</h3>
          <p className="muted small" style={{ marginTop: 0, marginBottom: 8 }}>
            {brandOverlap.client_brand_count} client brands · {brandOverlap.discover_brand_count}{" "}
            Discover brands · {brandOverlap.overlap_count} direct overlap (more reached via fuzzy)
          </p>
          <div className="tbl-scroll" style={{ maxHeight: 340 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Brand</th>
                  <th className="num">Client sales</th>
                  <th className="num">Match rate</th>
                  <th className="num">Rows</th>
                </tr>
              </thead>
              <tbody>
                {visibleBrands.map((b) => (
                  <tr key={b.brand}>
                    <td>{b.brand}</td>
                    <td className="num">{money(b.client_sales)}</td>
                    <td className="num">
                      <span className={`badge ${badgeForRate(b.match_rate)}`}>
                        {pct(b.match_rate)}
                      </span>
                    </td>
                    <td className="num small muted">
                      {b.matched_rows}/{b.client_rows}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {brands.length > visibleBrands.length && (
            <button
              className="btn secondary"
              style={{ marginTop: 8 }}
              onClick={() => setShowAllBrands((v) => !v)}
            >
              {showAllBrands
                ? "Show top brands only"
                : `Show all ${brands.length} brands`}
            </button>
          )}
        </div>

        <div>
          <h3>By period</h3>
          <p className="muted small" style={{ marginTop: 0, marginBottom: 8 }}>
            How well each period of the client file matched Discover. Consistent low rates
            across periods usually means a brand-scope gap; one-off low periods usually
            mean missing Discover data for that week/month.
          </p>
          <div className="tbl-scroll" style={{ maxHeight: 340 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Period</th>
                  <th className="num">Client sales</th>
                  <th className="num">Matched</th>
                  <th className="num">Match rate</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((p) => (
                  <tr key={p.period}>
                    <td>{p.period}</td>
                    <td className="num">{money(p.client_sales)}</td>
                    <td className="num">{money(p.matched_client_sales)}</td>
                    <td className="num">
                      <span className={`badge ${badgeForRate(p.match_rate)}`}>
                        {pct(p.match_rate)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {aliasEntries.length > 0 && (
        <>
          <h3>Brand fuzzy aliases applied</h3>
          <p className="muted small" style={{ marginTop: 0, marginBottom: 8 }}>
            Client brand labels that matched a Discover brand via fuzzy/partial-ratio
            comparison (not exact string match). Useful when client and NIQ use slightly
            different conventions (e.g. client “smartwater”, Discover “Glaceau Smart
            Water”).
          </p>
          <div className="tbl-scroll" style={{ maxHeight: 220 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Client brand</th>
                  <th>Discover brand</th>
                </tr>
              </thead>
              <tbody>
                {aliasEntries.map(([c, d]) => (
                  <tr key={c}>
                    <td>{c}</td>
                    <td>{d}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
