/**
 * Authentication layout: Mercury's night world on the left (large screens) with the product
 * story, the light form world on the right.
 */
import type { ReactNode } from 'react';
import { Network } from 'lucide-react';

const Logo = ({ onDark }: { onDark?: boolean }) => (
  <div className="flex items-center gap-3">
    <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-primary">
      <Network className="h-[18px] w-[18px] text-white" aria-hidden />
    </span>
    <span className={`text-lg font-medium tracking-[0.01em] ${onDark ? 'text-on-dark' : 'text-ink'}`}>AI Orchestrator</span>
  </div>
);

/** One input fanning out to two parallel stages that merge into a result. */
const DagIllustration = () => (
  <svg className="w-full max-w-lg" viewBox="0 0 456 190" fill="none" aria-hidden>
    <g stroke="#9cb4e8" strokeOpacity="0.45" strokeWidth="1.5">
      <path d="M118 95 C150 95 150 52 182 52" />
      <path d="M118 95 C150 95 150 138 182 138" />
      <path d="M278 52 C310 52 310 95 342 95" />
      <path d="M278 138 C310 138 310 95 342 95" />
    </g>
    {[
      { x: 22, y: 75, label: 'Objective', sub: 'input' },
      { x: 182, y: 32, label: 'Design', sub: 'gemini' },
      { x: 182, y: 118, label: 'Generate', sub: 'groq · cached' },
      { x: 342, y: 75, label: 'Review', sub: 'merge' },
    ].map((n) => (
      <g key={n.label} transform={`translate(${n.x} ${n.y})`}>
        <rect width="96" height="40" rx="10" fill="#1e1e2a" stroke="#2d2d3c" />
        <text x="12" y="17" fill="#ededf3" fontSize="11" fontWeight="480">{n.label}</text>
        <text x="12" y="31" fill="#c3c3cc" fontSize="9.5">{n.sub}</text>
      </g>
    ))}
  </svg>
);

const POINTS = [
  'Plan multi-stage workflows from a single objective',
  'Route each stage to the best Gemini or Groq model',
  'Reuse prior results through semantic caching',
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-[100dvh] bg-canvas">
      <div className="relative hidden overflow-hidden bg-night lg:flex lg:w-[52%]">
        <div className="relative z-10 flex w-full flex-col justify-between px-12 py-12 xl:px-20">
          <Logo onDark />
          <div>
            <p className="eyebrow mb-5 !text-fog">AI workflow orchestration</p>
            <h2 className="max-w-lg text-display font-medium text-on-dark">Orchestrate AI.<br />Simplify work.</h2>
            <ul className="mt-8 space-y-3">
              {POINTS.map((p) => (
                <li key={p} className="flex items-center gap-3 text-[15px] font-light text-fog">
                  <span className="h-1.5 w-1.5 rounded-full bg-periwinkle" aria-hidden />
                  {p}
                </li>
              ))}
            </ul>
            <div className="mt-12"><DagIllustration /></div>
          </div>
          <p className="text-legal text-slate">Plans are reviewed before anything runs.</p>
        </div>
      </div>

      <div className="flex w-full items-center justify-center px-5 py-10 sm:px-8 lg:w-[48%]">
        <div className="w-full max-w-[420px]">
          <div className="mb-10 lg:hidden">
            <Logo />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
