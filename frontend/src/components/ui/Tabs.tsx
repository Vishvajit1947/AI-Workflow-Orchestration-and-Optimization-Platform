/**
 * Tab strip (underline, for switching views of one object) and segmented control
 * (pill group, for choosing a filter value). The active marker slides between options.
 */
import React, { useId } from 'react';
import { motion } from 'motion/react';
import { transition } from '../../lib/motion';

export interface TabItem<T extends string> {
  id: T;
  label: React.ReactNode;
  count?: number;
}

export function Tabs<T extends string>({ items, value, onChange, ariaLabel, className = '' }: {
  items: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  ariaLabel: string;
  className?: string;
}) {
  const indicatorId = useId();
  return (
    <div className={`-mx-1 overflow-x-auto border-b border-hairline px-1 ${className}`}>
      <div className="flex gap-6" role="tablist" aria-label={ariaLabel}>
        {items.map((tab) => {
          const active = tab.id === value;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(tab.id)}
              className={`relative -mb-px flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent pb-3 pt-1 text-sm font-book transition-colors duration-200 ease-soft focus-visible:text-ink ${
                active ? 'text-ink' : 'text-ink-muted hover:text-ink'
              }`}
            >
              {tab.label}
              {tab.count != null && (
                <span className={`rounded-pill px-1.5 py-0.5 text-[11px] leading-none tabular transition-colors duration-200 ${active ? 'bg-primary/10 text-primary-700' : 'bg-ink/[0.06] text-ink-muted'}`}>
                  {tab.count}
                </span>
              )}
              {active && (
                <motion.span
                  layoutId={`${indicatorId}-underline`}
                  transition={transition.indicator}
                  aria-hidden
                  className="absolute inset-x-0 -bottom-0.5 h-0.5 bg-primary"
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SegmentedControl<T extends string | number>({ options, value, onChange, ariaLabel, size = 'md' }: {
  options: { value: T; label: React.ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  size?: 'sm' | 'md';
}) {
  const indicatorId = useId();
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex max-w-full overflow-x-auto rounded-pill bg-[rgba(112,115,147,0.1)] p-1"
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`relative whitespace-nowrap rounded-pill font-book transition-colors duration-200 ease-soft focus-visible:ring-2 focus-visible:ring-primary/40 ${
              size === 'sm' ? 'px-3 py-1 text-xs' : 'px-3.5 py-1.5 text-[13px]'
            } ${active ? 'text-ink' : 'text-ink-secondary hover:text-ink'}`}
          >
            {active && (
              <motion.span
                layoutId={`${indicatorId}-thumb`}
                transition={transition.indicator}
                aria-hidden
                className="absolute inset-0 rounded-pill bg-surface shadow-soft"
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
