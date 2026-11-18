/**
 * App shell: collapsible sidebar, focus mode, keyboard shortcuts and the guarantee that
 * toggling either never remounts the page (so form input and live state survive).
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Layout from '../src/components/Layout';
import { AuthContext } from '../src/contexts/AuthContext';

const auth = {
  user: { id: 'u1', email: 'ada@example.com', full_name: 'Ada Lovelace' },
  logout: async () => {},
} as unknown as React.ContextType<typeof AuthContext>;

let mounts = 0;
function DraftPage() {
  const [mountId] = useState(() => ++mounts);
  return (
    <div>
      <label htmlFor="objective">Objective</label>
      <input id="objective" />
      <span data-testid="mount">{mountId}</span>
    </div>
  );
}

const renderShell = (path = '/') =>
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DraftPage />} />
            <Route path="dashboard" element={<p>Dashboard page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );

const sidebar = () => document.getElementById('app-sidebar')!;

beforeEach(() => {
  localStorage.clear();
  mounts = 0;
});

describe('collapsible sidebar', () => {
  it('collapses to an icon rail, keeps navigation working, and remembers the choice', () => {
    const { unmount } = renderShell();
    expect(sidebar()).toHaveAttribute('data-state', 'expanded');

    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(sidebar()).toHaveAttribute('data-state', 'collapsed');
    expect(sidebar()).toHaveClass('w-[72px]');

    // Rail links keep an accessible name and still navigate
    fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }));
    expect(screen.getByText('Dashboard page')).toBeInTheDocument();

    unmount();
    renderShell();
    expect(sidebar()).toHaveAttribute('data-state', 'collapsed');
    fireEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }));
    expect(sidebar()).toHaveAttribute('data-state', 'expanded');
  });

  it('shows a tooltip for rail items on hover', () => {
    renderShell();
    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    fireEvent.mouseEnter(screen.getByRole('link', { name: 'Workflows' }));
    expect(document.body).toHaveTextContent('Workflows');
    expect(document.querySelector('.fixed.z-\\[60\\]')).toHaveTextContent('Workflows');
  });

  it('toggles with Ctrl+B', () => {
    renderShell();
    fireEvent.keyDown(window, { key: 'b', ctrlKey: true });
    expect(sidebar()).toHaveAttribute('data-state', 'collapsed');
  });
});

describe('focus mode', () => {
  it('hides the sidebar and widens content without remounting the page', () => {
    renderShell();
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Build a todo app' } });

    fireEvent.click(screen.getByRole('button', { name: 'Enter focus mode' }));
    expect(sidebar()).toHaveAttribute('data-state', 'hidden');
    expect(sidebar()).toHaveClass('invisible');
    expect(screen.getByRole('main').firstElementChild).toHaveClass('max-w-[100vw]');

    // The sidebar button now restores the sidebar
    fireEvent.click(screen.getByRole('button', { name: 'Show sidebar' }));
    expect(sidebar()).toHaveAttribute('data-state', 'expanded');

    fireEvent.keyDown(window, { key: 'F', ctrlKey: true, shiftKey: true });
    expect(sidebar()).toHaveAttribute('data-state', 'hidden');
    fireEvent.click(screen.getByRole('button', { name: 'Exit focus mode' }));

    expect(screen.getByLabelText('Objective')).toHaveValue('Build a todo app');
    expect(screen.getByTestId('mount')).toHaveTextContent('1');
  });
});
