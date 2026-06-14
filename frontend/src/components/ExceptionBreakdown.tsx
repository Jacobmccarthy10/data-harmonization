import type { ExceptionRow } from "../types";

const STATUS_BADGE: Record<string, string> = {
  matched: "green",
  matched_with_caveat: "blue",
  low_confidence_product_match: "amber",
  missing_from_discover: "amber",
  missing_from_client: "gray",
  market_mismatch: "amber",
  period_mismatch: "amber",
  metric_mismatch: "red",
  not_comparable: "red",
  needs_review: "red",
};

function money(v: number | null): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

export default function ExceptionBreakdown({ exceptions }: { exceptions: ExceptionRow[] }) {
  const totalRows = exceptions
    .filter((e) => e.status !== "missing_from_client")
    .reduce((s, e) => s + e.rows, 0);

  return (
    <div className="card">
      <h2>Exception breakdown</h2>
      <p className="sub">
        Client rows by coverage status, with the sales value tied to each status.
        “Missing from client” counts Discover item/periods with no client counterpart.
      </p>
      <table className="tbl">
        <thead>
          <tr>
            <th>Status</th>
            <th className="num">Rows</th>
            <th className="num">% of rows</th>
            <th className="num">Client sales</th>
            <th className="num">NIQ sales</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {exceptions.map((e) => (
            <tr key={e.status}>
              <td>
                <span className={`badge ${STATUS_BADGE[e.status] ?? "gray"}`}>{e.status}</span>
              </td>
              <td className="num">{e.rows.toLocaleString()}</td>
              <td className="num">
                {e.status === "missing_from_client" || totalRows === 0
                  ? "—"
                  : `${((e.rows / totalRows) * 100).toFixed(1)}%`}
              </td>
              <td className="num">{money(e.client_sales)}</td>
              <td className="num">{money(e.niq_sales)}</td>
              <td className="small muted">{e.note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
