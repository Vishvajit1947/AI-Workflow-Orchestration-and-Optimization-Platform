/**
 * Project Builder UI: mode choice on the planner, the project panel (status, steps, logs,
 * repairs, files, ZIP) and the Projects page.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectPanel } from '../src/components/project/ProjectPanel';
import ProjectsPage from '../src/pages/ProjectsPage';
import ObjectiveInput from '../src/pages/ObjectiveInput';
import { projectsApi, type Project, type ProjectFile } from '../src/api/projectsApi';
import { plannerApi } from '../src/api/plannerApi';

vi.mock('../src/api/projectsApi', () => ({
  projectsApi: { list: vi.fn(), get: vi.fn(), files: vi.fn(), download: vi.fn() },
}));
vi.mock('../src/api/plannerApi', () => ({
  plannerApi: { analyzeObjective: vi.fn(), generateWorkflow: vi.fn() },
}));
const api = vi.mocked(projectsApi);
const planner = vi.mocked(plannerApi);

const savedNames: string[] = [];
beforeEach(() => {
  vi.clearAllMocks();
  savedNames.length = 0;
  Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    savedNames.push(this.download);
  });
});

const step = (over: object) => ({
  attempt: 0, component: '(root)', kind: 'pip_install', label: 'Install Python dependencies',
  command: 'pip install -r requirements.txt', cwd: '', status: 'passed', exit_code: 0, duration_ms: 1200,
  timed_out: false, output: 'ok', ...over,
});

const project = (over: Partial<Project> = {}): Project => ({
  id: 'p1', name: 'Student API', description: null, status: 'succeeded', project_type: 'fastapi',
  workflow_id: 'w1', execution_id: 'e1', file_count: 2, created_at: '2026-11-17T10:00:00Z',
  updated_at: '2026-11-17T10:05:00Z',
  latest_run: {
    id: 'r1', execution_id: 'e1', status: 'succeeded', project_type: 'fastapi', current_step: null,
    warnings: ['.gitignore is missing'], error_summary: null, started_at: null, completed_at: null,
    steps: [
      step({ kind: 'py_import', label: 'Import the application', command: "python -c 'import main'",
             status: 'failed', exit_code: 1, output: "ModuleNotFoundError: No module named 'fastapi'" }),
      step({ attempt: 1 }),
      step({ attempt: 1, kind: 'py_import', label: 'Import the application', command: "python -c 'import main'" }),
    ],
    repairs: [{ attempt: 1, failed_step: 'Import the application ((root))',
                diagnosis: 'FastAPI is missing from requirements.txt.', model: 'm', error: null,
                files: [{ path: 'requirements.txt', action: 'modified', previous_sha256: 'a', new_sha256: 'b' }] }],
  },
  ...over,
});

const files: ProjectFile[] = [
  { path: 'main.py', size: 10, language: 'python', content: 'app = FastAPI()\n' },
  { path: 'requirements.txt', size: 8, language: 'text', content: 'fastapi\n' },
];

describe('ProjectPanel', () => {
  it('shows the verified result, every step, the repair and the files', async () => {
    api.list.mockResolvedValue([project()]);
    api.files.mockResolvedValue(files);
    render(<ProjectPanel workflowId="w1" active={false} />);

    expect(await screen.findByTestId('project-status')).toHaveTextContent('succeeded');
    expect(screen.getByText('Every install, build and test step passed.')).toBeInTheDocument();
    expect(screen.getByText('Rebuild after repair 1')).toBeInTheDocument();
    expect(screen.getByText('FastAPI is missing from requirements.txt.')).toBeInTheDocument();
    expect(screen.getByText(/requirements\.txt \(modified\)/)).toBeInTheDocument();
    expect(screen.getByText('.gitignore is missing')).toBeInTheDocument();
    // The failed step's log is open; passed steps are collapsed
    expect(screen.getByText("ModuleNotFoundError: No module named 'fastapi'")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('navigation', { name: 'Generated files' })).toBeInTheDocument());
  });

  it('reports a failed build honestly with the remaining error', async () => {
    const failed = project({ status: 'failed' });
    failed.latest_run = { ...failed.latest_run!, status: 'failed', error_summary: 'Still failing after 3 automatic repair attempt(s).' };
    api.list.mockResolvedValue([failed]);
    api.files.mockResolvedValue(files);
    render(<ProjectPanel workflowId="w1" active={false} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Still failing after 3 automatic repair attempt(s).');
    expect(screen.getByTestId('project-status')).toHaveTextContent('failed');
    expect(screen.queryByText('Every install, build and test step passed.')).not.toBeInTheDocument();
  });

  it('explains an unavailable sandbox instead of claiming success', async () => {
    api.list.mockResolvedValue([project({ status: 'unavailable', latest_run: null })]);
    api.files.mockResolvedValue(files);
    render(<ProjectPanel workflowId="w1" active={false} />);
    expect(await screen.findByText(/sandbox could not run it, so it has not been verified/)).toBeInTheDocument();
  });

  it('shows the current step while building and downloads the ZIP', async () => {
    const building = project({ status: 'building' });
    building.latest_run = { ...building.latest_run!, status: 'running', current_step: 'Install Python dependencies ((root))' };
    api.list.mockResolvedValue([building]);
    api.files.mockResolvedValue(files);
    api.download.mockResolvedValue(new Blob(['zip']));
    render(<ProjectPanel workflowId="w1" active />);
    expect(await screen.findByRole('status')).toHaveTextContent('Install Python dependencies');
    fireEvent.click(screen.getByRole('button', { name: /download zip/i }));
    await waitFor(() => expect(savedNames).toEqual(['student-api.zip']));
    expect(api.download).toHaveBeenCalledWith('p1');
  });

  it('renders nothing for a workflow without a project when idle', async () => {
    api.list.mockResolvedValue([]);
    const { container } = render(<ProjectPanel workflowId="w1" active={false} />);
    await waitFor(() => expect(api.list).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

describe('ProjectsPage', () => {
  it('lists projects and downloads one without regenerating', async () => {
    api.list.mockResolvedValue([project()]);
    api.download.mockResolvedValue(new Blob(['zip']));
    render(<MemoryRouter><ProjectsPage /></MemoryRouter>);
    const row = (await screen.findByText('Student API')).closest('tr')!;
    expect(within(row).getByText('succeeded')).toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: 'Download Student API as ZIP' }));
    await waitFor(() => expect(savedNames).toEqual(['student-api.zip']));
  });
});

describe('Planner mode', () => {
  it('sends the chosen mode with the objective', async () => {
    planner.analyzeObjective.mockResolvedValue({ complexity: 'complex', reason: 'A project with stages.', stages: [] });
    render(<MemoryRouter><ObjectiveInput /></MemoryRouter>);
    fireEvent.click(screen.getByLabelText(/Complete project/));
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Build a student management system' } });
    fireEvent.click(screen.getByRole('button', { name: /plan workflow/i }));
    await waitFor(() => expect(planner.analyzeObjective).toHaveBeenCalledWith('Build a student management system', 'project'));
    expect(await screen.findByText('Build & verify project')).toBeInTheDocument();
  });

  it('keeps artifact mode as the default', async () => {
    planner.analyzeObjective.mockResolvedValue({ complexity: 'simple', reason: 'One explanatory task.', stages: [] });
    render(<MemoryRouter><ObjectiveInput /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Explain binary search in Python' } });
    fireEvent.click(screen.getByRole('button', { name: /plan workflow/i }));
    await waitFor(() => expect(planner.analyzeObjective).toHaveBeenCalledWith('Explain binary search in Python', 'artifact'));
    expect(screen.queryByText('Build & verify project')).not.toBeInTheDocument();
  });
});
