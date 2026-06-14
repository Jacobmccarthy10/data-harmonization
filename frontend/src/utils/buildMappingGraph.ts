import type {
  AnalysisResponse,
  ColumnMapping,
  CoverageResponse,
  MappingGraphBusinessArea,
  MappingGraphConfidenceBand,
  MappingGraphData,
  MappingGraphEdge,
  MappingGraphException,
  MappingGraphNode,
} from "../types";

const AREA_ANCHORS: Record<MappingGraphBusinessArea, { x: number; y: number }> = {
  product: { x: -520, y: -280 },
  geography: { x: 220, y: -260 },
  time: { x: -520, y: 260 },
  metrics: { x: 220, y: 260 },
  exceptions: { x: 820, y: 0 },
};

const AREA_SPREAD: Record<MappingGraphBusinessArea, { radiusX: number; radiusY: number }> = {
  product: { radiusX: 300, radiusY: 190 },
  geography: { radiusX: 300, radiusY: 190 },
  time: { radiusX: 260, radiusY: 160 },
  metrics: { radiusX: 270, radiusY: 170 },
  exceptions: { radiusX: 230, radiusY: 220 },
};

function safeId(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90);
}

function uniqueId(prefix: string, label: string): string {
  return `${prefix}-${safeId(label) || "item"}`;
}

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "Needs review";
  return `${Math.round(value * 100)}% confidence`;
}

export function confidenceBand(value: number | null | undefined): MappingGraphConfidenceBand {
  if (value == null || Number.isNaN(value)) return "none";
  if (value >= 0.9) return "high";
  if (value >= 0.7) return "medium";
  if (value >= 0.5) return "low";
  return "needs_review";
}

function areaForText(text: string | null | undefined): MappingGraphBusinessArea {
  const t = (text ?? "").toLowerCase();
  if (/exception|warning|mismatch|missing|unmapped|review|blocked|low confidence/.test(t)) return "exceptions";
  if (/upc|ean|sku|item|product|brand|manufacturer|category|description|pack|size|crosswalk/.test(t)) return "product";
  if (/market|region|geo|geography|city|state|province|customer|retailer|banner|store/.test(t)) return "geography";
  if (/period|week|month|quarter|year|date|time|calendar/.test(t)) return "time";
  if (/sales|dollar|revenue|unit|volume|measure|metric|value|qty|quantity/.test(t)) return "metrics";
  return "product";
}

function niqFieldForConcept(concept: string | null, role: string): string {
  const t = `${concept ?? ""} ${role}`.toLowerCase();
  if (/upc|ean|sku|item|product identifier/.test(t)) return "NIQ Product ID";
  if (/description|item description|product description/.test(t)) return "NIQ Item Description";
  if (/brand/.test(t)) return "NIQ Brand";
  if (/manufacturer/.test(t)) return "NIQ Manufacturer";
  if (/category/.test(t)) return "NIQ Category";
  if (/market|region|geo|city|province|state/.test(t)) return "NIQ Market";
  if (/customer|retailer|banner/.test(t)) return "NIQ Customer";
  if (/period|week|month|date|time/.test(t)) return "NIQ Period";
  if (/unit/.test(t)) return "NIQ Units";
  if (/sales|dollar|revenue|value/.test(t)) return "NIQ Sales";
  if (/volume/.test(t)) return "NIQ Volume";
  if (/metric|measure/.test(t)) return "NIQ Measure";
  return concept ? `NIQ ${concept}` : "NIQ Target Field";
}

function meaningForMapping(mapping: ColumnMapping): string {
  if (mapping.concept) return mapping.concept;
  if (mapping.role === "wide_period") return "Period and metric";
  if (mapping.role === "ignored") return "Ignored field";
  if (mapping.role === "unmapped") return "Unmapped field";
  return "Needs interpretation";
}

