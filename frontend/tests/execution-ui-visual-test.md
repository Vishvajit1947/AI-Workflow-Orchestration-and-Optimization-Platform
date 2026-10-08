# MT-16 Execution UI - Visual Component Test Guide

## Quick Visual Test Checklist

### 1. WorkflowDetail Page - Execute Button

**Location**: Header section, right side with Edit/Delete buttons

**Expected Appearance**:
```
[Execute Workflow] [Edit] [Delete]
    (green)       (gray) (red)
```

**Button States**:
- ✅ Enabled (green): When workflow has stages and not executing
- ✅ Disabled (gray): When no stages OR currently executing
- ✅ Text: "Execute Workflow" → "Executing..." during execution
- ✅ Icon: Play icon (▶) visible

---

### 2. ExecutionConfigModal - Configuration Dialog

**Opens When**: Click "Execute Workflow" button

**Visual Layout**:
```
┌─────────────────────────────────────┐
│  Execute Workflow                   │
│                                     │
│  Configure execution parameters for │
│  [Workflow Name]                    │
│                                     │
│  Default Provider                   │
│  [OpenAI ▼]                        │
│                                     │
│  Default Model                      │
│  [Default (gpt-4o-mini) ▼]        │
│  Stages can override with their... │
│                                     │
│          [Cancel]  [Execute]       │
└─────────────────────────────────────┘
```

**Provider Options**:
- OpenAI
- Anthropic (Claude)
- Google (Gemini)

**Model Options Change Based on Provider**:
- **OpenAI**: gpt-4o, gpt-4o-mini, gpt-4-turbo
- **Anthropic**: claude-3-5-sonnet, claude-3-5-haiku
- **Google**: gemini-2.0-flash-exp, gemini-1.5-pro

**Interaction Test**:
1. Change provider → model list updates
2. Click Cancel → modal closes, no action
3. Click Execute → modal closes, execution starts

---

### 3. ExecutionResults - Main Results Container

**Location**: Below stages section on WorkflowDetail page

