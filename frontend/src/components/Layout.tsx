/**
 * Application shell. Mercury frames the light canvas with its night colour: a night sidebar
 * (full on desktop, an icon rail on tablets, a drawer on phones) and a light top bar with
 * breadcrumbs above the page.
 */
import { useEffect, useId, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Outlet, NavLink, Link, useLocation, matchPath } from 'react-router-dom';
import {
  Sparkles, LayoutDashboard, GitBranch, Database, Zap, Cpu, LogOut, Menu, X, Network, Boxes, ChevronRight, Plus,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { PageTransition } from './motion/Motion';
import { EASE, transition } from '../lib/motion';

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Build',
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

interface Crumb { label: string; to?: string }

/** Breadcrumb trail for the current route (route params have no names here, so ids read as "Workflow"). */
export const breadcrumbsFor = (pathname: string): Crumb[] => {
  const match = (pattern: string) => matchPath({ path: pattern, end: true }, pathname);
  let m;
  if (match('/')) return [{ label: 'Build' }, { label: 'New workflow' }];
  if (match('/workflows')) return [{ label: 'Build' }, { label: 'Workflows' }];
  if (match('/workflows/new')) return [{ label: 'Workflows', to: '/workflows' }, { label: 'Create manually' }];
  if ((m = match('/workflows/:id/edit'))) {
    return [{ label: 'Workflows', to: '/workflows' }, { label: 'Workflow', to: `/workflows/${m.params.id}` }, { label: 'Edit' }];
  }
  if (match('/workflows/:id')) return [{ label: 'Workflows', to: '/workflows' }, { label: 'Workflow' }];
  if (match('/executions')) return [{ label: 'Build' }, { label: 'Executions' }];
  if (match('/projects')) return [{ label: 'Build' }, { label: 'Projects' }];
  if (match('/dashboard')) return [{ label: 'Insights' }, { label: 'Dashboard' }];
  if (match('/cache')) return [{ label: 'Insights' }, { label: 'Semantic cache' }];
  if (match('/models')) return [{ label: 'Insights' }, { label: 'Models & routing' }];
  return [];
};

const BrandMark = () => (
  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-primary">
    <Network size={16} className="text-white" aria-hidden />
  </span>
);

const Brand = ({ onDark = true }: { onDark?: boolean }) => (
  <Link to="/" className="flex items-center gap-2.5 rounded-lg focus-visible:ring-2 focus-visible:ring-primary/50">
    <BrandMark />
    <span className={`text-[15px] font-medium tracking-[0.01em] ${onDark ? 'text-on-dark' : 'text-ink'}`}>AI Orchestrator</span>
  </Link>
);

const navLinkClass = (compact: boolean) => ({ isActive }: { isActive: boolean }) =>
  `group relative flex items-center rounded-[10px] text-sm font-book transition-colors duration-200 ease-soft focus-visible:ring-2 focus-visible:ring-primary/60 ${
    compact ? 'h-10 w-10 justify-center' : 'gap-3 px-3 py-2'
  } ${
    isActive
      ? 'text-on-dark'
      : 'text-fog hover:bg-[rgba(175,178,206,0.08)] hover:text-on-dark'
  }`;

function Sidebar({ compact = false, onClose }: { compact?: boolean; onClose?: () => void }) {
  const { user, logout } = useAuth();
  // Each sidebar instance (desktop, rail, drawer) slides its own active indicator
  const indicatorId = useId();
  return (
    <div className="flex h-full flex-col bg-night">
      <div className={`flex h-16 shrink-0 items-center ${compact ? 'justify-center' : 'justify-between px-5'}`}>
        {compact ? <Link to="/" aria-label="AI Orchestrator home"><BrandMark /></Link> : <Brand />}
        {onClose && (
          <button onClick={onClose} className="btn btn-glass btn-icon btn-sm" aria-label="Close navigation">
            <X size={16} />
          </button>
        )}
      </div>

      <nav className={`flex-1 space-y-7 overflow-y-auto pb-4 pt-3 ${compact ? 'px-3' : 'px-3'}`} aria-label="Main">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            {compact ? (
              <div className="mx-auto mb-2 h-px w-6 bg-night-line" aria-hidden />
            ) : (
              <p className="mb-2 px-3 text-eyebrow font-semibold uppercase text-slate">{section.title}</p>
            )}
            <div className={`space-y-0.5 ${compact ? 'flex flex-col items-center' : ''}`}>
              {section.items.map(({ to, icon: Icon, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={navLinkClass(compact)}
                  title={compact ? label : undefined}
                  aria-label={compact ? label : undefined}
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <>
                          <motion.span
                            layoutId={`${indicatorId}-bg`}
                            transition={transition.indicator}
                            aria-hidden
                            className="absolute inset-0 rounded-[10px] bg-[rgba(175,178,206,0.14)]"
                          />
                          <motion.span
                            layoutId={`${indicatorId}-bar`}
                            transition={transition.indicator}
                            aria-hidden
                            className="absolute -left-3 h-5 w-[3px] rounded-full bg-primary"
                          />
                        </>
                      )}
                      <Icon size={17} strokeWidth={1.75} aria-hidden
                        className={`relative transition-colors duration-200 ease-soft ${isActive ? 'text-periwinkle' : ''}`} />
                      {!compact && <span className="relative">{label}</span>}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {user && (
        <div className={`shrink-0 border-t border-night-line ${compact ? 'flex flex-col items-center gap-2 py-3' : 'p-3'}`}>
          {compact ? (
            <>
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full bg-[rgba(156,180,232,0.2)] text-sm font-medium text-on-dark"
                title={`${user.full_name} · ${user.email}`}
                aria-hidden
              >
                {user.full_name.charAt(0).toUpperCase()}
              </span>
              <button onClick={logout} className="btn btn-glass btn-icon btn-sm" aria-label="Log out" title="Log out">
                <LogOut size={15} />
              </button>
            </>
          ) : (
            <div className="flex items-center gap-3 rounded-card px-2 py-1.5">
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[rgba(156,180,232,0.2)] text-sm font-medium text-on-dark"
                aria-hidden
              >
                {user.full_name.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-book text-on-dark">{user.full_name}</p>
                <p className="truncate text-xs text-fog/80">{user.email}</p>
              </div>
              <button onClick={logout} className="btn btn-glass btn-icon btn-sm" aria-label="Log out" title="Log out">
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  if (crumbs.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-[13px]">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={`${c.label}-${i}`} className={`flex min-w-0 items-center gap-1.5 ${last ? '' : 'hidden sm:flex'}`}>
              {c.to && !last ? (
                <Link to={c.to} className="truncate text-ink-muted transition-colors hover:text-ink">{c.label}</Link>
              ) : (
                <span className={`truncate ${last ? 'font-book text-ink' : 'text-ink-muted'}`} aria-current={last ? 'page' : undefined}>
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight size={13} className="shrink-0 text-ink-faint" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const crumbs = breadcrumbsFor(location.pathname);
  // Pages whose own header already offers "New workflow" don't repeat it in the top bar
  const hideTopCta = location.pathname === '/' || location.pathname === '/workflows';

  // Close the mobile drawer after navigating
  useEffect(() => setMenuOpen(false), [location.pathname]);

  // Escape closes the drawer
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuOpen]);

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-canvas">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 lg:block">
        <Sidebar />
      </aside>
      {/* Tablet icon rail */}
      <aside className="hidden w-[72px] shrink-0 md:block lg:hidden">
        <Sidebar compact />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {menuOpen && (
          <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <motion.div
              className="absolute inset-0 bg-night/60 backdrop-blur-[2px]"
              onClick={() => setMenuOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE.soft }}
            />
            <motion.aside
              className="relative h-full w-[min(18rem,85vw)] shadow-pop"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.4, ease: EASE.out }}
            >
              <Sidebar onClose={() => setMenuOpen(false)} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-hairline bg-canvas/90 px-4 backdrop-blur sm:px-6 lg:px-10">
          <button onClick={() => setMenuOpen(true)} className="btn btn-ghost btn-icon -ml-2 md:hidden" aria-label="Open navigation">
            <Menu size={19} />
          </button>
          <div className="md:hidden">
            <Link to="/" aria-label="AI Orchestrator home"><BrandMark /></Link>
          </div>
          <div className="min-w-0 flex-1">
            <Breadcrumbs crumbs={crumbs} />
          </div>
          {!hideTopCta && (
            <Link to="/" className="btn btn-secondary btn-sm">
              <Plus size={14} aria-hidden />
              <span className="hidden sm:inline">New workflow</span>
              <span className="sr-only sm:hidden">New workflow</span>
            </Link>
          )}
        </header>

        <main className="flex-1 overflow-y-auto" id="main">
          <div className="mx-auto w-full max-w-content px-4 pb-16 pt-6 sm:px-6 sm:pt-8 lg:px-10 lg:pt-10">
            {/* Keyed by route: the entry plays on navigation, not on re-renders or live updates */}
            <PageTransition key={location.pathname}>
              <Outlet />
            </PageTransition>
          </div>
        </main>
      </div>
    </div>
  );
}
