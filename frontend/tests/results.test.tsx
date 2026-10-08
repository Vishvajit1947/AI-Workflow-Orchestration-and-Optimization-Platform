/**
 * Stage result presentation: header/status, metric grid, routing/cache panels,
 * and safe Markdown rendering of LLM output.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import { StageResult } from '../src/components/results/StageResult';
import { MarkdownRenderer, buildOutline } from '../src/components/results/MarkdownRenderer';
import { formatModelName, formatProvider, parseRoutingReason } from '../src/lib/resultFormat';
import type { StageExecutionDetail } from '../src/types/execution';

const stage = (overrides: Partial<StageExecutionDetail> = {}): StageExecutionDetail => ({
  id: 'rec-1', stage_id: 's1', stage_name: 'Data Cleaning', stage_order: 1,
  model_used: 'qwen/qwen3.8-27b', provider: 'groq', input_tokens: 1200, output_tokens: 4437,
  total_tokens: 5637, latency_ms: 6659, estimated_cost: '0.001400', status: 'completed',
  result: 'Done.', error_message: null, started_at: null, completed_at: null, duration_ms: 7156,
  cache_hit: false, cache_similarity: null, tokens_saved: null, cost_saved: null,
  was_routed: true, routing_reason: 'Routing: balanced priority for analysis, score=0.87, 1 candidate(s)',
  ...overrides,
});

describe('display helpers', () => {
  it('formats model ids and providers without losing unknown ids', () => {
    expect(formatModelName('qwen/qwen3.8-27b')).toBe('Qwen 3.8 27B');
    expect(formatModelName('openai/gpt-oss-20b')).toBe('GPT-OSS 20B');
    expect(formatModelName('gemini-3.8-flash')).toBe('Gemini 3.8 Flash');
    expect(formatModelName('mistral-7b-instruct')).toBe('Mistral 7B Instruct');
    expect(formatModelName(null)).toBe('—');
    expect(formatProvider('groq')).toBe('Groq');
  });

  it('parses scored routing reasons and keeps other reasons verbatim', () => {
    expect(parseRoutingReason('Routing: balanced priority for analysis, score=0.87, 1 candidate(s)')).toEqual({
      strategy: 'Balanced', task: 'Analysis', score: '0.87', candidates: 1,
    });
    expect(parseRoutingReason('User override: gpt-4o', { was_user_override: true })).toEqual({
      strategy: 'Override', detail: 'User override: gpt-4o',
    });
    expect(parseRoutingReason(null)).toBeNull();
  });
});

describe('StageResult', () => {
  it('shows stage name, number and status as text, not colour alone', () => {
    render(<StageResult stage={stage()} />);
    expect(screen.getByRole('heading', { name: 'Data Cleaning' })).toBeInTheDocument();
    expect(screen.getByText('Stage 2')).toBeInTheDocument();
    expect(screen.getByTestId('stage-status')).toHaveTextContent('✓Completed');
  });

  it('renders metrics in a grid with readable model, provider, latency, cost and tokens', () => {
    render(<StageResult stage={stage()} />);
    const metrics = within(screen.getByTestId('stage-metrics'));
    expect(metrics.getByText('Qwen 3.8 27B')).toBeInTheDocument();
    expect(metrics.getByText('via Groq')).toBeInTheDocument();
    expect(metrics.getByText('6.66s')).toBeInTheDocument();
    expect(metrics.getByText('7.16s')).toBeInTheDocument(); // duration
    expect(metrics.getByText('$0.0014')).toBeInTheDocument();
    expect(metrics.getByText('5,637')).toBeInTheDocument();
    expect(metrics.getByText('1,200 in · 4,437 out')).toBeInTheDocument();
    expect(metrics.getByText('Balanced')).toBeInTheDocument();
    expect(metrics.getByText('○ MISS')).toBeInTheDocument();
  });

  it('breaks the routing decision into fields and keeps the raw model id', () => {
    render(<StageResult stage={stage()} />);
    const panel = within(screen.getByTestId('routing-decision'));
    expect(panel.getByText('Analysis')).toBeInTheDocument();
    expect(panel.getByText('0.87')).toBeInTheDocument();
    expect(panel.getByText('1')).toBeInTheDocument();
    expect(panel.getByText('qwen/qwen3.8-27b')).toBeInTheDocument();
  });

  it('shows failed stages with an error section and status text', () => {
    render(<StageResult stage={stage({ status: 'failed', result: null, error_message: 'Rate limit exceeded' })} />);
    expect(screen.getByTestId('stage-status')).toHaveTextContent('Failed');
    expect(screen.getByText('Rate limit exceeded')).toBeInTheDocument();
    expect(screen.queryByTestId('cache-status')).not.toBeInTheDocument();
  });

  it('collapses and expands a stage', () => {
    render(<StageResult stage={stage({ result: 'Visible output' })} />);
    fireEvent.click(screen.getByRole('button', { name: 'Collapse Data Cleaning' }));
    expect(screen.queryByText('Visible output')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Expand Data Cleaning' }));
    expect(screen.getByText('Visible output')).toBeInTheDocument();
  });

  it('adds section navigation to long outputs only', () => {
    const sections = ['Overview', 'Strategy', 'Architecture', 'Validation']
      .map((h) => `## ${h}\n\n${'Lorem ipsum dolor sit amet. '.repeat(20)}`)
      .join('\n\n');
    const { rerender } = render(<StageResult stage={stage({ result: sections })} />);
    const nav = within(screen.getByRole('navigation', { name: 'Output sections' }));
    expect(nav.getAllByRole('button').map((b) => b.textContent)).toEqual(['Overview', 'Strategy', 'Architecture', 'Validation']);

    rerender(<StageResult stage={stage({ result: '## Short\n\nOne paragraph.' })} />);
    expect(screen.queryByRole('navigation', { name: 'Output sections' })).not.toBeInTheDocument();
  });
});

describe('MarkdownRenderer', () => {
  const md = [
    '# Title',
    '## Section',
    '### Sub',
    'Some **bold** and *italic* text with `inline_code`.',
    '',
    '- one',
    '- two',
    '',
    '1. first',
    '2. second',
    '',
    '> quoted',
    '',
    '| Principle | Count |',
    '|---|---|',
    '| Standardization | 12 |',
    '| Normalization | 7 |',
    '',
    '```python',
    'from pyspark.sql import SparkSession',
    'spark = SparkSession.builder.getOrCreate()',
    '```',
  ].join('\n');

  it('renders headings, lists, quotes, tables and code', () => {
    const { container } = render(<MarkdownRenderer content={md} idPrefix="t" />);
    expect(screen.getByRole('heading', { level: 1, name: 'Title' })).toHaveAttribute('id', 't-title');
    expect(screen.getByRole('heading', { level: 2, name: 'Section' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Sub' })).toBeInTheDocument();
    expect(screen.getByText('bold').tagName).toBe('STRONG');
    expect(screen.getByText('italic').tagName).toBe('EM');
    expect(screen.getByText('inline_code').tagName).toBe('CODE');
    expect(container.querySelectorAll('ul > li')).toHaveLength(2);
    expect(container.querySelectorAll('ol > li')).toHaveLength(2);
    expect(container.querySelector('blockquote')).toHaveTextContent('quoted');

    const table = screen.getByRole('table');
    expect(table.parentElement).toHaveClass('overflow-x-auto');
    expect(within(table).getByRole('columnheader', { name: 'Principle' })).toBeInTheDocument();
    // all-numeric column is right-aligned; text column is not
    expect(within(table).getByRole('cell', { name: '12' })).toHaveStyle({ textAlign: 'right' });
    expect(within(table).getByRole('cell', { name: 'Standardization' })).not.toHaveStyle({ textAlign: 'right' });
  });

  it('labels and highlights code blocks without changing the code', () => {
    const { container } = render(<MarkdownRenderer content={md} idPrefix="t" />);
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy' })).toBeInTheDocument();
    const code = container.querySelector('pre code')!;
    expect(code).toHaveClass('hljs');
    expect(code.querySelector('.hljs-keyword')).not.toBeNull();
    expect(code.textContent).toBe('from pyspark.sql import SparkSession\nspark = SparkSession.builder.getOrCreate()\n');
  });

  it('collapses very long code blocks to a preview with an expand control', () => {
    const longCode = '```sql\n' + Array.from({ length: 120 }, (_, i) => `SELECT ${i};`).join('\n') + '\n```';
    render(<MarkdownRenderer content={longCode} idPrefix="t" />);
    const toggle = screen.getByRole('button', { name: /SQL/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Show all 120 lines' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });

  it('does not render raw HTML or unsafe links', () => {
    const { container } = render(
      <MarkdownRenderer content={'<script>alert(1)</script><img src=x onerror=alert(1)>\n\n[click](javascript:alert(1)) [ok](https://example.com)'} idPrefix="t" />,
    );
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('click').getAttribute('href') ?? '').not.toMatch(/javascript/i);
    const safe = screen.getByText('ok');
    expect(safe).toHaveAttribute('href', 'https://example.com');
    expect(safe).toHaveAttribute('rel', 'noopener noreferrer nofollow');
  });

  it('builds an outline whose ids match the rendered headings, ignoring code fences', () => {
    const text = '## A\n\n```\n## not a heading\n```\n\n## B\n\n## A\n';
    expect(buildOutline(text, 'p').map((e) => e.id)).toEqual(['p-a', 'p-b', 'p-a-2']);
    render(<MarkdownRenderer content={text} idPrefix="p" />);
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.id)).toEqual(['p-a', 'p-b', 'p-a-2']);
  });
});
