import type { AnalysisResponse } from "../types";

function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}

const GRAIN_BADGE: Record<string, string> = {
  weekly: "blue",
  monthly: "blue",
  unknown: "amber",
};
const STRUCTURE_BADGE: Record<string, string> = {
  long: "green",
  wide: "green",
  mixed: "green",
  unknown: "amber",
};

export default function ClientProfileSummary({ analysis }: { analysis: AnalysisResponse }) {
  const p = analysis.client_profile;
  const q = analysis.quality_summary;
  const sd = analysis.schema_detection;
  const fp = analysis.file_profile;

  return (
    <div className="card">
      <h2>Detected client file profile</h2>
      <p className="sub">
        The app detected the likely structure of the client file and generated a
        recommended Discover pull for coverage evaluation. Review the detection
        below — this step is read-only in v1.
      </p>

      <div className="grid-2">
        <div>
          <h3>File</h3>
          <dl className="facts">
            <dt>File</dt>
            <dd>
              {fp.file_name}
              {fp.sheet_used ? (
                <span className="muted small"> — sheet “{fp.sheet_used}”</span>
              ) : null}
            </dd>
            <dt>Rows × columns</dt>
            <dd>
              {fp.rows.toLocaleString()} × {fp.columns}
            </dd>
            <dt>Structure</dt>
            <dd>
              <span className={`badge ${STRUCTURE_BADGE[sd.structure_type] ?? "gray"}`}>
                {sd.structure_type}
              </span>
              {sd.wide_period_columns > 0 && (
                <span className="muted small">
                  {" "}
                  {sd.wide_period_columns} period columns unpivoted
                </span>
              )}
            </dd>
            <dt>Time grain</dt>
            <dd>
              <span className={`badge ${GRAIN_BADGE[p.time_grain] ?? "gray"}`}>{p.time_grain}</span>
            </dd>
            <dt>Period range</dt>
            <dd>
              {p.period_start ?? "—"} → {p.period_end ?? "—"} ({q.distinct_periods} periods)
            </dd>
            <dt>Business type</dt>
            <dd>
              <span className={`badge ${sd.business_type === "pos" ? "green" : sd.business_type === "shipment" ? "amber" : "gray"}`}>
                {sd.business_type === "pos"
                  ? "POS-style"
                  : sd.business_type === "shipment"
                    ? "shipment-style"
                    : "unknown"}
              </span>
            </dd>
          </dl>

          <h3>Quality</h3>
          <dl className="facts">
            <dt>Periods parsed</dt>
            <dd>{fmtPct(q.period_parse_rate)}</dd>
            <dt>Valid UPC/GTIN values</dt>
            <dd>{fmtPct(q.upc_valid_rate)}</dd>
            <dt>Rows with sales values</dt>
            <dd>{fmtPct(q.sales_present_rate)}</dd>
            <dt>Rows needing review</dt>
            <dd>{q.rows_needing_review.toLocaleString()}</dd>
          </dl>
        </div>

        <div>
          <h3>Business scope</h3>
          <dl className="facts">
            <dt>Retailer / customer</dt>
            <dd>{p.customer ?? "—"}</dd>
            <dt>Manufacturer scope</dt>
            <dd>{p.manufacturers.map((m) => m.value).join(", ") || "—"}</dd>
            <dt>Category universe</dt>
            <dd>
              <div className="pill-list">
                {p.categories.slice(0, 8).map((c) => (
                  <span className="pill" key={c.value}>
                    {c.value}
                  </span>
                ))}
                {p.categories.length === 0 && "—"}
              </div>
            </dd>
            {p.brands.length > 0 && (
              <>
                <dt>Brands detected</dt>
                <dd>
                  <div className="pill-list">
                    {p.brands.slice(0, 8).map((b) => (
                      <span className="pill" key={b.value}>
                        {b.value}
                      </span>
                    ))}
                  </div>
                </dd>
              </>
            )}
            <dt>Products</dt>
            <dd>{p.distinct_products.toLocaleString()} distinct items</dd>
            <dt>Product key fields</dt>
            <dd>
              {p.product_identifier_fields.map((f) => (
                <code className="field" key={f}>
                  {f}
                </code>
              ))}
            </dd>
            <dt>Description fields</dt>
            <dd>
              {p.description_fields.map((f) => (
                <code className="field" key={f}>
                  {f}
                </code>
              ))}
            </dd>
          </dl>

          <h3>Client markets / regions</h3>
          <div className="pill-list">
            {p.markets.map((m) => (
              <span className={m.total_like ? "pill total" : "pill"} key={m.value} title={`${m.rows} rows`}>
                {m.value}
                {m.total_like ? " (total-level)" : ""}
              </span>
            ))}
          </div>
        </div>
      </div>

      {(q.warnings.length > 0 || fp.notes.length > 0) && (
        <>
          <h3>Exceptions &amp; warnings</h3>
          <ul className="tight">
            {fp.notes.map((n) => (
              <li key={n} className="muted">
                {n}
              </li>
            ))}
            {q.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
