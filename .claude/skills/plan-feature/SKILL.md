---
name: plan-feature
description: Based on the current conversation context, output a Notion task ready to copy.
---

# Plan Feature

Generate a Notion task from the current analysis or conversation context.

## Workflow

### 1. Understand the Context

- Review the current conversation to identify what feature, fix, or improvement is being discussed
- Identify the target package(s) by checking `## Package Context Files` in `CLAUDE.md`
  - **BLOCKING**: If no package can be determined, ask the user which package this task belongs to

### 2. Draft the Task

Produce output in this exact format, ready to paste into a Notion task:

```
Title: <Package>: <Task title>

## Description

<One short paragraph explaining the problem or motivation. Omit if not needed.>

## Acceptance criteria

- <Criterion 1>
- <Criterion 2>
- ...
```

Rules:
- Title format: `Package: Short imperative title` (e.g. `Web: Add pagination to archive view`)
- For multiple packages: `Package1|Package2: Title`
- Description is optional — include only when the motivation isn't obvious from the title and criteria
- Each acceptance criterion must be a single, testable, concrete statement
- No vague criteria like "it works" or "improve performance" — be specific

### 3. Output

Print the drafted task as a fenced code block so the user can copy it directly.
