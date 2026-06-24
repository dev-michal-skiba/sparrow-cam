# Stream

Captures a USB webcam feed and produces an HLS stream for the web server to serve.

## Key Parameters

- Resolution: 960×540, 8 FPS
- Segment duration: 1 second
- Rolling window: 60 segments retained at any time

## Crop Configuration

Crop is configured via `app/stream/stream.conf`, a bash-sourceable key=value file:

Values are percentages (0–100) of the input frame. The script converts them to an ffmpeg `crop` expression at startup and on every reload.

Invalid values (RIGHT ≤ LEFT, BOTTOM ≤ TOP, or any value outside 0–100) are logged and the crop is skipped — the full frame is streamed instead.

When `stream.conf` is modified on disk, the script detects the change (via mtime polling every 1 second), kills ffmpeg, and immediately restarts with the new crop. The retry counter is reset on a config-driven restart.

## Constraint: FPS, Keyframe Interval, and Segment Duration

Segments begin on keyframes. The FPS, keyframe interval, and segment duration are
tightly coupled — all three must be consistent with each other. Changing any one
value requires updating the other two to match.

## Retry Backoff

When the ffmpeg process exits for any reason, the stream restarts after a delay:

- 1st retry: 2 seconds
- 2nd retry: 5 seconds
- 3rd and subsequent retries: 10 seconds
