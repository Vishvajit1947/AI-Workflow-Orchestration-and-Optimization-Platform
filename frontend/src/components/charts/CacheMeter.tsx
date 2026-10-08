/**
 * Cache hit rate as a meter (a single ratio: a meter, not a two-slice pie), plus savings.
 */
import React from 'react';
import type { CacheMetrics } from '../../types/analytics';
import { formatCompact, formatPercent, formatUSD } from '../../lib/format';
import { CHART, ChartCard, DataTable } from './chartKit';

export const CacheMeter: React.FC<{ data: CacheMetrics }> = ({ data }) => {
  const lookups = data.total_hits + data.total_misses;
  return (
    <ChartCard
      title="Semantic cache"
      subtitle="Stage runs served from cache vs sent to an LLM"
      empty={lookups === 0}
      emptyText="No stage runs in this range"
      table={<DataTable headers={['Metric', 'Value']} align={['left']} rows={[
        ['Cache hits', data.total_hits], ['LLM calls (misses)', data.total_misses], ['Hit rate', formatPercent(data.hit_rate)],
        ['Tokens saved', data.total_tokens_saved.toLocaleString()], ['Cost saved', formatUSD(data.total_cost_saved)],
        ['Valid cache entries', data.valid_entries],
      ]} />}
    >
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-3xl font-semibold" data-testid="cache-hit-rate">{formatPercent(data.hit_rate)}</span>
        <span className="text-xs text-surface-200/60">{data.total_hits} of {lookups} stage runs</span>
      </div>
      <div className="h-2.5 rounded-full overflow-hidden" style={{ background: CHART.track }}
           role="meter" aria-label="Cache hit rate" aria-valuenow={Math.round(data.hit_rate)} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full" style={{ width: `${data.hit_rate}%`, background: CHART.series1 }} />
      </div>
      <dl className="grid grid-cols-3 gap-3 mt-5 text-sm">
        <div>
          <dt className="text-xs text-surface-200/50">Tokens saved</dt>
          <dd className="font-semibold mt-0.5">{formatCompact(data.total_tokens_saved)}</dd>
        </div>
        <div>
          <dt className="text-xs text-surface-200/50">Cost saved</dt>
          <dd className="font-semibold mt-0.5">{formatUSD(data.total_cost_saved)}</dd>
        </div>
        <div>
          <dt className="text-xs text-surface-200/50">Valid entries</dt>
          <dd className="font-semibold mt-0.5">{data.valid_entries.toLocaleString()}</dd>
        </div>
      </dl>
    </ChartCard>
  );
};
