/**
 * One stage of an execution result, always in the same order:
 * header → execution metrics → routing / cache → output.
 */
import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, GitFork } from 'lucide-react';
import type { StageExecutionDetail } from '../../types/execution';
import { formatDuration } from '../../lib/format';
import { formatModelName, formatProvider, parseRoutingReason, type RoutingInfo } from '../../lib/resultFormat';
import { buildOutline, CopyButton, MarkdownRenderer, type OutlineEntry } from './MarkdownRenderer';

// Decimal fields arrive as strings from the API
export const usd = (value: number | string | null | undefined) => `$${Number(value ?? 0).toFixed(4)}`;

type StageStatus = StageExecutionDetail['status'];

// Icon + text for every status, so meaning never depends on colour alone
export const STAGE_STATUS: Record<StageStatus, { icon: string; label: string; badge: string; text: string }> = {
  completed: { icon: '✓', label: 'Completed', badge: 'bg-primary-500/10 text-primary-400 border-primary-500/30', text: 'text-primary-400' },
  running: { icon: '⟳', label: 'Running', badge: 'bg-blue-500/10 text-blue-300 border-blue-500/30', text: 'text-blue-300' },
  pending: { icon: '○', label: 'Pending', badge: 'bg-surface-700/40 text-surface-200/70 border-surface-700', text: 'text-surface-200/70' },
  failed: { icon: '✕', label: 'Failed', badge: 'bg-red-500/10 text-red-300 border-red-500/30', text: 'text-red-300' },
  skipped: { icon: '⚠', label: 'Skipped', badge: 'bg-amber-500/10 text-amber-300 border-amber-500/30', text: 'text-amber-300' },
  cancelled: { icon: '⊘', label: 'Cancelled', badge: 'bg-surface-700/40 text-surface-200/60 border-surface-700', text: 'text-surface-200/60' },
};

const SectionLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <p className={`text-[11px] font-semibold uppercase tracking-wider text-surface-200/50 ${className}`}>{children}</p>
);

// ---------- Level 1: header ----------

