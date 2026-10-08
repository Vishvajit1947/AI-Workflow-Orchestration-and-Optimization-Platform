/**
 * Frontend Phase 5 tests: live status reducer, WebSocket-driven execution monitor,
 * DAG visualization, execution controls, and parallel stages in the stage editor.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import { applyExecutionEvent } from '../src/hooks/useExecutionStatus';
import { DAGVisualization } from '../src/components/DAGVisualization';
import { ExecutionControls } from '../src/components/ExecutionControls';
import { ExecutionMonitor } from '../src/components/ExecutionMonitor';
import { ExecutionConfigModal } from '../src/components/ExecutionConfigModal';
import StageEditor from '../src/components/StageEditor';
import { executionApi } from '../src/api/executionApi';
import { stageApi } from '../src/lib/stages';
import type { ExecutionStatus, LiveStageStatus, WorkflowDAG } from '../src/types/execution';
import type { Stage } from '../src/types';

vi.mock('../src/api/executionApi', () => ({
  executionApi: {
    getStatus: vi.fn(), pause: vi.fn(), resume: vi.fn(), cancel: vi.fn(),
    getDag: vi.fn(), getLiveExecution: vi.fn(),
  },
}));
vi.mock('../src/api/modelsApi', () => ({ modelsApi: { listModels: vi.fn().mockResolvedValue([]) } }));
vi.mock('../src/lib/stages', () => ({
  stageApi: { update: vi.fn(), create: vi.fn(), delete: vi.fn(), reorder: vi.fn() },
}));

const execApi = vi.mocked(executionApi);
const stages = vi.mocked(stageApi);

// ---------- fixtures ----------

const liveStage = (id: string, name: string, level: number, overrides: Partial<LiveStageStatus> = {}): LiveStageStatus => ({
  stage_id: id, name, stage_order: level, stage_type: 'analysis', level, status: 'pending',
  provider: null, model: null, cache_hit: false, error: null, started_at: null, completed_at: null,
  ...overrides,
});

const dag: WorkflowDAG = {
  nodes: [
    { stage_id: 'a', name: 'Start', stage_order: 0, stage_type: 'analysis', level: 0, dependencies: [], is_merge_point: false, on_critical_path: true },
    { stage_id: 'b', name: 'Left', stage_order: 1, stage_type: 'design', level: 1, dependencies: ['a'], is_merge_point: false, on_critical_path: true },
    { stage_id: 'c', name: 'Right', stage_order: 1, stage_type: 'design', level: 1, dependencies: ['a'], is_merge_point: false, on_critical_path: false },
    { stage_id: 'd', name: 'Merge', stage_order: 2, stage_type: 'review', level: 2, dependencies: ['b', 'c'], is_merge_point: true, on_critical_path: true },
  ],
  edges: [
    { source: 'a', target: 'b' }, { source: 'a', target: 'c' },
    { source: 'b', target: 'd' }, { source: 'c', target: 'd' },
  ],
  levels: [['a'], ['b', 'c'], ['d']],
  critical_path: ['a', 'b', 'd'],
  parallelism_factor: 1.33,
  max_width: 2,
};

const snapshot = (overrides: Partial<ExecutionStatus> = {}): ExecutionStatus => ({
  execution_id: 'exec-1', workflow_id: 'wf-1', workflow_name: 'WF', status: 'running', parallel: true,
  progress: 0, error: null, started_at: '2026-09-27T10:00:00Z', completed_at: null,
  stages: [liveStage('a', 'Start', 0, { status: 'running', started_at: '2026-09-27T10:00:00Z' }),
           liveStage('b', 'Left', 1), liveStage('c', 'Right', 1), liveStage('d', 'Merge', 2)],
  dag,
  ...overrides,
});

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];
  readyState = 0;
  url: string;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; }
  open() { this.readyState = 1; this.onopen?.(); }
  emit(event: object) { this.onmessage?.({ data: JSON.stringify(event) }); }
}

beforeEach(() => {
  vi.clearAllMocks();
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------- reducer ----------

describe('applyExecutionEvent', () => {
  it('replaces state on snapshot and merges stage updates', () => {
    let state = applyExecutionEvent(null, { type: 'snapshot', ...snapshot() });
    expect(state?.stages[0].status).toBe('running');

    state = applyExecutionEvent(state, {
      type: 'stage_update', execution_id: 'exec-1', progress: 0.25,
      stage: liveStage('a', 'Start', 0, { status: 'completed', model: 'gpt-4o-mini' }),
    });
    expect(state?.progress).toBe(0.25);
    expect(state?.stages[0]).toMatchObject({ status: 'completed', model: 'gpt-4o-mini' });
    expect(state?.stages[1].status).toBe('pending');
  });

  it('applies execution status but ignores the transient cancelling notice', () => {
    const base = snapshot();
    expect(applyExecutionEvent(base, { type: 'execution_status', execution_id: 'exec-1', status: 'cancelling', progress: 0 }))
      .toBe(base);
    expect(applyExecutionEvent(base, { type: 'execution_status', execution_id: 'exec-1', status: 'paused', progress: 0.5 }))
      .toMatchObject({ status: 'paused', progress: 0.5 });
    expect(applyExecutionEvent(null, { type: 'stage_update', execution_id: 'x', progress: 1, stage: liveStage('a', 'A', 0) }))
      .toBeNull();
  });
});

// ---------- DAG ----------

describe('DAGVisualization', () => {
  it('draws every stage and dependency, highlighting the critical path when idle', () => {
    render(<DAGVisualization dag={dag} />);
    expect(screen.getByRole('img', { name: 'Workflow graph: 4 stages in 3 levels' })).toBeInTheDocument();
    for (const id of ['a', 'b', 'c', 'd']) expect(screen.getByTestId(`dag-node-${id}`)).toBeInTheDocument();
    expect(screen.getByTestId('dag-edge-a-b').getAttribute('stroke')).toBe('#a78bfa');   // on critical path
    expect(screen.getByTestId('dag-edge-a-c').getAttribute('stroke')).toBe('#475569');   // not
    expect(screen.getByText('⤚ merge')).toBeInTheDocument();
  });

  it('colors nodes by live status and animates edges into running stages', () => {
    const statuses = {
      a: liveStage('a', 'Start', 0, { status: 'completed', model: 'gpt-4o-mini' }),
      b: liveStage('b', 'Left', 1, { status: 'running' }),
      c: liveStage('c', 'Right', 1, { status: 'failed', error: 'boom' }),
      d: liveStage('d', 'Merge', 2, { status: 'skipped' }),
    };
    render(<DAGVisualization dag={dag} stageStatuses={statuses} />);
    expect(screen.getByTestId('dag-node-a')).toHaveAttribute('data-status', 'completed');
    expect(screen.getByTestId('dag-node-c')).toHaveAttribute('data-status', 'failed');
    expect(screen.getByText('gpt-4o-mini')).toBeInTheDocument();
    expect(screen.getByTestId('dag-edge-a-b').getAttribute('stroke-dasharray')).toBe('6 4');
    expect(screen.getByTestId('dag-edge-a-c').getAttribute('stroke-dasharray')).toBeNull();
  });
});

// ---------- controls ----------

describe('ExecutionControls', () => {
  it('offers pause and cancel while running', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ExecutionControls executionId="exec-1" status="running" />);
    fireEvent.click(screen.getByRole('button', { name: /pause/i }));
    await waitFor(() => expect(execApi.pause).toHaveBeenCalledWith('exec-1'));
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => expect(execApi.cancel).toHaveBeenCalledWith('exec-1'));
  });

  it('offers resume while paused and nothing once finished', async () => {
    const { rerender } = render(<ExecutionControls executionId="exec-1" status="paused" />);
    fireEvent.click(screen.getByRole('button', { name: /resume/i }));
    await waitFor(() => expect(execApi.resume).toHaveBeenCalledWith('exec-1'));

    rerender(<ExecutionControls executionId="exec-1" status="completed" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows API errors', async () => {
    execApi.pause.mockRejectedValueOnce({ response: { data: { detail: 'Execution is already completed' } } });
    render(<ExecutionControls executionId="exec-1" status="running" />);
    fireEvent.click(screen.getByRole('button', { name: /pause/i }));
    expect(await screen.findByText('Execution is already completed')).toBeInTheDocument();
  });
});

// ---------- monitor ----------

describe('ExecutionMonitor', () => {
  it('follows WebSocket events through to completion', async () => {
    execApi.getStatus.mockResolvedValue(snapshot());
    const onFinished = vi.fn();
    render(<ExecutionMonitor executionId="exec-1" onFinished={onFinished} />);

    expect(await screen.findByTestId('live-status')).toHaveTextContent('running');
    const [socket] = MockWebSocket.instances;
    expect(socket.url).toMatch(/\/ws\/executions\/exec-1$/);
    act(() => socket.open());
    expect(screen.getByText('live')).toBeInTheDocument();

    act(() => socket.emit({
      type: 'stage_update', execution_id: 'exec-1', progress: 0.25,
      stage: liveStage('a', 'Start', 0, { status: 'completed', started_at: '2026-09-27T10:00:00Z', completed_at: '2026-09-27T10:00:02Z' }),
    }));
    expect(screen.getByTestId('dag-node-a')).toHaveAttribute('data-status', 'completed');
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '25');
    expect(within(screen.getByTestId('timeline-a')).getByText('2.0s')).toBeInTheDocument();

    act(() => socket.emit({ type: 'execution_status', execution_id: 'exec-1', status: 'paused', progress: 0.25 }));
    expect(screen.getByTestId('live-status')).toHaveTextContent('paused');
    expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument();
    expect(onFinished).not.toHaveBeenCalled();

    act(() => socket.emit({ type: 'execution_status', execution_id: 'exec-1', status: 'completed', progress: 1 }));
    await waitFor(() => expect(onFinished).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole('button', { name: /pause|resume|cancel/i })).not.toBeInTheDocument();
  });

  it('lists stage errors', async () => {
    execApi.getStatus.mockResolvedValue(snapshot({
      status: 'failed',
      stages: [liveStage('a', 'Start', 0, { status: 'failed', error: 'openai/gpt-4o failed after 3 attempt(s)' })],
    }));
    render(<ExecutionMonitor executionId="exec-1" />);
    expect(await screen.findByText('openai/gpt-4o failed after 3 attempt(s)')).toBeInTheDocument();
  });
});

// ---------- execute modal ----------

describe('ExecutionConfigModal parallel option', () => {
  it('sends parallel=false when unticked', () => {
    const onExecute = vi.fn();
    render(<ExecutionConfigModal isOpen onClose={vi.fn()} onExecute={onExecute} workflowName="WF" />);
    fireEvent.click(screen.getByLabelText('Run independent stages in parallel'));
    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));
    expect(onExecute).toHaveBeenCalledWith(expect.objectContaining({ parallel: false }));
  });
});

// ---------- stage editor ----------

describe('StageEditor parallel stages', () => {
  const stage = (id: string, name: string, order: number): Stage => ({
    id, workflow_id: 'wf-1', name, instruction: `Do ${name}`, stage_order: order, stage_type: null,
    model_preference: null, config: {}, status: 'pending', created_at: '', updated_at: '', dependencies: [],
  });
  const workflowStages = [stage('a', 'Start', 0), stage('b', 'Left', 1), stage('c', 'Right', 1), stage('d', 'End', 2)];

  it('numbers steps by stage_order and marks parallel stages', () => {
    render(<StageEditor workflowId="wf-1" stages={workflowStages} onUpdate={vi.fn()} />);
    expect(screen.getAllByText('parallel')).toHaveLength(2);
    expect(screen.getAllByText('2')).toHaveLength(2); // Left and Right share step 2
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('adds a stage in parallel with the last step', async () => {
    stages.create.mockResolvedValue({} as Stage);
    render(<StageEditor workflowId="wf-1" stages={workflowStages} onUpdate={vi.fn()} />);
    fireEvent.click(screen.getByText('Add Stage'));
    fireEvent.change(screen.getByPlaceholderText('Stage name'), { target: { value: 'Also End' } });
    fireEvent.change(screen.getByPlaceholderText('Instruction for the LLM...'), { target: { value: 'Do it' } });
    fireEvent.click(screen.getByLabelText('Run in parallel with the previous step'));
    const [, submit] = screen.getAllByRole('button', { name: /add stage/i }); // header button, then the form's
    fireEvent.click(submit);

    await waitFor(() => expect(stages.create).toHaveBeenCalledWith(expect.objectContaining({ stage_order: 2 })));
  });

  it('moves a stage by swapping stage_order values, keeping groups', async () => {
    stages.update.mockResolvedValue({} as Stage);
    const onUpdate = vi.fn();
    render(<StageEditor workflowId="wf-1" stages={workflowStages} onUpdate={onUpdate} />);
    // "up" arrow of the last stage (End, order 2) swaps with Right (order 1)
    const endRow = screen.getByText('End').closest('.glass')!;
    fireEvent.click(endRow.querySelectorAll('button')[0]);

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    expect(stages.update).toHaveBeenCalledWith('d', { stage_order: 1 });
    expect(stages.update).toHaveBeenCalledWith('c', { stage_order: 2 });
    expect(stages.reorder).not.toHaveBeenCalled();
  });
});
