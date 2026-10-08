/**
 * TypeScript types for execution operations.
 */

export interface ExecutionStartRequest {
  default_provider?: string;
  default_model?: string | null;
  user_inputs?: Record<string, any>;
  use_cache?: boolean;
  use_routing?: boolean;                        // Let the router pick each stage's model
  routing_preferences?: Record<string, string>; // stage_id -> model_name override
  parallel?: boolean;                           // Run independent stages concurrently
  background?: boolean;                         // Return at once; follow via status/WebSocket
}

export interface StageExecutionDetail {
  id: string;
  stage_id: string;
  stage_name: string;
  stage_order: number;
  model_used: string | null;
  provider: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number;
  latency_ms: number | null;
  estimated_cost: number | string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled';
  result: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  cache_hit: boolean;                    // Whether result was served from cache
  cache_similarity: number | null;       // Cache hits only
  tokens_saved: number | null;           // Cache hits only
  cost_saved: number | string | null;    // Cache hits only (Decimal → string)
  was_routed?: boolean;                  // Model chosen by the routing engine
  routing_reason?: string | null;
  was_user_override?: boolean;
  was_fallback?: boolean;
  retry_count?: number;                  // Failed LLM attempts before the result
  fallback_from?: string | null;         // provider/model that failed before the fallback answered
}

export interface ExecutionSummary {
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_stages: number;
  completed_stages: number;
  failed_stages: number;
  total_tokens: number;
  total_cost: number | string;
  total_latency_ms: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface ExecutionDetailResponse {
  summary: ExecutionSummary;
  stages: StageExecutionDetail[];
}

export interface ExecutionStartResponse {
  execution_id: string;
  workflow_id: string;
  status: string;
  message: string;
  started_at: string;
}

export interface ExecutionListItem {
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  total_stages: number;
  completed_stages: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  total_cost: number;
}

// ---------- Live execution (Phase 5) ----------

export type LiveExecutionStatus = 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
export type LiveStageStatusValue = 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled';

export interface LiveStageStatus {
  stage_id: string;
  name: string;
  stage_order: number;
  stage_type: string | null;
  level: number;
  status: LiveStageStatusValue;
  provider: string | null;
  model: string | null;
  cache_hit: boolean;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExecutionStatus {
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: LiveExecutionStatus;
  parallel: boolean;
  progress: number;          // 0..1
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  stages: LiveStageStatus[];
  dag: WorkflowDAG | null;
}

/** Messages from /ws/executions/{id} */
export type ExecutionEvent =
  | ({ type: 'snapshot' } & ExecutionStatus)
  | { type: 'stage_update'; execution_id: string; stage: LiveStageStatus; progress: number }
  | { type: 'execution_status'; execution_id: string; status: LiveExecutionStatus | 'cancelling'; progress: number; error?: string | null }
  | { type: 'unknown_execution'; execution_id: string }
  | { type: 'pong' };

export interface ExecutionControlResponse {
  execution_id: string;
  status: string;
  message: string;
}

export const ACTIVE_EXECUTION_STATUSES: LiveExecutionStatus[] = ['queued', 'running', 'paused'];

// ---------- Workflow DAG ----------

export interface DAGNode {
  stage_id: string;
  name: string;
  stage_order: number;
  stage_type: string | null;
  level: number;
  dependencies: string[];
  is_merge_point: boolean;
  on_critical_path: boolean;
}

export interface WorkflowDAG {
  workflow_id?: string;
  nodes: DAGNode[];
  edges: { source: string; target: string }[];
  levels: string[][];
  critical_path: string[];
  parallelism_factor: number;
  max_width: number;
  ascii?: string;
}
