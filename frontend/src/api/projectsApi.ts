/**
 * Project Builder API: generated projects, their files, build runs and ZIP downloads.
 */
import api from '../lib/api';

export type ProjectStatus = 'initializing' | 'building' | 'succeeded' | 'failed' | 'cancelled' | 'unavailable';

export interface ProjectStep {
  attempt: number;
  component: string;
  kind: string;
  label: string;
  command: string;
  cwd: string;
  status: 'passed' | 'failed';
  exit_code: number | null;
  duration_ms: number;
  timed_out: boolean;
  output: string;
}

export interface ProjectRepairFile {
  path: string;
  action: 'modified' | 'created';
  previous_sha256: string | null;
  new_sha256: string;
}

export interface ProjectRepair {
  attempt: number;
  failed_step: string;
  diagnosis: string;
  files: ProjectRepairFile[];
  model: string | null;
  error: string | null;
}

export interface ProjectRun {
  id: string;
  execution_id: string | null;
  status: 'running' | 'succeeded' | 'failed' | 'cancelled' | 'unavailable';
  project_type: string | null;
  current_step: string | null;
  steps: ProjectStep[];
  repairs: ProjectRepair[];
  warnings: string[];
  error_summary: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  project_type: string | null;
  workflow_id: string | null;
  execution_id: string | null;
  file_count: number;
  created_at: string;
  updated_at: string;
  latest_run: ProjectRun | null;
}

export interface ProjectFile {
  path: string;
  size: number;
  language: string;
  content: string | null;
}

export const projectsApi = {
  async list(workflowId?: string): Promise<Project[]> {
    const { data } = await api.get<Project[]>('/projects', { params: workflowId ? { workflow_id: workflowId } : {} });
    return data;
  },
  async get(id: string): Promise<Project> {
    const { data } = await api.get<Project>(`/projects/${id}`);
    return data;
  },
  async files(id: string): Promise<ProjectFile[]> {
    const { data } = await api.get<ProjectFile[]>(`/projects/${id}/files`);
    return data;
  },
  async download(id: string): Promise<Blob> {
    const { data } = await api.get(`/projects/${id}/download`, { responseType: 'blob' });
    return data;
  },
};
