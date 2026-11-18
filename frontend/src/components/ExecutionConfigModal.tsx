/**
 * Modal for configuring execution parameters: routing, fallback provider/model,
 * per-stage model overrides, parallelism and cache use.
 */
import React, { useEffect, useState } from 'react';
import { ChevronDown, Play, TriangleAlert } from 'lucide-react';
import { modelsApi } from '../api/modelsApi';
import { routingApi } from '../api/routingApi';
import { ModelSelect } from './ModelSelect';
import { Dialog } from './ui/Dialog';
import { Collapse } from './motion/Motion';
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

/** One on/off option: label on the left, Mercury pill switch on the right. */
const SwitchRow: React.FC<{
  id: string;
  label: string;
  description: React.ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
}> = ({ id, label, description, checked, onChange }) => (
  <div className="flex items-start justify-between gap-4 py-3.5">
    <div className="min-w-0">
      <label htmlFor={id} className="cursor-pointer text-sm font-book text-ink">{label}</label>
      <p id={`${id}-hint`} className="mt-1 text-xs leading-relaxed text-ink-muted">{description}</p>
    </div>
    <input
      id={id}
      type="checkbox"
      role="switch"
      className="switch mt-0.5"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      aria-describedby={`${id}-hint`}
    />
  </div>
);

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

  const overrideCount = Object.keys(overrides).length;

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      titleId="execute-dialog-title"
      title="Execute Workflow"
      description={<>Run settings for <strong className="font-medium text-ink">{workflowName}</strong></>}
      footer={
        <>
          <button onClick={onClose} className="btn btn-outline">
            Cancel
          </button>
          <button onClick={handleExecute} className="btn btn-primary" data-autofocus>
            <Play size={15} aria-hidden />
            Execute
          </button>
        </>
      }
    >
      <div className="divide-y divide-hairline">
        <SwitchRow
          id="execution-routing"
          label="Smart routing"
          checked={useRouting}
          onChange={setUseRouting}
          description={useRouting
            ? 'Each stage goes to the best model for its type under the routing rules'
            : 'Every stage uses the default provider and model below'}
        />

        <div className="grid gap-4 py-4 sm:grid-cols-2">
          <div>
            <label htmlFor="execution-provider" className="label">
              Default Provider
            </label>
            <select
              id="execution-provider"
              value={activeProvider}
              onChange={(e) => {
                setProvider(e.target.value);
                setModel(null); // Reset model when provider changes
              }}
              className="input"
            >
              {providers.map((p) => (
                <option key={p} value={p}>
                  {providerLabel(p)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="execution-model" className="label">
              Default Model
            </label>
            <select
              id="execution-model"
              value={model || ''}
              onChange={(e) => setModel(e.target.value || null)}
              className="input"
            >
              <option value="">Provider default</option>
              {providerModels.map((m) => (
                <option key={m.model_name} value={m.model_name}>
                  {m.display_name}
                </option>
              ))}
            </select>
          </div>
          <p className="-mt-2 text-xs text-ink-muted sm:col-span-2">
            {useRouting
              ? 'Used only when no registered model can be routed'
              : 'Stages can override with their own model preference'}
          </p>
          {registryError && (
            <p className="flex items-start gap-2 rounded-[10px] bg-warning-soft px-3 py-2 text-xs text-warning sm:col-span-2">
              <TriangleAlert size={13} className="mt-px shrink-0" aria-hidden />
              Couldn't load the model registry; showing all providers. Ones without an API key will fail.
            </p>
          )}
        </div>

        {/* Per-stage overrides */}
        {useRouting && stages.length > 0 && (
          <div className="py-3.5">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              aria-expanded={showAdvanced}
              className="flex w-full items-center justify-between gap-2 text-left text-sm font-book text-ink hover:text-primary-700"
            >
              <span>
                {showAdvanced ? '− Hide' : '+ Show'} per-stage models
                {overrideCount > 0 && ` (${overrideCount} overridden)`}
              </span>
              <ChevronDown size={15} aria-hidden className={`text-ink-muted transition-transform duration-300 ease-mercury ${showAdvanced ? 'rotate-180' : ''}`} />
            </button>

            <Collapse open={showAdvanced}>
              <div className="mt-3 space-y-3 rounded-card bg-lavender-soft p-4">
                {[...stages].sort((a, b) => a.stage_order - b.stage_order).map((stage) => {
                  const pick = preview[stage.id];
                  const autoLabel = pick?.model_name ? `Auto → ${pick.model_name}` : 'Auto (routing rules)';
                  return (
                    <div key={stage.id}>
                      <label htmlFor={`override-${stage.id}`} className="mb-1 block text-xs text-ink-secondary">
                        {stage.name} <span className="text-ink-muted">({stage.stage_type || 'untyped'})</span>
                      </label>
                      <ModelSelect
                        id={`override-${stage.id}`}
                        models={models}
                        stageType={stage.stage_type}
                        value={overrides[stage.id] || null}
                        onChange={(modelName) => setOverride(stage.id, modelName)}
                        autoLabel={autoLabel}
                        className="input input-sm"
                      />
                      {!overrides[stage.id] && pick && (
                        <p className="mt-1 text-xs text-ink-muted">{pick.reason}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </Collapse>
          </div>
        )}

        <SwitchRow
          id="execution-parallel"
          label="Run independent stages in parallel"
          checked={parallel}
          onChange={setParallel}
          description="Turn off to run one stage at a time, still in dependency order"
        />
        <SwitchRow
          id="execution-cache"
          label="Use semantic cache"
          checked={useCache}
          onChange={setUseCache}
          description="Turn off to force fresh LLM calls; new results still refresh the cache"
        />
      </div>
    </Dialog>
  );
};
