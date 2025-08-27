import cv2
import time
import sys
from flask import Flask, Response
import threading
from ultralytics import YOLO

BIRD_COCO_CLASS_ID = 14
DETECT_EVERY_FRAMES = 12
BIRD_STATUS_DURATION_FRAMES = 5 * 24  # 5 seconds at 24fps detection rate
IMAGE_SIZE_FOR_DETECTION = 420

app = Flask(__name__)

class BirdDetector:
    def __init__(self):
        self.model = YOLO('yolov8n.pt')
        self.model.fuse()
        self.bird_status_remaining = 0  # Frames remaining for "Birds detected" status

    def __has_birds(self, frame):
        results = self.model(
            frame,
            classes=[BIRD_COCO_CLASS_ID],
            imgsz=IMAGE_SIZE_FOR_DETECTION,
            verbose=False
        )
        return results[0].boxes is not None and len(results[0].boxes) > 0

    def __add_status_text(self, frame):
        """Add 'Birds detected' text to top-right corner if status is active"""
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

            # Decrement status timer
            self.bird_status_remaining -= 1

        return frame

    def detect(self, frame, detect):
        if detect and self.__has_birds(frame):
            self.bird_status_remaining = BIRD_STATUS_DURATION_FRAMES
        return self.__add_status_text(frame)

class FrameGenerator:
    INPUT_STREAM = "rtmp://rtmp-server:1935/stream/sparrow_cam"
    MAX_RETRIES = 30

    def __init__(self, bird_detector):
        self.bird_detector = bird_detector
        self.cap = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.frame_idx = 0

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

                frame = self.bird_detector.detect(
                    frame,
                    detect=self.frame_idx % DETECT_EVERY_FRAMES == 0,
                )

                with self.frame_lock:
                    self.current_frame = frame.copy()
                self.frame_idx += 1
        except Exception as e:
            print(f"Error in capture_frames: {e}")
        finally:
            if self.cap is not None:
                self.cap.release()
                print("Released video capture")

    def get_frame(self):
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def stop(self):
        self.running = False

bird_detector = BirdDetector()
frame_generator = FrameGenerator(bird_detector)

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
