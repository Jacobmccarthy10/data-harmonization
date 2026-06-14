import { useMemo, useState } from "react";
import MappingGraph, { type MappingGraphFilters } from "../components/MappingGraph";
import MappingGraphLegend from "../components/MappingGraphLegend";
import MappingGraphSidePanel from "../components/MappingGraphSidePanel";
import type {
  AnalysisResponse,
  CoverageResponse,
  MappingGraphBusinessArea,
  MappingGraphConfidenceBand,
  MappingGraphNodeType,
} from "../types";
import { buildMappingGraphData } from "../utils/buildMappingGraph";

const NODE_TYPES: { key: MappingGraphNodeType; label: string }[] = [
  { key: "client_field", label: "Client fields" },
  { key: "interpreted_meaning", label: "Interpreted meanings" },
  { key: "niq_field", label: "NIQ fields" },
  { key: "rule", label: "Rules" },
  { key: "exception", label: "Exceptions" },
];

const BUSINESS_AREAS: { key: MappingGraphBusinessArea; label: string }[] = [
  { key: "product", label: "Product" },
  { key: "geography", label: "Geography" },
  { key: "time", label: "Time" },
  { key: "metrics", label: "Metrics" },
  { key: "exceptions", label: "Exceptions" },
];

const CONFIDENCE_BANDS: { key: MappingGraphConfidenceBand; label: string }[] = [
  { key: "high", label: "High" },
  { key: "medium", label: "Medium" },
  { key: "low", label: "Low" },
  { key: "needs_review", label: "Needs review" },
  { key: "none", label: "No score" },
];

const DEFAULT_FILTERS: MappingGraphFilters = {
  nodeTypes: {
    client_field: true,
    interpreted_meaning: true,
    niq_field: true,
    rule: true,
    exception: true,
  },
  businessAreas: {
    product: true,
    geography: true,
    time: true,
    metrics: true,
    exceptions: true,
  },
  confidenceBands: {
    high: true,
    medium: true,
    low: true,
    needs_review: true,
    none: true,
  },
};

function cloneDefaultFilters(): MappingGraphFilters {
  return {
    nodeTypes: { ...DEFAULT_FILTERS.nodeTypes },
    businessAreas: { ...DEFAULT_FILTERS.businessAreas },
    confidenceBands: { ...DEFAULT_FILTERS.confidenceBands },
  };
}

interface Props {
  analysis: AnalysisResponse;
  coverage?: CoverageResponse | null;
  onBack: () => void;
}

export default function MappingGraphPage({ analysis, coverage, onBack }: Props) {
  const [filters, setFilters] = useState<MappingGraphFilters>(() => cloneDefaultFilters());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const graph = useMemo(() => buildMappingGraphData(analysis, coverage), [analysis, coverage]);
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? null;

  const toggleNodeType = (key: MappingGraphNodeType) => {
    setFilters((current) => ({
      ...current,
      nodeTypes: { ...current.nodeTypes, [key]: !current.nodeTypes[key] },
    }));
  };

  const toggleBusinessArea = (key: MappingGraphBusinessArea) => {
    setFilters((current) => ({
      ...current,
      businessAreas: { ...current.businessAreas, [key]: !current.businessAreas[key] },
    }));
  };

  const toggleConfidenceBand = (key: MappingGraphConfidenceBand) => {
    setFilters((current) => ({
      ...current,
      confidenceBands: { ...current.confidenceBands, [key]: !current.confidenceBands[key] },
    }));
  };

  return (
    <>
      <div className="graph-page-header card">
        <div>
          <span className="badge blue">Mapping graph</span>
          <h2>{graph.title}</h2>
          <p className="sub">{graph.subtitle}</p>
        </div>
        <div className="graph-header-actions">
          <button className="btn secondary" onClick={onBack}>
            Back to workflow
          </button>
        </div>
      </div>

      <div className="graph-stat-grid">
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
        <div>
          <strong>{graph.stats.needsReview + graph.stats.lowConfidence}</strong>
          <span>Review signals</span>
        </div>
      </div>

      <div className="card graph-controls-card">
        <div className="graph-filter-section">
          <strong>Node type</strong>
          <div className="graph-filter-row">
            {NODE_TYPES.map((item) => (
              <label className="check-chip" key={item.key}>
                <input
                  type="checkbox"
                  checked={filters.nodeTypes[item.key]}
                  onChange={() => toggleNodeType(item.key)}
                />
                {item.label}
              </label>
            ))}
          </div>
        </div>
        <div className="graph-filter-section">
          <strong>Business area</strong>
          <div className="graph-filter-row">
            {BUSINESS_AREAS.map((item) => (
              <label className="check-chip" key={item.key}>
                <input
                  type="checkbox"
                  checked={filters.businessAreas[item.key]}
                  onChange={() => toggleBusinessArea(item.key)}
                />
                {item.label}
              </label>
            ))}
          </div>
        </div>
        <div className="graph-filter-section">
          <strong>Confidence</strong>
          <div className="graph-filter-row">
            {CONFIDENCE_BANDS.map((item) => (
              <label className="check-chip" key={item.key}>
                <input
                  type="checkbox"
                  checked={filters.confidenceBands[item.key]}
                  onChange={() => toggleConfidenceBand(item.key)}
                />
                {item.label}
              </label>
            ))}
          </div>
        </div>
        <button className="btn secondary" onClick={() => setFilters(cloneDefaultFilters())}>
          Reset filters
        </button>
      </div>

      <MappingGraphLegend />

      <div className="mapping-workspace">
        <MappingGraph
          graph={graph}
          filters={filters}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
        />
        <MappingGraphSidePanel
          graph={graph}
          selectedNode={selectedNode}
          onSelectNode={setSelectedNodeId}
          onClearSelection={() => setSelectedNodeId(null)}
        />
      </div>
    </>
  );
}
