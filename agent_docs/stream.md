# Stream

Captures a USB webcam feed and produces an HLS stream for the web server to serve.

## Key Parameters

- Resolution: 960×540, 8 FPS
- Segment duration: 1 second
- Rolling window: 60 segments retained at any time

## Constraint: FPS, Keyframe Interval, and Segment Duration

Segments begin on keyframes. The FPS, keyframe interval, and segment duration are
tightly coupled — all three must be consistent with each other. Changing any one
value requires updating the other two to match.

## Retry Backoff

When the ffmpeg process exits for any reason, the stream restarts after a delay:

- 1st retry: 10 seconds
- 2nd retry: 30 seconds
- 3rd and subsequent retries: 60 seconds
