/**
 * Two-panel authentication layout: branding on the left (large screens), form on the right.
 */
import type { ReactNode } from 'react';
import { Network } from 'lucide-react';

const Logo = ({ dark }: { dark?: boolean }) => (
  <div className="flex items-center gap-3">
    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-600">
      <Network className="h-5 w-5 text-white" aria-hidden />
    </div>
    <span className={`text-xl font-semibold ${dark ? 'text-gray-900' : 'text-white'}`}>AI Orchestrator</span>
  </div>
);

/** Small DAG: one input fanning out to two parallel stages that merge into a result. */
const DagIllustration = () => (
  <svg className="w-full max-w-md text-primary-400" viewBox="0 0 400 200" fill="none" aria-hidden>
    <g stroke="currentColor" strokeWidth="2" opacity="0.5">
      <line x1="80" y1="100" x2="180" y2="60" />
      <line x1="80" y1="100" x2="180" y2="140" />
      <line x1="180" y1="60" x2="300" y2="100" />
      <line x1="180" y1="140" x2="300" y2="100" />
      <line x1="300" y1="100" x2="370" y2="100" />
    </g>
    <g fill="currentColor" opacity="0.85">
      <circle cx="80" cy="100" r="22" />
      <circle cx="180" cy="60" r="22" />
      <circle cx="180" cy="140" r="22" />
      <circle cx="300" cy="100" r="22" />
      <circle cx="370" cy="100" r="12" />
    </g>
    <g fill="#0f2a1e" fontSize="10" fontWeight="600" textAnchor="middle">
      <text x="80" y="104">Input</text>
      <text x="180" y="64">Stage</text>
      <text x="180" y="144">Stage</text>
      <text x="300" y="104">Merge</text>
    </g>
  </svg>
);

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <div className="relative hidden overflow-hidden bg-surface-900 lg:flex lg:w-[55%]">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-500/15 to-transparent" />
        <div className="relative z-10 flex w-full flex-col justify-center px-12 xl:px-20">
          <div className="mb-10">
            <Logo />
          </div>
          <h2 className="mb-4 text-4xl font-semibold tracking-tight text-white">Orchestrate AI. Simplify work.</h2>
          <p className="mb-12 max-w-lg text-lg text-surface-200/70">
            Plan multi-stage AI workflows from a single objective, run them across Gemini and Groq models, and
            reuse results through semantic caching.
          </p>
          <DagIllustration />
        </div>
      </div>

      <div className="flex w-full items-center justify-center bg-white p-6 sm:p-8 lg:w-[45%]">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Logo dark />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