function ruleForMapping(mapping: ColumnMapping): string {
  if (mapping.role === "wide_period") return "Wide period parser";
  if (mapping.role === "metric" || mapping.role === "auxiliary_metric") return "Metric classifier";
  if (mapping.role === "mapped") return "Header and sample pattern match";
  if (mapping.role === "alternate") return "Alternate field candidate";
  if (mapping.role === "ignored") return "Excluded from mapping";
  if (mapping.role === "unmapped") return "Manual review required";
  return `${mapping.role} rule`;
}

function severityForBand(band: MappingGraphConfidenceBand): "info" | "warning" | "critical" {
  if (band === "needs_review") return "critical";
  if (band === "low") return "warning";
  return "info";
}

function addPositioning(nodes: MappingGraphNode[]): MappingGraphNode[] {
  const grouped = nodes.reduce<Record<MappingGraphBusinessArea, MappingGraphNode[]>>(
    (acc, node) => {
      acc[node.businessArea].push(node);
      return acc;
    },
    { product: [], geography: [], time: [], metrics: [], exceptions: [] }
  );

  return nodes.map((node) => {
    const group = grouped[node.businessArea];
    const idx = group.findIndex((n) => n.id === node.id);
    const count = Math.max(group.length, 1);
    const angle = (idx / count) * Math.PI * 2;
    const anchor = AREA_ANCHORS[node.businessArea];
    const spread = AREA_SPREAD[node.businessArea];
    const typeOffset = node.type === "rule" ? 42 : node.type === "exception" ? 72 : 0;

    return {
      ...node,
      position: {
        x: anchor.x + Math.cos(angle) * (spread.radiusX + typeOffset),
        y: anchor.y + Math.sin(angle) * (spread.radiusY + typeOffset),
      },
    };
  });
}

function makeStats(nodes: MappingGraphNode[]): MappingGraphData["stats"] {
  return {
    clientFields: nodes.filter((n) => n.type === "client_field").length,
    niqFields: nodes.filter((n) => n.type === "niq_field").length,
    rules: nodes.filter((n) => n.type === "rule").length,
    exceptions: nodes.filter((n) => n.type === "exception").length,
    highConfidence: nodes.filter((n) => n.confidenceBand === "high").length,
    mediumConfidence: nodes.filter((n) => n.confidenceBand === "medium").length,
    lowConfidence: nodes.filter((n) => n.confidenceBand === "low").length,
    needsReview: nodes.filter((n) => n.confidenceBand === "needs_review").length,
  };
}

function makeBuilder() {
  const nodes = new Map<string, MappingGraphNode>();
  const edges = new Map<string, MappingGraphEdge>();
  const exceptions = new Map<string, MappingGraphException>();

  const addNode = (node: MappingGraphNode) => {
    if (!nodes.has(node.id)) {
      nodes.set(node.id, node);
      return;
    }
    const existing = nodes.get(node.id)!;
    nodes.set(node.id, {
      ...existing,
      details: { ...(existing.details ?? {}), ...(node.details ?? {}) },
      description: existing.description || node.description,
    });
  };

  const addEdge = (edge: MappingGraphEdge) => {
    if (!edges.has(edge.id)) edges.set(edge.id, edge);
  };

  const addException = (exception: MappingGraphException) => {
    if (!exceptions.has(exception.id)) exceptions.set(exception.id, exception);
  };

  return { nodes, edges, exceptions, addNode, addEdge, addException };
}

