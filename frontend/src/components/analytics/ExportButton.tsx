/**
 * Export menu: summary report (JSON/CSV) or raw stage runs (CSV/JSON), for the current filters.
 */
import React, { useState } from 'react';
import { Download } from 'lucide-react';
import { analyticsApi } from '../../api/analyticsApi';
import type { AnalyticsFilters, ExportDataset, ExportFormat } from '../../types/analytics';

const OPTIONS: { label: string; format: ExportFormat; dataset: ExportDataset }[] = [
  { label: 'Summary report (JSON)', format: 'json', dataset: 'summary' },
  { label: 'Summary report (CSV)', format: 'csv', dataset: 'summary' },
  { label: 'Stage runs (CSV)', format: 'csv', dataset: 'stage_runs' },
  { label: 'Stage runs (JSON)', format: 'json', dataset: 'stage_runs' },
];

export const ExportButton: React.FC<{ filters: AnalyticsFilters }> = ({ filters }) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async (format: ExportFormat, dataset: ExportDataset) => {
    setOpen(false);
    setBusy(true);
    setError(null);
    try {
      await analyticsApi.downloadExport(format, dataset, filters);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 px-3 py-2 bg-surface-700/50 hover:bg-surface-700 rounded-lg text-sm transition-colors disabled:opacity-50"
      >
        <Download size={14} /> {busy ? 'Exporting…' : 'Export'}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-1 w-56 z-20 rounded-lg border border-surface-700 bg-surface-900 py-1 shadow-lg">
          {OPTIONS.map((o) => (
            <button key={o.label} role="menuitem" onClick={() => download(o.format, o.dataset)}
                    className="block w-full text-left px-3 py-2 text-sm text-surface-200/80 hover:bg-surface-700/60 hover:text-white">
              {o.label}
            </button>
          ))}
        </div>
      )}
      {error && <p className="absolute right-0 mt-1 text-xs text-red-400 whitespace-nowrap">{error}</p>}
    </div>
  );
};
