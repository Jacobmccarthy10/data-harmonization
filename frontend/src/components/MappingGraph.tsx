import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  type Edge as FlowEdge,
  type Node as FlowNode,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import type {
  MappingGraphBusinessArea,
  MappingGraphConfidenceBand,
  MappingGraphData,
  MappingGraphNode,
  MappingGraphNodeType,
} from "../types";

export interface MappingGraphFilters {
  nodeTypes: Record<MappingGraphNodeType, boolean>;
  businessAreas: Record<MappingGraphBusinessArea, boolean>;
  confidenceBands: Record<MappingGraphConfidenceBand, boolean>;
}

interface MappingNodeData {
  graphNode: MappingGraphNode;
  selected: boolean;
  highlighted: boolean;
  dimmed: boolean;
}

function confidenceLabel(node: MappingGraphNode): string {
  if (node.confidence == null) {
    if (node.confidenceBand === "needs_review") return "Needs review";
    if (node.confidenceBand === "none") return "No score";
    return node.confidenceBand?.replace(/_/g, " ") ?? "No score";
  }
  return `${Math.round(node.confidence * 100)}%`;
}

function typeLabel(type: MappingGraphNodeType): string {
  return type.replace(/_/g, " ");
}

function MappingNodeCard({ data }: NodeProps<MappingNodeData>) {
  const node = data.graphNode;
  return (
    <div
      className={[
        "mapping-flow-node",
        `node-${node.type}`,
        `area-${node.businessArea}`,
        `confidence-${node.confidenceBand ?? "none"}`,
        node.severity ? `severity-${node.severity}` : "",
        data.selected ? "is-selected" : "",
        data.highlighted ? "is-highlighted" : "",
        data.dimmed ? "is-dimmed" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <Handle type="target" position={Position.Left} className="mapping-handle" />
      <div className="node-meta">
        <span>{typeLabel(node.type)}</span>
        <span>{node.businessArea}</span>
      </div>
      <strong>{node.label}</strong>
      <div className="node-confidence">{confidenceLabel(node)}</div>
      <Handle type="source" position={Position.Right} className="mapping-handle" />
    </div>
  );
}

const nodeTypes = { mappingNode: MappingNodeCard };

function connectedNodeIds(graph: MappingGraphData, selectedNodeId: string | null): Set<string> {
  const connected = new Set<string>();
  if (!selectedNodeId) return connected;
  connected.add(selectedNodeId);
  graph.edges.forEach((edge) => {
    if (edge.source === selectedNodeId) connected.add(edge.target);
    if (edge.target === selectedNodeId) connected.add(edge.source);
  });
  return connected;
}

function visibleByFilter(node: MappingGraphNode, filters: MappingGraphFilters): boolean {
  return (
    filters.nodeTypes[node.type] &&
    filters.businessAreas[node.businessArea] &&
    filters.confidenceBands[node.confidenceBand ?? "none"]
  );
}

interface Props {
  graph: MappingGraphData;
  filters: MappingGraphFilters;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
}

export default function MappingGraph({ graph, filters, selectedNodeId, onSelectNode }: Props) {
  const connected = useMemo(() => connectedNodeIds(graph, selectedNodeId), [graph, selectedNodeId]);

  const visibleNodeIds = useMemo(() => {
    return new Set(
      graph.nodes.filter((node) => visibleByFilter(node, filters)).map((node) => node.id)
    );
  }, [graph.nodes, filters]);

  const flowNodes = useMemo<FlowNode<MappingNodeData>[]>(() => {
    return graph.nodes
      .filter((node) => visibleNodeIds.has(node.id))
      .map((node) => {
        const hasSelection = !!selectedNodeId;
        const isConnected = hasSelection && connected.has(node.id);
        return {
          id: node.id,
          type: "mappingNode",
          position: node.position ?? { x: 0, y: 0 },
          data: {
            graphNode: node,
            selected: selectedNodeId === node.id,
            highlighted: isConnected,
            dimmed: hasSelection && !isConnected,
          },
          draggable: true,
        };
      });
  }, [connected, graph.nodes, selectedNodeId, visibleNodeIds]);

  const flowEdges = useMemo<FlowEdge[]>(() => {
    return graph.edges
      .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
      .filter((edge) => filters.confidenceBands[edge.confidenceBand ?? "none"])
      .map((edge) => {
        const hasSelection = !!selectedNodeId;
        const isConnected = hasSelection && (edge.source === selectedNodeId || edge.target === selectedNodeId);
        const dimmed = hasSelection && !isConnected;
        const band = edge.confidenceBand ?? "none";
        const strokeWidth = band === "high" ? 2.8 : band === "medium" ? 2.2 : band === "low" ? 1.8 : 1.4;
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label,
          type: "smoothstep",
          animated: band === "needs_review",
          markerEnd: { type: MarkerType.ArrowClosed },
          className: [
            "mapping-flow-edge",
            `confidence-${band}`,
            isConnected ? "is-highlighted" : "",
            dimmed ? "is-dimmed" : "",
          ]
            .filter(Boolean)
            .join(" "),
          style: {
            strokeWidth,
            opacity: dimmed ? 0.15 : 0.85,
          },
          labelBgPadding: [8, 4] as [number, number],
          labelBgBorderRadius: 8,
        };
      });
  }, [filters.confidenceBands, graph.edges, selectedNodeId, visibleNodeIds]);

  return (
    <div className="mapping-graph-canvas">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.16 }}
        minZoom={0.18}
        maxZoom={1.6}
        onNodeClick={(_event, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
      >
        <Background gap={26} size={1} />
        <Controls showInteractive={false} />
        <MiniMap nodeStrokeWidth={3} pannable zoomable className="mapping-minimap" />
      </ReactFlow>
    </div>
  );
}