function addColumnMappings(builder: ReturnType<typeof makeBuilder>, analysis: AnalysisResponse): void {
  const widePeriodColumns = analysis.column_mapping_summary.filter((m) => m.role === "wide_period");
  const normalMappings = analysis.column_mapping_summary.filter((m) => m.role !== "wide_period");

  for (const mapping of normalMappings) {
    const area = areaForText(`${mapping.source_column} ${mapping.concept ?? ""} ${mapping.role}`);
    const band = confidenceBand(mapping.confidence);
    const sourceId = uniqueId("client-field", mapping.source_column);
    const meaningLabel = meaningForMapping(mapping);
    const meaningId = uniqueId("meaning", `${area}-${meaningLabel}`);
    const niqLabel = niqFieldForConcept(mapping.concept, mapping.role);
    const niqId = uniqueId("niq-field", niqLabel);
    const ruleLabel = ruleForMapping(mapping);
    const ruleId = uniqueId("rule", `${area}-${ruleLabel}`);

    builder.addNode({
      id: sourceId,
      label: mapping.source_column,
      type: "client_field",
      businessArea: area,
      confidence: mapping.confidence,
      confidenceBand: band,
      description: "Raw column detected in the client file.",
      details: {
        role: mapping.role,
        concept: mapping.concept ?? "Not detected",
        evidence: mapping.evidence,
        sample_values: mapping.sample_values.slice(0, 5),
      },
      severity: severityForBand(band),
    });

    builder.addNode({
      id: meaningId,
      label: meaningLabel,
      type: "interpreted_meaning",
      businessArea: area,
      confidence: mapping.confidence,
      confidenceBand: band,
      description: "Business meaning inferred from the source field.",
      details: {
        source_column: mapping.source_column,
        evidence: mapping.evidence,
      },
      severity: severityForBand(band),
    });

    builder.addNode({
      id: niqId,
      label: niqLabel,
      type: "niq_field",
      businessArea: area,
      confidence: mapping.confidence,
      confidenceBand: band,
      description: "Likely NIQ standard field or comparable concept.",
      details: {
        derived_from: mapping.source_column,
        detected_concept: mapping.concept ?? "Needs review",
      },
      severity: severityForBand(band),
    });

    builder.addNode({
      id: ruleId,
      label: ruleLabel,
      type: "rule",
      businessArea: area,
      confidence: mapping.confidence,
      confidenceBand: band,
      description: "Rule or heuristic used to explain this mapping.",
      details: {
        evidence: mapping.evidence,
        source_column: mapping.source_column,
      },
      severity: severityForBand(band),
    });

    builder.addEdge({
      id: `${sourceId}->${meaningId}`,
      source: sourceId,
      target: meaningId,
      label: pct(mapping.confidence),
      relationship: "interpreted as",
      confidence: mapping.confidence,
      confidenceBand: band,
    });
    builder.addEdge({
      id: `${meaningId}->${niqId}`,
      source: meaningId,
      target: niqId,
      label: pct(mapping.confidence),
      relationship: "maps to",
      confidence: mapping.confidence,
      confidenceBand: band,
    });
    builder.addEdge({
      id: `${ruleId}->${meaningId}`,
      source: ruleId,
      target: meaningId,
      label: "rule used",
      relationship: "supports",
      confidence: mapping.confidence,
      confidenceBand: band,
    });

    if (mapping.role === "unmapped" || band === "needs_review" || band === "low") {
      const exceptionId = uniqueId("exception", `${mapping.source_column}-${mapping.role}-${band}`);
      builder.addNode({
        id: exceptionId,
        label: mapping.role === "unmapped" ? "Unmapped client field" : "Low confidence field mapping",
        type: "exception",
        businessArea: "exceptions",
        confidence: mapping.confidence,
        confidenceBand: band,
        description: "This field likely needs a human review before the mapping is trusted.",
        details: {
          source_column: mapping.source_column,
          role: mapping.role,
          confidence: mapping.confidence,
          evidence: mapping.evidence,
        },
        severity: mapping.role === "unmapped" || band === "needs_review" ? "critical" : "warning",
      });
      builder.addEdge({
        id: `${sourceId}->${exceptionId}`,
        source: sourceId,
        target: exceptionId,
        label: mapping.role === "unmapped" ? "unmapped" : pct(mapping.confidence),
        relationship: "flagged by",
        confidence: mapping.confidence,
        confidenceBand: band,
      });
      builder.addException({
        id: exceptionId,
        title: mapping.role === "unmapped" ? "Unmapped client field" : "Low confidence field mapping",
        businessArea: area,
        severity: mapping.role === "unmapped" || band === "needs_review" ? "critical" : "warning",
        note: `${mapping.source_column}: ${mapping.evidence}`,
        linkedNodeId: sourceId,
      });
    }
  }

  if (widePeriodColumns.length > 0) {
    const sourceId = "client-field-wide-period-columns";
    const meaningId = "meaning-wide-periods";
    const niqId = "niq-field-niq-period";
    const ruleId = "rule-wide-period-parser";

    builder.addNode({
      id: sourceId,
      label: `${widePeriodColumns.length} wide period columns`,
      type: "client_field",
      businessArea: "time",
      confidence: 0.9,
      confidenceBand: "high",
      description: "Multiple client columns appear to encode period and metric information.",
      details: {
        examples: widePeriodColumns.slice(0, 8).map((m) => m.source_column),
      },
      severity: "info",
    });
    builder.addNode({
      id: meaningId,
      label: "Period and metric in header",
      type: "interpreted_meaning",
      businessArea: "time",
      confidence: 0.9,
      confidenceBand: "high",
      description: "The column headers are treated as period and metric values, then unpivoted.",
      severity: "info",
    });
    builder.addNode({
      id: niqId,
      label: "NIQ Period",
      type: "niq_field",
      businessArea: "time",
      confidence: 0.9,
      confidenceBand: "high",
      description: "Normalized reporting period comparable to Discover time fields.",
      severity: "info",
    });
    builder.addNode({
      id: ruleId,
      label: "Wide period parser",
      type: "rule",
      businessArea: "time",
      confidence: 0.9,
      confidenceBand: "high",
      description: "Parser that converts month or week columns into normalized period rows.",
      severity: "info",
    });
    builder.addEdge({ id: `${sourceId}->${meaningId}`, source: sourceId, target: meaningId, label: "90% confidence", relationship: "interpreted as", confidence: 0.9, confidenceBand: "high" });
    builder.addEdge({ id: `${meaningId}->${niqId}`, source: meaningId, target: niqId, label: "unpivoted", relationship: "normalizes to", confidence: 0.9, confidenceBand: "high" });
    builder.addEdge({ id: `${ruleId}->${meaningId}`, source: ruleId, target: meaningId, label: "rule used", relationship: "supports", confidence: 0.9, confidenceBand: "high" });
  }
}

