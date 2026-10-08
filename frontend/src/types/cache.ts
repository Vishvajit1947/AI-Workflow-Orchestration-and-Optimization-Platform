/**
 * TypeScript types for cache operations.
 * Decimal fields arrive from the API as strings (Pydantic serialises Decimal
 * as a string); wrap them in Number() before formatting.
 */

export interface CacheEntry {
  id: string;
  workflow_id: string | null;
  stage_id: string | null;
  stage_type: string | null;
  input_text: string;
  result: string;
  result_tokens: number | null;
  model_used: string | null;
  hit_count: number;
  similarity_score: number | null;
  is_valid: boolean;
  created_at: string;
  expires_at: string | null;
}

export interface CacheStats {
  total_entries: number;
  total_hits: number;
  hit_rate: number;
  total_tokens_saved: number;
  total_cost_saved: number | string;
  avg_similarity_score: number;
}

export interface CacheHitRate {
  workflow_id: string;
  total_cache_entries: number;
  total_cache_hits: number;
  hit_rate: number;
  hit_rate_percentage: string;
}

export interface CacheEntryFilters {
  workflow_id?: string;
  stage_type?: string;
  is_valid?: boolean;
  limit?: number;
  offset?: number;
}
