/**
 * Types for /api/analytics. Rates are percentages (0-100), costs USD, times milliseconds.
 */

export interface AnalyticsFilters {
  start_date?: string;
  end_date?: string;
  workflow_id?: string;
}

export interface WorkflowMetrics {
  total_executions: number;
  successful_executions: number;
  execution_success_rate: number;
  avg_execution_duration_ms: number;
  total_stages: number;
  completed_stages: number;
  failed_stages: number;
  cancelled_stages: number;
  llm_calls: number;
  cache_hits: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number;
  success_rate: number;
  failure_rate: number;
}

export interface StageTypeMetrics {
  stage_type: string;
  runs: number;
  completed: number;
  failed: number;
  cache_hits: number;
  cache_hit_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  total_cost: number;
}

export interface ModelUtilization {
  provider: string;
  model: string;
  usage_count: number;
  share: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number;
}

export interface CacheMetrics {
  valid_entries: number;
  total_hits: number;
  total_misses: number;
  hit_rate: number;
  total_tokens_saved: number;
  total_cost_saved: number;
}

export interface LatencyMetrics {
  sample_count: number;
  min_ms: number;
  max_ms: number;
  avg_ms: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
}

export interface CostTrendPoint {
  date: string;
  cost: number;
  executions: number;
  llm_calls: number;
  cache_hits: number;
}

export interface TokenTrendPoint {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface RoutingEffectiveness {
  total_decisions: number;
  override_count: number;
  override_rate: number;
  fallback_count: number;
  fallback_rate: number;
  priority_distribution: Record<string, number>;
  top_models: { model: string; decisions: number }[];
}

export interface TimelineStage {
  stage_id: string | null;
  stage_name: string;
  stage_order: number;
  stage_type: string | null;
  status: string;
  cache_hit: boolean;
  model_used: string | null;
  provider: string | null;
  started_at: string | null;
  completed_at: string | null;
  start_offset_ms: number | null;
  end_offset_ms: number | null;
  duration_ms: number | null;
  latency_ms: number | null;
  estimated_cost: number;
}

export interface ExecutionTimeline {
  execution_id: string;
  workflow_id: string;
  started_at: string | null;
  completed_at: string | null;
  total_duration_ms: number;
  parallelism: number;
  stages: TimelineStage[];
}

export type ExportFormat = 'csv' | 'json';
export type ExportDataset = 'summary' | 'stage_runs';
