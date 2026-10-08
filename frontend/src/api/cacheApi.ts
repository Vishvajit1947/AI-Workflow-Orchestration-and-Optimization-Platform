/**
 * API client for cache operations.
 */
import api from '../lib/api';
import type { CacheEntry, CacheEntryFilters, CacheStats, CacheHitRate } from '../types/cache';

export const cacheApi = {
  /**
   * List cache entries, newest first.
   */
  async listEntries(params?: CacheEntryFilters): Promise<CacheEntry[]> {
    const response = await api.get('/cache/entries', { params });
    return response.data;
  },

  /**
   * Get cache statistics, optionally for one workflow.
   */
  async getStats(workflowId?: string): Promise<CacheStats> {
    const params = workflowId ? { workflow_id: workflowId } : {};
    const response = await api.get('/cache/stats', { params });
    return response.data;
  },

  /**
   * Permanently delete a cache entry.
   */
  async deleteEntry(entryId: string): Promise<void> {
    await api.delete(`/cache/entries/${entryId}`);
  },

  /**
   * Invalidate cache entries (all entries when no filter is given).
   */
  async clearCache(params?: {
    workflow_id?: string;
    stage_type?: string;
  }): Promise<{ entries_invalidated: number }> {
    const response = await api.post('/cache/clear', null, { params });
    return response.data;
  },

  /**
   * Invalidate entries whose TTL has passed.
   */
  async cleanupExpired(): Promise<{ entries_cleaned: number }> {
    const response = await api.post('/cache/cleanup-expired');
    return response.data;
  },

  /**
   * Get cache hit rate for a workflow.
   */
  async getWorkflowHitRate(workflowId: string): Promise<CacheHitRate> {
    const response = await api.get(`/cache/hit-rate/${workflowId}`);
    return response.data;
  }
};
