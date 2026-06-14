import type { CoverageKpis } from "../types";

function money(v: number | null | undefined): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const fmt =
    abs >= 1_000_000
      ? `$${(v / 1_000_000).toFixed(2)}M`
      : abs >= 1_000
        ? `$${(v / 1_000).toFixed(1)}K`
        : `$${v.toFixed(0)}`;
  return fmt;
}

function count(v: number | null | undefined): string {
  return v == null ? "—" : v.toLocaleString();
}

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}

interface Kpi {
  label: string;
  value: string;
  detail?: string;
  tone?: "pos" | "neg";
}

export default function CoverageKpiCards({ kpis }: { kpis: CoverageKpis }) {
  const directional = kpis.delta_label === "directional";
  const dl = directional ? "Directional " : "";
  const hasUnits = kpis.client_units_uploaded != null;

  const cards: Kpi[] = [
    {
      label: "Total client rows",
      value: count(kpis.total_client_rows),
      detail: `${count(kpis.matched_rows)} matched`,
    },
    {
      label: "Row coverage",
      value: pct(kpis.row_coverage_pct),
      detail: `Comparison scope: ${pct(kpis.kpi_slice_row_coverage_pct)} of ${count(kpis.kpi_slice_rows)} rows`,
    },
    {
      label: "Client sales uploaded",
      value: money(kpis.client_sales_uploaded),
      detail: kpis.kpi_slice_note ? "total-level rows" : undefined,
    },
    {
      label: "Sales coverage",
      value: pct(kpis.sales_coverage_pct),
      detail: `${money(kpis.matched_client_sales)} matched`,
    },
    {
      label: "NIQ comparable sales",
      value: money(kpis.niq_comparable_sales),
    },
    {
      label: `${dl}Sales delta`,
      value: money(kpis.sales_delta),
      tone: kpis.sales_delta != null ? (kpis.sales_delta >= 0 ? "pos" : "neg") : undefined,
      detail: "client − NIQ on matched scope",
    },
  ];

  if (hasUnits) {
    cards.push(
      {
        label: "Client units uploaded",
        value: count(kpis.client_units_uploaded),
      },
      {
        label: "Unit coverage",
        value: pct(kpis.unit_coverage_pct),
        detail: `${count(kpis.matched_client_units)} matched`,
      },
      {
        label: `${dl}Unit delta`,
        value: count(kpis.unit_delta),
        tone: kpis.unit_delta != null ? (kpis.unit_delta >= 0 ? "pos" : "neg") : undefined,
      },
    );
  }

  cards.push(
    {
      label: "Rows needing review",
      value: count(kpis.rows_needing_review),
    },
    {
      label: "Uncovered / not comparable value",
      value: money(kpis.uncovered_sales),
    },
  );

  return (
    <>
      <div className="kpi-grid">
        {cards.map((c) => (
          <div className="kpi" key={c.label}>
            <div className="label">{c.label}</div>
            <div className={`value ${c.tone ?? ""}`}>{c.value}</div>
            {c.detail && <div className="detail">{c.detail}</div>}
          </div>
        ))}
      </div>
      {kpis.kpi_slice_note && (
        <p className="muted small" style={{ marginTop: 10 }}>
          {kpis.kpi_slice_note}
        </p>
      )}
    </>
  );
}
