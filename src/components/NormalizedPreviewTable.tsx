const COLUMNS: { key: string; label: string; num?: boolean }[] = [
  { key: "period_key", label: "Period" },
  { key: "customer_standardized", label: "Customer" },
  { key: "client_market_standardized", label: "Market" },
  { key: "market_level", label: "Level" },
  { key: "upc_normalized", label: "UPC" },
  { key: "item_description_raw", label: "Item description" },
  { key: "category_standardized", label: "Category" },
  { key: "sales_value", label: "Sales", num: true },
  { key: "unit_value", label: "Units", num: true },
  { key: "volume_value", label: "Volume", num: true },
  { key: "mapping_confidence", label: "Conf.", num: true },
  { key: "record_status", label: "Status" },
];

export default function NormalizedPreviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  return (
    <div className="card">
      <h2>Normalized preview</h2>
      <p className="sub">
        First {rows.length} rows after standardizing into the internal schema (one
        row per source row × period).
      </p>
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {COLUMNS.map((c) => {
                  const v = r[c.key];
                  const text =
                    v == null
                      ? "—"
                      : typeof v === "number"
                        ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
                        : String(v);
                  return (
                    <td key={c.key} className={c.num ? "num" : undefined}>
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
