/**
 * Progress through the planner: describe the objective → review the plan → create the workflow.
 */
import React from 'react';
import { Check } from 'lucide-react';

const STEPS = ['Describe objective', 'Review plan', 'Create workflow'];

export const PlannerSteps: React.FC<{ current: 0 | 1 | 2 }> = ({ current }) => (
  <ol className="mb-8 flex items-center gap-2 text-[13px]" aria-label="Planner progress">
    {STEPS.map((label, i) => {
      const done = i < current;
      const active = i === current;
      return (
        <li key={label} className="flex min-w-0 items-center gap-2" aria-current={active ? 'step' : undefined}>
          <span
            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs tabular transition-colors duration-500 ease-standard ${
              done ? 'bg-primary text-white' : active ? 'bg-primary/10 text-primary-700 ring-1 ring-primary/40' : 'bg-ink/[0.06] text-ink-muted'
            }`}
          >
            {done ? <Check size={13} aria-hidden className="animate-pop-in" /> : i + 1}
          </span>
          <span className={`truncate ${active ? 'font-book text-ink' : 'text-ink-muted'} ${active ? '' : 'hidden sm:inline'}`}>{label}</span>
          {i < STEPS.length - 1 && (
            <span className="relative mx-1 h-px w-5 shrink-0 overflow-hidden bg-hairline-strong sm:w-8" aria-hidden>
              {done && <span className="absolute inset-0 origin-left animate-grow-x bg-primary" />}
            </span>
          )}
        </li>
      );
    })}
  </ol>
);
