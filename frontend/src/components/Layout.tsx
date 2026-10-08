import { Outlet, NavLink } from 'react-router-dom';
import {
  Home, LayoutDashboard, GitBranch, Database, Zap, Cpu
} from 'lucide-react';

const navItems = [
  { to: '/', icon: Home, label: 'Create Workflow', exact: true },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/workflows', icon: GitBranch, label: 'Workflows' },
  { to: '/executions', icon: Zap, label: 'Executions' },
  { to: '/cache', icon: Database, label: 'Cache' },
  { to: '/models', icon: Cpu, label: 'Models & Routing' },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 glass border-r border-primary-500/10 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-primary-500/10">
          <h1 className="text-lg font-bold text-primary-400">
            AI Orchestrator
          </h1>
          <p className="text-xs text-surface-200/50 mt-1">Workflow Intelligence</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-primary-500/15 text-primary-400 shadow-sm shadow-primary-500/10'
                    : 'text-surface-200/60 hover:text-white hover:bg-surface-700/50'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-primary-500/10">
          <div className="text-xs text-surface-200/40">
            v1.0.0 with AI Planning
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