function addClientProfile(builder: ReturnType<typeof makeBuilder>, analysis: AnalysisResponse): void {
  const profile = analysis.client_profile;
  const quality = analysis.quality_summary;

  const profileFacts: Array<{
    label: string;
    area: MappingGraphBusinessArea;
    meaning: string;
    niq: string;
    detail: string | number | null;
    confidence: number | null;
  }> = [
    { label: profile.customer ?? "Customer scope", area: "geography", meaning: "Customer scope", niq: "NIQ Customer", detail: profile.customer, confidence: profile.customer ? 0.85 : null },
    { label: `${quality.distinct_markets} market values`, area: "geography", meaning: "Market scope", niq: "NIQ Market", detail: quality.distinct_markets, confidence: quality.distinct_markets > 0 ? 0.8 : null },
    { label: `${quality.distinct_periods} periods`, area: "time", meaning: analysis.schema_detection.time_grain || "Period scope", niq: "NIQ Period", detail: `${profile.period_start ?? "?"} to ${profile.period_end ?? "?"}`, confidence: quality.period_parse_rate || null },
    { label: `${quality.distinct_products} products`, area: "product", meaning: "Product scope", niq: "NIQ Product Universe", detail: quality.distinct_products, confidence: profile.distinct_products > 0 ? 0.75 : null },
  ];

  for (const fact of profileFacts) {
    const sourceId = uniqueId("client-profile", `${fact.area}-${fact.label}`);
    const meaningId = uniqueId("meaning", `${fact.area}-${fact.meaning}`);
    const niqId = uniqueId("niq-field", fact.niq);
    const band = confidenceBand(fact.confidence);

    builder.addNode({ id: sourceId, label: fact.label, type: "client_field", businessArea: fact.area, confidence: fact.confidence, confidenceBand: band, description: "Profile signal inferred from the client file as a whole.", details: { value: fact.detail }, severity: severityForBand(band) });
    builder.addNode({ id: meaningId, label: fact.meaning, type: "interpreted_meaning", businessArea: fact.area, confidence: fact.confidence, confidenceBand: band, description: "Business scope inferred from the client submission.", severity: severityForBand(band) });
    builder.addNode({ id: niqId, label: fact.niq, type: "niq_field", businessArea: fact.area, confidence: fact.confidence, confidenceBand: band, description: "NIQ standard target used for comparison.", severity: severityForBand(band) });
    builder.addEdge({ id: `${sourceId}->${meaningId}`, source: sourceId, target: meaningId, label: pct(fact.confidence), relationship: "summarized as", confidence: fact.confidence, confidenceBand: band });
    builder.addEdge({ id: `${meaningId}->${niqId}`, source: meaningId, target: niqId, label: "target scope", relationship: "aligns to", confidence: fact.confidence, confidenceBand: band });
  }

  if (quality.warnings.length > 0 || quality.rows_needing_review > 0) {
    const exceptionId = "exception-quality-review";
    builder.addNode({
      id: exceptionId,
      label: "Rows needing review",
      type: "exception",
      businessArea: "exceptions",
      confidence: null,
      confidenceBand: "needs_review",
      description: "Quality checks found rows or warnings that need review.",
      details: { rows_needing_review: quality.rows_needing_review, warnings: quality.warnings },
      severity: quality.rows_needing_review > 0 ? "critical" : "warning",
    });
    builder.addException({ id: exceptionId, title: "Client file quality review", businessArea: "exceptions", severity: quality.rows_needing_review > 0 ? "critical" : "warning", rows: quality.rows_needing_review, note: quality.warnings.join(" ") || "Rows need manual review.", linkedNodeId: exceptionId });
  }
}

