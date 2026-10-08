/**
 * API client for execution operations.
 */
import api from '../lib/api';
import type {
  ExecutionStartRequest,
  ExecutionStartResponse,
  ExecutionDetailResponse,
  ExecutionListItem,
  ExecutionStatus,
  ExecutionControlResponse,
  WorkflowDAG
} from '../types/execution';

export const executionApi = {
  /**
   * Start workflow execution.
   */
  async startExecution(
    workflowId: string,
    request: ExecutionStartRequest
  ): Promise<ExecutionStartResponse> {
    const response = await api.post(
      `/workflows/${workflowId}/execute`,
      request
    );
    return response.data;
  },

  /**
   * Get execution details by ID.
   */
  async getExecution(executionId: string): Promise<ExecutionDetailResponse> {
    const response = await api.get(`/executions/${executionId}`);
    return response.data;
  },

  /**
   * List all executions, optionally filtered by workflow.
   */
  async listExecutions(
    workflowId?: string,
    limit: number = 20,
    offset: number = 0
  ): Promise<ExecutionListItem[]> {
    const params: any = { limit, offset };
    if (workflowId) params.workflow_id = workflowId;
    const response = await api.get('/executions', { params });
    return response.data;
  },

  /**
   * Get latest execution for a workflow.
   */
  async getLatestExecution(workflowId: string): Promise<ExecutionDetailResponse> {
    const response = await api.get(
      `/workflows/${workflowId}/executions/latest`
    );
    return response.data;
  },

  /**
   * Live per-stage status of an execution.
   */
  async getStatus(executionId: string): Promise<ExecutionStatus> {
    const response = await api.get(`/executions/${executionId}/status`);
    return response.data;
  },

  /**
   * The workflow's execution that is still queued, running or paused (404 if none).
   */
  async getLiveExecution(workflowId: string): Promise<ExecutionStatus> {
    const response = await api.get(`/workflows/${workflowId}/executions/live`);
    return response.data;
  },

  async pause(executionId: string): Promise<ExecutionControlResponse> {
    const response = await api.post(`/executions/${executionId}/pause`);
    return response.data;
  },

  async resume(executionId: string): Promise<ExecutionControlResponse> {
    const response = await api.post(`/executions/${executionId}/resume`);
    return response.data;
  },

  async cancel(executionId: string): Promise<ExecutionControlResponse> {
    const response = await api.post(`/executions/${executionId}/cancel`);
    return response.data;
  },

  /**
   * Dependency graph of a workflow: levels, edges, critical path.
   */
  async getDag(workflowId: string): Promise<WorkflowDAG> {
    const response = await api.get(`/workflows/${workflowId}/dag`);
    return response.data;
  }
};
