---
name: plan-feature
description: Based on the current conversation context, draft a Notion task, then add it to a Notion project once approved.
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
- DO NOT add any description or acceptance criteria for unit/e2e tests

### 3. Output

Print the drafted task as a fenced code block so the user can review it.

### 4. Ask for the Project Link

After the task, ask the user to review it and share the link to the Notion project it belongs to.
- Do not create anything in Notion until the user approves the task and provides the project link
- If the user asks for changes, update the draft, print it again and wait for approval

### 5. Add the Task to Notion

Once the task is approved and the project link is provided:
- Fetch the project page, then fetch its parent Projects data source; the `Tasks` relation property's `dataSourceUrl` is the Tasks data source (`collection://...`). Fetch it to confirm the property names
- Create the page in the Tasks data source with:
  - `Task`: the task title
  - `Status`: `Not started`
  - `Project`: the project page URL
  - Icon: `icons/clipping_lightgray`
  - Content: the `## Description` and `## Acceptance criteria` sections (no `Title:` line)
- Reply with a link to the created card
