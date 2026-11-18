import { useEffect, useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  Sparkles, LayoutDashboard, GitBranch, Database, Zap, Cpu, LogOut, Menu, X, Network, Boxes,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Workflows',
    items: [
      { to: '/', icon: Sparkles, label: 'New Workflow', end: true },
      { to: '/workflows', icon: GitBranch, label: 'Workflows' },
      { to: '/executions', icon: Zap, label: 'Executions' },
      { to: '/projects', icon: Boxes, label: 'Projects' },
    ],
  },
  {
    title: 'Insights',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/cache', icon: Database, label: 'Cache' },
      { to: '/models', icon: Cpu, label: 'Models & Routing' },
    ],
  },
];

const Brand = () => (
  <div className="flex items-center gap-2.5">
    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
      <Network size={16} className="text-white" aria-hidden />
    </div>
    <span className="font-semibold text-white">AI Orchestrator</span>
  </div>
);

export default function Layout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  // Close the mobile drawer after navigating
  useEffect(() => setMenuOpen(false), [location.pathname]);

  const sidebar = (
    <>
      <div className="flex h-16 items-center justify-between border-b border-surface-700 px-5">
        <Brand />
        <button
          onClick={() => setMenuOpen(false)}
          className="btn btn-ghost p-1.5 md:hidden"
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto p-3" aria-label="Main">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="mb-1.5 px-3 text-[11px] font-medium uppercase tracking-wider text-surface-200/40">
              {section.title}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400/60 ${
                      isActive
                        ? 'bg-primary-500/15 text-primary-400'
                        : 'text-surface-200/60 hover:bg-surface-700/50 hover:text-white'
                    }`
                  }
                >
                  <Icon size={16} aria-hidden />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {user && (
        <div className="space-y-2 border-t border-surface-700 p-3">
          <div className="flex items-center gap-3 px-2">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-600 text-sm font-semibold text-white"
              aria-hidden
            >
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
              <p className="truncate text-xs text-surface-200/50">{user.email}</p>
            </div>
          </div>
          <button onClick={logout} className="btn btn-ghost w-full justify-start">
            <LogOut size={16} aria-hidden />
            Log out
          </button>
        </div>
      )}
    </>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-surface-700 bg-surface-800 md:flex">{sidebar}</aside>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <aside className="relative flex h-full w-64 flex-col border-r border-surface-700 bg-surface-800">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-surface-700 px-4 md:hidden">
          <button onClick={() => setMenuOpen(true)} className="btn btn-ghost p-1.5" aria-label="Open navigation">
            <Menu size={20} />
          </button>
          <Brand />
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
