interface Props {
  mode: string;
  reasons?: string[];
}

export default function ComparisonModeBanner({ mode, reasons = [] }: Props) {
  if (mode === "comparable") {
    return (
      <div className="banner green">
        <strong>Comparable coverage</strong>
        This file appears POS-style. If the Discover export matches the recommended
        grain, the coverage and delta views can be interpreted as a closer
        like-for-like comparison.
      </div>
    );
  }
  if (mode === "directional") {
    return (
      <div className="banner amber">
        <strong>Directional coverage</strong>
        This client file appears shipment-based. NIQ/Discover data is expected to
        represent measured retail sales. Coverage can be evaluated, but sales and
        unit deltas should be interpreted directionally, not as true reconciliation.
        Future versions may include metric conversion or equivalency calculations,
        but v1 does not apply guessed conversion rules.
      </div>
    );
  }
  return (
    <div className="banner red">
      <strong>Coverage run blocked or limited — required fields missing</strong>
      {reasons.length > 0 ? (
        <ul className="tight">
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : (
        "The client file is missing dimensions or metrics needed for a comparison."
      )}
    </div>
  );
}
