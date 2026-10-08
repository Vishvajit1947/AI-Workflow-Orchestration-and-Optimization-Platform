import api from './api';
import type { Stage, StageCreate, StageUpdate, StageDependencyCreate, StageDependency, MessageResponse } from '../types';

export const stageApi = {
  list: async (workflowId: string) => {
    const { data } = await api.get<Stage[]>(`/stages/workflow/${workflowId}`);
    return data;
  },
  get: async (id: string) => {
    const { data } = await api.get<Stage>(`/stages/${id}`);
    return data;
  },
  create: async (payload: StageCreate) => {
    const { data } = await api.post<Stage>('/stages', payload);
    return data;
  },
  update: async (id: string, payload: StageUpdate) => {
    const { data } = await api.patch<Stage>(`/stages/${id}`, payload);
    return data;
  },
  delete: async (id: string) => {
    const { data } = await api.delete<MessageResponse>(`/stages/${id}`);
    return data;
  },
  reorder: async (workflowId: string, stageIds: string[]) => {
    const { data } = await api.put<Stage[]>(`/stages/workflow/${workflowId}/reorder`, { stage_ids: stageIds });
    return data;
  },
  addDependency: async (stageId: string, dep: StageDependencyCreate) => {
    const { data } = await api.post<StageDependency>(`/stages/${stageId}/dependencies`, dep);
    return data;
  },
  removeDependency: async (depId: string) => {
    await api.delete(`/stages/dependencies/${depId}`);
  },
};
