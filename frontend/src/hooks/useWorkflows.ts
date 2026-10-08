import { useState, useEffect, useCallback } from 'react';
import { workflowApi } from '../lib/workflows';
import type { WorkflowListItem, Workflow, PaginatedResponse } from '../types';

export function useWorkflowList() {
  const [data, setData] = useState<PaginatedResponse<WorkflowListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async (skip = 0, limit = 20, status?: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await workflowApi.list(skip, limit, status);
      setData(result);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useWorkflow(id: string | undefined) {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const result = await workflowApi.get(id);
      setWorkflow(result);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { workflow, loading, error, refetch: fetch };
}
