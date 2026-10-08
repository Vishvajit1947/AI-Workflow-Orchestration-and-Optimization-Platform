/**
 * Display helpers for execution results. These only change how values are shown;
 * the raw identifiers from the API are never modified.
 */

// Display names mirroring the backend model seed catalog (services/router/model_registry.py)
const MODEL_NAMES: Record<string, string> = {
  'qwen/qwen3.8-27b': 'Qwen 3.8 27B',
  'openai/gpt-oss-20b': 'GPT-OSS 20B',
  'openai/gpt-oss-120b': 'GPT-OSS 120B',
  'gemini-3.8-flash': 'Gemini 3.8 Flash',
  'gemini-2.5-pro': 'Gemini 2.5 Pro',
  'llama-3.3-70b-versatile': 'Llama 3.3 70B Versatile',
  'llama-3.1-8b-instant': 'Llama 3.1 8B Instant',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'claude-sonnet-4-20250514': 'Claude Sonnet 4',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
};

const ACRONYMS = new Set(['gpt', 'oss', 'ai', 'llm']);

/** "qwen/qwen3.8-27b" → "Qwen 3.8 27B"; unknown ids are title-cased. */
export const formatModelName = (model: string | null | undefined): string => {
  if (!model) return '—';
  if (MODEL_NAMES[model]) return MODEL_NAMES[model];
  const base = model.includes('/') ? model.slice(model.lastIndexOf('/') + 1) : model;
  return base
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => {
      if (/^\d+(\.\d+)?b$/i.test(part)) return part.toUpperCase(); // 27b → 27B
      if (ACRONYMS.has(part.toLowerCase())) return part.toUpperCase();
      // qwen3.8 → Qwen 3.8
      const split = part.match(/^([a-z]+)(\d[\d.]*)$/i);
      if (split) return `${split[1][0].toUpperCase()}${split[1].slice(1)} ${split[2]}`;
      return part[0].toUpperCase() + part.slice(1);
    })
    .join(' ');
};

const PROVIDER_NAMES: Record<string, string> = {
  groq: 'Groq',
  gemini: 'Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  cache: 'Semantic cache',
};

export const formatProvider = (provider: string | null | undefined): string =>
  provider ? PROVIDER_NAMES[provider] ?? provider[0].toUpperCase() + provider.slice(1) : '—';

const capitalize = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export interface RoutingInfo {
  /** Short label for the metric grid: Balanced, Override, Fallback, ... */
  strategy: string;
  task?: string;
  score?: string;
  candidates?: number;
  /** Free-text detail for reasons that are not a scored routing decision */
  detail?: string;
}

/**
 * Structure the backend's routing reason for display. Formats come from
 * services/router/routing_engine.py; anything unrecognised is shown verbatim as `detail`.
 */
export const parseRoutingReason = (
  reason: string | null | undefined,
  flags: { was_user_override?: boolean; was_fallback?: boolean } = {},
): RoutingInfo | null => {
  if (!reason) return null;
  const scored = reason.match(/^Routing: (\w+) priority for (\w+), score=([\d.]+), (\d+) candidate/);
  if (scored && !flags.was_fallback) {
    return {
      strategy: capitalize(scored[1]),
      task: capitalize(scored[2]),
      score: scored[3],
      candidates: Number(scored[4]),
    };
  }
  if (flags.was_user_override || reason.startsWith('User override')) return { strategy: 'Override', detail: reason };
  if (flags.was_fallback || reason.startsWith('Fallback')) return { strategy: 'Fallback', detail: reason };
  if (reason.startsWith('Stage preference')) return { strategy: 'Stage preference', detail: reason };
  if (reason.startsWith('Routing rule preferred')) return { strategy: 'Rule preferred', detail: reason };
  return { strategy: 'Routed', detail: reason };
};
