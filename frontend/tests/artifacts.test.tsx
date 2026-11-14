/**
 * Generated-file presentation: file tree, previews, per-file / PDF / TXT / ZIP downloads,
 * and unchanged rendering when a stage has no artifact.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { StageResult } from '../src/components/results/StageResult';
import { buildFileTree } from '../src/components/results/ArtifactOutput';
import { executionApi } from '../src/api/executionApi';
import type { Artifact, StageExecutionDetail } from '../src/types/execution';

vi.mock('../src/api/executionApi', () => ({
  executionApi: { downloadStageDocument: vi.fn(), downloadStageZip: vi.fn(), downloadExecutionZip: vi.fn() },
}));
const api = vi.mocked(executionApi);

const createObjectURL = vi.fn(() => 'blob:mock');
const savedNames: string[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  savedNames.length = 0;
  Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    savedNames.push(this.download);
  });
});

const project: Artifact = {
  artifact_type: 'project',
  name: 'fastapi-crud',
  conflicts: [],
  files: [
    { path: 'backend/main.py', content: 'app = FastAPI()\n', language: 'python' },
    { path: 'backend/routes/users.py', content: 'router = APIRouter()\n', language: 'python' },
    { path: 'README.md', content: '# CRUD\n\n```bash\nuvicorn main:app\n```\n', language: 'markdown' },
  ],
};

const stage = (overrides: Partial<StageExecutionDetail> = {}): StageExecutionDetail => ({
  id: 'rec-1', stage_id: 'stage-1', stage_name: 'Backend Implementation', stage_order: 0,
  model_used: 'm', provider: 'groq', input_tokens: 1, output_tokens: 2, total_tokens: 3, latency_ms: 10,
  estimated_cost: '0.0001', status: 'completed', result: 'Here is the project.', error_message: null,
  started_at: null, completed_at: null, duration_ms: 10, cache_hit: false, cache_similarity: null,
  tokens_saved: null, cost_saved: null, ...overrides,
});

describe('buildFileTree', () => {
  it('nests folders, folders first, alphabetical', () => {
    const tree = buildFileTree(project.files);
    expect(tree.map((n) => n.name)).toEqual(['backend', 'README.md']);
    const backend = tree[0].children!;
    expect(backend.map((n) => n.name)).toEqual(['routes', 'main.py']);
    expect(backend[0].children![0].path).toBe('backend/routes/users.py');
  });
});

describe('StageResult without an artifact', () => {
  it('renders the plain output with no file view and no downloads when no execution id is given', () => {
    render(<StageResult stage={stage({ artifact: null, result: '# Title\n\nBody text' })} />);
    expect(screen.getByText('Body text')).toBeInTheDocument();
    expect(screen.queryByTestId('artifact-output')).toBeNull();
    expect(screen.queryByTestId('document-downloads')).toBeNull();
    expect(screen.queryByRole('group', { name: 'Output view' })).toBeNull();
  });

  it('offers PDF and TXT downloads for completed text output', async () => {
    api.downloadStageDocument.mockResolvedValue(new Blob(['%PDF']));
    render(<StageResult stage={stage({ result: 'Explanation' })} executionId="exec-1" />);
    fireEvent.click(screen.getByRole('button', { name: /PDF/ }));
    await waitFor(() => expect(savedNames).toEqual(['backend-implementation.pdf']));
    expect(api.downloadStageDocument).toHaveBeenCalledWith('exec-1', 'stage-1', 'pdf');
    fireEvent.click(screen.getByRole('button', { name: /TXT/ }));
    await waitFor(() => expect(savedNames).toEqual(['backend-implementation.pdf', 'backend-implementation.txt']));
  });

  it('shows a non-blocking error when an export fails and keeps the output', async () => {
    api.downloadStageDocument.mockRejectedValue({
      response: { data: new Blob([JSON.stringify({ detail: 'Could not create PDF: boom' })]) },
    });
    render(<StageResult stage={stage({ result: 'Explanation stays' })} executionId="exec-1" />);
    fireEvent.click(screen.getByRole('button', { name: /PDF/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not create PDF: boom');
    expect(screen.getByText('Explanation stays')).toBeInTheDocument();
  });

  it('hides downloads for failed stages', () => {
    render(<StageResult stage={stage({ status: 'failed', error_message: 'x', result: null })} executionId="exec-1" />);
    expect(screen.queryByTestId('document-downloads')).toBeNull();
  });
});

describe('StageResult with a project artifact', () => {
  it('shows the file explorer and previews the selected file', () => {
    render(<StageResult stage={stage({ artifact: project })} executionId="exec-1" />);
    const explorer = screen.getByRole('navigation', { name: 'Generated files' });
    expect(within(explorer).getByText('main.py')).toBeInTheDocument();
    expect(screen.getByTestId('file-viewer')).toHaveTextContent('backend/main.py');
    fireEvent.click(within(explorer).getByText('README.md'));
    expect(screen.getByTestId('file-viewer')).toHaveTextContent('uvicorn main:app');
  });

  it('collapses folders', () => {
    render(<StageResult stage={stage({ artifact: project })} />);
    const explorer = screen.getByRole('navigation', { name: 'Generated files' });
    fireEvent.click(within(explorer).getByRole('button', { name: 'backend' }));
    expect(within(explorer).queryByText('main.py')).toBeNull();
  });

  it('switches between generated files and the full output', () => {
    render(<StageResult stage={stage({ artifact: project, result: 'Full model answer' })} />);
    expect(screen.queryByText('Full model answer')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'View full output' }));
    expect(screen.getByText('Full model answer')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /View generated files \(3\)/ }));
    expect(screen.getByTestId('artifact-output')).toBeInTheDocument();
  });

  it('downloads a single file with its own name and the project as a ZIP', async () => {
    api.downloadStageZip.mockResolvedValue(new Blob(['PK']));
    render(<StageResult stage={stage({ artifact: project })} executionId="exec-1" />);
    fireEvent.click(within(screen.getByTestId('file-viewer')).getByRole('button', { name: /Download/ }));
    expect(savedNames).toEqual(['main.py']);
    fireEvent.click(screen.getByRole('button', { name: /Download ZIP/ }));
    await waitFor(() => expect(savedNames).toEqual(['main.py', 'fastapi-crud.zip']));
    expect(api.downloadStageZip).toHaveBeenCalledWith('exec-1', 'stage-1');
  });

  it('has no ZIP button without an execution id or for a single code file', () => {
    const { unmount } = render(<StageResult stage={stage({ artifact: project })} />);
    expect(screen.queryByRole('button', { name: /Download ZIP/ })).toBeNull();
    unmount();
    const code: Artifact = { artifact_type: 'code', name: 'search.py', conflicts: [],
      files: [{ path: 'search.py', content: 'def search(): ...\n', language: 'python' }] };
    render(<StageResult stage={stage({ artifact: code })} executionId="exec-1" />);
    expect(screen.queryByRole('button', { name: /Download ZIP/ })).toBeNull();
    expect(screen.queryByRole('navigation', { name: 'Generated files' })).toBeNull();
    expect(screen.getByTestId('file-viewer')).toHaveTextContent('search.py');
  });

  it('lists path conflicts explicitly', () => {
    const withConflict = { ...project, conflicts: [{ path: 'README.md', kept_from: 'Docs', overridden_from: 'Backend' }] };
    render(<StageResult stage={stage({ artifact: withConflict })} />);
    expect(screen.getByText(/Docs replaced Backend/)).toBeInTheDocument();
  });

  it('treats an explanation artifact (no files) as plain output', () => {
    const explanation: Artifact = { artifact_type: 'explanation', name: 'x', files: [], conflicts: [] };
    render(<StageResult stage={stage({ artifact: explanation, result: 'Plain words' })} />);
    expect(screen.getByText('Plain words')).toBeInTheDocument();
    expect(screen.queryByTestId('artifact-output')).toBeNull();
  });
});
