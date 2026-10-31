"""Impact detection for a pale, banded ball (e.g. a white/yellow beach ball).

Colour-only detection (main.detect_ball) needs a solid, saturated ball. A beach
ball's white bands look like the projected wall and its yellow bands are only a
fragment of the ball, so its apparent radius is unreliable. This detector
instead uses the ball's shadow on the projection:

* A background model of the wall (projected game graphics included) marks the
  pixels that changed this frame.
* Changed pixels much darker than the background and unsaturated are shadow;
  changed pixels that are warm/yellowish and not dark are ball.
* As the ball flies toward the wall its shadow converges on it, and they touch
  only when the ball reaches the wall. A moving ball blob next to a ball-sized
  shadow blob is reported as an impact, once per cooldown.

Tuned on recordings of a ~25 cm white/yellow beach ball with the camera about
5 m from the wall (ball radius at the wall ~12 px at 640x480). Work is done at
half resolution (~10 ms per frame).
"""
import cv2
import numpy as np

SCALE = 0.5                 # processing scale relative to the camera frame
DIFF_THRESHOLD = 35         # per-channel change that counts as foreground
SHADOW_DARKNESS = 0.65      # shadow luminance below this fraction of background
SHADOW_MAX_SAT = 70
BALL_HUE = (12, 40)         # warm/yellow (OpenCV hue 0-180)
BALL_MIN_SAT = 50
BALL_RADIUS = (3.0, 8.5)    # ball radius at the wall, processing pixels
SHADOW_MAX_RADIUS = 8.0
PAIR_DISTANCE = 13.0        # max ball-shadow centre distance at impact
STATIC_FRAMES = 4           # blob within 2 px for this many frames = ghost
COOLDOWN = 0.6              # seconds between impacts
BG_RATE = 0.15              # background learning rate (unchanged pixels)
BG_RATE_FG = 0.03           # learning rate where something changed (ghosts fade)


class BeachBallImpactDetector:
    def __init__(self, screen_coords, frame_shape=(480, 640)):
        h, w = frame_shape[:2]
        self.size = (int(w * SCALE), int(h * SCALE))
        pts = (np.asarray(screen_coords, np.float32) * SCALE).astype(np.int32)
        roi = np.zeros((self.size[1], self.size[0]), np.uint8)
        cv2.fillPoly(roi, [pts], 255)
        self.roi = cv2.dilate(roi, np.ones((7, 7), np.uint8)) > 0
        self.k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self.bg = None
        self.history = []
        self.last_impact = -1e9
        self.last_masks = None  # (shadow, ball) for debugging displays

    @staticmethod
    def _blobs(mask, min_area, max_area):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in contours:
            area = cv2.contourArea(c)
            if min_area <= area <= max_area:
                (x, y), r = cv2.minEnclosingCircle(c)
                out.append((x, y, r))
        return out

    def update(self, frame, now):
        """Feed one BGR camera frame; return (x, y, radius) in camera pixels on impact, else None."""
        f = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA).astype(np.float32)
        if self.bg is None or self.bg.shape != f.shape:
            self.bg = f.copy()
            return None

        fg = (np.abs(f - self.bg).max(axis=2) > DIFF_THRESHOLD) & self.roi
        lum, lum_bg = f.mean(axis=2), self.bg.mean(axis=2)
        hsv = cv2.cvtColor(f.astype(np.uint8), cv2.COLOR_BGR2HSV)
        dark = lum < SHADOW_DARKNESS * lum_bg
        shadow = fg & dark & (hsv[..., 1] < SHADOW_MAX_SAT)
        ball = (fg & ~dark & (hsv[..., 0] >= BALL_HUE[0]) & (hsv[..., 0] <= BALL_HUE[1])
                & (hsv[..., 1] >= BALL_MIN_SAT))

        shadow_m = cv2.morphologyEx(shadow.astype(np.uint8) * 255, cv2.MORPH_OPEN, self.k3)
        ball_m = cv2.morphologyEx(ball.astype(np.uint8) * 255, cv2.MORPH_CLOSE, self.k7)
        ball_m = cv2.morphologyEx(ball_m, cv2.MORPH_OPEN, self.k3)
        self.last_masks = (shadow_m, ball_m)

        shadows = self._blobs(shadow_m, 25, 900)
        balls = self._blobs(ball_m, 10, 900)

        # Ignore ball blobs that have not moved (background ghosts, static yellow graphics).
        recent = self.history[-STATIC_FRAMES:]
        moving = [b for b in balls
                  if not (len(recent) == STATIC_FRAMES and all(
                      any(np.hypot(b[0] - p[0], b[1] - p[1]) < 2.0 for p in h) for h in recent))]
        self.history = (self.history + [balls])[-STATIC_FRAMES:]

        rate = np.where(fg[..., None], BG_RATE_FG, BG_RATE)
        self.bg = self.bg * (1 - rate) + f * rate

        if now - self.last_impact < COOLDOWN:
            return None
        best = None
        for s in shadows:
            if s[2] > SHADOW_MAX_RADIUS:
                continue
            for b in moving:
                if not BALL_RADIUS[0] <= b[2] <= BALL_RADIUS[1]:
                    continue
                d = np.hypot(s[0] - b[0], s[1] - b[1])
                if d < PAIR_DISTANCE and (best is None or d < best[0]):
                    best = (d, b)
        if best is None:
            return None
        self.last_impact = now
        x, y, r = best[1]
        return x / SCALE, y / SCALE, r / SCALE
