# Project Overview
SparrowCam is a local bird feeder observation system that monitors a camera feed, automatically detects birds via YOLOv8 fine tuned model, and streams HLS video. The system runs entirely on a local network on a Raspberry Pi with no cloud dependency.

## Architecture
1. ffmpeg (started manually in tmux session) consumes USB camera feed and produces HLS segments with playlist
2. Each new HLS segment is processed by Python app which detects birds
3. Birds detections are annotated in the annotations file
4. Web server serves web page, HLS segments with playlist and annotations file
5. Web page plays the stream with information if bird was detected in currently displayed segment

## Package Context Files
When working on a package, load the corresponding context file for architecture details:
- **Lab** → `agent_docs/lab.md`
- **Processor** → `agent_docs/processor.md`
- **Archive API** → `agent_docs/archive_api.md`
- **Web** → `agent_docs/web.md`
- **Infra** → `agent_docs/infra.md`
- **Stream** → `agent_docs/stream.md`