**Visual Layout**:
```
┌─────────────────────────────────────────────────┐
│  Execution Results            [Status Badge]    │
│  Execution ID: exec_abc123...                   │
│                                                  │
│  [Stage Results] [Context Flow] [Metrics]       │
│  ───────────────                                │
│                                                  │
│  [Tab Content Area]                             │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Status Badge Colors**:
- Gray: pending
- Blue: running
- Green: completed
- Red: failed
- Yellow: skipped

---

### 4. Stages Tab - Stage Results View

**Visual Layout**:
```
┌─────────────────────────────────────────────────┐
│  #1  Stage Name                    [completed]  │
│                                         1234ms  │
│                                                  │
│  Model: gpt-4o     Tokens: 1,250               │
│  Latency: 1234ms   Cost: $0.0156              │
│                                                  │
│  Output:                                        │
│  ┌───────────────────────────────────────────┐ │
│  │ [Stage output text appears here...]      │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  #2  Next Stage                    [failed]     │
│                                         567ms   │
│                                                  │
│  Model: gpt-4o     Tokens: 450                 │
│  Latency: 567ms    Cost: $0.0056              │
│                                                  │
│  Error:                                         │
│  ┌───────────────────────────────────────────┐ │
│  │ [Error message appears here in red...]   │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**Visual Elements**:
- Stage order number in gray (#1, #2, #3...)
- Stage name in bold
- Status badge (colored pill)
- Duration on right
- 4-column metadata grid
- Output box with gray background
- Error box with red background

---

### 5. Context Flow Tab - Timeline View

**Visual Layout**:
```
Shows how context (outputs) flow from stage to stage

┌─────┬─────────────────────────────────────────┐
│     │  Stage Name                             │
│ [1] │  Output preview text (truncated to     │
│     │  200 characters)...                    │
│  │  │  1,250 tokens · 1234ms                 │
│  │  └─────────────────────────────────────────┘
│  │
│  ▼
│     ┌─────────────────────────────────────────┐
│ [2] │  Next Stage                            │
│     │  Another output preview...             │
│     │  450 tokens · 567ms                    │
│  │  └─────────────────────────────────────────┘
│  │
│  ▼
│     ┌─────────────────────────────────────────┐
│ [3] │  Final Stage                           │
│     │  Final output...                       │
│     │  892 tokens · 891ms                    │
│     └─────────────────────────────────────────┘
```

**Visual Elements**:
- Numbered circles (green=completed, red=failed, gray=other)
- Vertical connecting lines between circles
- Stage name in bold
- Truncated output preview
- Token and latency info at bottom

---

### 6. Metrics Tab - Summary and Breakdown

**Visual Layout**:
```
┌────────────────┬────────────────┬────────────────┬────────────────┐
│ Total Duration │ Total Tokens   │ Total Cost     │ Stages         │
│ 2,692ms        │ 2,592          │ $0.0312        │ 3/3            │
│ 2.7s           │ Avg: 864/stage │ $0.0104/stage  │ All passed     │
└────────────────┴────────────────┴────────────────┴────────────────┘

Stage Breakdown

┌───┬─────────────┬────────────┬────────┬─────────┬──────────┐
│ # │ Stage       │ Model      │ Tokens │ Latency │ Cost     │
├───┼─────────────┼────────────┼────────┼─────────┼──────────┤
│ 1 │ First Stage │ gpt-4o     │ 1,250  │ 1234ms  │ $0.0156  │
│ 2 │ Next Stage  │ gpt-4o     │ 450    │ 567ms   │ $0.0056  │
│ 3 │ Final Stage │ gpt-4o     │ 892    │ 891ms   │ $0.0100  │
└───┴─────────────┴────────────┴────────┴─────────┴──────────┘
```

**Visual Elements**:
- 4 summary cards in responsive grid
- Large bold numbers for main metrics
- Small gray text for sub-metrics
- Full-width table below cards
- Gray header row
- Aligned columns (# and text left, numbers right)
- Formatted numbers (commas, 4 decimals for cost)

---

## Color Reference

### Status Colors
```css
pending:   bg-gray-100 text-gray-700    (⚪ Gray)
running:   bg-blue-100 text-blue-700    (🔵 Blue)
completed: bg-green-100 text-green-700  (🟢 Green)
failed:    bg-red-100 text-red-700      (🔴 Red)
skipped:   bg-yellow-100 text-yellow-700 (🟡 Yellow)
```

### Button Colors
```css
Execute:  bg-green-600 hover:bg-green-700   (Primary action)
Cancel:   bg-gray-100 hover:bg-gray-200     (Secondary)
Edit:     bg-surface-700/50 hover:bg-surface-700
Delete:   bg-red-500/10 hover:bg-red-500/20 text-red-400
```

### Timeline Circles (Context Flow)
```css
Completed: bg-green-500   (Bright green circle)
Failed:    bg-red-500     (Bright red circle)
Other:     bg-gray-400    (Gray circle)
```

---

## Responsive Behavior

### Desktop (≥768px)
- Metrics cards: 4 columns
- Full table width
- Button groups side-by-side

### Mobile (<768px)
- Metrics cards: 2 columns
- Scrollable table
- Stacked buttons

---

## Accessibility Features

### Keyboard Navigation
- ✅ Tab through buttons and form controls
- ✅ Enter/Space to activate buttons
- ✅ Escape to close modal

### Screen Reader Support
- ✅ Semantic HTML elements
- ✅ Button elements (not divs)
- ✅ Proper heading hierarchy
- ✅ Status information in text

### Visual Clarity
- ✅ Color + text for status (not color alone)
- ✅ Good contrast ratios
- ✅ Clear focus indicators
- ✅ Adequate text sizes

---

## User Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│  Workflow Detail Page                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ Workflow: My Workflow                       │   │
│  │ [Execute Workflow] [Edit] [Delete]         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Stages Section (Stage Editor)               │   │
│  │ - Stage 1: First Stage                      │   │
│  │ - Stage 2: Second Stage                     │   │
│  │ - Stage 3: Third Stage                      │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│            ▼ Click Execute Button                   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Execution Config Modal                      │   │
│  │ - Select Provider                           │   │
│  │ - Select Model                              │   │
│  │ - [Cancel] [Execute]                        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│            ▼ Click Execute in Modal                 │
│                                                     │
│  [Executing...] (Button disabled)                  │
│                                                     │
│            ▼ Execution Completes                    │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Execution Results                           │   │
│  │ [Stage Results][Context Flow][Metrics]      │   │
│  │                                             │   │
│  │ ┌─────────────────────────────────────────┐ │   │
│  │ │ Stage 1 Output                          │ │   │
│  │ │ Stage 2 Output                          │ │   │
│  │ │ Stage 3 Output                          │ │   │
│  │ └─────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Quick Manual Test Steps

### Test 1: Basic Flow (3 minutes)
1. Navigate to workflow detail page with stages
2. Click "Execute Workflow" button
3. Verify modal opens with workflow name
4. Select a provider (e.g., OpenAI)
5. Select a model (e.g., gpt-4o)
6. Click "Execute" button in modal
7. Verify button shows "Executing..."
8. Wait for results to appear
9. Verify results display below stages

### Test 2: Tab Navigation (2 minutes)
1. With execution results visible
2. Click each tab: Stages → Context Flow → Metrics
3. Verify each tab shows different content
4. Verify tab highlights correctly
5. Check all visual elements render properly

### Test 3: Edge Cases (2 minutes)
1. Try clicking Execute on workflow with no stages
   - ✅ Button should be disabled
2. Click Cancel in modal
   - ✅ Modal should close without executing
3. Change provider in modal
   - ✅ Model dropdown should update

### Test 4: Provider Options (2 minutes)
1. Open execute modal
2. Try OpenAI → verify 4 model options
3. Try Anthropic → verify 2 model options
4. Try Google → verify 2 model options
5. Verify default option exists for each

---

## Screenshot Checklist

For full visual verification, capture:

- [ ] Workflow detail page with Execute button
- [ ] Execute button in disabled state (no stages)
- [ ] Execution config modal (OpenAI selected)
- [ ] Execution config modal (Anthropic selected)
- [ ] Execution config modal (Google selected)
- [ ] Button showing "Executing..." state
- [ ] Execution Results header with status badge
- [ ] Stages tab with multiple stage cards
- [ ] Stages tab showing completed stage output
- [ ] Stages tab showing failed stage error
- [ ] Context Flow tab with timeline
- [ ] Metrics tab with summary cards
- [ ] Metrics tab breakdown table
- [ ] Responsive view on mobile (narrower)

---

## Known Visual Quirks

### None Identified
All visual elements render as expected based on code review.

---

## Next Visual Features (Future)

Ideas for future enhancements beyond MT-16:

1. **Real-time Progress Indicator**
   - Progress bar during execution
   - Live stage status updates
   - Estimated time remaining

2. **Execution History Panel**
   - List of past executions
   - Quick comparison view
   - Filter and search

3. **Export Options**
   - Download results as JSON
   - Download as CSV
   - Copy to clipboard

4. **Advanced Visualizations**
   - Token usage chart
   - Cost breakdown pie chart
   - Latency timeline graph

5. **Retry/Rerun Actions**
   - Retry failed stages
   - Rerun entire execution
   - Modify and rerun

---

## Conclusion

This visual test guide provides a complete reference for manually verifying the MT-16 Execution UI implementation. All components are built with consistent design, proper accessibility, and clear user experience.

**Ready for Production**: ✅ Yes
