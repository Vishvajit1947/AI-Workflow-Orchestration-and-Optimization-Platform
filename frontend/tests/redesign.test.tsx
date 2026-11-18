/**
 * Tests for behaviour added with the Mercury redesign: plan editing before approval,
 * execution-step grouping, breadcrumbs, the confirmation dialog, status tones and the DAG's
 * state-driven motion.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import PlanReview, { planLevels } from '../src/components/PlanReview';
import { breadcrumbsFor } from '../src/components/Layout';
import { useConfirm } from '../src/components/ui/Dialog';
import { StatusBadge } from '../src/components/ui/StatusBadge';
import { DAGVisualization } from '../src/components/DAGVisualization';
import type { LiveStageStatus, WorkflowDAG } from '../src/types/execution';
import { plannerApi, type ObjectiveAnalysisResponse, type StagePlan } from '../src/api/plannerApi';

vi.mock('../src/api/plannerApi', () => ({ plannerApi: { analyzeObjective: vi.fn(), generateWorkflow: vi.fn() } }));
const planner = vi.mocked(plannerApi);

const stage = (id: string, name: string, dependencies: string[] = []): StagePlan => ({
  id, name, description: `${name} description`, instruction: `Do ${name}`, stage_type: 'analysis',
  dependencies, expected_output: `${name} output`,
});

const plan: ObjectiveAnalysisResponse = {
  complexity: 'complex',
  reason: 'Needs design and implementation.',
  stages: [stage('s1', 'Requirements'), stage('s2', 'API design', ['s1']), stage('s3', 'UI design', ['s1']), stage('s4', 'Review', ['s2', 's3'])],
};

beforeEach(() => vi.clearAllMocks());

describe('planLevels', () => {
  it('groups stages into execution steps by dependency depth', () => {
    expect(planLevels(plan.stages).map((level) => level.map((s) => s.id))).toEqual([['s1'], ['s2', 's3'], ['s4']]);
  });

  it('ignores dependencies on stages that are not in the plan', () => {
    expect(planLevels([stage('a', 'A', ['missing'])]).map((l) => l.map((s) => s.id))).toEqual([['a']]);
  });
});

describe('PlanReview editing', () => {
  it('shows parallel steps and sends edits and removals with the approved plan', async () => {
    planner.generateWorkflow.mockResolvedValue({ id: 'wf-9' } as never);
    const onApproved = vi.fn();
    render(<PlanReview objective="Build an app" plan={plan} onApproved={onApproved} onBack={vi.fn()} />);

    expect(screen.getByText('runs 2 in parallel')).toBeInTheDocument();

    // Rename a stage
    fireEvent.click(screen.getByRole('button', { name: 'Edit Requirements' }));
    fireEvent.change(screen.getByLabelText('Stage name'), { target: { value: 'Gather requirements' } });
    // Approval waits until editing is finished
    expect(screen.getByRole('button', { name: /approve & create workflow/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Done' }));

    // Remove a stage: it also disappears from the dependents' dependency lists
    fireEvent.click(screen.getByRole('button', { name: 'Remove UI design' }));
    // The removed card animates out, then unmounts
    await waitFor(() => expect(screen.queryByText('UI design')).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /approve & create workflow/i }));
    await waitFor(() => expect(onApproved).toHaveBeenCalledWith('wf-9'));

    const sent = planner.generateWorkflow.mock.calls[0][0].plan.stages;
    expect(sent.map((s) => s.id)).toEqual(['s1', 's2', 's4']);
    expect(sent[0].name).toBe('Gather requirements');
    expect(sent[2].dependencies).toEqual(['s2']);
  });

  it('can reset edits back to the proposed plan', () => {
    render(<PlanReview objective="Build an app" plan={plan} onApproved={vi.fn()} onBack={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Remove Review' }));
    expect(screen.getByText('Stages (3)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /reset edits/i }));
    expect(screen.getByText('Stages (4)')).toBeInTheDocument();
  });
});

describe('breadcrumbsFor', () => {
  it('names the section and page for each route', () => {
    expect(breadcrumbsFor('/').map((c) => c.label)).toEqual(['Build', 'New workflow']);
    expect(breadcrumbsFor('/cache').map((c) => c.label)).toEqual(['Insights', 'Semantic cache']);
    expect(breadcrumbsFor('/workflows/abc/edit')).toEqual([
      { label: 'Workflows', to: '/workflows' },
      { label: 'Workflow', to: '/workflows/abc' },
      { label: 'Edit' },
    ]);
    expect(breadcrumbsFor('/nope')).toEqual([]);
  });
});

describe('useConfirm', () => {
  function Harness({ onResult }: { onResult: (ok: boolean) => void }) {
    const [confirm, dialog] = useConfirm();
    return (
      <>
        <button onClick={async () => onResult(await confirm({ title: 'Delete it?', confirmLabel: 'Delete', destructive: true }))}>
          Open
        </button>
        {dialog}
      </>
    );
  }

  it('resolves true on confirm, false on cancel or Escape', async () => {
    const onResult = vi.fn();
    render(<Harness onResult={onResult} />);

    fireEvent.click(screen.getByText('Open'));
    expect(screen.getByRole('dialog', { name: /delete it\?/i })).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(onResult).toHaveBeenLastCalledWith(true));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Open'));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(onResult).toHaveBeenLastCalledWith(false));

    fireEvent.click(screen.getByText('Open'));
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(onResult).toHaveBeenCalledTimes(3));
    expect(onResult).toHaveBeenLastCalledWith(false);
  });
});

describe('StatusBadge', () => {
  it('maps every status to one tone and shows the status text', () => {
    const { rerender } = render(<StatusBadge status="running" />);
    expect(screen.getByText('running')).toHaveAttribute('data-tone', 'info');
    rerender(<StatusBadge status="succeeded" />);
    expect(screen.getByText('succeeded')).toHaveAttribute('data-tone', 'success');
    rerender(<StatusBadge status="something-new" />);
    expect(screen.getByText('something-new')).toHaveAttribute('data-tone', 'neutral');
  });
});


describe('DAG motion reflects execution state', () => {
  const dag: WorkflowDAG = {
    nodes: [
      { stage_id: 'a', name: 'Start', stage_order: 0, stage_type: null, level: 0, dependencies: [], is_merge_point: false, on_critical_path: true },
      { stage_id: 'b', name: 'Next', stage_order: 1, stage_type: null, level: 1, dependencies: ['a'], is_merge_point: false, on_critical_path: true },
    ],
    edges: [{ source: 'a', target: 'b' }],
    levels: [['a'], ['b']], critical_path: ['a', 'b'], parallelism_factor: 1, max_width: 1,
  };
  const live = (a: LiveStageStatus['status'], b: LiveStageStatus['status']) => Object.fromEntries(
    [['a', a], ['b', b]].map(([id, status]) => [id, {
      stage_id: id, name: id, stage_order: 0, stage_type: null, level: 0, status, provider: null, model: null,
      cache_hit: false, error: null, started_at: null, completed_at: null,
    } as LiveStageStatus]),
  );

  it('pulses running stages, flows into them, and flashes a stage only when it finishes', () => {
    const { container, rerender } = render(<DAGVisualization dag={dag} stageStatuses={live('completed', 'running')} />);
    // Already completed on first render: no flash
    expect(container.querySelectorAll('.animate-flash-ring')).toHaveLength(0);
    expect(screen.getByTestId('dag-node-b').querySelector('.animate-pulse-ring')).not.toBeNull();
    expect(screen.getByTestId('dag-edge-a-b')).toHaveClass('animate-flow-dash');

    // b finishes: one flash on b, the pulse and edge flow stop
    rerender(<DAGVisualization dag={dag} stageStatuses={live('completed', 'completed')} />);
    const flashes = container.querySelectorAll('.animate-flash-ring');
    expect(flashes).toHaveLength(1);
    expect(screen.getByTestId('dag-node-b').contains(flashes[0])).toBe(true);
    expect(container.querySelectorAll('.animate-pulse-ring')).toHaveLength(0);
    expect(screen.getByTestId('dag-edge-a-b')).not.toHaveClass('animate-flow-dash');
  });
});
