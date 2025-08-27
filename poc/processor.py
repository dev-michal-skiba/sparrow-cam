import cv2
import time
import sys
from flask import Flask, Response
import threading
from ultralytics import YOLO
import os
from datetime import datetime

BIRD_COCO_CLASS_ID = 14
DETECT_EVERY_FRAMES = 12
BIRD_STATUS_DURATION_FRAMES = 5 * 24  # 5 seconds at 24fps detection rate
IMAGE_SIZE_FOR_DETECTION = 480

app = Flask(__name__)

class BirdDetector:
    def __init__(self):
        self.model = YOLO('yolov8n.pt')
        self.model.fuse()

    def detect(self, frame) -> bool:
        results = self.model(
            frame,
            classes=[BIRD_COCO_CLASS_ID],
            imgsz=IMAGE_SIZE_FOR_DETECTION,
            verbose=False
        )
        return results[0].boxes is not None and len(results[0].boxes) > 0


class LocalStorage:
    SAVE_DIR = "/app/recordings"

    def __init__(self):
        self.frame_buffers = {}  # Dict with timestamp as key, list of frames as value
        self.recording = False
        self.current_recording_timestamp = None
        self.buffer_lock = threading.Lock()  # To protect the dictionary
        
        # Create recordings directory if it doesn't exist
        os.makedirs(self.SAVE_DIR, exist_ok=True)
        
        # Video settings
        self.fps = 24.0
        self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    def push(self, frame, recording):
        with self.buffer_lock:
            if recording and not self.recording:
                # Start recording
                self.recording = True
                self.current_recording_timestamp = datetime.utcnow()
                self.frame_buffers[self.current_recording_timestamp] = [frame.copy()]
                print(f"Started recording at {self.current_recording_timestamp}")
                
            elif recording and self.recording:
                # Continue recording - add frame to current buffer
                if self.current_recording_timestamp in self.frame_buffers:
                    self.frame_buffers[self.current_recording_timestamp].append(frame.copy())
                
            elif not recording and self.recording:
                # Stop recording - save video in separate thread
                self.recording = False
                timestamp_to_save = self.current_recording_timestamp
                frame_count = len(self.frame_buffers.get(timestamp_to_save, []))
                
                # Start save thread - it will clean up the buffer entry when done
                save_thread = threading.Thread(
                    target=self._save_video_threaded,
                    args=(timestamp_to_save,)
                )
                save_thread.daemon = True
                save_thread.start()
                
                print(f"Stopped recording. Saving {frame_count} frames in background...")
                self.current_recording_timestamp = None
    
    def _save_video_threaded(self, timestamp):
        """Save video in a separate thread to avoid blocking frame processing"""
        with self.buffer_lock:
            frames = self.frame_buffers.get(timestamp)
            if not frames:
                return
                
        # Generate filename with UTC timestamp of first frame
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}.mp4"
        filepath = os.path.join(self.SAVE_DIR, filename)
        
        # Get frame dimensions from first frame
        height, width, channels = frames[0].shape
        frame_count = len(frames)
        
        # Create video writer
        video_writer = cv2.VideoWriter(filepath, self.fourcc, self.fps, (width, height))
        
        try:
            # Write all frames to video
            for frame in frames:
                video_writer.write(frame)
            print(f"Successfully saved video: {filepath} ({frame_count} frames)")
        except Exception as e:
            print(f"Error saving video {filepath}: {e}")
        finally:
            video_writer.release()
            # Clean up the buffer entry after saving
            with self.buffer_lock:
                if timestamp in self.frame_buffers:
                    del self.frame_buffers[timestamp]
                    print(f"Cleaned up buffer for timestamp {timestamp_str}")


class FrameGenerator:
    INPUT_STREAM = "rtmp://rtmp-server:1935/stream/sparrow_cam"
    MAX_RETRIES = 30

    def __init__(self, bird_detector, local_storage):
        self.bird_detector = bird_detector
        self.local_storage = local_storage
        self.cap = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.frame_idx = 0
        self.bird_status_remaining = 0

    def connect_to_stream(self):
        retries = 0
        print(f"Attempting to connect to {self.INPUT_STREAM}")
        while retries < self.MAX_RETRIES:
            try:
                self.cap = cv2.VideoCapture(self.INPUT_STREAM)
                if self.cap.isOpened():
                    print("Successfully connected to stream")
                    return True
            except Exception as e:
                print(f"Attempt {retries + 1}: Failed to connect: {e}")
            retries += 1
            time.sleep(1)
        print("Failed to open stream after maximum retries")
        return False

    def capture_frames(self):
        if not self.connect_to_stream():
            return
        self.running = True
        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    print("Failed to read frame, attempting to reconnect...")
                    if not self.connect_to_stream():
                        break
                    continue

                bird_detected = False
                if self.frame_idx % DETECT_EVERY_FRAMES == 0:
                    bird_detected = self.bird_detector.detect(frame)
                frame = self.add_status_overlay(frame, bird_detected)
                self.local_storage.push(frame, recording=self.bird_status_remaining > 0)

                with self.frame_lock:
                    self.current_frame = frame.copy()
                self.frame_idx += 1
        except Exception as e:
            print(f"Error in capture_frames: {e}")
        finally:
            if self.cap is not None:
                self.cap.release()
                print("Released video capture")

    def add_status_overlay(self, frame, bird_detected):
        if bird_detected:
            self.bird_status_remaining = BIRD_STATUS_DURATION_FRAMES
        elif self.bird_status_remaining > 0:
            self.bird_status_remaining -= 1

        if self.bird_status_remaining > 0:
            # Get frame dimensions
            h, w = frame.shape[:2]
            # Text properties
            text = "Birds detected"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            color = (0, 255, 0)  # Green
            thickness = 2
            # Get text size to position it in top-right
            (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
            # Position in top-right with some padding
            x = w - text_w - 10
            y = text_h + 10
            # Add text
            cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

        return frame

    def get_frame(self):
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def stop(self):
        self.running = False

bird_detector = BirdDetector()
local_storage = LocalStorage()
frame_generator = FrameGenerator(bird_detector, local_storage)

def generate_mjpeg():
    while True:
        frame = frame_generator.get_frame()
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)


@app.route('/mjpeg')
def mjpeg_stream():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')


def main():
    # Start frame capture in a separate thread
    capture_thread = threading.Thread(target=frame_generator.capture_frames)
    capture_thread.daemon = True
    capture_thread.start()

    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        frame_generator.stop()


if __name__ == "__main__":
    main()
