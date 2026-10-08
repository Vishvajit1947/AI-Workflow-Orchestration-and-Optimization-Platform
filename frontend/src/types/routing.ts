/**
 * TypeScript types for the model registry and stage-aware routing.
 */

export type PriorityFactor = 'cost' | 'speed' | 'quality' | 'balanced';

export interface ModelProfile {
  id: string;
  provider: string;
  model_name: string;
  display_name: string;
  capabilities: Record<string, number>;
  max_context_tokens: number;
  max_output_tokens: number | null;
  cost_per_input_token: number | string;   // Decimal → string
  cost_per_output_token: number | string;
  avg_latency_ms: number | null;
  is_available: boolean;
  supports_streaming: boolean;
  supports_function_calling: boolean;
  description: string | null;
  strengths: string[];
  limitations: string[];
  created_at: string;
  routable: boolean;                       // Available and provider has an API key
}

export interface ModelComparison {
  models: ModelProfile[];
  cheapest: string | null;
  fastest: string | null;
  most_capable: Record<string, string>;
}

export interface ModelRef {
  id: string;
  provider: string;
  model_name: string;
  display_name: string;
}

export interface RoutingRule {
  id: string;
  stage_type: string;
  priority_factor: PriorityFactor;
  max_cost_per_call: number | string | null;
  max_latency_ms: number | null;
  min_capability_score: number | string;
  preferred_model_id: string | null;
  fallback_model_id: string | null;
  preferred_model: ModelRef | null;
  fallback_model: ModelRef | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoutingRuleInput {
  priority_factor?: PriorityFactor;
  max_cost_per_call?: number | null;
  max_latency_ms?: number | null;
  min_capability_score?: number;
  preferred_model_id?: string | null;
  fallback_model_id?: string | null;
  is_active?: boolean;
}

export interface RoutingDecision {
  id: string;
  execution_id: string;
  stage_id: string;
  stage_type: string | null;
  selected_model_id: string | null;
  selected_provider: string;
  selected_model_name: string;
  selection_reason: string | null;
  priority_factor: string | null;
  alternatives_considered: Array<{
    model: string;
    provider: string;
    score: number;
    cost_per_call?: number;
    avg_latency_ms?: number | null;
  }>;
  was_user_override: boolean;
  was_fallback: boolean;
  created_at: string;
}

export interface RoutingPreviewItem {
  stage_id: string;
  stage_name: string;
  stage_type: string | null;
  provider: string | null;
  model_name: string | null;
  reason: string;
}

/** Capability scored for a stage type (mirrors backend capability_for_stage_type). */
export const CAPABILITIES = ['analysis', 'design', 'generation', 'testing', 'documentation', 'review', 'reasoning'];

export const capabilityForStageType = (stageType: string | null | undefined): string =>
  stageType && CAPABILITIES.includes(stageType) ? stageType : 'reasoning';

/** USD for a typical 1K-input / 500-output call (same basis the router's max_cost_per_call uses). */
export const typicalCallCost = (m: ModelProfile): number =>
  1000 * Number(m.cost_per_input_token) + 500 * Number(m.cost_per_output_token);
