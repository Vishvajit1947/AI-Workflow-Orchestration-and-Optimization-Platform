/**
 * Section card: the standard container for a block of page content, with an optional
 * header row (title, description, actions). Mercury cards are flat, 12px-rounded, and
 * separated from the canvas by a hairline rather than a shadow.
 */
import React from 'react';

interface SectionProps {
  title?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  /** Remove body padding (tables, lists that run edge to edge) */
  flush?: boolean;
  'aria-label'?: string;
  'data-testid'?: string;
  as?: 'section' | 'div';
}

export const Section: React.FC<SectionProps> = ({
  title, description, actions, children, className = '', flush = false, as = 'section', ...rest
}) => {
  const Tag = as;
  const hasHeader = title || description || actions;
  return (
    <Tag className={`card min-w-0 ${className}`} {...rest}>
      {hasHeader && (
        <div className={`flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6 ${flush ? 'pb-4' : ''}`}>
          <div className="min-w-0">
            {title && <h2 className="text-[17px] font-medium leading-snug text-ink">{title}</h2>}
            {description && <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={flush ? '' : `px-5 pb-5 sm:px-6 sm:pb-6 ${hasHeader ? 'pt-4' : 'pt-5 sm:pt-6'}`}>{children}</div>
    </Tag>
  );
};

/** Label / value pair list used inside cards. */
export const KeyValue: React.FC<{ label: React.ReactNode; children: React.ReactNode; mono?: boolean }> = ({
  label, children, mono,
}) => (
  <div className="flex gap-3 py-1.5 text-sm">
    <dt className="w-28 shrink-0 text-ink-muted">{label}</dt>
    <dd className={`min-w-0 text-ink ${mono ? 'break-all font-mono text-xs leading-5' : 'break-words'}`}>{children}</dd>
  </div>
);
