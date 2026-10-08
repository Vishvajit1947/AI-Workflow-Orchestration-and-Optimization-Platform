/**
 * Model dropdown ranked by fit for a stage type. The empty value means "let the router decide".
 */
import React from 'react';
import type { ModelProfile } from '../types/routing';
import { capabilityForStageType } from '../types/routing';

interface ModelSelectProps {
  models: ModelProfile[];
  stageType?: string | null;
  value: string | null;
  onChange: (modelName: string | null) => void;
  autoLabel?: string;
  className?: string;
  id?: string;
  'aria-label'?: string;
}

export const ModelSelect: React.FC<ModelSelectProps> = ({
  models,
  stageType,
  value,
  onChange,
  autoLabel = 'Auto (routing rules)',
  className,
  id,
  'aria-label': ariaLabel,
}) => {
  const capability = capabilityForStageType(stageType);
  const ranked = [...models].sort(
    (a, b) => (b.capabilities[capability] ?? 0) - (a.capabilities[capability] ?? 0)
  );
  // Keep a preference that isn't in the registry selectable instead of silently dropping it
  const unknown = value && !models.some((m) => m.model_name === value);

  return (
    <select
      id={id}
      aria-label={ariaLabel}
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      className={className}
    >
      <option value="">{autoLabel}</option>
      {unknown && <option value={value}>{value} (not in registry)</option>}
      {ranked.map((m) => {
        const score = m.capabilities[capability];
        return (
          <option key={m.id} value={m.model_name}>
            {m.display_name} · {m.provider}
            {score != null && ` · ${Math.round(score * 100)}% ${capability}`}
            {!m.routable && ' · no API key'}
          </option>
        );
      })}
    </select>
  );
};
