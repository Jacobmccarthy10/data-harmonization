import type { MappingGraphData, MappingGraphException, MappingGraphNode } from "../types";

function typeLabel(type: MappingGraphNode["type"]): string {
  return type.replace(/_/g, " ");
}

function valueToText(value: unknown): string {
  if (Array.isArray(value)) return value.join(" | ");
  if (value == null) return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (Math.abs(value) <= 1 && !Number.isInteger(value)) return `${Math.round(value * 100)}%`;
    return value.toLocaleString();
  }
  return String(value);
}

function severityClass(severity: MappingGraphException["severity"] | MappingGraphNode["severity"]): string {
  if (severity === "critical") return "red";
  if (severity === "warning") return "amber";
  return "blue";
}

interface Props {
  graph: MappingGraphData;
  selectedNode: MappingGraphNode | null;
  onSelectNode: (id: string) => void;
  onClearSelection: () => void;
}

export default function MappingGraphSidePanel({
  graph,
  selectedNode,
  onSelectNode,
  onClearSelection,
}: Props) {
  if (selectedNode) {
    const detailEntries = Object.entries(selectedNode.details ?? {});
    const linkedExceptions = graph.exceptions.filter((e) => e.linkedNodeId === selectedNode.id);

    return (
      <aside className="mapping-side-panel">
        <div className="side-panel-header">
          <div>
            <span className={`badge ${severityClass(selectedNode.severity)}`}>
              {typeLabel(selectedNode.type)}
            </span>
            <h2>{selectedNode.label}</h2>
          </div>
          <button className="link-button" onClick={onClearSelection}>
            Clear
          </button>
        </div>

        {selectedNode.description && <p className="sub">{selectedNode.description}</p>}

        <dl className="facts side-facts">
          <dt>Business area</dt>
          <dd>{selectedNode.businessArea}</dd>
          <dt>Confidence</dt>
          <dd>
            {selectedNode.confidence == null
              ? selectedNode.confidenceBand ?? "No score"
              : `${Math.round(selectedNode.confidence * 100)}%`}
          </dd>
          <dt>Status</dt>
          <dd>{selectedNode.severity ?? "info"}</dd>
        </dl>

        {detailEntries.length > 0 && (
          <>
            <h3>Details</h3>
            <dl className="facts side-facts detail-facts">
              {detailEntries.map(([key, value]) => (
                <div className="fact-pair" key={key}>
                  <dt>{key.replace(/_/g, " ")}</dt>
                  <dd>{valueToText(value)}</dd>
                </div>
              ))}
            </dl>
          </>
        )}

        {linkedExceptions.length > 0 && (
          <>
            <h3>Related exceptions</h3>
            <div className="exception-list compact">
              {linkedExceptions.map((exception) => (
                <button
                  className={`exception-card ${exception.severity}`}
                  key={exception.id}
                  onClick={() => exception.linkedNodeId && onSelectNode(exception.linkedNodeId)}
                >
                  <strong>{exception.title}</strong>
                  {exception.note && <span>{exception.note}</span>}
                </button>
              ))}
            </div>
          </>
        )}
      </aside>
    );
  }

  return (
    <aside className="mapping-side-panel">
      <div className="side-panel-header">
        <div>
          <span className="badge blue">Graph summary</span>
          <h2>Mapping overview</h2>
        </div>
      </div>
      <p className="sub">
        Click any node to inspect the source field, interpreted meaning, NIQ target,
        rule, confidence, and exceptions connected to it.
      </p>

      <div className="graph-stat-grid side-stats">
        <div>
          <strong>{graph.stats.clientFields}</strong>
          <span>Client fields</span>
        </div>
        <div>
          <strong>{graph.stats.niqFields}</strong>
          <span>NIQ fields</span>
        </div>
        <div>
          <strong>{graph.stats.rules}</strong>
          <span>Rules</span>
        </div>
        <div>
          <strong>{graph.stats.exceptions}</strong>
          <span>Exceptions</span>
        </div>
      </div>

      <h3>Exceptions needing attention</h3>
      {graph.exceptions.length === 0 ? (
        <p className="muted small">No major exceptions are currently represented in this graph.</p>
      ) : (
        <div className="exception-list">
          {graph.exceptions.slice(0, 20).map((exception) => (
            <button
              className={`exception-card ${exception.severity}`}
              key={exception.id}
              onClick={() => exception.linkedNodeId && onSelectNode(exception.linkedNodeId)}
            >
              <strong>{exception.title}</strong>
              <span>
                {exception.rows != null ? `${exception.rows.toLocaleString()} rows` : exception.businessArea}
                {exception.note ? ` | ${exception.note}` : ""}
              </span>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
