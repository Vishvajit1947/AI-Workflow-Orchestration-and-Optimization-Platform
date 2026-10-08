import api from './api';
import type { Workflow, WorkflowCreate, WorkflowUpdate, WorkflowListItem, PaginatedResponse } from '../types';

export const workflowApi = {
  list: async (skip = 0, limit = 20, status?: string) => {
    const params: Record<string, unknown> = { skip, limit };
    if (status) params.status = status;
    const { data } = await api.get<PaginatedResponse<WorkflowListItem>>('/workflows', { params });
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get<Workflow>(`/workflows/${id}`);
    return data;
  },

  create: async (payload: WorkflowCreate) => {
    const { data } = await api.post<Workflow>('/workflows', payload);
    return data;
  },

  update: async (id: string, payload: WorkflowUpdate) => {
    const { data } = await api.patch<Workflow>(`/workflows/${id}`, payload);
    return data;
  },

  delete: async (id: string) => {
    await api.delete(`/workflows/${id}`);
  },

  validate: async (id: string) => {
    const { data } = await api.post<{ is_valid: boolean; errors: string[] }>(`/workflows/${id}/validate`);
    return data;
  },
};
