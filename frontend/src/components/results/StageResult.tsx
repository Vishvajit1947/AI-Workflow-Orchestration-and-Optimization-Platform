/**
 * One stage of an execution result, always in the same order:
 * header → execution metrics → routing / cache → output.
 */
import React, { useMemo, useState } from 'react';
import { ChevronRight, GitFork } from 'lucide-react';
import type { StageExecutionDetail } from '../../types/execution';
import { formatDuration } from '../../lib/format';
import { formatModelName, formatProvider, parseRoutingReason, type RoutingInfo } from '../../lib/resultFormat';
import { buildOutline, CopyButton, MarkdownRenderer, type OutlineEntry } from './MarkdownRenderer';
import { ArtifactOutput, DocumentDownloads } from './ArtifactOutput';
import { executionApi } from '../../api/executionApi';
import { Collapse } from '../motion/Motion';
import { safeFileStem } from '../../lib/download';

// Decimal fields arrive as strings from the API
export const usd = (value: number | string | null | undefined) => `$${Number(value ?? 0).toFixed(4)}`;

type StageStatus = StageExecutionDetail['status'];

// Icon + text for every status, so meaning never depends on colour alone
export const STAGE_STATUS: Record<StageStatus, { icon: string; label: string; badge: string; text: string }> = {
  completed: { icon: '✓', label: 'Completed', badge: 'bg-success-soft text-success border-success-line', text: 'text-success' },
  running: { icon: '⟳', label: 'Running', badge: 'bg-info-soft text-info border-info-line', text: 'text-info' },
  pending: { icon: '○', label: 'Pending', badge: 'bg-lavender-soft text-ink-secondary border-hairline-strong', text: 'text-ink-secondary' },
  failed: { icon: '✕', label: 'Failed', badge: 'bg-danger-soft text-danger border-danger-line', text: 'text-danger' },
  skipped: { icon: '⚠', label: 'Skipped', badge: 'bg-warning-soft text-warning border-warning-line', text: 'text-warning' },
  cancelled: { icon: '⊘', label: 'Cancelled', badge: 'bg-lavender-soft text-ink-muted border-hairline-strong', text: 'text-ink-muted' },
};

const SectionLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <p className={`text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted ${className}`}>{children}</p>
);

// ---------- Level 1: header ----------