function addRecommendation(builder: ReturnType<typeof makeBuilder>, analysis: AnalysisResponse): void {
  const rec = analysis.discover_recommendation;
  const ruleId = "rule-discover-pull-recommendation";
  const datasetId = uniqueId("niq-field", rec.recommended_dataset || "Discover dataset");

  builder.addNode({
    id: ruleId,
    label: "Discover pull recommendation",
    type: "rule",
    businessArea: "metrics",
    confidence: 0.8,
    confidenceBand: "medium",
    description: "Recommendation for the Discover export needed for coverage comparison.",
    details: {
      country: rec.country,
      comparison_mode: rec.comparison_mode,
      required_fields: rec.required_discover_fields,
      optional_fields: rec.optional_discover_fields,
      caveats: rec.caveats,
    },
    severity: rec.caveats.length > 0 ? "warning" : "info",
  });
  builder.addNode({
    id: datasetId,
    label: rec.recommended_dataset || "Discover dataset",
    type: "niq_field",
    businessArea: "metrics",
    confidence: 0.8,
    confidenceBand: "medium",
    description: "Recommended Discover dataset for the comparison.",
    details: { required_measures: rec.required_measures, product_grain: rec.product_grain, time_grain: rec.time_grain },
    severity: rec.caveats.length > 0 ? "warning" : "info",
  });
  builder.addEdge({ id: `${ruleId}->${datasetId}`, source: ruleId, target: datasetId, label: "recommended pull", relationship: "selects", confidence: 0.8, confidenceBand: "medium" });

  for (const caveat of rec.caveats) {
    const exceptionId = uniqueId("exception", `recommendation-${caveat}`);
    builder.addNode({ id: exceptionId, label: "Recommendation caveat", type: "exception", businessArea: "exceptions", confidence: null, confidenceBand: "needs_review", description: caveat, details: { caveat }, severity: "warning" });
    builder.addEdge({ id: `${datasetId}->${exceptionId}`, source: datasetId, target: exceptionId, label: "caveat", relationship: "flagged by", confidence: null, confidenceBand: "needs_review" });
    builder.addException({ id: exceptionId, title: "Discover recommendation caveat", businessArea: "exceptions", severity: "warning", note: caveat, linkedNodeId: exceptionId });
  }
}

