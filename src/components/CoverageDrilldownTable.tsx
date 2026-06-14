import { useMemo, useState } from "react";
import type { DrilldownRow } from "../types";

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
  return v == null ? "—" : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
function num(v: number | null): string {
  return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function uniq(values: (string | null)[]): string[] {
  return Array.from(new Set(values.filter((v): v is string => v != null))).sort();
}

const PAGE = 100;

export default function CoverageDrilldownTable({ rows }: { rows: DrilldownRow[] }) {
  const [status, setStatus] = useState("");
  const [period, setPeriod] = useState("");
  const [market, setMarket] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(PAGE);

  const options = useMemo(
    () => ({
      status: uniq(rows.map((r) => r.status)),
      period: uniq(rows.map((r) => r.period)),
      market: uniq(rows.map((r) => r.market)),
      category: uniq(rows.map((r) => r.category)),
      brand: uniq(rows.map((r) => r.brand)),
    }),
    [rows],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (!status || r.status === status) &&
        (!period || r.period === period) &&
        (!market || r.market === market) &&
        (!category || r.category === category) &&
        (!brand || r.brand === brand) &&
        (!q ||
          (r.client_item_description ?? "").toLowerCase().includes(q) ||
          (r.discover_item_description ?? "").toLowerCase().includes(q) ||
          (r.client_upc ?? "").includes(q) ||
          (r.discover_upc ?? "").includes(q)),
    );
  }, [rows, status, period, market, category, brand, search]);

  const shown = filtered.slice(0, limit);

  const sel = (
    value: string,
    set: (v: string) => void,
    opts: string[],
    label: string,
  ) => (
    <select
      value={value}
      onChange={(e) => {
        set(e.target.value);
        setLimit(PAGE);
      }}
    >
      <option value="">{label}: all</option>
      {opts.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );

  return (
    <div className="card">
      <h2>Drill-down</h2>
      <p className="sub">
        Comparison grain: UPC/item × period × customer × market. {filtered.length.toLocaleString()}{" "}
        of {rows.length.toLocaleString()} rows match the current filters.
      </p>
      <div className="filters">
        {sel(status, setStatus, options.status, "Status")}
        {sel(period, setPeriod, options.period, "Period")}
        {sel(market, setMarket, options.market, "Market")}
        {sel(category, setCategory, options.category, "Category")}
        {options.brand.length > 0 && sel(brand, setBrand, options.brand, "Brand")}
        <input
          placeholder="Search item / UPC…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setLimit(PAGE);
          }}
        />
      </div>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Status</th>
              <th>Period</th>
              <th>Market</th>
              <th>Client UPC</th>
              <th>Client item</th>
              <th>Discover item</th>
              <th className="num">Client sales</th>
              <th className="num">NIQ sales</th>
              <th className="num">Δ Sales</th>
              <th className="num">Client units</th>
              <th className="num">NIQ units</th>
              <th className="num">Δ Units</th>
              <th className="num">Conf.</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i}>
                <td>
                  <span className={`badge ${STATUS_BADGE[r.status] ?? "gray"}`}>{r.status}</span>
                </td>
                <td>{r.period ?? "—"}</td>
                <td>{r.market ?? "—"}</td>
                <td>{r.client_upc ?? "—"}</td>
                <td>{r.client_item_description ?? "—"}</td>
                <td>{r.discover_item_description ?? "—"}</td>
                <td className="num">{money(r.client_sales)}</td>
                <td className="num">{money(r.discover_sales)}</td>
                <td className="num">{money(r.sales_delta)}</td>
                <td className="num">{num(r.client_units)}</td>
                <td className="num">{num(r.discover_units)}</td>
                <td className="num">{num(r.unit_delta)}</td>
                <td className="num">{r.match_confidence ?? "—"}</td>
                <td className="small muted">{r.exception_reason ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > shown.length && (
        <div className="btn-row">
          <button className="btn secondary" onClick={() => setLimit(limit + PAGE)}>
            Show more ({(filtered.length - shown.length).toLocaleString()} remaining)
          </button>
        </div>
      )}
    </div>
  );
}
