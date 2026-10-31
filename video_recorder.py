import cv2


class VideoRecorder:
    """Minimal stand-in for the uncommitted video_recorder module."""

    def __init__(self, filename="video.avi", fps=30):
        self.filename = filename
        self.fps = fps
        self.writer = None

    def record_frame(self, frame):
        if self.writer is None:
            h, w = frame.shape[:2]
            self.writer = cv2.VideoWriter(
                self.filename, cv2.VideoWriter_fourcc(*"XVID"), self.fps, (w, h)
            )
        self.writer.write(frame)

    def stop(self):
        if self.writer is not None:
            self.writer.release()
            self.writer = None
