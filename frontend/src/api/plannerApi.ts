/**
 * Workflow Planner API client
 * 
 * Provides intelligent workflow planning from natural language objectives.
 */

import api from '../lib/api';

export interface ObjectiveAnalysisRequest {
  objective: string;
}

export interface StagePlan {
  id: string;
  name: string;
  description: string;
  instruction: string;
  stage_type: 'analysis' | 'design' | 'generation' | 'testing' | 'documentation' | 'review' | 'custom';
  dependencies: string[];
  expected_output: string;
  model_preference?: string | null;
}

export interface ObjectiveAnalysisResponse {
  complexity: 'simple' | 'complex';
  reason: string;
  stages: StagePlan[];
  estimated_duration_minutes?: number;
}

export interface WorkflowGenerationRequest {
  objective: string;
  plan: ObjectiveAnalysisResponse;
  auto_execute?: boolean;
}

export const plannerApi = {
  /**
   * Analyze a user's objective and generate a workflow plan
   */
  analyzeObjective: async (
    objective: string,
    provider?: string,
    model?: string
  ): Promise<ObjectiveAnalysisResponse> => {
    const params: Record<string, string> = {};
    if (provider) params.provider = provider;
    if (model) params.model = model;

    const { data } = await api.post<ObjectiveAnalysisResponse>(
      '/planner/analyze',
      { objective },
      { params }
    );
    return data;
  },

  /**
   * Generate a complete workflow from an approved plan
   */
  generateWorkflow: async (
    request: WorkflowGenerationRequest
  ) => {
    const { data } = await api.post('/planner/generate', request);
    return data;
  },
};

