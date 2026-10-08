/**
 * Frontend routing UI tests: Models & Routing page, per-stage overrides in the
 * execute modal, routing badges in results, and the stage editor model dropdown.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { ModelComparison } from '../src/pages/ModelComparison';
import { ExecutionConfigModal } from '../src/components/ExecutionConfigModal';
import { ExecutionResults } from '../src/components/ExecutionResults';
import StageEditor from '../src/components/StageEditor';
import { modelsApi } from '../src/api/modelsApi';
import { routingApi } from '../src/api/routingApi';
import { stageApi } from '../src/lib/stages';
import type { ModelProfile, RoutingRule } from '../src/types/routing';
import type { Stage } from '../src/types';
import type { ExecutionDetailResponse, StageExecutionDetail } from '../src/types/execution';

vi.mock('../src/api/modelsApi', () => ({
  modelsApi: {
    listModels: vi.fn(),
    getModel: vi.fn(),
    compareModels: vi.fn(),
    setAvailability: vi.fn(),
  },
}));

vi.mock('../src/api/routingApi', () => ({
  routingApi: {
    listRules: vi.fn(),
    createRule: vi.fn(),
    updateRule: vi.fn(),
    deleteRule: vi.fn(),
    listDecisions: vi.fn(),
    preview: vi.fn(),
  },
}));

vi.mock('../src/lib/stages', () => ({
  stageApi: { update: vi.fn(), create: vi.fn(), delete: vi.fn(), reorder: vi.fn() },
}));

const models = vi.mocked(modelsApi);
const routing = vi.mocked(routingApi);
const stages = vi.mocked(stageApi);

const profile = (overrides: Partial<ModelProfile>): ModelProfile => ({
  id: 'id', provider: 'openai', model_name: 'm', display_name: 'M',
  capabilities: {}, max_context_tokens: 128000, max_output_tokens: 8192,
  cost_per_input_token: '0.0000001500', cost_per_output_token: '0.0000006000',
  avg_latency_ms: 800, is_available: true, supports_streaming: true, supports_function_calling: true,
  description: null, strengths: [], limitations: [], created_at: '2026-09-27T00:00:00Z', routable: true,
  ...overrides,
});

const mini = profile({
  id: 'mini-id', model_name: 'gpt-4o-mini', display_name: 'GPT-4o Mini',
  capabilities: { analysis: 0.85, generation: 0.87 },
});
const sonnet = profile({
  id: 'sonnet-id', provider: 'anthropic', model_name: 'claude-sonnet-4-20250514', display_name: 'Claude Sonnet 4',
  capabilities: { analysis: 0.96, generation: 0.97 }, cost_per_input_token: '0.000003',
  cost_per_output_token: '0.000015', avg_latency_ms: 1800, routable: false,
});
const disabled = profile({ id: 'off-id', model_name: 'gpt-4o', display_name: 'GPT-4o', is_available: false });

const generationRule: RoutingRule = {
  id: 'rule-1', stage_type: 'generation', priority_factor: 'quality',
  max_cost_per_call: null, max_latency_ms: null, min_capability_score: '0.85',
  preferred_model_id: null, fallback_model_id: 'mini-id', preferred_model: null,
  fallback_model: { id: 'mini-id', provider: 'openai', model_name: 'gpt-4o-mini', display_name: 'GPT-4o Mini' },
  is_active: true, created_at: '2026-09-27T00:00:00Z', updated_at: '2026-09-27T00:00:00Z',
};

const stage = (overrides: Partial<Stage>): Stage => ({
  id: 's', workflow_id: 'wf-1', name: 'S', instruction: 'Do it', stage_order: 0,
  stage_type: null, model_preference: null, config: {}, status: 'pending',
  created_at: '', updated_at: '', dependencies: [], ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  models.compareModels.mockResolvedValue({
    models: [mini, sonnet],
    cheapest: 'gpt-4o-mini',
    fastest: 'gpt-4o-mini',
    most_capable: { generation: 'claude-sonnet-4-20250514' },
  });
  models.listModels.mockResolvedValue([mini, sonnet, disabled]);
  models.setAvailability.mockResolvedValue(mini);
  routing.listRules.mockResolvedValue([generationRule]);
  routing.updateRule.mockResolvedValue(generationRule);
  routing.createRule.mockResolvedValue(generationRule);
  routing.listDecisions.mockResolvedValue([{
    id: 'd1', execution_id: 'e1', stage_id: 's1', stage_type: 'generation', selected_model_id: 'sonnet-id',
    selected_provider: 'anthropic', selected_model_name: 'claude-sonnet-4-20250514',
    selection_reason: 'Routing: quality priority for generation', priority_factor: 'quality',
    alternatives_considered: [], was_user_override: false, was_fallback: true, created_at: '2026-09-27T10:00:00Z',
  }]);
  routing.preview.mockResolvedValue([
    { stage_id: 's1', stage_name: 'Analyze', stage_type: 'analysis', provider: 'openai', model_name: 'gpt-4o-mini', reason: 'Routing: balanced priority' },
    { stage_id: 's2', stage_name: 'Code', stage_type: 'generation', provider: 'anthropic', model_name: 'claude-sonnet-4-20250514', reason: 'Routing: quality priority' },
  ]);
  stages.update.mockResolvedValue({} as Stage);
});

// ============================================================================
// Models & Routing page
// ============================================================================

describe('ModelComparison page', () => {
  it('shows highlights, model statuses and decision log', async () => {
    render(<ModelComparison />);

    const cheapest = (await screen.findByText('Most Cost-Effective')).parentElement!;
    expect(within(cheapest).getByText('GPT-4o Mini')).toBeInTheDocument();
    const best = screen.getByText('Best for Code Generation').parentElement!;
    expect(within(best).getByText('Claude Sonnet 4')).toBeInTheDocument();

    expect(screen.getByText('routable')).toBeInTheDocument();
    expect(screen.getByText('no API key')).toBeInTheDocument();
    expect(screen.getByText('disabled')).toBeInTheDocument();
    expect(screen.getByText('Routing: quality priority for generation')).toBeInTheDocument();
    expect(screen.getByText('fallback')).toBeInTheDocument();
  });

  it('lists every stage type, with Add rule where none exists', async () => {
    render(<ModelComparison />);
    expect(await screen.findByLabelText('generation priority')).toHaveValue('quality');
    // 7 stage types, 1 has a rule
    expect(screen.getAllByText('Add rule')).toHaveLength(6);
  });

  it('saves an edited rule with parsed values', async () => {
    render(<ModelComparison />);
    fireEvent.change(await screen.findByLabelText('generation priority'), { target: { value: 'cost' } });
    fireEvent.change(screen.getByLabelText('generation max latency'), { target: { value: '1000' } });
    fireEvent.click(screen.getByTitle('Save rule'));

    await waitFor(() => expect(routing.updateRule).toHaveBeenCalledWith('generation', {
      priority_factor: 'cost',
      min_capability_score: 0.85,
      max_cost_per_call: null,
      max_latency_ms: 1000,
      preferred_model_id: null,
      fallback_model_id: 'mini-id',
      is_active: true,
    }));
    expect(await screen.findByText('Routing rule for generation saved')).toBeInTheDocument();
  });

  it('creates a rule for a stage type without one', async () => {
    render(<ModelComparison />);
    fireEvent.click((await screen.findAllByText('Add rule'))[0]); // analysis
    fireEvent.change(screen.getByLabelText('analysis priority'), { target: { value: 'speed' } });
    fireEvent.click(screen.getAllByTitle('Save rule')[0]);

    await waitFor(() => expect(routing.createRule).toHaveBeenCalledWith(
      'analysis', expect.objectContaining({ priority_factor: 'speed', min_capability_score: 0.8 })
    ));
  });

  it('toggles model availability', async () => {
    render(<ModelComparison />);
    fireEvent.click((await screen.findAllByText('Disable'))[0]);
    await waitFor(() => expect(models.setAvailability).toHaveBeenCalledWith('openai', 'gpt-4o-mini', false));
  });
});

// ============================================================================
// Execute modal
// ============================================================================

describe('ExecutionConfigModal routing', () => {
  const workflowStages = [
    stage({ id: 's1', name: 'Analyze', stage_type: 'analysis', stage_order: 0 }),
    stage({ id: 's2', name: 'Code', stage_type: 'generation', stage_order: 1 }),
  ];

  it('shows the routing preview and sends per-stage overrides', async () => {
    const onExecute = vi.fn();
    render(
      <ExecutionConfigModal isOpen onClose={vi.fn()} onExecute={onExecute}
        workflowName="WF" workflowId="wf-1" stages={workflowStages} />
    );
    await waitFor(() => expect(routing.preview).toHaveBeenCalledWith('wf-1'));

    fireEvent.click(screen.getByText(/per-stage models/));
    expect(await screen.findByText('Auto → claude-sonnet-4-20250514')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Analyze/), { target: { value: 'claude-sonnet-4-20250514' } });
    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));

    expect(onExecute).toHaveBeenCalledWith(expect.objectContaining({
      use_routing: true,
      routing_preferences: { s1: 'claude-sonnet-4-20250514' },
    }));
  });

  it('disabling smart routing drops overrides', async () => {
    const onExecute = vi.fn();
    render(
      <ExecutionConfigModal isOpen onClose={vi.fn()} onExecute={onExecute}
        workflowName="WF" workflowId="wf-1" stages={workflowStages} />
    );
    fireEvent.click(screen.getByText(/per-stage models/));
    fireEvent.change(await screen.findByLabelText(/Analyze/), { target: { value: 'gpt-4o-mini' } });
    fireEvent.click(screen.getByLabelText('Smart routing'));
    expect(screen.queryByText(/per-stage models/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Execute' }));
    expect(onExecute).toHaveBeenCalledWith(expect.objectContaining({ use_routing: false, routing_preferences: {} }));
  });

  it('does not call the API without stages', () => {
    render(<ExecutionConfigModal isOpen onClose={vi.fn()} onExecute={vi.fn()} workflowName="WF" />);
    expect(models.listModels).not.toHaveBeenCalled();
    expect(routing.preview).not.toHaveBeenCalled();
  });
});

// ============================================================================
// Execution results
// ============================================================================

describe('ExecutionResults routing badges', () => {
  const stageResult = (overrides: Partial<StageExecutionDetail>): StageExecutionDetail => ({
    id: 'r', stage_id: 's', stage_name: 'S', stage_order: 0, model_used: 'gpt-4o-mini', provider: 'openai',
    input_tokens: 100, output_tokens: 50, total_tokens: 150, latency_ms: 300, estimated_cost: 0.0001,
    status: 'completed', result: 'ok', error_message: null, started_at: null, completed_at: null,
    duration_ms: 300, cache_hit: false, cache_similarity: null, tokens_saved: null, cost_saved: null,
    ...overrides,
  });

  const execution: ExecutionDetailResponse = {
    summary: {
      execution_id: 'exec-1', workflow_id: 'wf-1', workflow_name: 'WF', status: 'completed',
      total_stages: 4, completed_stages: 4, failed_stages: 0, total_tokens: 450, total_cost: 0.0003,
      total_latency_ms: 900, started_at: null, completed_at: null, duration_ms: 900,
    },
    stages: [
      stageResult({ id: 'r1', stage_name: 'Analyze', was_routed: true, routing_reason: 'Routing: balanced priority for analysis' }),
      stageResult({ id: 'r2', stage_name: 'Design', was_routed: true, was_user_override: true, routing_reason: 'User override: gpt-4o-mini' }),
      stageResult({ id: 'r3', stage_name: 'Build', was_fallback: true, routing_reason: 'No routable model; using execution default' }),
      stageResult({ id: 'r4', stage_name: 'Docs', cache_hit: true, provider: 'cache' }),
    ],
  };

  it('labels each stage by how its model was chosen', () => {
    render(<ExecutionResults execution={execution} />);
    const chips = screen.getAllByTestId('routing-chip').map((chip) => chip.textContent);
    expect(chips).toEqual(['Routed', 'Override', 'Fallback']); // none for the cached stage
    expect(screen.getByText('Routing: balanced priority for analysis')).toBeInTheDocument();
    expect(screen.getAllByText('(openai)')).toHaveLength(3); // provider shown except for cache hits
  });
});

// ============================================================================
// Stage editor
// ============================================================================

describe('StageEditor model preference', () => {
  it('ranks models by stage-type fit and clears the preference with Auto', async () => {
    const onUpdate = vi.fn();
    render(
      <StageEditor
        workflowId="wf-1"
        onUpdate={onUpdate}
        stages={[stage({ id: 's2', name: 'Code', stage_type: 'generation', model_preference: 'gpt-4o-mini' })]}
      />
    );
    const select = screen.getByLabelText('Model for Code');
    await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(4));

    const labels = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(labels[0]).toBe('Auto (routing rules)');
    expect(labels[1]).toContain('Claude Sonnet 4'); // 97% generation ranks first
    expect(labels[1]).toContain('no API key');
    expect(select).toHaveValue('gpt-4o-mini');

    fireEvent.change(select, { target: { value: '' } });
    await waitFor(() => expect(stages.update).toHaveBeenCalledWith('s2', { model_preference: null }));
    expect(onUpdate).toHaveBeenCalled();
  });
});
