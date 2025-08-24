import cv2
import time
import sys
from flask import Flask, Response
import threading

app = Flask(__name__)

def detect_and_frame_birds(frame):
    # TODO: Implement actual bird detection and framing
    height, width = frame.shape[:2]
    cv2.rectangle(frame, (10, 10), (150, 40), (0, 255, 0), -1)
    cv2.putText(frame, "PLACEHOLDER", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    return frame

class FrameGenerator:
    def __init__(self):
        self.cap = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.running = False

    def connect_to_stream(self):
        input_stream = "rtmp://rtmp-server:1935/stream/sparrow_cam"
        print(f"Attempting to connect to {input_stream}")

        retries = 0
        max_retries = 30

        while retries < max_retries:
            try:
                self.cap = cv2.VideoCapture(input_stream)
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
                frame = detect_and_frame_birds(frame)
                if not ret:
                    print("Failed to read frame, attempting to reconnect...")
                    if not self.connect_to_stream():
                        break
                    continue

                with self.frame_lock:
                    self.current_frame = frame.copy()

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

frame_generator = FrameGenerator()

def generate_mjpeg():
    while True:
        frame = frame_generator.get_frame()
        if frame is not None:
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS

@app.route('/mjpeg')
def mjpeg_stream():
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    return 'OK'

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
