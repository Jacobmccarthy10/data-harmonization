import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendPoint } from "../types";

function moneyTick(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v}`;
}

export default function CoverageTrendChart({
  trend,
  grain,
  directional,
}: {
  trend: TrendPoint[];
  grain: string;
  directional: boolean;
}) {
  const hasUnits = trend.some((t) => t.client_units != null);
  const [measure, setMeasure] = useState<"sales" | "units">("sales");
  const data = trend.map((t) => ({
    ...t,
    coverage_pct: Math.round(t.coverage_rate * 1000) / 10,
  }));

  return (
    <div className="card">
      <h2>
        Trend by {grain === "monthly" ? "month" : "week"}{" "}
        {directional && <span className="badge amber">directional</span>}
      </h2>
      <p className="sub">
        Client reported {measure} vs NIQ comparable {measure}, with{" "}
        {directional ? "directional " : ""}delta and coverage rate per period.
      </p>
      {hasUnits && (
        <div className="filters">
          <select value={measure} onChange={(e) => setMeasure(e.target.value as "sales" | "units")}>
            <option value="sales">Sales</option>
            <option value="units">Units</option>
          </select>
        </div>
      )}
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid stroke="#edf0f4" vertical={false} />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis
            yAxisId="value"
            tickFormatter={measure === "sales" ? moneyTick : (v: number) => v.toLocaleString()}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            yAxisId="rate"
            orientation="right"
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            formatter={(value: number | string, name: string) => {
              if (name === "Coverage rate") return [`${value}%`, name];
              if (measure === "sales" && typeof value === "number")
                return [moneyTick(value), name];
              return [typeof value === "number" ? value.toLocaleString() : value, name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {measure === "sales" ? (
            <>
              <Bar yAxisId="value" dataKey="client_sales" name="Client sales" fill="#0a1a5c" radius={[4, 4, 0, 0]} />
              <Bar yAxisId="value" dataKey="niq_sales" name="NIQ comparable sales" fill="#2c5df2" radius={[4, 4, 0, 0]} />
              <Line
                yAxisId="value"
                dataKey="sales_delta"
                name={directional ? "Directional sales delta" : "Sales delta"}
                stroke="#e85a1f"
                strokeWidth={2.5}
                dot={{ r: 3 }}
              />
            </>
          ) : (
            <>
              <Bar yAxisId="value" dataKey="client_units" name="Client units" fill="#0a1a5c" radius={[4, 4, 0, 0]} />
              <Bar yAxisId="value" dataKey="niq_units" name="NIQ comparable units" fill="#2c5df2" radius={[4, 4, 0, 0]} />
            </>
          )}
          <Line
            yAxisId="rate"
            dataKey="coverage_pct"
            name="Coverage rate"
            stroke="#3dbeeb"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
