/**
 * API client for analytics.
 */
import api from '../lib/api';
import type {
  AnalyticsFilters, CacheMetrics, CostTrendPoint, ExecutionTimeline, ExportDataset, ExportFormat,
  LatencyMetrics, ModelUtilization, RoutingEffectiveness, StageTypeMetrics, TokenTrendPoint, WorkflowMetrics,
} from '../types/analytics';

const get = async <T,>(path: string, params?: object): Promise<T> => (await api.get(path, { params })).data;

export const analyticsApi = {
  getOverview: (filters?: AnalyticsFilters) => get<WorkflowMetrics>('/analytics/overview', filters),
  getStageTypes: (filters?: AnalyticsFilters) => get<StageTypeMetrics[]>('/analytics/stage-types', filters),
  getModels: (filters?: AnalyticsFilters) => get<ModelUtilization[]>('/analytics/models', filters),
  getCache: (filters?: AnalyticsFilters) => get<CacheMetrics>('/analytics/cache', filters),
  getLatency: (filters?: AnalyticsFilters) => get<LatencyMetrics>('/analytics/latency', filters),
  getRouting: (filters?: AnalyticsFilters) => get<RoutingEffectiveness>('/analytics/routing', filters),
  getCostTrend: (filters?: AnalyticsFilters) => get<CostTrendPoint[]>('/analytics/costs', filters),
  getTokenTrend: (filters?: AnalyticsFilters) => get<TokenTrendPoint[]>('/analytics/tokens', filters),
  getTimeline: (executionId: string) => get<ExecutionTimeline>(`/analytics/timeline/${executionId}`),

  /**
   * Download an export as a file (fetched as a blob, saved via a temporary link).
   */
  async downloadExport(format: ExportFormat, dataset: ExportDataset, filters?: AnalyticsFilters): Promise<void> {
    const response = await api.get('/analytics/export', {
      params: { format, dataset, ...filters },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = `analytics-${dataset}-${new Date().toISOString().slice(0, 10)}.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};
