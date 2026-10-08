/**
 * Frontend integration tests for execution UI.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ExecutionConfigModal } from '../src/components/ExecutionConfigModal';
import { ExecutionResults } from '../src/components/ExecutionResults';
import type { ExecutionDetailResponse } from '../src/types/execution';

describe('ExecutionConfigModal', () => {
  const mockOnExecute = vi.fn();
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnExecute.mockClear();
    mockOnClose.mockClear();
  });

  it('renders when open', () => {
    render(
      <ExecutionConfigModal
        isOpen={true}
        onClose={mockOnClose}
        onExecute={mockOnExecute}
        workflowName="Test Workflow"
      />
    );

    expect(screen.getByText('Execute Workflow')).toBeInTheDocument();
    expect(screen.getByText('Test Workflow')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <ExecutionConfigModal
        isOpen={false}
        onClose={mockOnClose}
        onExecute={mockOnExecute}
        workflowName="Test Workflow"
      />
    );

    expect(screen.queryByText('Execute Workflow')).not.toBeInTheDocument();
  });

  it('displays provider options', () => {
    render(
      <ExecutionConfigModal
        isOpen={true}
        onClose={mockOnClose}
        onExecute={mockOnExecute}
        workflowName="Test Workflow"
      />
    );

    expect(screen.getByLabelText('Default Provider')).toBeInTheDocument();
    expect(screen.getByText('OpenAI')).toBeInTheDocument();
    expect(screen.getByText('Anthropic (Claude)')).toBeInTheDocument();
    expect(screen.getByText('Google (Gemini)')).toBeInTheDocument();
  });

  it('calls onExecute with selected config', async () => {
    render(
      <ExecutionConfigModal
        isOpen={true}
        onClose={mockOnClose}
        onExecute={mockOnExecute}
        workflowName="Test Workflow"
      />
    );

    // Select Anthropic provider
    const providerSelect = screen.getByLabelText('Default Provider');
    fireEvent.change(providerSelect, { target: { value: 'anthropic' } });

    // Click execute
    const executeButton = screen.getByRole('button', { name: /execute/i });
    fireEvent.click(executeButton);

    await waitFor(() => {
      expect(mockOnExecute).toHaveBeenCalledWith({
        default_provider: 'anthropic',
        default_model: null,
        use_cache: true,
        use_routing: true,
        routing_preferences: {},
        parallel: true
      });
    });
  });

  it('calls onClose when cancelled', () => {
    render(
      <ExecutionConfigModal
        isOpen={true}
        onClose={mockOnClose}
        onExecute={mockOnExecute}
        workflowName="Test Workflow"
      />
    );

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('updates model options when provider changes', () => {
    render(
      <ExecutionConfigModal
        isOpen={true}
        onClose={mockOnClose}
        onExecute={mockOnExecute}
        workflowName="Test Workflow"
      />
    );

    const providerSelect = screen.getByLabelText('Default Provider');
    
    // Change to Google (backend provider name "gemini")
    fireEvent.change(providerSelect, { target: { value: 'gemini' } });
    
    // Should see Gemini models
    expect(screen.getByText(/Gemini 2.0 Flash/)).toBeInTheDocument();
  });
});

describe('ExecutionResults', () => {
  const mockExecution: ExecutionDetailResponse = {
    summary: {
      execution_id: 'exec-123',
      workflow_id: 'wf-123',
      workflow_name: 'Test Workflow',
      status: 'completed',
      total_stages: 2,
      completed_stages: 2,
      failed_stages: 0,
      total_tokens: 300,
      total_cost: 0.0002,
      total_latency_ms: 1000,
      started_at: '2024-01-01T10:00:00Z',
      completed_at: '2024-01-01T10:00:01Z',
      duration_ms: 1000
    },
    stages: [
      {
        id: 'stage-1',
        stage_id: 's1',
        stage_name: 'Analysis',
        stage_order: 0,
        model_used: 'gpt-4o-mini',
        provider: 'openai',
        input_tokens: 100,
        output_tokens: 50,
        total_tokens: 150,
        latency_ms: 500,
        estimated_cost: 0.0001,
        status: 'completed',
        result: 'Analysis complete',
        error_message: null,
        started_at: '2024-01-01T10:00:00Z',
        completed_at: '2024-01-01T10:00:00.5Z',
        duration_ms: 500
      },
      {
        id: 'stage-2',
        stage_id: 's2',
        stage_name: 'Design',
        stage_order: 1,
        model_used: 'gpt-4o-mini',
        provider: 'openai',
        input_tokens: 100,
        output_tokens: 50,
        total_tokens: 150,
        latency_ms: 500,
        estimated_cost: 0.0001,
        status: 'completed',
        result: 'Design complete',
        error_message: null,
        started_at: '2024-01-01T10:00:00.5Z',
        completed_at: '2024-01-01T10:00:01Z',
        duration_ms: 500
      }
    ]
  };

  it('renders execution summary', () => {
    render(<ExecutionResults execution={mockExecution} />);

    expect(screen.getByText('Execution Results')).toBeInTheDocument();
    expect(screen.getByTestId('execution-status')).toHaveTextContent('completed');
    expect(screen.getByText(/exec-123/)).toBeInTheDocument();
  });

  it('renders all tabs', () => {
    render(<ExecutionResults execution={mockExecution} />);

    expect(screen.getByText('Stage Results')).toBeInTheDocument();
    expect(screen.getByText('Context Flow')).toBeInTheDocument();
    expect(screen.getByText('Metrics')).toBeInTheDocument();
  });

  it('shows stage details in Stages tab', () => {
    render(<ExecutionResults execution={mockExecution} />);

    expect(screen.getByText('Analysis')).toBeInTheDocument();
    expect(screen.getByText('Design')).toBeInTheDocument();
    expect(screen.getByText('Analysis complete')).toBeInTheDocument();
    expect(screen.getByText('Design complete')).toBeInTheDocument();
  });

  it('switches tabs correctly', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Initially on Stages tab
    expect(screen.getByText('Analysis complete')).toBeInTheDocument();

    // Click Context Flow tab
    const contextTab = screen.getByText('Context Flow');
    fireEvent.click(contextTab);

    // Should show context flow content
    expect(screen.getByText(/Shows how context/)).toBeInTheDocument();

    // Click Metrics tab
    const metricsTab = screen.getByText('Metrics');
    fireEvent.click(metricsTab);

    // Should show metrics
    expect(screen.getByText('Total Duration')).toBeInTheDocument();
    expect(screen.getByText('Total Tokens')).toBeInTheDocument();
  });

  it('displays stage metrics correctly', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Switch to metrics tab
    const metricsTab = screen.getByText('Metrics');
    fireEvent.click(metricsTab);

    // Check summary cards
    expect(screen.getByText('1,000ms')).toBeInTheDocument(); // Duration in ms
    expect(screen.getByText('1.0s')).toBeInTheDocument(); // Duration in seconds
    expect(screen.getByText('300')).toBeInTheDocument(); // Total tokens
    expect(screen.getByText('$0.0002')).toBeInTheDocument(); // Total cost
    expect(screen.getByText('2/2')).toBeInTheDocument(); // Stages completed
  });

  it('shows status badge with correct color', () => {
    render(<ExecutionResults execution={mockExecution} />);

    const statusBadge = screen.getByTestId('execution-status');
    expect(statusBadge).toHaveTextContent('completed');
    expect(statusBadge).toHaveClass('bg-primary-500/15');
    expect(statusBadge).toHaveClass('text-primary-400');
  });

  it('displays stage order numbers', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Look for stage numbering
    expect(screen.getByText('Stage 1')).toBeInTheDocument();
    expect(screen.getByText('Stage 2')).toBeInTheDocument();
  });

  it('shows model information for each stage', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Both stages use gpt-4o-mini: shown by display name, provider separately, raw id kept as tooltip
    const modelLabels = screen.getAllByText('GPT-4o Mini');
    expect(modelLabels).toHaveLength(2);
    expect(screen.getAllByText('via OpenAI')).toHaveLength(2);
    expect(modelLabels[0].closest('[title]')).toHaveAttribute('title', 'gpt-4o-mini');
  });

  it('renders failed execution correctly', () => {
    const failedExecution: ExecutionDetailResponse = {
      ...mockExecution,
      summary: {
        ...mockExecution.summary,
        status: 'failed',
        completed_stages: 1,
        failed_stages: 1
      },
      stages: [
        mockExecution.stages[0],
        {
          ...mockExecution.stages[1],
          status: 'failed',
          result: null,
          error_message: 'LLM API error'
        }
      ]
    };

    render(<ExecutionResults execution={failedExecution} />);

    const statusBadge = screen.getByTestId('execution-status');
    expect(statusBadge).toHaveTextContent('failed');
    expect(statusBadge).toHaveClass('bg-red-500/15');
    expect(statusBadge).toHaveClass('text-red-300');
    
    expect(screen.getByText('LLM API error')).toBeInTheDocument();
  });

  it('displays context flow timeline', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Click Context Flow tab
    const contextTab = screen.getByText('Context Flow');
    fireEvent.click(contextTab);

    // Should show both stages in timeline
    expect(screen.getByText('Analysis')).toBeInTheDocument();
    expect(screen.getByText('Design')).toBeInTheDocument();
  });

  it('shows token and cost breakdown in metrics', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Switch to metrics tab
    const metricsTab = screen.getByText('Metrics');
    fireEvent.click(metricsTab);

    // Check for breakdown table
    expect(screen.getByText('Stage')).toBeInTheDocument();
    expect(screen.getByText('Tokens')).toBeInTheDocument();
    expect(screen.getByText('Latency')).toBeInTheDocument();
    expect(screen.getByText('Cost')).toBeInTheDocument();
  });

  it('calculates average metrics correctly', () => {
    render(<ExecutionResults execution={mockExecution} />);

    // Switch to metrics tab
    const metricsTab = screen.getByText('Metrics');
    fireEvent.click(metricsTab);

    // Average tokens = 300 / 2 = 150
    expect(screen.getByText('Avg: 150/stage')).toBeInTheDocument();
    
    // Average cost = 0.0002 / 2 = 0.0001
    expect(screen.getByText('$0.0001/stage')).toBeInTheDocument();
  });
});
