/**
 * Models & Routing page: model registry comparison, per-stage-type routing rules
 * editor, and the recent routing decision log.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Coins, Zap, Trophy, RefreshCw, Save, Trash2, Plus, X, Cpu } from 'lucide-react';
import { modelsApi } from '../api/modelsApi';
import { routingApi } from '../api/routingApi';
import type {
  ModelComparison as Comparison, ModelProfile, PriorityFactor, RoutingDecision, RoutingRule, RoutingRuleInput,
} from '../types/routing';
import { CAPABILITIES, typicalCallCost } from '../types/routing';
import { getErrorMessage } from '../lib/errors';
import { PageHeader } from '../components/ui/PageHeader';
import { MetricCard } from '../components/metrics/MetricCard';
import { EmptyState, ErrorState, LoadingState, Notice } from '../components/ui/States';
import { useConfirm } from '../components/ui/Dialog';

const STAGE_TYPES = ['analysis', 'design', 'generation', 'testing', 'documentation', 'review', 'custom'];
const PRIORITIES: PriorityFactor[] = ['balanced', 'quality', 'cost', 'speed'];

const inputClass = 'input input-sm';

interface RuleDraft {
  priority_factor: PriorityFactor;
  min_capability_score: string;
  max_cost_per_call: string;
  max_latency_ms: string;
  preferred_model_id: string;
  fallback_model_id: string;
  is_active: boolean;
}

const EMPTY_DRAFT: RuleDraft = {
  priority_factor: 'balanced',
  min_capability_score: '0.80',
  max_cost_per_call: '',
  max_latency_ms: '',
  preferred_model_id: '',
  fallback_model_id: '',
  is_active: true,
};

const toDraft = (rule: RoutingRule): RuleDraft => ({
  priority_factor: rule.priority_factor,
  min_capability_score: Number(rule.min_capability_score).toFixed(2),
  max_cost_per_call: rule.max_cost_per_call != null ? String(Number(rule.max_cost_per_call)) : '',
  max_latency_ms: rule.max_latency_ms != null ? String(rule.max_latency_ms) : '',
  preferred_model_id: rule.preferred_model_id || '',
  fallback_model_id: rule.fallback_model_id || '',
  is_active: rule.is_active,
});

const fromDraft = (d: RuleDraft): RoutingRuleInput => ({
  priority_factor: d.priority_factor,
  min_capability_score: Number(d.min_capability_score),
  max_cost_per_call: d.max_cost_per_call === '' ? null : Number(d.max_cost_per_call),
  max_latency_ms: d.max_latency_ms === '' ? null : Number(d.max_latency_ms),
  preferred_model_id: d.preferred_model_id || null,
  fallback_model_id: d.fallback_model_id || null,
  is_active: d.is_active,
});

export const ModelComparison: React.FC = () => {
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [allModels, setAllModels] = useState<ModelProfile[]>([]);
  const [rules, setRules] = useState<Record<string, RoutingRule>>({});
  const [drafts, setDrafts] = useState<Record<string, RuleDraft>>({});
  const [decisions, setDecisions] = useState<RoutingDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, confirmDialog] = useConfirm();

  const loadData = useCallback(async () => {
    try {
      const [comparisonData, modelList, ruleList, decisionList] = await Promise.all([
        modelsApi.compareModels(),
        modelsApi.listModels({ include_unavailable: true }),
        routingApi.listRules(),
        routingApi.listDecisions({ limit: 20 }),
      ]);
      setComparison(comparisonData);
      setAllModels(modelList);
      setRules(Object.fromEntries(ruleList.map((r) => [r.stage_type, r])));
      setDrafts(Object.fromEntries(ruleList.map((r) => [r.stage_type, toDraft(r)])));
      setDecisions(decisionList);
      setError(null);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const run = async (action: () => Promise<void>, message: string) => {
    setBusy(true);
    try {
      await action();
      setNotice(message);
      await loadData();
    } catch (err: unknown) {
      setNotice(`Failed: ${getErrorMessage(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const toggleAvailability = (m: ModelProfile) =>
    run(
      async () => { await modelsApi.setAvailability(m.provider, m.model_name, !m.is_available); },
      `${m.display_name} ${m.is_available ? 'disabled' : 'enabled'} for routing`
    );

  const saveRule = (stageType: string) =>
    run(async () => {
      const payload = fromDraft(drafts[stageType]);
      if (rules[stageType]) await routingApi.updateRule(stageType, payload);
      else await routingApi.createRule(stageType, payload);
    }, `Routing rule for ${stageType} saved`);

  const deleteRule = async (stageType: string) => {
    const ok = await confirm({
      title: `Delete the ${stageType} rule?`,
      message: 'Stages of this type will use balanced routing with min score 0.70.',
      confirmLabel: 'Delete rule',
      destructive: true,
    });
    if (!ok) return;
    run(async () => { await routingApi.deleteRule(stageType); }, `Routing rule for ${stageType} deleted`);
  };

  const updateDraft = (stageType: string, changes: Partial<RuleDraft>) =>
    setDrafts((prev) => ({ ...prev, [stageType]: { ...(prev[stageType] || EMPTY_DRAFT), ...changes } }));

  const displayName = (modelName: string | null | undefined) =>
    allModels.find((m) => m.model_name === modelName)?.display_name || modelName || 'N/A';

  const models = comparison?.models || [];
  // Disabled models are never routed to, so keep them out of the registry and rule pickers.
  const availableModels = allModels.filter((m) => m.is_available);

  return (
    <div>
      <PageHeader
        eyebrow="Insights"
        title="Models & Routing"
        description="Which LLM each stage type is sent to, and why."
        actions={
          <button onClick={() => loadData()} disabled={busy} className="btn btn-outline">
            <RefreshCw size={14} aria-hidden /> Refresh
          </button>
        }
      />

      {notice && (
        <Notice tone={notice.startsWith('Failed') ? 'warning' : 'success'} className="mb-6" onDismiss={() => setNotice(null)}>
          {notice}
        </Notice>
      )}

      {loading && <LoadingState label="Loading models…" />}
      {error && <ErrorState className="mb-6" title="Could not load models" message={error} onRetry={() => loadData()} />}

      {comparison && (
        <>
          {/* Highlights */}
          <div className="mb-10 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <MetricCard compact icon={Coins} label="Most Cost-Effective" value={displayName(comparison.cheapest)} />
            <MetricCard compact icon={Zap} label="Fastest" value={displayName(comparison.fastest)} />
            <MetricCard compact icon={Trophy} label="Best for Code Generation" value={displayName(comparison.most_capable.generation)} />
          </div>

          {/* Models table */}
          <SectionTitle title="Model Registry" description="Capability scores per task, cost and latency for the models available for routing." />
          <div className="card mb-12 overflow-x-auto">
            <table className="data-table tabular">
              <thead>
                <tr>
                  <th className="sticky left-0 z-[1] bg-surface-tint">Model</th>
                  <th>Status</th>
                  <th className="!text-right">Context</th>
                  <th className="!text-right">Latency</th>
                  <th className="!text-right" title="1K input + 500 output tokens">Cost / call</th>
                  {CAPABILITIES.map((cap) => (
                    <th key={cap} className="!px-2 !text-center">{cap}</th>
                  ))}
                  <th><span className="sr-only">Availability</span></th>
                </tr>
              </thead>
              <tbody>
                {availableModels.map((model) => (
                  <tr key={model.id}>
                    <td className="sticky left-0 z-[1] min-w-[11rem] bg-surface">
                      <div className="font-book text-ink">{model.display_name}</div>
                      <div className="mt-0.5 text-xs text-ink-muted">{model.provider} · {model.model_name}</div>
                    </td>
                    <td>
                      <ModelStatus model={model} />
                    </td>
                    <td className="text-right">{Math.round(model.max_context_tokens / 1000)}K</td>
                    <td className="text-right">{model.avg_latency_ms != null ? `${model.avg_latency_ms}ms` : 'N/A'}</td>
                    <td className="text-right">${typicalCallCost(model).toFixed(4)}</td>
                    {CAPABILITIES.map((cap) => (
                      <td key={cap} className="!px-2 text-center">
                        <CapabilityBadge
                          score={model.capabilities[cap]}
                          best={comparison.most_capable[cap] === model.model_name}
                        />
                      </td>
                    ))}
                    <td className="text-right">
                      <button
                        onClick={() => toggleAvailability(model)}
                        disabled={busy}
                        className="btn btn-ghost btn-sm"
                      >
                        {model.is_available ? 'Disable' : 'Enable'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Routing rules */}
          <SectionTitle
            title="Routing Rules"
            description="Per stage type: candidates must meet the minimum score and limits; the priority picks among them. A preferred model skips selection; the fallback is used when no candidate qualifies. User overrides and stage model preferences always win."
          />
          <div className="card mb-12 overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="!px-3">Stage Type</th>
                  <th className="!px-3 !text-center">Active</th>
                  <th className="!px-3">Priority</th>
                  <th className="!px-3">Min Score</th>
                  <th className="!px-3" title="USD for 1K input + 500 output tokens">Max $/call</th>
                  <th className="!px-3">Max Latency</th>
                  <th className="!px-3">Preferred</th>
                  <th className="!px-3">Fallback</th>
                  <th className="!px-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {STAGE_TYPES.map((stageType) => {
                  const rule = rules[stageType];
                  const draft = drafts[stageType];
                  if (!draft) {
                    return (
                      <tr key={stageType}>
                        <td className="!px-3 font-book text-ink">{stageType}</td>
                        <td colSpan={7} className="!px-3 text-xs text-ink-muted">
                          No rule: balanced routing with min score 0.70
                        </td>
                        <td className="!px-3 text-right">
                          <button
                            onClick={() => updateDraft(stageType, {})}
                            className="btn btn-secondary btn-sm ml-auto"
                          >
                            <Plus size={12} /> Add rule
                          </button>
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={stageType} className="bg-surface-tint/50">
                      <td className="!px-3 font-book text-ink">{stageType}</td>
                      <td className="!px-3 text-center">
                        <input
                          type="checkbox"
                          role="switch"
                          className="switch"
                          aria-label={`${stageType} rule active`}
                          checked={draft.is_active}
                          onChange={(e) => updateDraft(stageType, { is_active: e.target.checked })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <select
                          aria-label={`${stageType} priority`}
                          value={draft.priority_factor}
                          onChange={(e) => updateDraft(stageType, { priority_factor: e.target.value as PriorityFactor })}
                          className={inputClass}
                        >
                          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <input
                          type="number" min={0} max={1} step={0.01}
                          aria-label={`${stageType} min score`}
                          value={draft.min_capability_score}
                          onChange={(e) => updateDraft(stageType, { min_capability_score: e.target.value })}
                          className={`${inputClass} w-20`}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <input
                          type="number" min={0} step={0.001} placeholder="none"
                          aria-label={`${stageType} max cost`}
                          value={draft.max_cost_per_call}
                          onChange={(e) => updateDraft(stageType, { max_cost_per_call: e.target.value })}
                          className={`${inputClass} w-24`}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <input
                          type="number" min={1} step={100} placeholder="none"
                          aria-label={`${stageType} max latency`}
                          value={draft.max_latency_ms}
                          onChange={(e) => updateDraft(stageType, { max_latency_ms: e.target.value })}
                          className={`${inputClass} w-24`}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <ModelIdSelect
                          label={`${stageType} preferred model`}
                          models={availableModels}
                          value={draft.preferred_model_id}
                          onChange={(id) => updateDraft(stageType, { preferred_model_id: id })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <ModelIdSelect
                          label={`${stageType} fallback model`}
                          models={availableModels}
                          value={draft.fallback_model_id}
                          onChange={(id) => updateDraft(stageType, { fallback_model_id: id })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => saveRule(stageType)}
                            disabled={busy}
                            title="Save rule"
                            aria-label={`Save ${stageType} rule`}
                            className="btn btn-secondary btn-icon btn-sm"
                          >
                            <Save size={14} />
                          </button>
                          {rule ? (
                            <button
                              onClick={() => deleteRule(stageType)}
                              disabled={busy}
                              title="Delete rule"
                              aria-label={`Delete ${stageType} rule`}
                              className="btn btn-ghost btn-icon btn-sm text-ink-faint hover:!text-danger"
                            >
                              <Trash2 size={14} />
                            </button>
                          ) : (
                            <button
                              onClick={() => setDrafts(({ [stageType]: _, ...rest }) => rest)}
                              title="Discard"
                              aria-label={`Discard ${stageType} rule`}
                              className="btn btn-ghost btn-icon btn-sm"
                            >
                              <X size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Recent decisions */}
          <SectionTitle title="Recent Routing Decisions" description="The last 20 model selections and the reason for each." />
          <div className="card overflow-x-auto">
            {decisions.length === 0 ? (
              <EmptyState className="m-3" compact icon={Cpu} title="No routing decisions yet." description="Execute a workflow to see them." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="hidden md:table-cell">When</th>
                    <th>Stage Type</th>
                    <th>Model</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d) => (
                    <tr key={d.id}>
                      <td className="hidden whitespace-nowrap text-ink-muted md:table-cell">
                        {new Date(d.created_at).toLocaleString()}
                      </td>
                      <td className="text-ink">{d.stage_type || 'untyped'}</td>
                      <td className="min-w-[10rem]">
                        <span className="font-book text-ink">{d.selected_model_name}</span>
                        <span className="ml-1 text-xs text-ink-muted">({d.selected_provider})</span>
                        {d.was_user_override && <Tag className="bg-[rgba(112,115,147,0.1)] text-ink-secondary">override</Tag>}
                        {d.was_fallback && <Tag className="bg-warning-soft text-warning">fallback</Tag>}
                      </td>
                      <td className="min-w-[14rem] text-ink-secondary">{d.selection_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {!loading && !error && models.length === 0 && (
        <EmptyState
          className="mt-6"
          icon={Cpu}
          title="No models registered."
          description={<>Run <code className="rounded-md bg-surface px-1.5 py-0.5 font-mono text-xs">alembic upgrade head</code> and restart the backend to seed the registry.</>}
        />
      )}
      {confirmDialog}
    </div>
  );
};

const SectionTitle: React.FC<{ title: string; description?: string }> = ({ title, description }) => (
  <div className="mb-4">
    <h2 className="text-[17px] font-medium text-ink">{title}</h2>
    {description && <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-ink-muted">{description}</p>}
  </div>
);

const ModelStatus: React.FC<{ model: ModelProfile }> = ({ model }) => {
  if (!model.is_available) return <Tag className="bg-[rgba(112,115,147,0.1)] text-ink-muted">disabled</Tag>;
  if (!model.routable) return <Tag className="bg-warning-soft text-warning">no API key</Tag>;
  return <Tag className="bg-success-soft text-success">routable</Tag>;
};

const Tag: React.FC<{ className: string; children: React.ReactNode }> = ({ className, children }) => (
  <span className={`ml-1 inline-flex whitespace-nowrap rounded-pill px-2 py-0.5 text-xs font-book first:ml-0 ${className}`}>{children}</span>
);

// Static class names so Tailwind keeps them
const SCORE_CLASSES = {
  high: 'bg-primary/10 text-primary-700',
  mid: 'bg-lavender text-ink-secondary',
  low: 'bg-lavender-soft text-ink-muted',
};

const CapabilityBadge: React.FC<{ score?: number; best?: boolean }> = ({ score, best }) => {
  if (score == null) return <span className="text-ink-faint">–</span>;
  const tier = score >= 0.9 ? 'high' : score >= 0.8 ? 'mid' : 'low';
  return (
    <span
      className={`inline-flex rounded-pill px-2 py-0.5 text-xs font-book tabular ${SCORE_CLASSES[tier]} ${best ? 'ring-1 ring-primary' : ''}`}
      title={best ? 'Best in registry' : undefined}
    >
      {Math.round(score * 100)}%
    </span>
  );
};

const ModelIdSelect: React.FC<{
  label: string;
  models: ModelProfile[];
  value: string;
  onChange: (id: string) => void;
}> = ({ label, models, value, onChange }) => (
  <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className={`${inputClass} max-w-[10rem]`}>
    <option value="">None</option>
    {models.map((m) => (
      <option key={m.id} value={m.id}>{m.display_name}</option>
    ))}
  </select>
);

export default ModelComparison;
