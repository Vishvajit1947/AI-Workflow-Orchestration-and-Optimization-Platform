/**
 * Modal for configuring execution parameters: routing, fallback provider/model,
 * per-stage model overrides and cache use.
 */
import React, { useEffect, useState } from 'react';
import { modelsApi } from '../api/modelsApi';
import { routingApi } from '../api/routingApi';
import { ModelSelect } from './ModelSelect';
import type { Stage } from '../types';
import type { ModelProfile, RoutingPreviewItem } from '../types/routing';

export interface ExecutionConfig {
  default_provider: string;
  default_model: string | null;
  use_cache: boolean;
  use_routing: boolean;
  routing_preferences: Record<string, string>;
  parallel: boolean;
}

interface ExecutionConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExecute: (config: ExecutionConfig) => void;
  workflowName: string;
  workflowId?: string;
  stages?: Stage[];
}

// Values are backend provider names (LLM provider_name). Plain names only: which models a
// provider serves comes from the model registry, not from this list.
const PROVIDER_NAMES: Record<string, string> = {
  groq: 'Groq',
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
};
const PROVIDER_ORDER = ['groq', 'gemini', 'openai', 'anthropic'];

const providerLabel = (name: string) => PROVIDER_NAMES[name] ?? name;

/** Providers that have a routable model (API key configured), in preference order. */
const configuredProviders = (models: ModelProfile[]): string[] => {
  const names = Array.from(new Set(models.filter((m) => m.routable).map((m) => m.provider)));
  const rank = (p: string) => (PROVIDER_ORDER.includes(p) ? PROVIDER_ORDER.indexOf(p) : PROVIDER_ORDER.length);
  return names.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
};

