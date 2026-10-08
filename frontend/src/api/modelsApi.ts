/**
 * API client for the model registry.
 */
import api from '../lib/api';
import type { ModelComparison, ModelProfile } from '../types/routing';

export const modelsApi = {
  /**
   * List available models, optionally only those good at a capability.
   */
  async listModels(params?: {
    provider?: string;
    capability?: string;
    min_score?: number;
    include_unavailable?: boolean;
  }): Promise<ModelProfile[]> {
    const response = await api.get('/models', { params });
    return response.data;
  },

  /**
   * Get one model profile.
   */
  async getModel(provider: string, modelName: string): Promise<ModelProfile> {
    const response = await api.get(`/models/${provider}/${modelName}`);
    return response.data;
  },

  /**
   * Compare models: cheapest, fastest and most capable per capability.
   */
  async compareModels(capability?: string): Promise<ModelComparison> {
    const params = capability ? { capability } : {};
    const response = await api.get('/models/compare', { params });
    return response.data;
  },

  /**
   * Toggle whether the router may pick a model.
   */
  async setAvailability(provider: string, modelName: string, isAvailable: boolean): Promise<ModelProfile> {
    const response = await api.patch(`/models/${provider}/${modelName}`, { is_available: isAvailable });
    return response.data;
  }
};
