/**
 * Export menu: summary report (JSON/CSV) or raw stage runs (CSV/JSON), for the current filters.
 */
import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronDown, Download } from 'lucide-react';
import { EASE, transition } from '../../lib/motion';
import { analyticsApi } from '../../api/analyticsApi';
import type { AnalyticsFilters, ExportDataset, ExportFormat } from '../../types/analytics';

const OPTIONS: { label: string; format: ExportFormat; dataset: ExportDataset; group: string }[] = [
  { label: 'Summary report (JSON)', format: 'json', dataset: 'summary', group: 'Summary' },
  { label: 'Summary report (CSV)', format: 'csv', dataset: 'summary', group: 'Summary' },
  { label: 'Stage runs (CSV)', format: 'csv', dataset: 'stage_runs', group: 'Raw data' },
  { label: 'Stage runs (JSON)', format: 'json', dataset: 'stage_runs', group: 'Raw data' },
];

export const ExportButton: React.FC<{ filters: AnalyticsFilters }> = ({ filters }) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);

  // Close on outside click / Escape
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

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
    <div className="relative" ref={root}>
      <button
        onClick={() => setOpen(!open)}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={open}
        className="btn btn-outline"
      >
        <Download size={14} aria-hidden /> {busy ? 'Exporting…' : 'Export'}
        <ChevronDown size={14} aria-hidden className={`transition-transform duration-300 ease-mercury ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
      {open && (
        <motion.div
          role="menu"
          className="absolute right-0 z-20 mt-2 w-60 origin-top-right rounded-card border border-hairline bg-surface p-1.5 shadow-pop"
          initial={{ opacity: 0, y: -4, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.25, ease: EASE.out } }}
          exit={{ opacity: 0, y: -4, scale: 0.97, transition: transition.exit }}
        >
          {OPTIONS.map((o, i) => (
            <React.Fragment key={o.label}>
              {(i === 0 || OPTIONS[i - 1].group !== o.group) && (
                <p className="eyebrow px-2.5 pb-1.5 pt-2" aria-hidden>{o.group}</p>
              )}
              <button
                role="menuitem"
                onClick={() => download(o.format, o.dataset)}
                className="block w-full rounded-[8px] px-2.5 py-2 text-left text-sm text-ink transition-colors duration-150 ease-soft hover:bg-lavender-soft focus-visible:bg-lavender-soft"
              >
                {o.label}
              </button>
            </React.Fragment>
          ))}
        </motion.div>
      )}
      </AnimatePresence>
      {error && <p role="alert" className="absolute right-0 mt-1.5 whitespace-nowrap text-xs text-danger">{error}</p>}
    </div>
  );
}