function addCoverage(builder: ReturnType<typeof makeBuilder>, coverage: CoverageResponse): void {
  const summary = coverage.coverage_summary;
  const coverageBand = confidenceBand(coverage.kpis.row_coverage_pct);
  const coverageRuleId = "rule-coverage-match-engine";
  const matchedNodeId = "meaning-matched-coverage";

  builder.addNode({
    id: coverageRuleId,
    label: "Coverage match engine",
    type: "rule",
    businessArea: "metrics",
    confidence: coverage.kpis.row_coverage_pct,
    confidenceBand: coverageBand,
    description: "Engine that reconciles client rows against the uploaded Discover export.",
    details: {
      match_grain: summary.match_grain,
      comparison_mode: summary.comparison_mode,
      matched_rows: coverage.kpis.matched_rows,
      total_client_rows: coverage.kpis.total_client_rows,
      row_coverage_pct: coverage.kpis.row_coverage_pct,
      sales_coverage_pct: coverage.kpis.sales_coverage_pct,
    },
    severity: coverage.kpis.rows_needing_review > 0 ? "warning" : "info",
  });
  builder.addNode({
    id: matchedNodeId,
    label: "Matched coverage result",
    type: "interpreted_meaning",
    businessArea: "metrics",
    confidence: coverage.kpis.row_coverage_pct,
    confidenceBand: coverageBand,
    description: "Coverage result after matching client rows to NIQ or Discover data.",
    details: {
      row_coverage: `${Math.round(coverage.kpis.row_coverage_pct * 100)}%`,
      sales_coverage: `${Math.round(coverage.kpis.sales_coverage_pct * 100)}%`,
      delta_label: coverage.kpis.delta_label,
    },
    severity: coverage.kpis.rows_needing_review > 0 ? "warning" : "info",
  });
  builder.addEdge({ id: `${coverageRuleId}->${matchedNodeId}`, source: coverageRuleId, target: matchedNodeId, label: pct(coverage.kpis.row_coverage_pct), relationship: "produces", confidence: coverage.kpis.row_coverage_pct, confidenceBand: coverageBand });

  const marketRuleId = "rule-market-alignment";
  const marketBand: MappingGraphConfidenceBand = summary.unmapped_client_markets.length > 0 ? "low" : "high";
  builder.addNode({
    id: marketRuleId,
    label: summary.market_rollup_mode ? "Market rollup rule" : "Market alignment rule",
    type: "rule",
    businessArea: "geography",
    confidence: summary.unmapped_client_markets.length > 0 ? 0.6 : 0.9,
    confidenceBand: marketBand,
    description: "Maps client market labels to Discover market scope.",
    details: {
      market_rollup_mode: summary.market_rollup_mode,
      market_hierarchy_detected: summary.market_hierarchy_detected,
      unmapped_client_markets: summary.unmapped_client_markets,
    },
    severity: summary.unmapped_client_markets.length > 0 ? "warning" : "info",
  });

  Object.entries(summary.market_alignment ?? {}).slice(0, 12).forEach(([clientMarket, niqMarket]) => {
    const sourceId = uniqueId("client-market", clientMarket);
    const niqId = uniqueId("niq-market", niqMarket);
    builder.addNode({ id: sourceId, label: clientMarket, type: "client_field", businessArea: "geography", confidence: 0.9, confidenceBand: "high", description: "Client market value found during coverage matching.", severity: "info" });
    builder.addNode({ id: niqId, label: niqMarket, type: "niq_field", businessArea: "geography", confidence: 0.9, confidenceBand: "high", description: "Discover or NIQ market value used for comparison.", severity: "info" });
    builder.addEdge({ id: `${sourceId}->${marketRuleId}`, source: sourceId, target: marketRuleId, label: "market lookup", relationship: "uses", confidence: 0.9, confidenceBand: "high" });
    builder.addEdge({ id: `${marketRuleId}->${niqId}`, source: marketRuleId, target: niqId, label: "aligned", relationship: "maps to", confidence: 0.9, confidenceBand: "high" });
  });

  Object.entries(summary.customer_alignment ?? {}).slice(0, 8).forEach(([clientCustomer, niqCustomer]) => {
    const sourceId = uniqueId("client-customer", clientCustomer);
    const niqId = uniqueId("niq-customer", niqCustomer);
    const ruleId = "rule-customer-alignment";
    builder.addNode({ id: ruleId, label: "Customer alignment rule", type: "rule", businessArea: "geography", confidence: 0.85, confidenceBand: "medium", description: "Maps client customer or retailer values to Discover customer scope.", severity: "info" });
    builder.addNode({ id: sourceId, label: clientCustomer, type: "client_field", businessArea: "geography", confidence: 0.85, confidenceBand: "medium", description: "Client customer value found during coverage matching.", severity: "info" });
    builder.addNode({ id: niqId, label: niqCustomer, type: "niq_field", businessArea: "geography", confidence: 0.85, confidenceBand: "medium", description: "Discover or NIQ customer value used for comparison.", severity: "info" });
    builder.addEdge({ id: `${sourceId}->${ruleId}`, source: sourceId, target: ruleId, label: "customer lookup", relationship: "uses", confidence: 0.85, confidenceBand: "medium" });
    builder.addEdge({ id: `${ruleId}->${niqId}`, source: ruleId, target: niqId, label: "aligned", relationship: "maps to", confidence: 0.85, confidenceBand: "medium" });
  });

  if (Object.keys(summary.brand_alias_map ?? {}).length > 0) {
    const aliasRuleId = "rule-brand-fuzzy-aliases";
    builder.addNode({ id: aliasRuleId, label: "Brand fuzzy alias rule", type: "rule", businessArea: "product", confidence: 0.75, confidenceBand: "medium", description: "Fuzzy brand matching applied when client and Discover labels differ.", details: { aliases: Object.entries(summary.brand_alias_map).slice(0, 12).map(([c, d]) => `${c} to ${d}`) }, severity: "info" });
    Object.entries(summary.brand_alias_map).slice(0, 10).forEach(([clientBrand, niqBrand]) => {
      const sourceId = uniqueId("client-brand", clientBrand);
      const niqId = uniqueId("niq-brand", niqBrand);
      builder.addNode({ id: sourceId, label: clientBrand, type: "client_field", businessArea: "product", confidence: 0.75, confidenceBand: "medium", description: "Client brand value matched through fuzzy aliasing.", severity: "info" });
      builder.addNode({ id: niqId, label: niqBrand, type: "niq_field", businessArea: "product", confidence: 0.75, confidenceBand: "medium", description: "Discover brand matched to the client brand label.", severity: "info" });
      builder.addEdge({ id: `${sourceId}->${aliasRuleId}`, source: sourceId, target: aliasRuleId, label: "fuzzy alias", relationship: "uses", confidence: 0.75, confidenceBand: "medium" });
      builder.addEdge({ id: `${aliasRuleId}->${niqId}`, source: aliasRuleId, target: niqId, label: "matched", relationship: "maps to", confidence: 0.75, confidenceBand: "medium" });
    });
  }

  summary.unmapped_client_markets.slice(0, 12).forEach((market) => {
    const exceptionId = uniqueId("exception", `unmapped-market-${market}`);
    builder.addNode({ id: exceptionId, label: `Unmapped market: ${market}`, type: "exception", businessArea: "exceptions", confidence: null, confidenceBand: "needs_review", description: "Client market has no current NIQ market mapping.", details: { client_market: market }, severity: "critical" });
    builder.addEdge({ id: `${marketRuleId}->${exceptionId}`, source: marketRuleId, target: exceptionId, label: "unmapped", relationship: "flags", confidence: null, confidenceBand: "needs_review" });
    builder.addException({ id: exceptionId, title: `Unmapped client market: ${market}`, businessArea: "geography", severity: "critical", note: "No NIQ market mapping exists yet for this client market value.", linkedNodeId: exceptionId });
  });

  coverage.exceptions.forEach((exception) => {
    if (exception.status === "matched" && exception.rows === 0) return;
    const area = areaForText(exception.status);
    const nodeId = uniqueId("exception", `${exception.status}-${exception.rows}`);
    const severe = /not_comparable|metric_mismatch|needs_review/.test(exception.status) ? "critical" : /matched/.test(exception.status) ? "info" : "warning";
    const band: MappingGraphConfidenceBand = severe === "info" ? "medium" : severe === "warning" ? "low" : "needs_review";
    builder.addNode({ id: nodeId, label: exception.status, type: "exception", businessArea: "exceptions", confidence: null, confidenceBand: band, description: exception.note ?? "Coverage status from the reconciliation output.", details: { rows: exception.rows, client_sales: exception.client_sales, niq_sales: exception.niq_sales, note: exception.note }, severity: severe });
    builder.addEdge({ id: `${matchedNodeId}->${nodeId}`, source: matchedNodeId, target: nodeId, label: `${exception.rows.toLocaleString()} rows`, relationship: "breaks out into", confidence: null, confidenceBand: band });
    if (severe !== "info") builder.addException({ id: nodeId, title: exception.status, businessArea: area, severity: severe, rows: exception.rows, note: exception.note, linkedNodeId: nodeId });
  });

  summary.brand_diagnostic
    .filter((b) => b.match_rate < 0.95)
    .sort((a, b) => a.match_rate - b.match_rate || b.client_rows - a.client_rows)
    .slice(0, 10)
    .forEach((brand) => {
      const nodeId = uniqueId("exception", `brand-match-${brand.brand}`);
      const band = confidenceBand(brand.match_rate);
      builder.addNode({ id: nodeId, label: `Brand match: ${brand.brand}`, type: "exception", businessArea: "exceptions", confidence: brand.match_rate, confidenceBand: band, description: "Brand has incomplete match coverage.", details: { brand: brand.brand, client_rows: brand.client_rows, matched_rows: brand.matched_rows, match_rate: brand.match_rate, client_sales: brand.client_sales }, severity: brand.match_rate === 0 ? "critical" : "warning" });
      builder.addException({ id: nodeId, title: `Brand coverage gap: ${brand.brand}`, businessArea: "product", severity: brand.match_rate === 0 ? "critical" : "warning", rows: brand.client_rows - brand.matched_rows, note: `${Math.round(brand.match_rate * 100)}% match rate for ${brand.brand}.`, linkedNodeId: nodeId });
    });
}

export function buildMappingGraphData(analysis: AnalysisResponse, coverage?: CoverageResponse | null): MappingGraphData {
  const builder = makeBuilder();

  addColumnMappings(builder, analysis);
  addClientProfile(builder, analysis);
  addRecommendation(builder, analysis);
  if (coverage) addCoverage(builder, coverage);

  const nodes = addPositioning(Array.from(builder.nodes.values()));
  const edges = Array.from(builder.edges.values()).filter((edge) => builder.nodes.has(edge.source) && builder.nodes.has(edge.target));
  const exceptions = Array.from(builder.exceptions.values());

  return {
    title: coverage ? "Coverage Mapping Graph" : "Structure Mapping Graph",
    subtitle: coverage
      ? "How the client file, Discover pull, mapping rules, confidence, and coverage exceptions connect."
      : "How the client file was interpreted before the Discover comparison runs.",
    source: coverage ? "coverage" : "structure",
    nodes,
    edges,
    exceptions,
    stats: makeStats(nodes),
  };
}
