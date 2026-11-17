/**
 * Tabbed interface for viewing execution results.
 */
import React, { useState } from 'react';
import { Database } from 'lucide-react';
import type { ExecutionDetailResponse, StageExecutionDetail } from '../types/execution';
import { ExecutionTimelineView } from './charts/TimelineChart';
import { StageResult, usd } from './results/StageResult';
import { ArtifactOutput } from './results/ArtifactOutput';
import { executionApi } from '../api/executionApi';
import { safeFileStem } from '../lib/download';
import type { Artifact } from '../types/execution';
import { StatusBadge } from './ui/StatusBadge';
import { MetricCard } from './metrics/MetricCard';

const CacheHitBadge: React.FC = () => (
  <span className="px-2 py-1 bg-primary-500/15 text-primary-400 rounded text-xs font-medium flex items-center gap-1">
    <Database size={12} />
    Cache Hit
  </span>
);

interface ExecutionResultsProps {
  execution: ExecutionDetailResponse;
}

const TABS = [
  { id: 'stages', label: 'Stage Results' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'context', label: 'Context Flow' },
  { id: 'metrics', label: 'Metrics' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export const ExecutionResults: React.FC<ExecutionResultsProps> = ({ execution }) => {
  const [activeTab, setActiveTab] = useState<TabId>('stages');

  return (
    <div className="glass rounded-xl p-5 text-white sm:p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">Execution Results</h2>
          <p className="mt-0.5 truncate font-mono text-xs text-surface-200/40" title="Execution ID">
            {execution.summary.execution_id}
          </p>
        </div>
        <StatusBadge status={execution.summary.status} data-testid="execution-status" />
      </div>

      <div className="mb-6 overflow-x-auto border-b border-surface-700">
        <div className="flex gap-5" role="tablist" aria-label="Execution result views">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`-mb-px whitespace-nowrap border-b-2 px-1 pb-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:text-white ${
                activeTab === tab.id
                  ? 'border-primary-400 text-primary-400'
                  : 'border-transparent text-surface-200/50 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'stages' && (
        <StagesTab stages={execution.stages} executionId={execution.summary.execution_id} artifact={execution.artifact ?? null} />
      )}
      {activeTab === 'timeline' && <ExecutionTimelineView executionId={execution.summary.execution_id} />}
      {activeTab === 'context' && <ContextTab stages={execution.stages} />}
      {activeTab === 'metrics' && <MetricsTab summary={execution.summary} stages={execution.stages} />}
    </div>
  );
};

// --- Stage Results Tab ---
const StagesTab: React.FC<{ stages: StageExecutionDetail[]; executionId: string; artifact: Artifact | null }> = ({
  stages, executionId, artifact,
}) => (
  <div className="space-y-5">
    {artifact && artifact.files.length > 0 && (
      <section aria-label="Combined project" className="rounded-xl border border-primary-500/30 bg-surface-800 px-5 py-4">
        <p className="mb-3 text-xs text-surface-200/60">Files from all stages, combined into one project.</p>
        <ArtifactOutput
          artifact={artifact}
          getZip={() => executionApi.downloadExecutionZip(executionId)}
          zipName={`${safeFileStem(artifact.name, 'project')}.zip`}
        />
      </section>
    )}
    {stages.map((stage) => (
      <StageResult key={stage.id} stage={stage} executionId={executionId} />
    ))}
  </div>
);

// --- Context Flow Tab ---
const ContextTab: React.FC<{ stages: StageExecutionDetail[] }> = ({ stages }) => {
  return (
    <div className="space-y-6">
      <p className="text-surface-200/60 text-sm">
        Shows how context (outputs) flow from stage to stage
      </p>
      <div className="relative">
        {stages.map((stage, index) => (
          <div key={stage.id} className="flex items-start mb-6">
            {/* Timeline connector */}
            <div className="flex flex-col items-center mr-4">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-semibold ${
                  stage.status === 'completed'
                    ? 'bg-primary-500'
                    : stage.status === 'failed'
                    ? 'bg-red-500'
                    : 'bg-surface-700'
                }`}
              >
                {index + 1}
              </div>
              {index < stages.length - 1 && (
                <div className="w-0.5 h-16 bg-surface-700 my-2" />
              )}
            </div>

            {/* Stage card */}
            <div className="flex-1 bg-surface-900/60 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="font-semibold">{stage.stage_name}</h4>
                {stage.cache_hit && <CacheHitBadge />}
              </div>
              {stage.result && (
                <p className="text-sm text-surface-200/80 line-clamp-3">
                  {stage.result.substring(0, 200)}
                  {stage.result.length > 200 && '...'}
                </p>
              )}
              <div className="mt-2 text-xs text-surface-200/50">
                {stage.total_tokens} tokens · {stage.latency_ms}ms
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// --- Metrics Tab ---
const MetricsTab: React.FC<{
  summary: ExecutionDetailResponse['summary'];
  stages: StageExecutionDetail[];
}> = ({ summary, stages }) => {
  const avgTokens = summary.total_stages > 0 ? summary.total_tokens / summary.total_stages : 0;
  const totalCost = Number(summary.total_cost);
  const cachedStages = stages.filter((s) => s.cache_hit);
  const cacheHits = cachedStages.length;
  const savedTokens = cachedStages.reduce((sum, s) => sum + (s.tokens_saved ?? 0), 0);
  const savedCost = cachedStages.reduce((sum, s) => sum + Number(s.cost_saved ?? 0), 0);
  const hitRate = stages.length > 0 ? (cacheHits / stages.length) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MetricCard
          label="Total Duration"
          value={`${(summary.duration_ms || 0).toLocaleString()}ms`}
          detail={`${((summary.duration_ms || 0) / 1000).toFixed(1)}s`}
        />
        <MetricCard
          label="Total Tokens"
          value={summary.total_tokens.toLocaleString()}
          detail={
            cacheHits > 0
              ? `${savedTokens.toLocaleString()} saved via cache`
              : `Avg: ${Math.round(avgTokens)}/stage`
          }
        />
        <MetricCard
          label="Total Cost"
          value={usd(totalCost)}
          detail={
            cacheHits > 0
              ? `${usd(savedCost)} saved via cache`
              : `${usd(totalCost / (summary.total_stages || 1))}/stage`
          }
        />
        <MetricCard
          label="Stages"
          value={`${summary.completed_stages}/${summary.total_stages}`}
          detail={summary.failed_stages > 0 ? `${summary.failed_stages} failed` : 'All passed'}
        />
        <MetricCard
          label="Cache Hits"
          value={`${cacheHits}/${stages.length}`}
          detail={`${hitRate.toFixed(0)}% hit rate`}
        />
      </div>

      {/* Stage breakdown */}
      <div>
        <h3 className="font-semibold mb-3">Stage Breakdown</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-900">
              <tr>
                <th className="px-4 py-2 text-left">#</th>
                <th className="px-4 py-2 text-left">Stage</th>
                <th className="px-4 py-2 text-left">Model</th>
                <th className="px-4 py-2 text-left">Source</th>
                <th className="px-4 py-2 text-right">Tokens</th>
                <th className="px-4 py-2 text-right">Latency</th>
                <th className="px-4 py-2 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((stage) => (
                <tr key={stage.id} className="border-b border-surface-700">
                  <td className="px-4 py-2">{stage.stage_order + 1}</td>
                  <td className="px-4 py-2 font-medium">{stage.stage_name}</td>
                  <td className="px-4 py-2 text-surface-200/60">{stage.model_used || 'N/A'}</td>
                  <td className="px-4 py-2">
                    {stage.cache_hit ? (
                      <span className="text-primary-400 font-medium">Cache</span>
                    ) : (
                      <span className="text-surface-200/60">{stage.provider || 'LLM'}</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">{stage.total_tokens.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right">{stage.latency_ms || 0}ms</td>
                  <td className="px-4 py-2 text-right">
                    {usd(stage.estimated_cost)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
