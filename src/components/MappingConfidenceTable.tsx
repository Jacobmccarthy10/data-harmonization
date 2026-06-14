import type { ColumnMapping } from "../types";

const ROLE_BADGE: Record<string, { cls: string; label: string }> = {
  mapped: { cls: "green", label: "mapped" },
  metric: { cls: "blue", label: "metric" },
  wide_period: { cls: "blue", label: "period column" },
  auxiliary_metric: { cls: "gray", label: "auxiliary" },
  alternate: { cls: "gray", label: "alternate" },
  ignored: { cls: "gray", label: "ignored" },
  unmapped: { cls: "amber", label: "unmapped" },
};

function confLabel(c: number): string {
  if (c >= 0.9) return "high";
  if (c >= 0.7) return "medium";
  if (c >= 0.5) return "low";
  return "unresolved";
}

export default function MappingConfidenceTable({ mappings }: { mappings: ColumnMapping[] }) {
  // Collapse repeated wide period columns into a single summary row.
  const wide = mappings.filter((m) => m.role === "wide_period");
  const rest = mappings.filter((m) => m.role !== "wide_period");
  const shown = [...rest];

  return (
    <div className="card">
      <h2>Column mapping &amp; confidence</h2>
      <p className="sub">
        How each source column was interpreted as an NIQ-style concept. Confidence
        combines header similarity, sample value patterns, and parse success.
      </p>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Source column</th>
              <th>Detected concept</th>
              <th>Role</th>
              <th>Confidence</th>
              <th>Evidence</th>
              <th>Sample values</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((m) => {
              const role = ROLE_BADGE[m.role] ?? ROLE_BADGE.unmapped;
              return (
                <tr key={m.source_column + m.role}>
                  <td>
                    <code className="field">{m.source_column}</code>
                  </td>
                  <td>{m.concept ?? <span className="muted">—</span>}</td>
                  <td>
                    <span className={`badge ${role.cls}`}>{role.label}</span>
                  </td>
                  <td>
                    {m.confidence > 0 ? (
                      <>
                        <span className="conf-bar">
                          <i style={{ width: `${Math.round(m.confidence * 100)}%` }} />
                        </span>
                        {m.confidence.toFixed(2)}{" "}
                        <span className="muted small">({confLabel(m.confidence)})</span>
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="small muted">{m.evidence}</td>
                  <td className="small muted">{m.sample_values.slice(0, 3).join(" · ")}</td>
                </tr>
              );
            })}
            {wide.length > 0 && (
              <tr>
                <td>
                  <code className="field">{wide.length} wide period columns</code>
                </td>
                <td>period + metric</td>
                <td>
                  <span className="badge blue">unpivoted</span>
                </td>
                <td>0.90</td>
                <td className="small muted">
                  Headers embed a period plus a metric label (e.g.{" "}
                  {wide
                    .slice(0, 3)
                    .map((w) => `“${w.source_column}”`)
                    .join(", ")}
                  …). Each was unpivoted into normalized period rows.
                </td>
                <td />
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