const RoutingChip: React.FC<{ stage: StageExecutionDetail }> = ({ stage }) => {
  if (stage.cache_hit || !stage.routing_reason) return null;
  const [label, color] = stage.was_user_override
    ? ['Override', 'bg-[rgba(112,115,147,0.1)] text-ink-secondary']
    : stage.was_fallback
    ? ['Fallback', 'bg-warning-soft text-warning']
    : ['Routed', 'bg-[rgba(112,115,147,0.1)] text-ink-secondary'];
  return (
    <span data-testid="routing-chip" title={stage.routing_reason} className={`inline-flex items-center gap-1 rounded-pill px-2 py-0.5 text-[11px] font-book ${color}`}>
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
    <div className="flex items-start gap-3 px-4 py-4 sm:px-5">
      <span
        aria-hidden
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm ${status.badge}`}
      >
        {status.icon}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="break-words text-base font-medium leading-snug text-ink">{stage.stage_name}</h3>
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
          <span className="font-book">Stage {stage.stage_order + 1}</span>
          {stage.cache_hit && (
            <span className="inline-flex items-center gap-1 rounded-pill bg-primary/10 px-2 py-0.5 text-[11px] font-book text-primary-700">
              ▣ Cache Hit
            </span>
          )}
          <RoutingChip stage={stage} />
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <span
          data-testid="stage-status"
          className={`hidden items-center gap-1.5 rounded-pill border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.05em] sm:inline-flex ${status.badge}`}
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
          className="btn btn-ghost btn-icon btn-sm"
        >
          <ChevronRight size={18} className={`transition-transform duration-300 ease-mercury ${expanded ? 'rotate-90' : ''}`} />
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
}> = ({ label, value, sub, title, valueClass = 'text-ink' }) => (
  <div className="min-w-0 rounded-[10px] bg-lavender-soft px-3.5 py-2.5" title={title}>
    <SectionLabel>{label}</SectionLabel>
    <p className={`mt-1 truncate text-[15px] font-medium tabular-nums ${valueClass}`}>{value}</p>
    {sub != null && <p className="mt-0.5 truncate text-xs text-ink-muted">{sub}</p>}
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
        valueClass={routing?.strategy === 'Fallback' ? 'text-warning' : 'text-ink'}
      />
      <Metric
        label="Cache"
        value={stage.cache_hit ? '▣ HIT' : '○ MISS'}
        sub={
          stage.cache_hit && stage.cache_similarity != null
            ? `${(stage.cache_similarity * 100).toFixed(2)}% similar`
            : stage.cache_hit ? 'reused result' : 'executed live'
        }
        valueClass={stage.cache_hit ? 'text-primary-700' : 'text-ink-secondary'}
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
    <dt className="w-24 shrink-0 text-ink-muted">{label}</dt>
    <dd className={`min-w-0 text-ink ${mono ? 'break-all font-mono text-xs leading-5' : 'break-words'}`}>{children}</dd>
  </div>
);

export const RoutingDecision: React.FC<{ stage: StageExecutionDetail; routing: RoutingInfo }> = ({ stage, routing }) => (
  <div data-testid="routing-decision" className="min-w-0 rounded-card border border-hairline px-4 py-3">
    <SectionLabel className="mb-1.5">Routing decision</SectionLabel>
    <dl>
      <Row label="Strategy">{routing.strategy}</Row>
      {routing.task && <Row label="Task">{routing.task}</Row>}
      {routing.score && <Row label="Score"><span className="tabular-nums">{routing.score}</span></Row>}
      {routing.candidates != null && <Row label="Candidates"><span className="tabular-nums">{routing.candidates}</span></Row>}
      {stage.model_used && (
        <Row label="Model ID" mono>
          {stage.model_used}
          {stage.provider && <span className="text-ink-muted"> ({stage.provider})</span>}
        </Row>
      )}
      {routing.detail && <Row label="Reason">{routing.detail}</Row>}
    </dl>
  </div>
);

export const CacheStatus: React.FC<{ stage: StageExecutionDetail }> = ({ stage }) => (
  <div data-testid="cache-status" className="min-w-0 rounded-card border border-hairline px-4 py-3">
    <SectionLabel className="mb-1.5">Cache</SectionLabel>
    {stage.cache_hit ? (
      <>
        <p className="text-sm font-medium text-primary-700">▣ HIT</p>
        <p className="mt-0.5 text-sm text-ink-secondary">
          Reused a previous valid stage result
          {stage.cache_similarity != null && <> · similarity {(stage.cache_similarity * 100).toFixed(2)}%</>}
        </p>
        {(stage.tokens_saved != null || stage.cost_saved != null) && (
          <p className="mt-1 text-xs text-ink-muted">
            Saved {stage.tokens_saved != null && `${stage.tokens_saved.toLocaleString()} tokens`}
            {stage.tokens_saved != null && stage.cost_saved != null && ' · '}
            {stage.cost_saved != null && usd(stage.cost_saved)}
          </p>
        )}
      </>
    ) : (
      <>
        <p className="text-sm font-medium text-ink-secondary">○ MISS</p>
        <p className="mt-0.5 text-sm text-ink-secondary">Executed stage using the selected model</p>
      </>
    )}
  </div>
);

// ---------- Level 4–5: output ----------

const LONG_OUTPUT_CHARS = 1500;

const OutlineNav: React.FC<{ entries: OutlineEntry[] }> = ({ entries }) => (
  <nav
    aria-label="Output sections"
    className="sticky top-0 z-10 -mx-4 mb-2 flex items-center gap-2 border-y border-hairline bg-surface/95 px-4 py-2 backdrop-blur sm:-mx-5 sm:px-5"
  >
    <span className="eyebrow shrink-0">Jump to</span>
    <div className="flex min-w-0 gap-1.5 overflow-x-auto">
      {entries.map((entry) => (
        <button
          key={entry.id}
          type="button"
          onClick={() => document.getElementById(entry.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          className="shrink-0 rounded-pill bg-[rgba(112,115,147,0.1)] px-2.5 py-1 text-xs text-ink-secondary hover:bg-primary/10 hover:text-ink"
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

/**
 * `executionId` enables the server downloads (PDF/TXT, ZIP); without it they are not shown.
 * A stage without an artifact renders exactly as plain Markdown output.
 */
export const OutputSection: React.FC<{ stage: StageExecutionDetail; executionId?: string }> = ({ stage, executionId }) => {
  const idPrefix = `out-${stage.id}`;
  const outline = useMemo(
    () => (stage.result && stage.result.length > LONG_OUTPUT_CHARS ? buildOutline(stage.result, idPrefix) : []),
    [stage.result, idPrefix],
  );
  const [view, setView] = useState<'files' | 'output'>('files');

  if (stage.status === 'failed' && stage.error_message) {
    return (
      <div className="rounded-card border border-danger-line bg-danger-soft px-4 py-3">
        <SectionLabel className="!text-danger">✕ Error</SectionLabel>
        <p className="mt-1.5 whitespace-pre-wrap break-words font-mono text-[13px] leading-5 text-danger">{stage.error_message}</p>
      </div>
    );
  }
  if (!stage.result) {
    return <p className="rounded-card bg-lavender-soft px-4 py-3 text-sm text-ink-muted">{NO_OUTPUT[stage.status] ?? 'No output.'}</p>;
  }

  const words = stage.result.trim().split(/\s+/).length;
  const artifact = stage.artifact?.files.length ? stage.artifact : null;
  const showFiles = artifact !== null && view === 'files';
  const canDownload = executionId !== undefined && stage.status === 'completed';
  const tabClass = (active: boolean) =>
    `rounded-pill px-3 py-1 text-xs font-book ${active ? 'bg-surface text-ink shadow-soft' : 'text-ink-secondary hover:text-ink'}`;
  return (
    <section aria-label={`${stage.stage_name} output`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink">Output</h4>
          <span className="text-xs text-ink-muted">{words.toLocaleString()} words</span>
        </div>
        <div className="flex items-start gap-2">
          {canDownload && (
            <DocumentDownloads
              baseName={safeFileStem(stage.stage_name)}
              getDocument={(format) => executionApi.downloadStageDocument(executionId!, stage.stage_id, format)}
            />
          )}
          <CopyButton text={stage.result} label="Copy output" />
        </div>
      </div>
      {artifact && (
        <div role="group" aria-label="Output view" className="mb-3 inline-flex gap-1 rounded-pill bg-[rgba(112,115,147,0.1)] p-1">
          <button type="button" aria-pressed={showFiles} onClick={() => setView('files')} className={tabClass(showFiles)}>
            View generated files ({artifact.files.length})
          </button>
          <button type="button" aria-pressed={!showFiles} onClick={() => setView('output')} className={tabClass(!showFiles)}>
            View full output
          </button>
        </div>
      )}
      {showFiles ? (
        <ArtifactOutput
          artifact={artifact!}
          getZip={canDownload ? () => executionApi.downloadStageZip(executionId!, stage.stage_id) : undefined}
          zipName={`${safeFileStem(artifact!.name, 'project')}.zip`}
        />
      ) : (
        <>
          {outline.length > 0 && <OutlineNav entries={outline} />}
          <MarkdownRenderer content={stage.result} idPrefix={idPrefix} />
        </>
      )}
    </section>
  );
};

// ---------- composed stage ----------

export const StageResult: React.FC<{ stage: StageExecutionDetail; executionId?: string }> = ({ stage, executionId }) => {
  const [expanded, setExpanded] = useState(true);
  const routing = useMemo(
    () => (stage.cache_hit ? null : parseRoutingReason(stage.routing_reason, stage)),
    [stage],
  );
  const bodyId = `stage-body-${stage.id}`;
  const showCache = stage.cache_hit || stage.status === 'completed';
  const retries = stage.retry_count ?? 0;

  return (
    <article data-testid="stage-result" className="rounded-card border border-hairline bg-surface">
      <StageHeader stage={stage} expanded={expanded} onToggle={() => setExpanded((e) => !e)} bodyId={bodyId} />
      <Collapse open={expanded}>
        <div id={bodyId} className="space-y-4 border-t border-hairline px-4 pb-5 pt-4 sm:px-5 sm:pb-6">
          <ExecutionMetrics stage={stage} routing={routing} />

          {retries > 0 && (
            <p className="rounded-card border border-warning-line bg-warning-soft px-3.5 py-2 text-sm text-warning">
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

          <div className="border-t border-hairline pt-5">
            <OutputSection stage={stage} executionId={executionId} />
          </div>
        </div>
      </Collapse>
    </article>
  );
};
