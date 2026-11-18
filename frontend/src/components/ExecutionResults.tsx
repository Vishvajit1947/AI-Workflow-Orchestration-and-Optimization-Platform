/**
 * Tabbed interface for viewing execution results.
 */
import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Database } from 'lucide-react';
import { transition } from '../lib/motion';
import type { ExecutionDetailResponse, StageExecutionDetail } from '../types/execution';
import { ExecutionTimelineView } from './charts/TimelineChart';
import { StageResult, usd } from './results/StageResult';
import { ArtifactOutput } from './results/ArtifactOutput';
import { executionApi } from '../api/executionApi';
import { safeFileStem } from '../lib/download';
import type { Artifact } from '../types/execution';
import { StatusBadge } from './ui/StatusBadge';
import { Tabs } from './ui/Tabs';
import { MetricCard } from './metrics/MetricCard';

const CacheHitBadge: React.FC = () => (
  <span className="inline-flex items-center gap-1 rounded-pill bg-primary/10 px-2 py-0.5 text-[11px] font-book text-primary-700">
    <Database size={11} aria-hidden />
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
  const { summary } = execution;

  return (
    <section className="card min-w-0" aria-label="Execution results">
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
        <div className="min-w-0">
          <h2 className="text-[17px] font-medium text-ink">Execution Results</h2>
          <p className="mt-1 truncate font-mono text-xs text-ink-muted" title="Execution ID">
            {summary.execution_id}
          </p>
        </div>
        <StatusBadge status={summary.status} data-testid="execution-status" />
      </div>

      <Tabs
        className="mx-5 mt-4 sm:mx-6"
        ariaLabel="Execution result views"
        items={TABS.map((t) => ({ id: t.id, label: t.label }))}
        value={activeTab}
        onChange={setActiveTab}
      />

      <div className="p-5 sm:p-6">
        {/* The new tab panel settles in with a small slide, like Mercury's tabbed sections (no wait on exit) */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0, transition: transition.enter }}
        >
            {activeTab === 'stages' && (
              <StagesTab stages={execution.stages} executionId={summary.execution_id} artifact={execution.artifact ?? null} />
            )}
            {activeTab === 'timeline' && <ExecutionTimelineView executionId={summary.execution_id} />}
            {activeTab === 'context' && <ContextTab stages={execution.stages} />}
            {activeTab === 'metrics' && <MetricsTab summary={summary} stages={execution.stages} />}
        </motion.div>
      </div>
    </section>
  );
};

// --- Stage Results Tab ---
const StagesTab: React.FC<{ stages: StageExecutionDetail[]; executionId: string; artifact: Artifact | null }> = ({
  stages, executionId, artifact,
}) => (
  <div className="space-y-4">
    {artifact && artifact.files.length > 0 && (
      <section aria-label="Combined project" className="rounded-card border border-primary/25 bg-primary/[0.03] px-4 py-4 sm:px-5">
        <p className="mb-3 text-xs text-ink-secondary">Files from all stages, combined into one project.</p>
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
    <div>
      <p className="mb-5 text-sm text-ink-secondary">
        Shows how context (outputs) flow from stage to stage
      </p>
      <ol>
        {stages.map((stage, index) => (
          <li key={stage.id} className="flex items-stretch gap-4">
            {/* Timeline connector */}
            <div className="flex flex-col items-center">
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] tabular ${
                  stage.status === 'completed'
                    ? 'bg-primary text-white'
                    : stage.status === 'failed'
                    ? 'bg-danger text-white'
                    : 'bg-lavender text-ink-secondary'
                }`}
              >
                {index + 1}
              </div>
              {index < stages.length - 1 && <div className="my-1.5 w-px flex-1 bg-hairline-strong" />}
            </div>

            {/* Stage card */}
            <div className="mb-5 min-w-0 flex-1 rounded-card bg-lavender-soft p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-medium text-ink">{stage.stage_name}</h4>
                {stage.cache_hit && <CacheHitBadge />}
              </div>
              {stage.result && (
                <p className="line-clamp-3 text-sm leading-relaxed text-ink-secondary">
                  {stage.result.substring(0, 200)}
                  {stage.result.length > 200 && '...'}
                </p>
              )}
              <div className="mt-2 text-xs text-ink-muted tabular">
                {stage.total_tokens} tokens · {stage.latency_ms}ms
              </div>
            </div>
          </li>
        ))}
      </ol>
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
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
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
        <h3 className="mb-3 text-[15px] font-medium text-ink">Stage Breakdown</h3>
        <div className="overflow-x-auto rounded-card border border-hairline">
          <table className="data-table tabular">
            <thead>
              <tr>
                <th>#</th>
                <th>Stage</th>
                <th>Model</th>
                <th>Source</th>
                <th className="!text-right">Tokens</th>
                <th className="!text-right">Latency</th>
                <th className="!text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((stage) => (
                <tr key={stage.id}>
                  <td className="text-ink-muted">{stage.stage_order + 1}</td>
                  <td className="font-book text-ink">{stage.stage_name}</td>
                  <td className="text-ink-secondary">{stage.model_used || 'N/A'}</td>
                  <td>
                    {stage.cache_hit ? (
                      <span className="font-book text-primary-700">Cache</span>
                    ) : (
                      <span className="text-ink-secondary">{stage.provider || 'LLM'}</span>
                    )}
                  </td>
                  <td className="text-right">{stage.total_tokens.toLocaleString()}</td>
                  <td className="text-right">{stage.latency_ms || 0}ms</td>
                  <td className="text-right">
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
