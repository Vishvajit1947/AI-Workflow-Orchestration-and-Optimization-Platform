// ============================================
// Workflow Types
// ============================================

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  objective: string | null;
  status: 'draft' | 'running' | 'completed' | 'failed' | 'paused';
  created_at: string;
  updated_at: string;
  stages: StageBrief[];
}

export interface WorkflowListItem {
  id: string;
  name: string;
  description: string | null;
  status: string;
  stage_count: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  name: string;
  description?: string;
  objective?: string;
}

export interface WorkflowUpdate {
  name?: string;
  description?: string;
  objective?: string;
  status?: string;
}

// ============================================
// Stage Types
// ============================================

export interface StageBrief {
  id: string;
  name: string;
  stage_order: number;
  stage_type: string | null;
  status: string;
}

export interface Stage {
  id: string;
  workflow_id: string;
  name: string;
  instruction: string;
  stage_order: number;
  stage_type: string | null;
  model_preference: string | null;
  config: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
  dependencies: StageDependency[];
}

export interface StageCreate {
  workflow_id: string;
  name: string;
  instruction: string;
  stage_order: number;
  stage_type?: string;
  model_preference?: string;
  config?: Record<string, unknown>;
  dependencies?: StageDependencyCreate[];
}

export interface StageUpdate {
  name?: string;
  instruction?: string;
  stage_order?: number;
  stage_type?: string;
  model_preference?: string | null;  // null clears it (back to automatic routing)
  config?: Record<string, unknown>;
  status?: string;
}

export interface StageDependency {
  id: string;
  stage_id: string;
  depends_on_stage_id: string;
  dependency_type: 'sequential' | 'merge';
}

export interface StageDependencyCreate {
  depends_on_stage_id: string;
  dependency_type?: 'sequential' | 'merge';
}

// ============================================
// Pagination
// ============================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

export interface MessageResponse {
  message: string;
  detail?: string;
}
