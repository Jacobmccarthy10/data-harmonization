import type { DiscoverRecommendation } from "../types";

export default function DiscoverRecommendationCard({ rec }: { rec: DiscoverRecommendation }) {
  return (
    <div className="card">
      <h2>Recommended Discover pull</h2>
      <p className="sub">
        Based on what was detected in the client file, pull the following from
        Discover, then export it and upload it in the next step. This
        recommendation is on-screen only in v1 — no template download, no API pull.
      </p>

      <div className="grid-2">
        <div>
          <dl className="facts">
            <dt>Country</dt>
            <dd>{rec.country}</dd>
            <dt>Dataset</dt>
            <dd>{rec.recommended_dataset}</dd>
            <dt>Retailer / customer</dt>
            <dd>
              {rec.customer_scope.length > 0
                ? `${rec.customer_scope.join(", ")} — or closest available ${rec.customer_scope[0]} market selections`
                : "Closest available retailer selection"}
            </dd>
            <dt>Market</dt>
            <dd>
              <ul className="tight">
                {rec.market_scope.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </dd>
            <dt>Category</dt>
            <dd>
              <div className="pill-list">
                {rec.category_scope.map((c) => (
                  <span className="pill" key={c}>
                    {c}
                  </span>
                ))}
                {rec.category_scope.length === 0 && "Infer from product mix"}
              </div>
            </dd>
            <dt>Manufacturer</dt>
            <dd>
              {rec.manufacturer_scope.join(", ") || "Inferred from client product mix"}
            </dd>
            {rec.brand_scope.length > 0 && (
              <>
                <dt>Brands</dt>
                <dd>
                  <div className="pill-list">
                    {rec.brand_scope.map((b) => (
                      <span className="pill" key={b}>
                        {b}
                      </span>
                    ))}
                  </div>
                </dd>
              </>
            )}
          </dl>
        </div>
        <div>
          <dl className="facts">
            <dt>Time period</dt>
            <dd>
              {rec.period_start ?? "?"} → {rec.period_end ?? "?"}
              <br />
              <span className="badge blue">{rec.time_grain} grain</span>
            </dd>
            <dt>Product grain</dt>
            <dd>{rec.product_grain}</dd>
            <dt>Required measures</dt>
            <dd>
              <ul className="tight">
                {rec.required_measures.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </dd>
            <dt>Required Discover fields</dt>
            <dd>
              <div className="pill-list">
                {rec.required_discover_fields.map((f) => (
                  <code className="field" key={f}>
                    {f}
                  </code>
                ))}
              </div>
              <div className="muted small" style={{ marginTop: 6 }}>
                Optional: {rec.optional_discover_fields.join(", ")}
              </div>
            </dd>
          </dl>
        </div>
      </div>

      <h3>Caveats</h3>
      <ul className="tight">
        {rec.caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </div>
  );
}
