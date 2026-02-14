---
name: implement-feature
description: Implement a feature for the lab or processor package based on a structured task with acceptance criteria. Use when the user provides a feature task with a package name, title, and acceptance criteria, or asks to implement a feature.
---

# Implement Feature

Implement a feature based on a structured task prompt. Code only - no tests.

## Task Format

The user provides a task in this format:

```
<Package>: <Task title>
<Task description:optional>
## Acceptance Criteria
- <criterion 1>
- <criterion 2>
- ...
```

The package prefix determines the target:
- **Lab** → `app/lab/lab/` (bird detection lab GUI and tooling)
- **Processor** → `app/processor/processor/` (HLS stream processing and bird detection)

## Workflow

### 1. Understand the Task

- Parse the package name, task title, and acceptance criteria
- Read CLAUDE.md and relevant agent_docs/ files for project context
- Explore existing code in the target package to understand current structure

### 2. Plan Changes

Before writing code:
- Identify which existing files need modification
- Determine if new files are needed (prefer editing existing files)
- Understand how the change fits into the existing architecture
- Map each acceptance criterion to specific code changes

### 3. Implement

- Make changes to satisfy each acceptance criterion
- Follow existing code style and patterns in the package
- Prefer modifying existing files over creating new ones
- Keep changes minimal and focused on the task

### 4. Do NOT

- **Do NOT write tests** - tests are handled separately
- **Do NOT run format/check/test commands** - verification is a separate step
- **Do NOT modify test files**
- Do NOT change unrelated code

## Package Reference

### Lab Package (`app/lab/`)

Bird detection lab - GUI tool for managing recordings, syncing from remote, converting HLS to images, and annotating bird detections.

Key files:
- `lab/gui.py` - Tkinter GUI (main application)
- `lab/sync.py` - Remote sync via SFTP
- `lab/converter.py` - HLS to PNG conversion
- `lab/utils.py` - Image processing utilities
- `lab/constants.py` - Paths and configuration
- `lab/exception.py` - Custom exceptions

### Processor Package (`app/processor/`)

HLS stream processor - monitors camera feed, detects birds, and manages annotations.

Key files:
- `processor/hls_watchtower.py` - HLS playlist monitoring
- `processor/hls_segment_processor.py` - Segment processing pipeline
- `processor/bird_detector.py` - YOLOv8 bird detection
- `processor/bird_annotator.py` - Detection annotations
- `processor/stream_archiver.py` - Stream archiving
- `processor/utils.py` - Shared utilities
- `processor/constants.py` - Paths and configuration
- `processor/types.py` - Type definitions

### Additional Context

For deeper understanding, read:
- `agent_docs/processor_package.md` - Processor package details
- `agent_docs/web_server.md` - Web server setup
- `agent_docs/running_tests.md` - Test infrastructure

## Output

After implementation, summarize:
1. Which files were modified/created
2. How each acceptance criterion was addressed
3. Any design decisions or trade-offs made
