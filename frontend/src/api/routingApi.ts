/**
 * API client for routing rules, decisions and previews.
 */
import api from '../lib/api';
import type { RoutingDecision, RoutingPreviewItem, RoutingRule, RoutingRuleInput } from '../types/routing';

export const routingApi = {
  async listRules(): Promise<RoutingRule[]> {
    const response = await api.get('/routing/rules');
    return response.data;
  },

  async createRule(stageType: string, rule: RoutingRuleInput): Promise<RoutingRule> {
    const response = await api.post('/routing/rules', { stage_type: stageType, ...rule });
    return response.data;
  },

  async updateRule(stageType: string, updates: RoutingRuleInput): Promise<RoutingRule> {
    const response = await api.put(`/routing/rules/${stageType}`, updates);
    return response.data;
  },

  async deleteRule(stageType: string): Promise<void> {
    await api.delete(`/routing/rules/${stageType}`);
  },

  /**
   * Routing decision log, newest first.
   */
  async listDecisions(params?: { execution_id?: string; stage_type?: string; limit?: number }): Promise<RoutingDecision[]> {
    const response = await api.get('/routing/decisions', { params });
    return response.data;
  },

  /**
   * Which model each stage of a workflow would be routed to right now.
   */
  async preview(workflowId: string): Promise<RoutingPreviewItem[]> {
    const response = await api.get(`/routing/preview/${workflowId}`);
    return response.data;
  }
};
