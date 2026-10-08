/**
 * Models & Routing page: model registry comparison, per-stage-type routing rules
 * editor, and the recent routing decision log.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Coins, Zap, Trophy, RefreshCw, Save, Trash2, Plus, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { modelsApi } from '../api/modelsApi';
import { routingApi } from '../api/routingApi';
import type {
  ModelComparison as Comparison, ModelProfile, PriorityFactor, RoutingDecision, RoutingRule, RoutingRuleInput,
} from '../types/routing';
import { CAPABILITIES, typicalCallCost } from '../types/routing';

const STAGE_TYPES = ['analysis', 'design', 'generation', 'testing', 'documentation', 'review', 'custom'];
const PRIORITIES: PriorityFactor[] = ['balanced', 'quality', 'cost', 'speed'];

const inputClass =
  'px-2 py-1.5 bg-surface-800/50 border border-surface-700/50 rounded-lg text-xs text-white focus:outline-none focus:border-primary-500/50';

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
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
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
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setNotice(`Failed: ${typeof detail === 'string' ? detail : err.message}`);
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

  const deleteRule = (stageType: string) => {
    if (!confirm(`Delete the routing rule for ${stageType}? Stages of this type will use balanced routing.`)) return;
    run(async () => { await routingApi.deleteRule(stageType); }, `Routing rule for ${stageType} deleted`);
  };

  const updateDraft = (stageType: string, changes: Partial<RuleDraft>) =>
    setDrafts((prev) => ({ ...prev, [stageType]: { ...(prev[stageType] || EMPTY_DRAFT), ...changes } }));

  const displayName = (modelName: string | null | undefined) =>
    allModels.find((m) => m.model_name === modelName)?.display_name || modelName || 'N/A';

  const models = comparison?.models || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Models & Routing</h1>
          <p className="text-surface-200/50 mt-1">Which LLM each stage type is sent to, and why</p>
        </div>
        <button
          onClick={() => loadData()}
          disabled={busy}
          className="flex items-center gap-1.5 px-3 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {notice && (
        <div className="mb-6 flex items-center justify-between glass rounded-lg px-4 py-3 text-sm">
          <span>{notice}</span>
          <button onClick={() => setNotice(null)} className="text-surface-200/50 hover:text-white">
            <XCircle size={16} />
          </button>
        </div>
      )}

      {loading && <p className="text-surface-200/50">Loading models...</p>}
      {error && <p className="text-red-400 mb-6">Error: {error}</p>}

      {comparison && (
        <>
          {/* Highlights */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <Highlight icon={Coins} label="Most Cost-Effective" value={displayName(comparison.cheapest)} />
            <Highlight icon={Zap} label="Fastest" value={displayName(comparison.fastest)} />
            <Highlight icon={Trophy} label="Best for Code Generation" value={displayName(comparison.most_capable.generation)} />
          </div>

          {/* Models table */}
          <h2 className="text-xl font-semibold mb-3">Model Registry</h2>
          <div className="glass rounded-xl overflow-x-auto mb-10">
            <table className="w-full text-sm">
              <thead className="text-surface-200/50 text-xs uppercase tracking-wide border-b border-surface-700/50">
                <tr>
                  <th className="px-4 py-3 text-left">Model</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-right">Context</th>
                  <th className="px-4 py-3 text-right">Latency</th>
                  <th className="px-4 py-3 text-right" title="1K input + 500 output tokens">Cost / call</th>
                  {CAPABILITIES.map((cap) => (
                    <th key={cap} className="px-2 py-3 text-center">{cap}</th>
                  ))}
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {allModels.map((model) => (
                  <tr key={model.id} className={`border-b border-surface-700/30 ${model.is_available ? '' : 'opacity-50'}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium">{model.display_name}</div>
                      <div className="text-xs text-surface-200/40">{model.provider} · {model.model_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <ModelStatus model={model} />
                    </td>
                    <td className="px-4 py-3 text-right">{Math.round(model.max_context_tokens / 1000)}K</td>
                    <td className="px-4 py-3 text-right">{model.avg_latency_ms != null ? `${model.avg_latency_ms}ms` : 'N/A'}</td>
                    <td className="px-4 py-3 text-right">${typicalCallCost(model).toFixed(4)}</td>
                    {CAPABILITIES.map((cap) => (
                      <td key={cap} className="px-2 py-3 text-center">
                        <CapabilityBadge
                          score={model.capabilities[cap]}
                          best={comparison.most_capable[cap] === model.model_name}
                        />
                      </td>
                    ))}
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => toggleAvailability(model)}
                        disabled={busy}
                        className="text-xs text-primary-400 hover:text-primary-300 disabled:opacity-50"
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
          <h2 className="text-xl font-semibold mb-1">Routing Rules</h2>
          <p className="text-sm text-surface-200/50 mb-3">
            Per stage type: candidates must meet the minimum score and limits; the priority picks among them.
            A preferred model skips selection; the fallback is used when no candidate qualifies.
            User overrides and stage model preferences always win.
          </p>
          <div className="glass rounded-xl overflow-x-auto mb-10">
            <table className="w-full text-sm">
              <thead className="text-surface-200/50 text-xs uppercase tracking-wide border-b border-surface-700/50">
                <tr>
                  <th className="px-3 py-3 text-left">Stage Type</th>
                  <th className="px-3 py-3 text-center">Active</th>
                  <th className="px-3 py-3 text-left">Priority</th>
                  <th className="px-3 py-3 text-left">Min Score</th>
                  <th className="px-3 py-3 text-left" title="USD for 1K input + 500 output tokens">Max $/call</th>
                  <th className="px-3 py-3 text-left">Max Latency</th>
                  <th className="px-3 py-3 text-left">Preferred</th>
                  <th className="px-3 py-3 text-left">Fallback</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody>
                {STAGE_TYPES.map((stageType) => {
                  const rule = rules[stageType];
                  const draft = drafts[stageType];
                  if (!draft) {
                    return (
                      <tr key={stageType} className="border-b border-surface-700/30">
                        <td className="px-3 py-3 font-medium">{stageType}</td>
                        <td colSpan={7} className="px-3 py-3 text-surface-200/40 text-xs">
                          No rule: balanced routing with min score 0.70
                        </td>
                        <td className="px-3 py-3 text-right">
                          <button
                            onClick={() => updateDraft(stageType, {})}
                            className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 ml-auto"
                          >
                            <Plus size={12} /> Add rule
                          </button>
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={stageType} className="border-b border-surface-700/30">
                      <td className="px-3 py-3 font-medium">{stageType}</td>
                      <td className="px-3 py-3 text-center">
                        <input
                          type="checkbox"
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
                          models={allModels}
                          value={draft.preferred_model_id}
                          onChange={(id) => updateDraft(stageType, { preferred_model_id: id })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <ModelIdSelect
                          label={`${stageType} fallback model`}
                          models={allModels}
                          value={draft.fallback_model_id}
                          onChange={(id) => updateDraft(stageType, { fallback_model_id: id })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => saveRule(stageType)}
                            disabled={busy}
                            title="Save rule"
                            className="text-primary-400 hover:text-primary-300 disabled:opacity-50"
                          >
                            <Save size={14} />
                          </button>
                          {rule ? (
                            <button
                              onClick={() => deleteRule(stageType)}
                              disabled={busy}
                              title="Delete rule"
                              className="text-surface-200/40 hover:text-red-400 disabled:opacity-50"
                            >
                              <Trash2 size={14} />
                            </button>
                          ) : (
                            <button
                              onClick={() => setDrafts(({ [stageType]: _, ...rest }) => rest)}
                              title="Discard"
                              className="text-surface-200/40 hover:text-white"
                            >
                              <XCircle size={14} />
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
          <h2 className="text-xl font-semibold mb-3">Recent Routing Decisions</h2>
          <div className="glass rounded-xl overflow-x-auto">
            {decisions.length === 0 ? (
              <p className="px-4 py-6 text-sm text-surface-200/40">No routing decisions yet. Execute a workflow to see them.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-surface-200/50 text-xs uppercase tracking-wide border-b border-surface-700/50">
                  <tr>
                    <th className="px-4 py-3 text-left">When</th>
                    <th className="px-4 py-3 text-left">Stage Type</th>
                    <th className="px-4 py-3 text-left">Model</th>
                    <th className="px-4 py-3 text-left">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d) => (
                    <tr key={d.id} className="border-b border-surface-700/30">
                      <td className="px-4 py-3 text-surface-200/50 whitespace-nowrap">
                        {new Date(d.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">{d.stage_type || 'untyped'}</td>
                      <td className="px-4 py-3">
                        <span className="font-medium">{d.selected_model_name}</span>
                        <span className="text-xs text-surface-200/40 ml-1">({d.selected_provider})</span>
                        {d.was_user_override && <Tag className="bg-surface-700/50 text-surface-200/80">override</Tag>}
                        {d.was_fallback && <Tag className="bg-amber-500/15 text-amber-300">fallback</Tag>}
                      </td>
                      <td className="px-4 py-3 text-surface-200/60">{d.selection_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {!loading && !error && models.length === 0 && (
        <p className="text-surface-200/50">
          No models registered. Run <code>alembic upgrade head</code> and restart the backend to seed the registry.
        </p>
      )}
    </div>
  );
};

const Highlight: React.FC<{ icon: LucideIcon; label: string; value: string }> = ({ icon: Icon, label, value }) => (
  <div className="glass rounded-xl p-5">
    <div className="flex items-center gap-2 text-surface-200/50 text-sm mb-2">
      <Icon size={16} className="text-primary-400" />
      {label}
    </div>
    <p className="text-2xl font-bold">{value}</p>
  </div>
);

const ModelStatus: React.FC<{ model: ModelProfile }> = ({ model }) => {
  if (!model.is_available) return <Tag className="bg-surface-700/50 text-surface-200/50">disabled</Tag>;
  if (!model.routable) return <Tag className="bg-amber-500/15 text-amber-300">no API key</Tag>;
  return <Tag className="bg-primary-500/15 text-primary-400">routable</Tag>;
};

const Tag: React.FC<{ className: string; children: React.ReactNode }> = ({ className, children }) => (
  <span className={`text-xs px-2 py-0.5 rounded ml-1 first:ml-0 ${className}`}>{children}</span>
);

// Static class names so Tailwind keeps them
const SCORE_CLASSES = {
  high: 'bg-primary-500/15 text-primary-400',
  mid: 'bg-surface-700/50 text-surface-200/80',
  low: 'bg-surface-700/50 text-surface-200/50',
};

const CapabilityBadge: React.FC<{ score?: number; best?: boolean }> = ({ score, best }) => {
  if (score == null) return <span className="text-surface-200/30">–</span>;
  const tier = score >= 0.9 ? 'high' : score >= 0.8 ? 'mid' : 'low';
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${SCORE_CLASSES[tier]} ${best ? 'ring-1 ring-primary-400' : ''}`}
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
