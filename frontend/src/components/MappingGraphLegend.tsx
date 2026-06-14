import type {
  MappingGraphBusinessArea,
  MappingGraphConfidenceBand,
  MappingGraphNodeType,
} from "../types";

const NODE_TYPES: { key: MappingGraphNodeType; label: string }[] = [
  { key: "client_field", label: "Client field" },
  { key: "interpreted_meaning", label: "Interpreted meaning" },
  { key: "niq_field", label: "NIQ field" },
  { key: "rule", label: "Rule" },
  { key: "exception", label: "Exception" },
];

const AREAS: { key: MappingGraphBusinessArea; label: string }[] = [
  { key: "product", label: "Product" },
  { key: "geography", label: "Geography" },
  { key: "time", label: "Time" },
  { key: "metrics", label: "Metrics" },
  { key: "exceptions", label: "Exceptions" },
];

const CONFIDENCE: { key: MappingGraphConfidenceBand; label: string }[] = [
  { key: "high", label: "High" },
  { key: "medium", label: "Medium" },
  { key: "low", label: "Low" },
  { key: "needs_review", label: "Needs review" },
  { key: "none", label: "No score" },
];

export default function MappingGraphLegend() {
  return (
    <div className="mapping-legend">
      <div>
        <strong>Node types</strong>
        <div className="legend-row">
          {NODE_TYPES.map((item) => (
            <span className={`legend-chip node-${item.key}`} key={item.key}>
              {item.label}
            </span>
          ))}
        </div>
      </div>
      <div>
        <strong>Business areas</strong>
        <div className="legend-row">
          {AREAS.map((item) => (
            <span className={`legend-chip area-${item.key}`} key={item.key}>
              {item.label}
            </span>
          ))}
        </div>
      </div>
      <div>
        <strong>Confidence</strong>
        <div className="legend-row">
          {CONFIDENCE.map((item) => (
            <span className={`legend-chip confidence-${item.key}`} key={item.key}>
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
