/**
 * Stat tile: label, compact value, optional context line. MetricGrid lays tiles out responsively.
 */
import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string;
  detail?: string;
  icon?: LucideIcon;
  testId?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, detail, icon: Icon, testId }) => (
  <div className="glass rounded-xl p-4" data-testid={testId}>
    <div className="flex items-center gap-2 text-xs text-surface-200/60">
      {Icon && <Icon size={14} className="text-primary-400" aria-hidden />}
      {label}
    </div>
    <p className="text-2xl font-semibold mt-1.5">{value}</p>
    {detail && <p className="text-xs text-surface-200/50 mt-1">{detail}</p>}
  </div>
);

export const MetricGrid: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">{children}</div>
);
