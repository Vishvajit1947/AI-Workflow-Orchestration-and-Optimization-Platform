/**
 * Page title row: optional eyebrow, heading, one-line description and right-aligned actions.
 */
import React from 'react';

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
  /** Extra content under the description (chips, meta) */
  meta?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, actions, eyebrow, meta }) => (
  <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div className="min-w-0">
      {eyebrow && <p className="eyebrow mb-2.5">{eyebrow}</p>}
      <h1 className="break-words text-[26px] font-medium leading-tight tracking-[0.01em] text-ink sm:text-heading-2">{title}</h1>
      {description && <p className="mt-2 max-w-2xl text-[15px] font-light leading-relaxed text-ink-secondary">{description}</p>}
      {meta && <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div>}
    </div>
    {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
  </header>
);