const RoutingChip: React.FC<{ stage: StageExecutionDetail }> = ({ stage }) => {
  if (stage.cache_hit || !stage.routing_reason) return null;
  const [label, color] = stage.was_user_override
    ? ['Override', 'text-surface-200/80 border-surface-700']
    : stage.was_fallback
    ? ['Fallback', 'text-amber-300 border-amber-500/30']
    : ['Routed', 'text-surface-200/80 border-surface-700'];
  return (
    <span data-testid="routing-chip" title={stage.routing_reason} className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium ${color}`}>
      <GitFork size={11} />
      {label}
    </span>
  );
};

export const StageHeader: React.FC<{
  stage: StageExecutionDetail;
  expanded: boolean;
  onToggle: () => void;
  bodyId: string;
}> = ({ stage, expanded, onToggle, bodyId }) => {
  const status = STAGE_STATUS[stage.status] ?? STAGE_STATUS.pending;
  return (
    <div className="flex items-start gap-3 px-5 py-4">
      <span
        aria-hidden
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-bold ${status.badge}`}
      >
        {status.icon}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="break-words text-lg font-semibold leading-snug text-white">{stage.stage_name}</h3>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-surface-200/50">
          <span className="font-medium">Stage {stage.stage_order + 1}</span>
          {stage.cache_hit && (
            <span className="inline-flex items-center gap-1 rounded border border-primary-500/30 px-1.5 py-0.5 text-[11px] font-medium text-primary-400">
              ▣ Cache Hit
            </span>
          )}
          <RoutingChip stage={stage} />
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <span
          data-testid="stage-status"
          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${status.badge}`}
        >
          <span aria-hidden className={stage.status === 'running' ? 'inline-block animate-spin' : ''}>{status.icon}</span>
          {status.label}
        </span>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={bodyId}
          aria-label={expanded ? `Collapse ${stage.stage_name}` : `Expand ${stage.stage_name}`}
          className="rounded p-1.5 text-surface-200/50 hover:bg-surface-700/60 hover:text-white"
        >
          {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
      </div>
    </div>
  );
};

// ---------- Level 2: execution metrics ----------

const Metric: React.FC<{
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  title?: string;
  valueClass?: string;
}> = ({ label, value, sub, title, valueClass = 'text-white' }) => (
  <div className="min-w-0 rounded-lg border border-surface-700 bg-surface-900/40 px-3.5 py-2.5" title={title}>
    <SectionLabel>{label}</SectionLabel>
    <p className={`mt-1 truncate text-base font-semibold tabular-nums ${valueClass}`}>{value}</p>
    {sub != null && <p className="mt-0.5 truncate text-xs text-surface-200/50">{sub}</p>}
  </div>
);

const routingLabel = (stage: StageExecutionDetail, routing: RoutingInfo | null) =>
  stage.cache_hit ? 'Cache' : routing?.strategy ?? 'Default';

export const ExecutionMetrics: React.FC<{ stage: StageExecutionDetail; routing: RoutingInfo | null }> = ({ stage, routing }) => {
  const status = STAGE_STATUS[stage.status] ?? STAGE_STATUS.pending;
  const hasTokenSplit = stage.input_tokens != null && stage.output_tokens != null && !stage.cache_hit;
  return (
    <div
      data-testid="stage-metrics"
      className="grid grid-cols-[repeat(auto-fill,minmax(max(9.5rem,calc((100%_-_1.5rem)/4)),1fr))] gap-2"
    >
      <Metric label="Status" value={`${status.icon} ${status.label}`} valueClass={status.text} />
      <Metric
        label={stage.cache_hit ? 'Cached model' : 'Model'}
        value={formatModelName(stage.model_used)}
        sub={stage.cache_hit ? 'from semantic cache' : stage.provider ? `via ${formatProvider(stage.provider)}` : undefined}
        title={stage.model_used ?? undefined}
      />
      <Metric
        label="Latency"
        value={formatDuration(stage.latency_ms ?? 0)}
        sub={stage.cache_hit ? 'instant' : 'LLM call'}
      />
      <Metric
        label="Cost"
        value={usd(stage.estimated_cost)}
        sub={stage.cache_hit && stage.cost_saved != null ? `${usd(stage.cost_saved)} saved` : undefined}
      />
      <Metric
        label="Tokens"
        value={stage.total_tokens.toLocaleString()}
        sub={
          stage.cache_hit && stage.tokens_saved != null
            ? `${stage.tokens_saved.toLocaleString()} saved`
            : hasTokenSplit
            ? `${stage.input_tokens!.toLocaleString()} in · ${stage.output_tokens!.toLocaleString()} out`
            : undefined
        }
      />
      <Metric
        label="Routing"
        value={routingLabel(stage, routing)}
        sub={routing?.score ? `score ${routing.score}` : undefined}
        valueClass={routing?.strategy === 'Fallback' ? 'text-amber-300' : 'text-white'}
      />
      <Metric
        label="Cache"
        value={stage.cache_hit ? '▣ HIT' : '○ MISS'}
        sub={
          stage.cache_hit && stage.cache_similarity != null
            ? `${(stage.cache_similarity * 100).toFixed(2)}% similar`
            : stage.cache_hit ? 'reused result' : 'executed live'
        }
        valueClass={stage.cache_hit ? 'text-primary-400' : 'text-surface-200/80'}
      />
      <Metric
        label="Duration"
        value={stage.duration_ms != null ? formatDuration(stage.duration_ms) : '—'}
        sub="stage wall time"
      />
    </div>
  );
};

// ---------- Level 3: routing / cache ----------

const Row: React.FC<{ label: string; children: React.ReactNode; mono?: boolean }> = ({ label, children, mono }) => (
  <div className="flex gap-3 py-1 text-sm">
    <dt className="w-24 shrink-0 text-surface-200/50">{label}</dt>
    <dd className={`min-w-0 text-surface-200/90 ${mono ? 'break-all font-mono text-xs leading-5' : 'break-words'}`}>{children}</dd>
  </div>
);

export const RoutingDecision: React.FC<{ stage: StageExecutionDetail; routing: RoutingInfo }> = ({ stage, routing }) => (
  <div data-testid="routing-decision" className="min-w-0 rounded-lg border border-surface-700 bg-surface-900/40 px-4 py-3">
    <SectionLabel className="mb-1.5">Routing decision</SectionLabel>
    <dl>
      <Row label="Strategy">{routing.strategy}</Row>
      {routing.task && <Row label="Task">{routing.task}</Row>}
      {routing.score && <Row label="Score"><span className="tabular-nums">{routing.score}</span></Row>}
      {routing.candidates != null && <Row label="Candidates"><span className="tabular-nums">{routing.candidates}</span></Row>}
      {stage.model_used && (
        <Row label="Model ID" mono>
          {stage.model_used}
          {stage.provider && <span className="text-surface-200/40"> ({stage.provider})</span>}
        </Row>
      )}
      {routing.detail && <Row label="Reason">{routing.detail}</Row>}
    </dl>
  </div>
);

export const CacheStatus: React.FC<{ stage: StageExecutionDetail }> = ({ stage }) => (
  <div data-testid="cache-status" className="min-w-0 rounded-lg border border-surface-700 bg-surface-900/40 px-4 py-3">
    <SectionLabel className="mb-1.5">Cache</SectionLabel>
    {stage.cache_hit ? (
      <>
        <p className="text-sm font-semibold text-primary-400">▣ HIT</p>
        <p className="mt-0.5 text-sm text-surface-200/70">
          Reused a previous valid stage result
          {stage.cache_similarity != null && <> · similarity {(stage.cache_similarity * 100).toFixed(2)}%</>}
        </p>
        {(stage.tokens_saved != null || stage.cost_saved != null) && (
          <p className="mt-1 text-xs text-surface-200/50">
            Saved {stage.tokens_saved != null && `${stage.tokens_saved.toLocaleString()} tokens`}
            {stage.tokens_saved != null && stage.cost_saved != null && ' · '}
            {stage.cost_saved != null && usd(stage.cost_saved)}
          </p>
        )}
      </>
    ) : (
      <>
        <p className="text-sm font-semibold text-surface-200/80">○ MISS</p>
        <p className="mt-0.5 text-sm text-surface-200/70">Executed stage using the selected model</p>
      </>
    )}
  </div>
);

// ---------- Level 4–5: output ----------

const LONG_OUTPUT_CHARS = 1500;

const OutlineNav: React.FC<{ entries: OutlineEntry[] }> = ({ entries }) => (
  <nav
    aria-label="Output sections"
    className="sticky top-0 z-10 -mx-5 mb-2 flex items-center gap-2 border-y border-surface-700 bg-surface-800/95 px-5 py-2 backdrop-blur"
  >
    <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-surface-200/40">Jump to</span>
    <div className="flex min-w-0 gap-1.5 overflow-x-auto">
      {entries.map((entry) => (
        <button
          key={entry.id}
          type="button"
          onClick={() => document.getElementById(entry.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          className="shrink-0 rounded-md border border-surface-700 px-2 py-0.5 text-xs text-surface-200/70 hover:border-primary-500/40 hover:text-white"
        >
          {entry.text}
        </button>
      ))}
    </div>
  </nav>
);

const NO_OUTPUT: Partial<Record<StageStatus, string>> = {
  pending: 'This stage has not run yet.',
  running: 'This stage is still running.',
  skipped: 'Skipped because an upstream stage failed.',
  cancelled: 'Cancelled before this stage produced output.',
};

export const OutputSection: React.FC<{ stage: StageExecutionDetail }> = ({ stage }) => {
  const idPrefix = `out-${stage.id}`;
  const outline = useMemo(
    () => (stage.result && stage.result.length > LONG_OUTPUT_CHARS ? buildOutline(stage.result, idPrefix) : []),
    [stage.result, idPrefix],
  );

  if (stage.status === 'failed' && stage.error_message) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
        <SectionLabel className="!text-red-300/80">✕ Error</SectionLabel>
        <p className="mt-1.5 whitespace-pre-wrap break-words font-mono text-sm text-red-300">{stage.error_message}</p>
      </div>
    );
  }
  if (!stage.result) {
    return <p className="text-sm text-surface-200/50">{NO_OUTPUT[stage.status] ?? 'No output.'}</p>;
  }

  const words = stage.result.trim().split(/\s+/).length;
  return (
    <section aria-label={`${stage.stage_name} output`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <h4 className="text-xs font-bold uppercase tracking-[0.14em] text-white">Output</h4>
          <span className="text-xs text-surface-200/40">{words.toLocaleString()} words</span>
        </div>
        <CopyButton text={stage.result} label="Copy output" />
      </div>
      {outline.length > 0 && <OutlineNav entries={outline} />}
      <MarkdownRenderer content={stage.result} idPrefix={idPrefix} />
    </section>
  );
};

// ---------- composed stage ----------

export const StageResult: React.FC<{ stage: StageExecutionDetail }> = ({ stage }) => {
  const [expanded, setExpanded] = useState(true);
  const routing = useMemo(
    () => (stage.cache_hit ? null : parseRoutingReason(stage.routing_reason, stage)),
    [stage],
  );
  const bodyId = `stage-body-${stage.id}`;
  const showCache = stage.cache_hit || stage.status === 'completed';
  const retries = stage.retry_count ?? 0;

  return (
    <article data-testid="stage-result" className="rounded-xl border border-surface-700 bg-surface-800">
      <StageHeader stage={stage} expanded={expanded} onToggle={() => setExpanded((e) => !e)} bodyId={bodyId} />
      {expanded && (
        <div id={bodyId} className="space-y-4 border-t border-surface-700 px-5 pb-6 pt-4">
          <ExecutionMetrics stage={stage} routing={routing} />

          {retries > 0 && (
            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
              ⚠ {retries} failed attempt{retries === 1 ? '' : 's'}
              {stage.fallback_from && ` · fell back from ${stage.fallback_from}`}
            </p>
          )}

          {(routing || showCache) && (
            <div className="grid grid-cols-[repeat(auto-fit,minmax(17rem,1fr))] gap-3">
              {routing && <RoutingDecision stage={stage} routing={routing} />}
              {showCache && <CacheStatus stage={stage} />}
            </div>
          )}

          <div className="border-t-2 border-surface-700 pt-5">
            <OutputSection stage={stage} />
          </div>
        </div>
      )}
    </article>
  );
};
