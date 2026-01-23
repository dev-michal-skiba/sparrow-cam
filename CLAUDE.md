# Project Overview
SparrowCam is a local bird feeder observation system that monitors a camera feed, automatically detects birds via YOLOv8, and streams HLS video. The system runs entirely on a local network (typically on a Raspberry Pi) with no cloud dependency.
## Architecture
1. ffmpeg (started manually in tmux session) consumes USB camera feed and produces HLS segments with playlist
2. Each new HLS segment is processed by Python app which detects birds
3. Birds detections are annotated in the annotations file
4. Web server serves web page, HLS segments with playlist and annotations file
5. Web page plays the stream with information if bird was detected in currently displayed segment
## Additional Information Files
- How to run unit tests and end-to-end test: `agent_docs/running_tests.md`
- Processor package overview:  `agent_docs/processor_package.md`
- Web server overview: `agent_docs/web_server.md`