export const ExecutionConfigModal: React.FC<ExecutionConfigModalProps> = ({
  isOpen,
  onClose,
  onExecute,
  workflowName,
  workflowId,
  stages = []
}) => {
  const [provider, setProvider] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [useCache, setUseCache] = useState(true);
  const [useRouting, setUseRouting] = useState(true);
  const [parallel, setParallel] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [models, setModels] = useState<ModelProfile[]>([]);
  const [preview, setPreview] = useState<Record<string, RoutingPreviewItem>>({});
  const [registryError, setRegistryError] = useState(false);

  // Load the registry (provider/model choices) and the router's current picks when the modal opens
  useEffect(() => {
    if (!isOpen) return;
    modelsApi.listModels()
      .then((list) => {
        setModels(list);
        setRegistryError(false);
      })
      .catch((err) => {
        console.error('Failed to load models:', err);
        setRegistryError(true);
      });
    if (workflowId && stages.length > 0) {
      routingApi.preview(workflowId)
        .then((items) => setPreview(Object.fromEntries(items.map((p) => [p.stage_id, p]))))
        .catch((err) => console.error('Failed to load routing preview:', err));
    }
  }, [isOpen, workflowId, stages.length]);

  if (!isOpen) return null;

  // Until the registry answers (or if it fails) offer every provider the backend supports
  const configured = configuredProviders(models);
  const providers = configured.length > 0 ? configured : PROVIDER_ORDER;
  const activeProvider = provider && providers.includes(provider) ? provider : providers[0];
  const providerModels = models
    .filter((m) => m.routable && m.provider === activeProvider)
    .sort((a, b) => a.display_name.localeCompare(b.display_name));

  const handleExecute = () => {
    onExecute({
      default_provider: activeProvider,
      default_model: model,
      use_cache: useCache,
      use_routing: useRouting,
      routing_preferences: useRouting ? overrides : {},
      parallel
    });
    onClose();
  };

  const setOverride = (stageId: string, modelName: string | null) => {
    setOverrides((prev) => {
      const next = { ...prev };
      if (modelName) next[stageId] = modelName;
      else delete next[stageId];
      return next;
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-surface-800 text-white border border-surface-700 rounded-lg shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4">Execute Workflow</h2>
        <p className="text-surface-200/60 mb-6">
          Configure execution parameters for <strong>{workflowName}</strong>
        </p>

        {/* Routing toggle */}
        <div className="mb-4">
          <label className="flex items-center gap-2 text-sm font-medium text-surface-200/80">
            <input
              type="checkbox"
              checked={useRouting}
              onChange={(e) => setUseRouting(e.target.checked)}
              className="rounded border-surface-700 accent-primary-400"
            />
            Smart routing
          </label>
          <p className="text-xs text-surface-200/50 mt-1">
            {useRouting
              ? 'Each stage goes to the best model for its type under the routing rules'
              : 'Every stage uses the default provider and model below'}
          </p>
        </div>

        {/* Provider selection */}
        <div className="mb-4">
          <label htmlFor="execution-provider" className="block text-sm font-medium text-surface-200/80 mb-2">
            Default Provider
          </label>
          <select
            id="execution-provider"
            value={activeProvider}
            onChange={(e) => {
              setProvider(e.target.value);
              setModel(null); // Reset model when provider changes
            }}
            className="w-full px-3 py-2 bg-surface-900 border border-surface-700 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-400"
          >
            {providers.map((p) => (
              <option key={p} value={p}>
                {providerLabel(p)}
              </option>
            ))}
          </select>
          {registryError && (
            <p className="text-xs text-amber-300/80 mt-1">
              Couldn't load the model registry; showing all providers. Ones without an API key will fail.
            </p>
          )}
        </div>

        {/* Model selection */}
        <div className="mb-6">
          <label htmlFor="execution-model" className="block text-sm font-medium text-surface-200/80 mb-2">
            Default Model
          </label>
          <select
            id="execution-model"
            value={model || ''}
            onChange={(e) => setModel(e.target.value || null)}
            className="w-full px-3 py-2 bg-surface-900 border border-surface-700 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-400"
          >
            <option value="">Provider default</option>
            {providerModels.map((m) => (
              <option key={m.model_name} value={m.model_name}>
                {m.display_name}
              </option>
            ))}
          </select>
          <p className="text-xs text-surface-200/50 mt-1">
            {useRouting
              ? 'Used only when no registered model can be routed'
              : 'Stages can override with their own model preference'}
          </p>
        </div>

        {/* Per-stage overrides */}
        {useRouting && stages.length > 0 && (
          <div className="mb-6">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-primary-400 hover:text-primary-300"
            >
              {showAdvanced ? '− Hide' : '+ Show'} per-stage models
              {Object.keys(overrides).length > 0 && ` (${Object.keys(overrides).length} overridden)`}
            </button>

            {showAdvanced && (
              <div className="mt-3 p-4 bg-surface-900/60 border border-surface-700 rounded-md space-y-3">
                {[...stages].sort((a, b) => a.stage_order - b.stage_order).map((stage) => {
                  const pick = preview[stage.id];
                  const autoLabel = pick?.model_name ? `Auto → ${pick.model_name}` : 'Auto (routing rules)';
                  return (
                    <div key={stage.id}>
                      <label htmlFor={`override-${stage.id}`} className="block text-xs text-surface-200/60 mb-1">
                        {stage.name} <span className="text-surface-200/40">({stage.stage_type || 'untyped'})</span>
                      </label>
                      <ModelSelect
                        id={`override-${stage.id}`}
                        models={models}
                        stageType={stage.stage_type}
                        value={overrides[stage.id] || null}
                        onChange={(modelName) => setOverride(stage.id, modelName)}
                        autoLabel={autoLabel}
                        className="w-full px-2 py-1 text-sm bg-surface-900 border border-surface-700 rounded"
                      />
                      {!overrides[stage.id] && pick && (
                        <p className="text-xs text-surface-200/40 mt-0.5">{pick.reason}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Parallel toggle */}
        <div className="mb-4">
          <label className="flex items-center gap-2 text-sm font-medium text-surface-200/80">
            <input
              type="checkbox"
              checked={parallel}
              onChange={(e) => setParallel(e.target.checked)}
              className="rounded border-surface-700 accent-primary-400"
            />
            Run independent stages in parallel
          </label>
          <p className="text-xs text-surface-200/50 mt-1">
            Turn off to run one stage at a time, still in dependency order
          </p>
        </div>

        {/* Cache toggle */}
        <div className="mb-6">
          <label className="flex items-center gap-2 text-sm font-medium text-surface-200/80">
            <input
              type="checkbox"
              checked={useCache}
              onChange={(e) => setUseCache(e.target.checked)}
              className="rounded border-surface-700 accent-primary-400"
            />
            Use semantic cache
          </label>
          <p className="text-xs text-surface-200/50 mt-1">
            Turn off to force fresh LLM calls; new results still refresh the cache
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-surface-200 bg-surface-700/50 rounded-md hover:bg-surface-700"
          >
            Cancel
          </button>
          <button
            onClick={handleExecute}
            className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-500"
          >
            Execute
          </button>
        </div>
      </div>
    </div>
  );
};
