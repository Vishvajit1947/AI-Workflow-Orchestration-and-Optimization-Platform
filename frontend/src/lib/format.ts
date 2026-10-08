/**
 * Number formatting shared by dashboard figures, axes, tooltips and tables.
 */

/** 1,284 · 12.9K · 4.2M */
export const formatCompact = (n: number): string => {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${+(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${+(n / 1_000).toFixed(1)}K`;
  return Math.round(n).toLocaleString('en-US');
};

/** LLM costs are often fractions of a cent: 4 decimals below $1, 2 above. */
export const formatUSD = (n: number): string =>
  Math.abs(n) >= 1 ? `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : `$${n.toFixed(4)}`;

/** 850ms · 1.25s · 2m 5s */
export const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}s`;
  const minutes = Math.floor(ms / 60_000);
  return `${minutes}m ${Math.round((ms % 60_000) / 1000)}s`;
};

export const formatPercent = (pct: number, digits = 1): string => `${pct.toFixed(digits)}%`;

/** "Sep 27" from an ISO date (YYYY-MM-DD, treated as UTC) */
export const formatDay = (isoDate: string): string =>
  new Date(`${isoDate}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });

/** Clean axis ticks: 0 and 3-5 round steps up to >= max */
export const niceTicks = (max: number, count = 4): number[] => {
  if (max <= 0) return [0, 1];
  const raw = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const ticks = [];
  for (let v = 0; v < max + step * 0.999; v += step) ticks.push(+v.toPrecision(12));
  return ticks;
};
