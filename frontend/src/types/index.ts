export interface FileProfile {
  file_name: string;
  sheet_used: string | null;
  sheet_names: string[];
  rows: number;
  columns: number;
  notes: string[];
}

export interface ColumnMapping {
  source_column: string;
  concept: string | null;
  role: string;
  confidence: number;
  evidence: string;
  sample_values: string[];
}

export interface ComparisonMode {
  mode: "comparable" | "directional" | "not_comparable";
  reasons: string[];
}

export interface MarketValue {
  value: string;
  rows: number;
  total_like?: boolean;
}

export interface TopValue {
  value: string;
  rows: number;
}

export interface ClientProfile {
  customer: string | null;
  customer_values: TopValue[];
  markets: MarketValue[];
  manufacturers: TopValue[];
  brands: TopValue[];
  categories: TopValue[];
  period_start: string | null;
  period_end: string | null;
  time_grain: string;
  product_identifier_fields: string[];
  description_fields: string[];
  distinct_products: number;
  description_hints: { pack_counts: number[]; sizes: string[] };
}

export interface QualitySummary {
  total_rows: number;
  period_parse_rate: number;
  upc_valid_rate: number | null;
  sales_present_rate: number;
  rows_needing_review: number;
  distinct_periods: number;
  distinct_markets: number;
  distinct_products: number;
  warnings: string[];
}

export interface DiscoverRecommendation {
  country: string;
  recommended_dataset: string;
  customer_scope: string[];
  market_scope: string[];
  category_scope: string[];
  manufacturer_scope: string[];
  brand_scope: string[];
  period_start: string | null;
  period_end: string | null;
  time_grain: string;
  product_grain: string;
  required_measures: string[];
  comparison_mode: string;
  caveats: string[];
  required_discover_fields: string[];
  optional_discover_fields: string[];
}

export interface AnalysisResponse {
  analysis_id: string;
  file_profile: FileProfile;
  schema_detection: {
    structure_type: string;
    time_grain: string;
    business_type: string;
    primary_metrics: Record<string, string>;
    wide_period_columns: number;
  };
  column_mapping_summary: ColumnMapping[];
  structure_type: string;
  normalized_preview: Record<string, unknown>[];
  quality_summary: QualitySummary;
  comparison_mode: ComparisonMode;
  metric_summary: {
    business_type: string;
    primary_metrics: Record<string, string>;
    metric_fields: {
      column: string;
      kind: string;
      business_hint: string | null;
      modifier: string | null;
    }[];
  };
  client_profile: ClientProfile;
  discover_recommendation: DiscoverRecommendation;
}

export interface DiscoverFileDetail {
  file_name: string;
  sheet_used: string | null;
  valid: boolean;
  row_count: number;
  period_start: string | null;
  period_end: string | null;
  missing_required_fields: string[];
  warnings: string[];
}

export interface DiscoverValidation {
  discover_id: string | null;
  valid: boolean;
  matched_fields: Record<string, string>;
  missing_required_fields: string[];
  warnings: string[];
  row_count: number;
  period_start: string | null;
  period_end: string | null;
  preview: Record<string, string | null>[];
  files: DiscoverFileDetail[];
  file_profile: { file_name: string; sheet_used: string | null; notes: string[] };
}

export interface CoverageKpis {
  comparison_mode: string;
  delta_label: string;
  total_client_rows: number;
  matched_rows: number;
  row_coverage_pct: number;
  kpi_slice_rows: number;
  kpi_slice_row_coverage_pct: number;
  client_sales_uploaded: number | null;
  matched_client_sales: number | null;
  sales_coverage_pct: number;
  niq_comparable_sales: number | null;
  sales_delta: number | null;
  client_units_uploaded: number | null;
  matched_client_units: number | null;
  unit_coverage_pct: number | null;
  niq_comparable_units: number | null;
  unit_delta: number | null;
  rows_needing_review: number;
  uncovered_sales: number | null;
  kpi_slice_note: string | null;
}

export interface TrendPoint {
  period: string;
  client_sales: number | null;
  niq_sales: number | null;
  sales_delta: number | null;
  coverage_rate: number;
  client_units?: number | null;
  niq_units?: number | null;
}

export interface ExceptionRow {
  status: string;
  rows: number;
  client_sales: number | null;
  niq_sales: number | null;
  note: string | null;
}

export interface DrilldownRow {
  status: string;
  exception_reason: string | null;
  period: string | null;
  customer: string | null;
  market: string | null;
  client_upc: string | null;
  client_item_description: string | null;
  discover_upc: string | null;
  discover_item_description: string | null;
  brand: string | null;
  category: string | null;
  client_sales: number | null;
  discover_sales: number | null;
  sales_delta: number | null;
  client_units: number | null;
  discover_units: number | null;
  unit_delta: number | null;
  match_confidence: number | null;
  client_row_count: number;
}

export interface BrandDiagRow {
  brand: string;
  client_rows: number;
  matched_rows: number;
  client_sales: number | null;
  match_rate: number;
}

export interface PeriodDiagRow {
  period: string;
  client_rows: number;
  matched_rows: number;
  client_sales: number | null;
  matched_client_sales: number | null;
  match_rate: number;
}

export interface BrandOverlapDiag {
  client_brand_count: number;
  discover_brand_count: number;
  overlap_count: number;
  client_unmatched_brands: string[];
}

export interface CoverageResponse {
  coverage_id: string;
  blocked: boolean;
  blocked_reasons: string[];
  coverage_summary: {
    comparison_mode: string;
    time_grain: string;
    customer_alignment: Record<string, string>;
    market_alignment: Record<string, string>;
    market_rollup_mode: boolean;
    market_hierarchy_detected: boolean;
    unmapped_client_markets: string[];
    warnings: string[];
    match_grain: string;
    brand_overlap_diagnostic: BrandOverlapDiag;
    brand_diagnostic: BrandDiagRow[];
    period_diagnostic: PeriodDiagRow[];
    brand_alias_map: Record<string, string>;
  };
  kpis: CoverageKpis;
  trend: TrendPoint[];
  exceptions: ExceptionRow[];
  drilldown: DrilldownRow[];
}
